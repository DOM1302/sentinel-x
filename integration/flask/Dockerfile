FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=2
ENV YOLO_CONFIG_DIR=/tmp

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY serveur_tls.py .
COPY templates/ ./templates/

# YOLO téléchargera son modèle si absent.
# Pour une démonstration hors ligne, prévoir un
# montage local du fichier yolov8n.pt.

EXPOSE 5001

CMD ["python", "serveur_tls.py"]
