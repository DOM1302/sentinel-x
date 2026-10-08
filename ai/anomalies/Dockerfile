FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    scikit-learn==1.7.2 \
    numpy \
    paho-mqtt \
    joblib

CMD ["python", "-u", "predictive_observe.py"]
