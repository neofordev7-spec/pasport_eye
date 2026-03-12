# # Customs-Grade Passport Scanner - Railway.app Dockerfile
# # Python 3.9 with Mistral AI Vision API
# # Last updated: 2026-01-15 - Mistral AI Migration Complete

# FROM python:3.9-slim

# # Build argument for cache busting
# ARG BUILDKIT_INLINE_CACHE=1
# ARG BUILD_DATE=2026-01-15

# # Set working directory
# WORKDIR /app

# # Install system dependencies required for Tesseract OCR and OpenCV
# RUN apt-get update && apt-get install -y \
#     tesseract-ocr \
#     tesseract-ocr-eng \
#     libtesseract-dev \
#     libgl1 \
#     libglib2.0-0 \
#     libsm6 \
#     libxext6 \
#     libxrender-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Copy requirements first for better caching
# COPY requirements.txt .

# # Install Python dependencies
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy application files
# COPY . .

# # Create templates directory if it doesn't exist
# RUN mkdir -p templates static

# # Expose port for Railway
# EXPOSE 8000

# # Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# # Start the application
# CMD ["python", "bot.py"]




FROM python:3.10-slim

# OpenCV va PaddleOCR ishlashi uchun kerakli tizim kutubxonalari
# libgomp1 xatosi to'g'irlandi
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Avval oddiy kutubxonalarni o'rnatish
COPY requirements.txt .

# Pip'ni eng yangi versiyaga ko'tarish (yuklashdagi xatoliklarni kamaytiradi)
RUN python -m pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

# Maxsus muhit (environment) o'rnatilishi:
# Diqqat: Uzilib qolmasligi uchun timeout va retries qo'shildi!
RUN python -m pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

RUN python -m pip install "paddleocr[all]"

# Qolgan barcha kodlarni nusxalaymiz
COPY . .

# Serverni ishga tushirish
CMD ["sh", "-c", "python bot.py"]
