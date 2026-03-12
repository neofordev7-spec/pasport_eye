FROM python:3.10-slim

# PaddleOCR va OpenCV uchun tizim kutubxonalari
# gcc: libgomp runtime ni ta'minlaydi (libgomp.so.1)
# ldconfig: dinamik kutubxona keshini yangilaydi
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN ldconfig

WORKDIR /app

# requirements.txt ni alohida nusxalash (Docker layer cache uchun)
COPY border-control-scanner-main/requirements.txt .

RUN python -m pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

# paddlepaddle va paddleocr alohida o'rnatiladi
RUN python -m pip install paddlepaddle==3.2.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

RUN python -m pip install "paddleocr[all]"

# Loyiha fayllarini nusxalash
COPY border-control-scanner-main/ .

CMD ["python", "bot.py"]
