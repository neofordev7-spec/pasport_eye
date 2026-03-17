"""
YOLO + PaddleOCR yordamida passport MRZ zonasini aniqlash va o'qish moduli.
1. YOLO (best.pt) — MRZ zonani detect qiladi va crop qiladi
2. PaddleOCR — cropped MRZ zonani o'qiydi
scan_mrz_from_bytes(image_bytes) -> {"line1": "...", "line2": "..."} qaytaradi.
"""

import io
import json
import os
import re
import tempfile

from PIL import Image
from paddleocr import PaddleOCR

_ocr = None
_yolo_model = None

# YOLO model fayli (loyiha root da)
YOLO_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "best.pt")


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        print("PaddleOCR yuklanmoqda...", flush=True)
        _ocr = PaddleOCR(lang="en")
        print("PaddleOCR tayyor.", flush=True)
    return _ocr


def _get_yolo():
    """YOLO modelni bir marta yuklash (singleton)."""
    global _yolo_model
    if _yolo_model is None:
        print(f"YOLO model yuklanmoqda: {YOLO_MODEL_PATH}", flush=True)
        from ultralytics import YOLO
        _yolo_model = YOLO(YOLO_MODEL_PATH)
        print("YOLO model tayyor.", flush=True)
    return _yolo_model


def _detect_mrz_zone(image_bytes: bytes) -> bytes | None:
    """
    YOLO orqali MRZ zonani detect qiladi va crop qilingan rasmni qaytaradi.
    Agar topilmasa None qaytaradi.
    """
    try:
        model = _get_yolo()
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        results = model.predict(source=img, conf=0.25, verbose=False)

        if not results or len(results[0].boxes) == 0:
            print("YOLO: MRZ zona topilmadi", flush=True)
            return None

        # Eng yuqori confidence ga ega bbox ni olish
        boxes = results[0].boxes
        best_idx = boxes.conf.argmax().item()
        best_conf = boxes.conf[best_idx].item()
        x1, y1, x2, y2 = boxes.xyxy[best_idx].tolist()

        print(f"YOLO: MRZ zona topildi (conf={best_conf:.2f}, bbox=[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}])", flush=True)

        # Bbox ni biroz kengaytirish (padding 5%)
        w, h = img.size
        pad_x = (x2 - x1) * 0.05
        pad_y = (y2 - y1) * 0.05
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        # Crop
        cropped = img.crop((int(x1), int(y1), int(x2), int(y2)))

        # Bytes ga o'girish
        buf = io.BytesIO()
        cropped.save(buf, format="JPEG", quality=95)
        return buf.getvalue()

    except Exception as e:
        print(f"YOLO xato: {e}", flush=True)
        return None


def _normalize_line(line: str) -> str:
    line = line.strip().upper().replace(" ", "").replace("><", "<<")
    if len(line) > 44:
        line = line[:44]
    elif len(line) < 44:
        line = line.ljust(44, "<")
    return line


def _smart_split(text: str) -> tuple:
    """Birlashgan MRZ matnini ikkita 44-belgili qatorga ajratadi."""
    text = text.replace(" ", "").replace("\n", "").replace("\r", "")

    line2_anchor = re.compile(
        r"([A-Z0-9<]{9})(\d)([A-Z<]{3})(\d{6})(\d)", re.IGNORECASE
    )
    match = line2_anchor.search(text)
    if match:
        split_pos = match.start()
        line1_start = -1
        for prefix in ["P<", "I<", "A<", "C<", "V<"]:
            pos = text.rfind(prefix, 0, split_pos)
            if pos != -1:
                line1_start = pos
                break
        if line1_start != -1:
            line1 = text[line1_start : line1_start + 44]
            line2 = text[split_pos : split_pos + 44]
        else:
            start = max(0, split_pos - 44)
            line1 = text[start:split_pos]
            line2 = text[split_pos : split_pos + 44]
        return (_normalize_line(line1), _normalize_line(line2))

    # Fallback: ko'r bo'linish
    return (_normalize_line(text[:44]), _normalize_line(text[44:88]))


def _find_mrz_lines(rec_texts: list) -> tuple:
    """OCR natijalaridan 2 ta MRZ qatorini topadi."""
    # Birlashgan (88+ belgi) qatorni qidirish
    for text in rec_texts:
        sanitized = text.replace(" ", "")
        if len(sanitized) >= 80 and "P<" in sanitized.upper()[:10]:
            return _smart_split(sanitized)

    # 44-belgili alohida qatorlarni yig'ish
    candidates = []
    for text in rec_texts:
        clean = text.strip().replace(" ", "")
        if len(clean) >= 80 and "P<" in clean.upper()[:5]:
            return _smart_split(clean)
        MRZ_CHARS = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<')
        is_mrz_line = (
            len(clean) == 44
            and all(c in MRZ_CHARS for c in clean.upper())
            and clean.replace('<', '') != ''
        )
        if is_mrz_line:
            candidates.append(clean.upper())
        elif clean.upper().startswith("P<") and len(clean) >= 30:
            candidates.append(clean.ljust(44, "<")[:44])

    if len(candidates) >= 2:
        return (_normalize_line(candidates[0]), _normalize_line(candidates[1]))

    raise Exception(
        "Pasportdagi MRZ (mashina o'qiy oladigan zona) topilmadi. "
        "Iltimos, rasmni yorug'likda va aniq qilib qayta oling."
    )


def _run_ocr(image_bytes: bytes) -> dict:
    """PaddleOCR orqali rasmdan matn o'qish."""
    ocr = _get_ocr()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        results = ocr.predict(
            input=tmp_path,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )

        rec_texts = []
        rec_scores = []
        for res in results:
            data = res.json
            if isinstance(data, str):
                data = json.loads(data)
            main = data.get("res", {})
            rec_texts.extend(main.get("rec_texts", []))
            rec_scores.extend(main.get("rec_scores", []))

        return {"rec_texts": rec_texts, "rec_scores": rec_scores}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def scan_mrz_from_bytes(image_bytes: bytes) -> dict:
    """
    Rasm baytlaridan MRZ o'qiydi.
    1. YOLO bilan MRZ zonani detect qiladi
    2. Cropped zonani PaddleOCR ga beradi
    3. Fallback: YOLO topilmasa to'liq rasmni PaddleOCR ga beradi
    Qaytaradi: {"line1": "P<UZB...", "line2": "FA1234567...", "ocr_accuracy": 95.2}
    """
    # 1-bosqich: YOLO bilan MRZ zonani aniqlash
    mrz_cropped = _detect_mrz_zone(image_bytes)

    # 2-bosqich: OCR (cropped yoki to'liq rasm)
    if mrz_cropped:
        print("OCR: YOLO tomonidan cropped MRZ zona ishlatilmoqda", flush=True)
        ocr_result = _run_ocr(mrz_cropped)
    else:
        print("OCR: Fallback — to'liq rasm ishlatilmoqda", flush=True)
        ocr_result = _run_ocr(image_bytes)

    rec_texts = ocr_result["rec_texts"]
    rec_scores = ocr_result["rec_scores"]

    print(f"OCR topilgan matnlar: {rec_texts}", flush=True)
    line1, line2 = _find_mrz_lines(rec_texts)
    print(f"MRZ line1: {line1}", flush=True)
    print(f"MRZ line2: {line2}", flush=True)

    avg_score = round(sum(rec_scores) / len(rec_scores) * 100, 1) if rec_scores else 0.0
    return {"line1": line1, "line2": line2, "ocr_accuracy": avg_score}
