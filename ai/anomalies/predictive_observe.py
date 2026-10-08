import json
import time
from pathlib import Path
from collections import deque

import numpy as np
import joblib
import paho.mqtt.client as mqtt

# MODE OBSERVATION : aucune publication MQTT.
# Ne modifie ni le dashboard ni les actionneurs.

BASE_DIR = Path(__file__).resolve().parent

model = joblib.load(BASE_DIR / "isolation_forest.joblib")
scaler = joblib.load(BASE_DIR / "scaler.joblib")

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "sentinel/sensors"

historique = deque(maxlen=5)
total = 0
anomalies = 0


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[MQTT] Connecte - mode observation", flush=True)
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[MQTT] Erreur : {reason_code}", flush=True)


def on_message(client, userdata, msg):
    global total, anomalies

    try:
        data = json.loads(msg.payload.decode("utf-8"))

        # Utiliser les vrais noms de champs ESP32
        temperature = float(data["temperature"])
        humidite = float(data["humidite"])
        gaz = float(data["gaz"])

        if not np.isfinite([temperature, humidite, gaz]).all():
            raise ValueError("Valeurs capteurs invalides")

        instant = time.monotonic()

        d_temp = 0.0
        d_gaz = 0.0

        if historique:
            precedent = historique[-1]
            dt = max(instant - precedent["instant"], 0.1)

            d_temp = (temperature - precedent["temperature"]) / dt
            d_gaz = (gaz - precedent["gaz"]) / dt

        historique.append({
            "instant": instant,
            "temperature": temperature,
            "gaz": gaz,
        })

        if len(historique) < 5:
            print(f"[INIT] {len(historique)}/5 mesures", flush=True)
            return

        # Ordre identique au modele original de Krithika
        features = np.array([[
            temperature,
            humidite,
            gaz,
            d_temp,
            d_gaz,
        ]])

        scaled = scaler.transform(features)

        prediction = int(model.predict(scaled)[0])
        score = float(model.decision_function(scaled)[0])

        total += 1

        if prediction == -1:
            anomalies += 1
            etat = "ANOMALIE"
        else:
            etat = "NORMAL"

        taux = anomalies * 100 / total

        print(
            f"[{etat}] "
            f"T={temperature:.1f}C "
            f"H={humidite:.1f}% "
            f"G={gaz:.0f} "
            f"Score={score:.4f} "
            f"Taux={taux:.1f}% ({anomalies}/{total})",
            flush=True,
        )

    except Exception as erreur:
        print(f"[ERREUR] {erreur}", flush=True)


def main():
    print("[IA] IsolationForest - observation uniquement", flush=True)
    print("[IA] Aucune commande ni alerte MQTT envoyee", flush=True)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="Sentinel-IA-Observe",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever()


if __name__ == "__main__":
    main()
