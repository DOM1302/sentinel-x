# predictive_engine-analyse prédictive à l'aide d'un modèle Isolation Forest entraîné

import json
import time
from collections import deque
import paho.mqtt.client as mqtt
import numpy as np
import joblib

# Chargement du modèle IA et du normaliseur (scaler)
try:
    model = joblib.load("isolation_forest.joblib")
    scaler = joblib.load("scaler.joblib")
except FileNotFoundError:
    model = joblib.load("ai/anomalies/isolation_forest.joblib")
    scaler = joblib.load("ai/anomalies/scaler.joblib")

# Configuration du serveur MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_SENSOR_DATA = "sentinel/sensors/telemetry"
TOPIC_PREDICTIVE_ALERTS = "sentinel/alerts/predictive"

# Historique des 5 dernières mesures pour calculer les variations
WINDOW_SIZE = 5
telemetry_buffer = deque(maxlen=WINDOW_SIZE)

def extract_kinetic_features(current_readings, buffer):
    # Lecture des données avec des valeurs par défaut normales (Temp: 22, Hum: 50, Gaz: 775)
    temp = current_readings.get("temperature", 22.0)
    humidity = current_readings.get("humidity", 50.0)
    gas = current_readings.get("gas", 775.0)
    
    # Calcul de la vitesse de variation (dérivée) si un historique existe
    if len(buffer) < 2:
        d_temp = 0.0
        d_gas = 0.0
    else:
        prev_readings = buffer[-2]
        time_delta = max(current_readings["timestamp"] - prev_readings["timestamp"], 0.1)
        
        d_temp = (temp - prev_readings.get("temperature", temp)) / time_delta
        d_gas = (gas - prev_readings.get("gas", gas)) / time_delta
        
    return np.array([[temp, humidity, gas, d_temp, d_gas]])

def on_connect(client, userdata, flags, rc, properties=None):
    # Action lors de la connexion au broker MQTT
    print(f"Connecté au broker MQTT Mosquitto (Code: {rc})")
    client.subscribe(TOPIC_SENSOR_DATA)

def on_message(client, userdata, msg):
    try:
        # Décodage du message JSON et ajout de l'heure d'arrivée
        payload = json.loads(msg.payload.decode("utf-8"))
        payload["timestamp"] = time.time()
        
        telemetry_buffer.append(payload)
        
        # Préparation des données pour le modèle
        features = extract_kinetic_features(payload, telemetry_buffer)
        
        # Normalisation des données
        scaled_features = scaler.transform(features)
        
        # Prédiction par l'IA (1 = Normal, -1 = Anomalie)
        prediction = model.predict(scaled_features)
        anomaly_score = model.decision_function(scaled_features)[0]
        
        is_anomaly = bool(prediction[0] == -1)
        
        # Envoi d'une alerte si une anomalie est détectée
        if is_anomaly:
            alert_payload = {
                "event": "PREDICTIVE_ANOMALY_DETECTED",
                "source": "PREDICTIVE_AI_ENGINE",
                "severity": "WARNING" if anomaly_score > -0.1 else "CRITICAL",
                "anomaly_score": round(float(anomaly_score), 4),
                "metrics": {
                    "temperature": payload.get("temperature"),
                    "humidity": payload.get("humidity"),
                    "gas_ppm": payload.get("gas"),
                    "d_temp_dt": round(float(features[0][3]), 3),
                    "d_gas_dt": round(float(features[0][4]), 3)
                },
                "message": "Anomalie cinétique détectée"
            }
            client.publish(TOPIC_PREDICTIVE_ALERTS, json.dumps(alert_payload))
            print(f"[ALERTE PRÉDICTIVE] Anomalie détectée ! Score: {anomaly_score:.4f}")
        else:
            print(f"[STATUT NORMAL] Temp: {payload.get('temperature')}°C | Humidité: {payload.get('humidity')}% | Gaz: {payload.get('gas')} ppm")
            
    except Exception as e:
        print(f"Erreur lors de la lecture des données: {e}")

# Lancement du client MQTT
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
print("Démarrage du moteur d'analyse prédictive...")
client.loop_forever()