"""
Customs Committee Passport MRZ Scanner - Backend API
PaddleOCR yordamida MRZ o'qiydi (oflayn, API kerak emas)
"""

import io
import os
import time
import json
from datetime import datetime
from typing import Dict, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from PIL import Image
from telegram import Update
from mrz import scan_mrz_from_bytes

app = FastAPI(
    title="Customs Committee Passport Scanner",
    description="Professional MRZ Scanner System",
    version="3.5.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
templates = Jinja2Templates(directory="templates")

# ============================================
# STRICT ICAO 9303 MRZ PARSER
# ============================================

class StrictMRZParser:
    """Strict ICAO 9303 TD3 Parser"""

    @staticmethod
    def parse_mrz_strict(line1: str, line2: str) -> Dict:
        print(f"🔍 Parsing MRZ...", flush=True)

        # Basic cleanup
        line1 = line1.strip().upper()
        line2 = line2.strip().upper()

        if len(line1) != 44 or len(line2) != 44:
            raise ValueError("Invalid MRZ line length")

        # LINE 1
        doc_type = line1[0]
        country_code = line1[2:5].replace('<', '')
        names_section = line1[5:44]
        
        surname = names_section.split('<<')[0].replace('<', ' ').strip() if '<<' in names_section else names_section.replace('<', ' ').strip()
        given_names = names_section.split('<<')[1].replace('<', ' ').strip() if '<<' in names_section else ""

        # LINE 2 - FIXED GRID
        passport_raw = line2[0:9]
        passport_check = line2[9]
        nationality_raw = line2[10:13]
        dob_raw = line2[13:19]
        dob_check = line2[19]
        sex_raw = line2[20]
        expiry_raw = line2[21:27]
        expiry_check = line2[27]
        pinfl_raw = line2[28:42]
        pinfl_check = line2[42]

        # ERROR CORRECTION
        # 1. Pasport raqami: OCR ning O↔0, I↔1 xatolarini tuzatish
        #    Faqat UZB prefiklari uchun (FA/FB/FC/FD/AC/AD/AA): 2 harf + 7 raqam
        #    Boshqa davlatlar uchun: faqat raqamli qismdagi O→0 tuzatish
        pass_clean = passport_raw.replace('<', '')
        uzb_prefixes = {'FA', 'FB', 'FC', 'FD', 'AC', 'AD', 'AA', 'AB'}
        if len(pass_clean) >= 2 and pass_clean[:2].upper() in uzb_prefixes:
            prefix = pass_clean[:2].replace('0', 'O').replace('1', 'I')
            suffix = pass_clean[2:].replace('O', '0').replace('o', '0').replace('I', '1').replace('l', '1')
            passport_number = prefix + suffix
        else:
            passport_number = pass_clean

        # 2. Millat: faqat aniq OCR xatolarini tuzatish (UZB uchun)
        nationality = nationality_raw.replace('<', '')
        uzb_ocr_errors = {'ZBO', 'LZB', 'USB', 'U2B', 'UZ8', 'O2B', 'UZO', 'UZE'}
        if nationality in uzb_ocr_errors:
            nationality = 'UZB'
        # UZB prefiksi aniq ko'rinsa, millat ham UZB
        elif nationality != 'UZB' and passport_number[:2].upper() in uzb_prefixes:
            nationality = 'UZB'

        # 3. Sana va personal raqam: O→0 tuzatish
        dob    = dob_raw.replace('O', '0')
        expiry = expiry_raw.replace('O', '0')
        # Personal number: UZB bo'lsa O→0, boshqalarda qo'llanmaydi
        pinfl  = pinfl_raw.replace('O', '0') if nationality == 'UZB' else pinfl_raw
        pinfl  = pinfl.replace('<', '').strip()
        sex    = sex_raw.replace('<', '')

        # ICAO checksum validatsiyasi
        validations = {
            "passport_valid": StrictMRZParser.validate(passport_raw, passport_check),
            "dob_valid":      StrictMRZParser.validate(dob_raw, dob_check),
            "expiry_valid":   StrictMRZParser.validate(expiry_raw, expiry_check),
            "pinfl_valid":    StrictMRZParser.validate(pinfl_raw, pinfl_check)
        }
        all_valid = all(validations.values())

        # Haqiqiylik tekshiruvi
        authenticity = StrictMRZParser.authenticity_check(line1, line2)

        return {
            "passport_number": passport_number,
            "surname":         surname,
            "name":            given_names,
            "given_names":     given_names,
            "birth_date":      StrictMRZParser.fmt_date(dob),
            "date_of_birth":   StrictMRZParser.fmt_date(dob),
            "expiry_date":     StrictMRZParser.fmt_date(expiry),
            "date_of_expiry":  StrictMRZParser.fmt_date(expiry),
            "sex":             sex,
            "nationality":     nationality,
            "pinfl":           pinfl,
            "personal_number": pinfl,
            "document_type":   doc_type,
            "country_code":    country_code,
            "validation_status": "PASS" if all_valid else "WARNING",
            "authenticity":    authenticity,
            "raw_mrz":         {"line1": line1, "line2": line2}
        }

    @staticmethod
    def fmt_date(yymmdd):
        if len(yymmdd) != 6 or not yymmdd.isdigit(): return yymmdd
        return f"{yymmdd[4:6]}.{yymmdd[2:4]}.{'20'+yymmdd[0:2] if int(yymmdd[0:2])<50 else '19'+yymmdd[0:2]}"

    @staticmethod
    def validate(data, check):
        if not check.isdigit(): return False
        weights = [7, 3, 1]
        total = 0
        for i, c in enumerate(data):
            val = int(c) if c.isdigit() else (ord(c)-55 if c.isalpha() else 0)
            total += val * weights[i % 3]
        return (total % 10) == int(check)

    @staticmethod
    def authenticity_check(line1: str, line2: str) -> Dict:
        """
        ICAO Doc 9303 asosida pasport haqiqiyligini matematik tekshiradi.
        Barcha davlatlar fuqarolari uchun universal.

        Universal tekshiruvlar (barcha davlatlar):
          - Composite checksum (ICAO §4.2.2)
          - 4 ta alohida ICAO checksum
          - Hujjat turi ('P')
          - Pasport raqami MRZ formati (9 ta A-Z/0-9/< belgi)
          - Millat kodi formati (3 ta harf)
          - Sana mantiq tekshiruvi
          - Muddati tugamagan

        UZB-spetsifik (faqat O'zbekiston pasportlari):
          - Personal number formati (14 raqamli JSHSHIR)
          - JSHSHIR ↔ MRZ sana/jins cross-validation

        Qaytaradi: {"score": 0-100, "status": "HAQIQIY"/"SHUBHALI"/"SOXTA", "checks": {...}}
        """
        from datetime import date as _date

        checks = {}

        # Millat va UZB ekanligi aniqlanadi
        nationality = line1[2:5].replace('<', '')
        uzb_prefixes = {'FA', 'FB', 'FC', 'FD', 'AC', 'AD', 'AA', 'AB'}
        is_uzb = (nationality == 'UZB') or (line2[0:2].upper() in uzb_prefixes)

        # ── 1. Composite checksum (ICAO Doc 9303 Part 3 §4.2.2) ──────────────
        # Qamrovi: pasport(0:10) + tug'ilgan sana(13:20) + muddati+personal(21:43)
        composite_data = line2[0:10] + line2[13:20] + line2[21:43]
        checks["composite_checksum"] = StrictMRZParser.validate(composite_data, line2[43])

        # ── 2. Alohida maydon checksumlar (ICAO §4.9) ────────────────────────
        checks["passport_checksum"] = StrictMRZParser.validate(line2[0:9],  line2[9])
        checks["dob_checksum"]      = StrictMRZParser.validate(line2[13:19], line2[19])
        checks["expiry_checksum"]   = StrictMRZParser.validate(line2[21:27], line2[27])
        checks["personal_checksum"] = StrictMRZParser.validate(line2[28:42], line2[42])

        # ── 3. Hujjat turi (ICAO Doc 9303 Part 3 §4.1) ──────────────────────
        # P = Passport; ikkinchi belgi mamlakatga xos yoki filler (<)
        checks["doc_type_valid"] = (
            line1[0] == 'P' and
            (line1[1] == '<' or line1[1].isalpha())
        )

        # ── 4. Pasport raqami MRZ formati (universal) ────────────────────────
        # ICAO: 9 ta belgi, faqat A-Z, 0-9, < dan iborat bo'lishi kerak
        valid_mrz_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<')
        praw = line2[0:9].upper()
        checks["passport_format"] = (
            len(praw) == 9 and
            all(c in valid_mrz_chars for c in praw) and
            praw.replace('<', '') != ''  # kamida bitta belgi bo'lishi kerak
        )

        # ── 5. Millat kodi formati (ICAO: 3 ta harf yoki < bilan to'ldirilgan) ─
        nat_raw = line2[10:13].upper()
        checks["nationality_format"] = (
            len(nat_raw) == 3 and
            all(c.isalpha() or c == '<' for c in nat_raw) and
            nat_raw.replace('<', '') != ''
        )

        # ── 6. Sana mantiq tekshiruvi ─────────────────────────────────────────
        dob    = line2[13:19].replace('O', '0')
        expiry = line2[21:27].replace('O', '0')

        dob_logic    = False
        expiry_logic = False
        not_expired  = False

        if dob.isdigit():
            try:
                mm, dd = int(dob[2:4]), int(dob[4:6])
                dob_logic = (1 <= mm <= 12) and (1 <= dd <= 31)
            except Exception:
                pass

        if expiry.isdigit():
            try:
                yy, mm, dd = int(expiry[0:2]), int(expiry[2:4]), int(expiry[4:6])
                expiry_logic = (1 <= mm <= 12) and (1 <= dd <= 31)
                if expiry_logic:
                    exp_year = 2000 + yy if yy < 50 else 1900 + yy
                    not_expired = _date(exp_year, mm, dd) >= _date.today()
            except Exception:
                pass

        checks["dob_date_valid"]    = dob_logic
        checks["expiry_date_valid"] = expiry_logic
        checks["not_expired"]       = not_expired

        # ── 7. Personal number tekshiruvi (davlatga qarab farq qiladi) ────────
        pnum_raw = line2[28:42]
        pnum_clean = pnum_raw.replace('<', '').strip()
        is_empty_personal = (pnum_clean == '')  # ko'p davlatlar to'ldirmaydi

        if is_uzb:
            # UZB: 14 raqamli JSHSHIR majburiy
            pinfl = pnum_raw.replace('O', '0').replace('<', '').strip()
            checks["personal_number_format"] = (len(pinfl) == 14 and pinfl.isdigit())
        else:
            # Boshqa davlatlar: bo'sh yoki har qanday format to'g'ri
            checks["personal_number_format"] = True

        # ── 8. JSHSHIR ↔ MRZ cross-validation (faqat UZB) ───────────────────
        # O'zbekiston JSHSHIR standarti (ICAO §D3):
        #   1-raqam: 1=erkak(1900-99), 2=ayol(1900-99), 3=erkak(2000+), 4=ayol(2000+)
        #   2-7-raqam: tug'ilgan sana DDMMYY formatida
        if is_uzb:
            pinfl = pnum_raw.replace('O', '0').replace('<', '').strip()
            pinfl_cross = False
            sex = line2[20]
            if checks.get("personal_number_format") and dob_logic:
                try:
                    gender_century = int(pinfl[0])
                    is_male_mrz   = (sex == 'M')
                    is_male_pinfl = (gender_century in [1, 3])
                    gender_match  = (is_male_mrz == is_male_pinfl) if sex in ('M', 'F') else True
                    mrz_ddmmyy    = dob[4:6] + dob[2:4] + dob[0:2]  # YYMMDD → DDMMYY
                    dob_match     = (pinfl[1:7] == mrz_ddmmyy)
                    pinfl_cross   = gender_match and dob_match
                except Exception:
                    pass
            checks["pinfl_dob_sex_match"] = pinfl_cross
        else:
            # UZB emas — bu tekshiruv qo'llanmaydi, ball beriladi
            checks["pinfl_dob_sex_match"] = None  # N/A

        # ── Haqiqiylik balli ──────────────────────────────────────────────────
        # None (N/A) bo'lgan tekshiruvlar ball hisobiga kirmaydi, balki
        # ularning ulushi teng taqsimlanadi
        weights_map = {
            "composite_checksum":    25,
            "passport_checksum":     10,
            "dob_checksum":          10,
            "expiry_checksum":       10,
            "personal_checksum":      5,
            "doc_type_valid":         5,
            "passport_format":        5,
            "nationality_format":     3,
            "dob_date_valid":         5,
            "expiry_date_valid":      3,
            "not_expired":            9,
            "personal_number_format": 5,
            "pinfl_dob_sex_match":    5,
        }

        total_weight  = sum(w for k, w in weights_map.items() if checks.get(k) is not None)
        earned_weight = sum(w for k, w in weights_map.items() if checks.get(k) is True)

        # Ballni 100 ga normallashtirish (N/A tekshiruvlar hisobga olinmaydi)
        score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 0

        if score >= 90:
            status = "HAQIQIY"
        elif score >= 65:
            status = "SHUBHALI"
        else:
            status = "SOXTA"

        return {"score": score, "status": status, "is_uzb": is_uzb, "checks": checks}


# ============================================
# SECURITY & CONFIG
# ============================================

request_timestamps = {}
RATE_LIMIT_WINDOW = 60
MAX_REQUESTS_PER_WINDOW = 30
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png']

def check_rate_limit(client_id: str) -> bool:
    current_time = time.time()
    if client_id not in request_timestamps: request_timestamps[client_id] = []
    request_timestamps[client_id] = [ts for ts in request_timestamps[client_id] if current_time - ts < RATE_LIMIT_WINDOW]
    if len(request_timestamps[client_id]) >= MAX_REQUESTS_PER_WINDOW: return False
    request_timestamps[client_id].append(current_time)
    return True

def validate_image_file(file: UploadFile, contents: bytes) -> None:
    if len(contents) > MAX_FILE_SIZE: raise HTTPException(status_code=413, detail="File too large")
    if file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS: raise HTTPException(status_code=400, detail="Invalid file type")
    try:
        img = Image.open(io.BytesIO(contents))
        img.verify()
    except: raise HTTPException(status_code=400, detail="Invalid image")


# ============================================
# API ENDPOINTS
# ============================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "customs-passport-scanner",
        "version": "3.5.0"
    }

