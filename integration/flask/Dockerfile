FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY serveur.py .
COPY yolov8n.pt .
COPY templates/ ./templates/

EXPOSE 5000

CMD ["python", "serveur.py"]
