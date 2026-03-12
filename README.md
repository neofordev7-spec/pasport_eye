# Bojxona Passport MRZ Scanner

O'zbekiston xorijga chiqish biometrik pasportlarini **ICAO Doc 9303** standartiga muvofiq skanerlash va tekshirish tizimi.

---

## ICAO Doc 9303 standarti haqida

Bu loyiha [ICAO Doc 9303 — Machine Readable Travel Documents](https://www.icao.int/publications/pages/publication.aspx?docnum=9303) standartiga asoslangan.

| Standart | Tavsif |
|----------|--------|
| **ICAO Doc 9303 Part 1** | MRTDga kirish, umumiy qoidalar |
| **ICAO Doc 9303 Part 3** | TD3 format spetsifikatsiyasi (pasport) |
| **ICAO Doc 9303 Part 4** | MRZ texnik talablari |
| **TD3 format** | 2 qator × 44 belgi — biometrik pasport standarti |

### TD3 MRZ tuzilmasi

```
Qator 1 (44 belgi):
P<UZB KARIMOV<<AZIZ<<<<<<<<<<<<<<<<<<<<<<<<<<
│ │   │       └─ Ism (< bilan ajratilgan)
│ │   └─────── Familiya (<< dan keyin)
│ └─────────── Davlat kodi (UZB)
└───────────── Hujjat turi (P = Pasport)

Qator 2 (44 belgi):
FA12345678UZB9003151M3003151234567890123410
│         │   │     │ │     │              └─ JSHSHIR tekshiruv raqami
│         │   │     │ │     └──────────────── JSHSHIR/PINFL (14 raqam)
│         │   │     │ └────────────────────── Amal qilish muddati (YYMMDD)
│         │   │     └──────────────────────── Jins (M/F)
│         │   └────────────────────────────── Tug'ilgan sana (YYMMDD)
│         └────────────────────────────────── Millat (UZB)
└──────────────────────────────────────────── Pasport raqami (9 belgi)
```

### Modulo 10 checksum (ICAO 9303 §4.9)

Har bir muhim maydon uchun tekshiruv raqami hisoblanadi:

```
Og'irliklar: 7 → 3 → 1 → 7 → 3 → 1 → ... (takrorlanadi)
Belgi qiymati: 0-9 = o'zi, A-Z = 10-35, < = 0
Tekshiruv: (yig'indi) mod 10
```

Tekshiriladigan maydonlar:
- Pasport raqami + tekshiruv raqami
- Tug'ilgan sana + tekshiruv raqami
- Amal qilish muddati + tekshiruv raqami
- JSHSHIR/PINFL + tekshiruv raqami

---

## Texnologiyalar

| Qatlam | Texnologiya |
|--------|------------|
| Backend | Python 3.10, FastAPI |
| OCR | PaddleOCR (oflayn, bulut API kerak emas) |
| Bot | python-telegram-bot v22+ |
| Frontend | HTML5, Telegram Web App SDK |
| Deploy | Railway.app, Docker |

---

## Loyiha tuzilmasi

```
border-control-scanner-main/
├── main.py          # FastAPI backend + ICAO 9303 MRZ parser
├── mrz.py           # PaddleOCR OCR moduli
├── bot.py           # Telegram bot va server
├── requirements.txt # Python paketlari
├── Dockerfile       # Docker konfiguratsiyasi
└── templates/
    └── index.html   # Telegram Mini App (kamera UI)
```

---

## OCR va parse qilish jarayoni

```
Pasport rasmi (bytes)
        ↓
mrz.py → PaddleOCR → matnlar ro'yxati
        ↓
Smart split: TD3 regex bilan 2 ta 44-belgili qator ajratiladi
        ↓
{"line1": "P<UZB...", "line2": "FA123..."}
        ↓
main.py → StrictMRZParser
        ↓
ICAO 9303 checksum tekshiruvi
        ↓
JSON natija (pasport ma'lumotlari + validatsiya holati)
```

---

## Railway.app ga deploy qilish

1. Repository ni Railway ga ulang
2. Environment variables:
   ```
   BOT_TOKEN=<telegram_bot_token>
   WEBAPP_URL=https://<your-app>.railway.app
   ```
3. Deploy — Railway Dockerfile ni avtomatik aniqlaydi

Docker build tartibi:
- Tizim kutubxonalari (`libgl1`, `libglib2.0-0`, `libgomp1`)
- `requirements.txt` dan asosiy paketlar
- `paddlepaddle==3.2.0` (PaddlePaddle rasmiy serveridan)
- `paddleocr[all]`

---

## Lokal ishga tushirish

```bash
# 1. Tizim kutubxonalari (Ubuntu/Debian)
apt-get install -y libgl1 libglib2.0-0 libgomp1

# 2. Python paketlari
pip install -r requirements.txt
pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install "paddleocr[all]"

# 3. Ishga tushirish
python bot.py
```

---

## API

### `POST /scan`

**So'rov:** `multipart/form-data`, `file` maydoni

**Muvaffaqiyatli javob:**
```json
{
  "success": true,
  "data": {
    "passport_number": "FA1234567",
    "surname": "KARIMOV",
    "given_names": "AZIZ",
    "date_of_birth": "15.03.1990",
    "sex": "M",
    "date_of_expiry": "15.03.2030",
    "personal_number": "12345678901234",
    "nationality": "UZB",
    "validation_status": "PASS",
    "validations": {
      "passport_valid": true,
      "dob_valid": true,
      "expiry_valid": true,
      "pinfl_valid": true
    },
    "raw_mrz": {
      "line1": "P<UZBKARIMOV<<AZIZ<<<<<<<<<<<<<<<<<<<<<<<<<<",
      "line2": "FA12345670UZB9003151M3003151234567890123410"
    }
  }
}
```

### `GET /health`

```json
{"status": "healthy", "service": "customs-passport-scanner", "version": "3.5.0"}
```

---

## Telegram bot buyruqlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Mini App ni ochish |
| `/help` | Foydalanish yo'riqnomasi |
| `/info` | Tizim ma'lumotlari |

---

## Xavfsizlik

- Fayllar saqlanmaydi — xotirada qayta ishlanadi
- Hajm chegarasi: 10 MB
- Rate limit: 30 so'rov / 60 soniya
- Faqat `.jpg`, `.jpeg`, `.png` formatlar

---

**ICAO Doc 9303 — Machine Readable Travel Documents**
**O'zbekiston Davlat Bojxona Qo'mitasi**
