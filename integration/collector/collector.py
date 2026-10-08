
import json
import os
import time

import paho.mqtt.client as mqtt
import psycopg

MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "sentinel/sensors"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "sentinel",
    "user": "sentinel_collector",
    "password": open(
        "/run/secrets/db_password"
    ).read().strip(),
    "connect_timeout": 5,
}

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("[MQTT] Connecte", flush=True)
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[MQTT] Echec : {reason_code}", flush=True)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))

        required = ["temperature", "humidite", "gaz", "intrusion"]
        if not isinstance(data, dict) or not all(k in data for k in required):
            print("[DATA] Message incomplet ignore", flush=True)
            return

        temperature = float(data["temperature"])
        humidity = float(data["humidite"])
        gas = int(data["gaz"])
        intrusion = data["intrusion"]

        if type(intrusion) is not bool:
            print("[DATA] Intrusion invalide", flush=True)
            return

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sensor_readings
                    (temperature, humidity, gas, intrusion)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (temperature, humidity, gas, intrusion)
                )

        print(
            f"[DB] Enregistre : T={temperature}, "
            f"H={humidity}, G={gas}, PIR={intrusion}",
            flush=True
        )

    except Exception as error:
        print(f"[ERREUR] {error}", flush=True)

client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    client_id="Sentinel-DB-Collector"
)

client.on_connect = on_connect
client.on_message = on_message

while True:
    try:
        print("[MQTT] Connexion au broker...", flush=True)
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except Exception as error:
        print(f"[MQTT] Reconnexion : {error}", flush=True)
        time.sleep(5)