@app.post("/scan")
async def scan_passport(request: Request, file: UploadFile = File(...)):
    """Main scanning endpoint"""
    try:
        client_id = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_id):
            raise HTTPException(status_code=429, detail="Too many requests")

        contents = await file.read()
        if not contents: raise HTTPException(status_code=400, detail="Empty file")
        validate_image_file(file, contents)

        print(f"📸 Processing image: {file.filename}", flush=True)

        # 1. Scan (OCR via PaddleOCR)
        try:
            mrz_result = scan_mrz_from_bytes(contents)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=str(e) if "MRZ" in str(e) or "topilmadi" in str(e)
                else "Pasportdagi MRZ topilmadi. Iltimos, rasmni yorug'likda va aniq qilib qayta oling."
            )

        # 2. Parse (Strict Logic)
        parsed_data = StrictMRZParser.parse_mrz_strict(mrz_result["line1"], mrz_result["line2"])

        # 3. Add Metadata (BRANDING REMOVED)
        parsed_data["scan_metadata"] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "file_name": file.filename,
            "scanner": "Customs AI Scanner (v3.5)" # <--- NEW NAME
        }

        print(f"✅ Scan completed: {parsed_data['passport_number']}", flush=True)
        return JSONResponse(content={"success": True, "data": parsed_data})

    except HTTPException: raise
    except Exception as e:
        print(f"❌ Error: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    try:
        update_data = await request.json()
        from bot import get_application
        application = get_application()
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        print(f"❌ Webhook error: {str(e)}", flush=True)
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=200)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False, log_level="info")
