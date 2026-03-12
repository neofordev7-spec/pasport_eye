"""
PaddleOCR yordamida passport MRZ zonasini o'qish moduli.
scan_mrz_from_bytes(image_bytes) -> {"line1": "...", "line2": "..."} qaytaradi.
"""

import json
import os
import re
import tempfile

from paddleocr import PaddleOCR

_ocr = None


def _get_ocr() -> PaddleOCR:
    global _ocr
    if _ocr is None:
        print("PaddleOCR yuklanmoqda...", flush=True)
        _ocr = PaddleOCR(lang="en")
        print("PaddleOCR tayyor.", flush=True)
    return _ocr


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


def scan_mrz_from_bytes(image_bytes: bytes) -> dict:
    """
    Rasm baytlaridan MRZ o'qiydi.
    Qaytaradi: {"line1": "P<UZB...", "line2": "FA1234567..."}
    """
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

        print(f"OCR topilgan matnlar: {rec_texts}", flush=True)
        line1, line2 = _find_mrz_lines(rec_texts)
        print(f"MRZ line1: {line1}", flush=True)
        print(f"MRZ line2: {line2}", flush=True)

        avg_score = round(sum(rec_scores) / len(rec_scores) * 100, 1) if rec_scores else 0.0
        return {"line1": line1, "line2": line2, "ocr_accuracy": avg_score}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
