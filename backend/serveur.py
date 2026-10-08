from flask import Flask, request, jsonify, render_template, Response
import socket
import threading
import time
import cv2
import json
import paho.mqtt.client as mqtt
from ultralytics import YOLO
import db  # historique PostgreSQL (voir db.py)

_prev = {"intrusion": False, "gaz": False}  # detection des fronts pour le journal d'evenements

app = Flask(__name__)

# --- 1. LE PHARE UDP (Détection Auto ESP32) ---
def udp_beacon():
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        try:
            udp_sock.sendto(b"SENTINEL_HERE", ('255.255.255.255', 5555))
        except Exception:
            pass
        time.sleep(2)

threading.Thread(target=udp_beacon, daemon=True).start()

# --- 2. CONFIGURATION MQTT (Mosquitto) ---
MQTT_BROKER = "localhost" # L'IP du PC où Mosquitto tourne
MQTT_PORT = 1883

etat_station = {
    "temperature": "--",
    "humidite": "--",
    "gaz": "--",
    "intrusion": False,
    "ia_humain": False # Statut de l'IA
}
alarme_active = True

# Fonction qui écoute les messages venant de l'ESP32
def on_message(client, userdata, msg):
    global etat_station
    if msg.topic == "sentinel/sensors":
        try:
            donnees = json.loads(msg.payload.decode())
            etat_station["temperature"] = donnees.get("temperature", etat_station["temperature"])
            etat_station["humidite"] = donnees.get("humidite", etat_station["humidite"])
            etat_station["gaz"] = donnees.get("gaz", etat_station["gaz"])
            etat_station["intrusion"] = donnees.get("intrusion", False)

            # --- Historique PostgreSQL ---
            db.log_measure(etat_station["temperature"], etat_station["humidite"],
                           etat_station["gaz"], etat_station["intrusion"])
            if etat_station["intrusion"] and not _prev["intrusion"]:
                db.log_event("pir", "intrusion")
            _prev["intrusion"] = bool(etat_station["intrusion"])
            try:
                gaz_alerte = int(etat_station["gaz"]) > 1000
            except (TypeError, ValueError):
                gaz_alerte = False
            if gaz_alerte != _prev["gaz"]:
                db.log_event("gas", "gas_alert" if gaz_alerte else "gas_clear",
                             {"gaz": etat_station["gaz"]})
            _prev["gaz"] = gaz_alerte
        except Exception as e:
            pass

# Lancement du client MQTT en arrière-plan
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.subscribe("sentinel/sensors")
    mqtt_client.loop_start()
    print("Connecté au Broker Mosquitto local !")
except Exception as e:
    print("Avertissement : Mosquitto n'est pas lancé. L'IA fonctionne, mais pas l'ESP32.")

# --- 3. INTELLIGENCE ARTIFICIELLE & CAMÉRA ---
print("Chargement du réseau neuronal YOLOv8...")
model = YOLO("yolov8n.pt")

# Index 0 = Webcam par défaut. Mets 1 si tu veux forcer ta caméra Ugreen.
camera = cv2.VideoCapture(0, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

def generer_images():
    global etat_station
    last_alert_time = 0

    while True:
        success, frame = camera.read()
        if not success:
            break

        results = model(frame, verbose=False)[0]
        person_found = False
        person_conf = 0.0

        for box in results.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            if class_id == 0 and confidence > 0.50:
                person_found = True
                person_conf = confidence
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)

                cv2.putText(frame, f"INTRUS ({int(confidence*100)}%)", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                break

        etat_station["ia_humain"] = person_found


        now = time.time()
        if person_found and (now - last_alert_time) > 2.0:
            print("🚨 [IA] Cible verrouillée : Envoi de l'ordre de tir à l'ESP32 !")
            # On envoie une chaîne stricte pour éviter les bugs d'espacement JSON
            mqtt_client.publish("sentinel/control", '{"force_alarme":true}')
            db.log_event("camera", "intrusion", {"confidence": round(person_conf, 2)})
            last_alert_time = now

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        time.sleep(0.033)

# --- 4. ROUTES WEB (DASHBOARD) ---
@app.route('/video_feed')
def video_feed():
    return Response(generer_images(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/v1/status', methods=['GET'])
def envoyer_status():
    data = etat_station.copy()
    data["alarme_active"] = alarme_active
    return jsonify(data)

@app.route('/api/v1/control', methods=['POST'])
def controle_alarme():
    global alarme_active
    action = request.json.get('action')
    if action == 'toggle':
        alarme_active = not alarme_active
        # CORRECTION : On force la publication du statut d'alarme
        mqtt_client.publish("sentinel/control", json.dumps({"alarme_active": alarme_active}))
        db.log_command("arm" if alarme_active else "disarm", request.remote_addr, alarme_active)
    return jsonify({"alarme_active": alarme_active})

@app.route('/api/v1/history', methods=['GET'])
def historique():
    minutes = min(max(request.args.get('minutes', 30, type=int), 1), 1440)
    try:
        return jsonify({"measures": db.fetch_measures(minutes), "events": db.fetch_events(50)})
    except Exception as e:
        print(f"[DB] lecture impossible : {e}", flush=True)
        return jsonify({"error": "base indisponible"}), 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)