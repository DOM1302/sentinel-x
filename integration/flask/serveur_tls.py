
from flask import Flask, request, jsonify, render_template, Response

import socket
import threading
import time
import json
import ssl
import cv2

import paho.mqtt.client as mqtt
from ultralytics import YOLO


# ============================================================
# 1. INITIALISATION FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# 2. CONFIGURATION
# ============================================================

MQTT_BROKER = "192.168.137.29"
MQTT_PORT = 8883
MQTT_CA_CERT = "/app/certs/ca.crt"

MQTT_TOPIC_SENSORS = "sentinel/sensors"
MQTT_TOPIC_CONTROL = "sentinel/control"

CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 15

YOLO_MODEL = "yolov8n.pt"
YOLO_CONFIDENCE = 0.50

ALERT_COOLDOWN = 2.0


# ============================================================
# 3. ETAT GLOBAL
# ============================================================

etat_station = {
    "temperature": "--",
    "humidite": "--",
    "gaz": "--",
    "intrusion": False,
    "ia_humain": False
}

alarme_active = True

etat_lock = threading.Lock()
camera_lock = threading.Lock()


# ============================================================
# 4. PHARE UDP - DECOUVERTE AUTOMATIQUE ESP32
# ============================================================

def udp_beacon():
    udp_sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
        socket.IPPROTO_UDP
    )

    udp_sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_BROADCAST,
        1
    )

    print("[UDP] Phare Sentinel-X demarre", flush=True)

    while True:
        try:
            udp_sock.sendto(
                b"SENTINEL_HERE",
                ("255.255.255.255", 5555)
            )

        except Exception as e:
            print(
                f"[UDP] Erreur : {e}",
                flush=True
            )

        time.sleep(2)


threading.Thread(
    target=udp_beacon,
    daemon=True
).start()


# ============================================================
# 5. MQTT SECURISE TLS
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):
    """
    Callback MQTT v2.

    L'abonnement est effectue ici afin d'etre restaure
    automatiquement apres une reconnexion.
    """

    if reason_code == 0:
        print(
            f"[MQTT] Connecte a {MQTT_BROKER}:{MQTT_PORT} en TLS",
            flush=True
        )

        client.subscribe(MQTT_TOPIC_SENSORS)

        print(
            f"[MQTT] Abonne a {MQTT_TOPIC_SENSORS}",
            flush=True
        )

    else:
        print(
            f"[MQTT] Connexion refusee : {reason_code}",
            flush=True
        )


def on_disconnect(client, userdata, disconnect_flags,
                  reason_code, properties):

    print(
        f"[MQTT] Deconnexion : {reason_code}",
        flush=True
    )


def on_message(client, userdata, msg):
    """
    Reception des mesures de l'ESP32.
    """

    if msg.topic != MQTT_TOPIC_SENSORS:
        return

    try:
        donnees = json.loads(
            msg.payload.decode("utf-8")
        )

        if not isinstance(donnees, dict):
            raise ValueError("Payload JSON non valide")

        with etat_lock:
            etat_station["temperature"] = donnees.get(
                "temperature",
                etat_station["temperature"]
            )

            etat_station["humidite"] = donnees.get(
                "humidite",
                etat_station["humidite"]
            )

            etat_station["gaz"] = donnees.get(
                "gaz",
                etat_station["gaz"]
            )

            etat_station["intrusion"] = donnees.get(
                "intrusion",
                False
            )

    except Exception as e:
        print(
            f"[MQTT] Erreur traitement capteurs : {e}",
            flush=True
        )


mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

# Verification du certificat du broker Mosquitto
mqtt_client.tls_set(
    ca_certs=MQTT_CA_CERT,
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS_CLIENT
)

mqtt_client.tls_insecure_set(False)

mqtt_client.reconnect_delay_set(
    min_delay=1,
    max_delay=10
)

try:
    mqtt_client.connect(
        MQTT_BROKER,
        MQTT_PORT,
        keepalive=60
    )

    mqtt_client.loop_start()

except Exception as e:
    print(
        f"[MQTT] Erreur connexion TLS : {e}",
        flush=True
    )


# ============================================================
# 6. INITIALISATION DE L'IA YOLO
# ============================================================

print(
    "[IA] Chargement du modele YOLOv8...",
    flush=True
)

model = YOLO(YOLO_MODEL)

print(
    "[IA] Modele charge",
    flush=True
)


# ============================================================
# 7. INITIALISATION DE LA WEBCAM UGREEN
# ============================================================

def ouvrir_camera():
    """
    Ouvre la webcam UGREEN.

    Le peripherique /dev/video0 correspond au flux Video Capture.
    /dev/video1 correspond aux metadonnees et ne doit pas etre utilise.
    """

    cam = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_V4L2
    )

    if not cam.isOpened():
        print(
            "[CAMERA] ERREUR : impossible d'ouvrir /dev/video0",
            flush=True
        )
        return cam

    # MJPEG : format valide par les tests USB xHCI
    cam.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(*"MJPG")
    )

    cam.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        CAMERA_WIDTH
    )

    cam.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        CAMERA_HEIGHT
    )

    cam.set(
        cv2.CAP_PROP_FPS,
        CAMERA_FPS
    )

    largeur = int(
        cam.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    hauteur = int(
        cam.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    fps = cam.get(cv2.CAP_PROP_FPS)

    fourcc_int = int(
        cam.get(cv2.CAP_PROP_FOURCC)
    )

    fourcc = "".join(
        chr((fourcc_int >> (8 * i)) & 0xFF)
        for i in range(4)
    )

    print(
        f"[CAMERA] Ouverte : {cam.isOpened()}",
        flush=True
    )

    print(
        f"[CAMERA] Format : {fourcc}",
        flush=True
    )

    print(
        f"[CAMERA] Resolution : {largeur} x {hauteur}",
        flush=True
    )

    print(
        f"[CAMERA] FPS : {fps}",
        flush=True
    )

    return cam


camera = ouvrir_camera()


# ============================================================
# 8. GENERATION DU FLUX VIDEO + DETECTION YOLO
# ============================================================

def generer_images():
    global camera

    last_alert_time = 0
    consecutive_errors = 0

    print(
        "[VIDEO] Connexion au flux MJPEG",
        flush=True
    )

    while True:

        # Protection contre les lectures concurrentes
        with camera_lock:

            if camera is None or not camera.isOpened():
                print(
                    "[CAMERA] Reouverture de la webcam...",
                    flush=True
                )

                if camera is not None:
                    camera.release()

                camera = ouvrir_camera()

            if camera is not None and camera.isOpened():
                success, frame = camera.read()
            else:
                success, frame = False, None

        # Une erreur temporaire ne doit pas tuer le flux
        if not success or frame is None:
            consecutive_errors += 1

            if consecutive_errors == 1:
                print(
                    "[CAMERA] Echec lecture image",
                    flush=True
                )

            if consecutive_errors >= 10:
                print(
                    "[CAMERA] Trop d'erreurs : reinitialisation",
                    flush=True
                )

                with camera_lock:
                    if camera is not None:
                        camera.release()

                    camera = ouvrir_camera()

                consecutive_errors = 0

            time.sleep(0.5)
            continue

        consecutive_errors = 0

        # ----------------------------------------------------
        # DETECTION DE PERSONNES PAR YOLO
        # ----------------------------------------------------

        person_found = False

        try:
            results = model(
                frame,
                verbose=False,
                conf=YOLO_CONFIDENCE,
                classes=[0]
            )[0]

            for box in results.boxes:

                confidence = float(
                    box.conf[0]
                )

                person_found = True

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0]
                )

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 0, 255),
                    2
                )

                label = (
                    f"PERSONNE DETECTEE "
                    f"{int(confidence * 100)}%"
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2
                )

        except Exception as e:
            print(
                f"[IA] Erreur detection : {e}",
                flush=True
            )

        # ----------------------------------------------------
        # ACTUALISATION DE L'ETAT IA
        # ----------------------------------------------------

        with etat_lock:
            etat_station["ia_humain"] = person_found
            alarme_est_active = alarme_active

        # ----------------------------------------------------
        # PUBLICATION MQTT DE L'ALERTE
        # ----------------------------------------------------

        now = time.time()

        if (
            person_found
            and alarme_est_active
            and (now - last_alert_time) > ALERT_COOLDOWN
        ):
            if mqtt_client.is_connected():

                payload = json.dumps({
                    "force_alarme": True
                })

                mqtt_client.publish(
                    MQTT_TOPIC_CONTROL,
                    payload
                )

                print(
                    "[IA] Personne detectee : alerte ESP32 envoyee",
                    flush=True
                )

                last_alert_time = now

            else:
                print(
                    "[IA] Alerte non envoyee : MQTT deconnecte",
                    flush=True
                )

        # ----------------------------------------------------
        # ENCODAGE JPEG POUR LE DASHBOARD
        # ----------------------------------------------------

        encode_param = [
            int(cv2.IMWRITE_JPEG_QUALITY),
            80
        ]

        success_jpeg, buffer = cv2.imencode(
            ".jpg",
            frame,
            encode_param
        )

        if not success_jpeg:
            print(
                "[VIDEO] Erreur encodage JPEG",
                flush=True
            )

            time.sleep(0.1)
            continue

        image_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: "
            + str(len(image_bytes)).encode("ascii")
            + b"\r\n\r\n"
            + image_bytes
            + b"\r\n"
        )

        time.sleep(1.0 / CAMERA_FPS)


# ============================================================
# 9. ROUTES FLASK
# ============================================================

@app.route("/")
def index():
    return render_template(
        "index.html"
    )


@app.route("/video_feed")
def video_feed():

    response = Response(
        generer_images(),
        mimetype=(
            "multipart/x-mixed-replace; boundary=frame"
        )
    )

    response.headers["Cache-Control"] = (
        "no-cache, no-store, must-revalidate"
    )

    response.headers["X-Accel-Buffering"] = "no"

    return response


@app.route("/api/v1/status", methods=["GET"])
def envoyer_status():

    with etat_lock:
        data = etat_station.copy()
        data["alarme_active"] = alarme_active

    return jsonify(data)


@app.route("/api/v1/control", methods=["POST"])
def controle_alarme():
    global alarme_active

    donnees = request.get_json(silent=True) or {}
    action = donnees.get("action")

    if action != "toggle":
        return jsonify({
            "error": "Action invalide"
        }), 400

    if not mqtt_client.is_connected():
        return jsonify({
            "error": "Broker MQTT indisponible"
        }), 503

    with etat_lock:
        nouvel_etat = not alarme_active

        payload = json.dumps({
            "alarme_active": nouvel_etat
        })

        resultat = mqtt_client.publish(
            MQTT_TOPIC_CONTROL,
            payload
        )

        if resultat.rc != mqtt.MQTT_ERR_SUCCESS:
            return jsonify({
                "error": "Publication MQTT echouee"
            }), 503

        alarme_active = nouvel_etat

    print(
        f"[CONTROLE] Alarme active : {alarme_active}",
        flush=True
    )

    return jsonify({
        "alarme_active": alarme_active
    })


# ============================================================
# 10. DEMARRAGE
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        threaded=True
    )
