from flask import Flask, request, jsonify, render_template, Response

import os
import socket
import threading
import time
import json

import cv2
import paho.mqtt.client as mqtt
from ultralytics import YOLO


# ============================================================
# SENTINEL-X
# Serveur Flask + MQTT + Webcam + YOLO
# ============================================================

app = Flask(__name__)


# ============================================================
# 1. CONFIGURATION
# ============================================================

# ----------------------------
# MQTT
# ----------------------------

MQTT_BROKER = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

MQTT_TOPIC_SENSORS = os.getenv(
    "MQTT_TOPIC_SENSORS",
    "sentinel/sensors"
)

MQTT_TOPIC_CONTROL = os.getenv(
    "MQTT_TOPIC_CONTROL",
    "sentinel/control"
)


# ----------------------------
# Webcam
# ----------------------------

CAMERA_INDEX = int(
    os.getenv("CAMERA_INDEX", "0")
)

CAMERA_WIDTH = int(
    os.getenv("CAMERA_WIDTH", "640")
)

CAMERA_HEIGHT = int(
    os.getenv("CAMERA_HEIGHT", "480")
)

CAMERA_FPS = int(
    os.getenv("CAMERA_FPS", "10")
)


# ----------------------------
# YOLO
# ----------------------------

YOLO_MODEL = os.getenv(
    "YOLO_MODEL",
    "yolov8n.pt"
)

YOLO_CONFIDENCE = float(
    os.getenv("YOLO_CONFIDENCE", "0.50")
)

# Une inférence toutes les N frames
YOLO_FRAME_INTERVAL = int(
    os.getenv("YOLO_FRAME_INTERVAL", "3")
)

YOLO_IMAGE_SIZE = int(
    os.getenv("YOLO_IMAGE_SIZE", "320")
)


# ----------------------------
# Alertes
# ----------------------------

ALERT_COOLDOWN = float(
    os.getenv("ALERT_COOLDOWN", "5")
)


# ============================================================
# 2. ETAT GLOBAL
# ============================================================

etat_station = {
    "temperature": "--",
    "humidite": "--",
    "gaz": "--",
    "intrusion": False,
    "ia_humain": False
}

alarme_active = True


# Locks
etat_lock = threading.Lock()
camera_lock = threading.Lock()


# ============================================================
# 3. UDP BEACON
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

    print(
        "[UDP] Beacon Sentinel-X demarre",
        flush=True
    )

    while True:

        try:

            udp_sock.sendto(
                b"SENTINEL_HERE",
                ("255.255.255.255", 5555)
            )

        except Exception as e:

            print(
                f"[UDP] Erreur beacon : {e}",
                flush=True
            )

        time.sleep(2)


threading.Thread(
    target=udp_beacon,
    daemon=True
).start()


# ============================================================
# 4. MQTT
# ============================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties=None
):

    try:
        code = int(reason_code)
    except Exception:
        code = reason_code

    if code == 0:

        print(
            f"[MQTT] Connecte a {MQTT_BROKER}:{MQTT_PORT}",
            flush=True
        )

        client.subscribe(
            MQTT_TOPIC_SENSORS
        )

        print(
            f"[MQTT] Abonnement : {MQTT_TOPIC_SENSORS}",
            flush=True
        )

    else:

        print(
            f"[MQTT] Echec connexion : {reason_code}",
            flush=True
        )


def on_disconnect(
    client,
    userdata,
    disconnect_flags=None,
    reason_code=None,
    properties=None
):

    print(
        "[MQTT] Deconnecte",
        flush=True
    )


def on_message(
    client,
    userdata,
    msg
):

    global etat_station

    try:

        payload = msg.payload.decode(
            "utf-8"
        )

        data = json.loads(payload)

        if not isinstance(data, dict):
            return

        with etat_lock:

            if "temperature" in data:
                etat_station["temperature"] = data[
                    "temperature"
                ]

            if "humidite" in data:
                etat_station["humidite"] = data[
                    "humidite"
                ]

            if "gaz" in data:
                etat_station["gaz"] = data[
                    "gaz"
                ]

            if "intrusion" in data:
                etat_station["intrusion"] = bool(
                    data["intrusion"]
                )

    except Exception as e:

        print(
            f"[MQTT] Erreur message : {e}",
            flush=True
        )


try:

    mqtt_client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2
    )

except AttributeError:

    # Compatibilité avec ancien paho-mqtt
    mqtt_client = mqtt.Client()


mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


def connecter_mqtt():

    while True:

        try:

            print(
                f"[MQTT] Connexion vers "
                f"{MQTT_BROKER}:{MQTT_PORT}...",
                flush=True
            )

            mqtt_client.connect(
                MQTT_BROKER,
                MQTT_PORT,
                keepalive=60
            )

            mqtt_client.loop_forever()

        except Exception as e:

            print(
                f"[MQTT] Erreur connexion : {e}",
                flush=True
            )

            time.sleep(3)


threading.Thread(
    target=connecter_mqtt,
    daemon=True
).start()


# ============================================================
# 5. INITIALISATION YOLO
# ============================================================

print(
    "[IA] Chargement du modele YOLOv8...",
    flush=True
)

try:

    model = YOLO(
        YOLO_MODEL
    )

    print(
        "[IA] Modele YOLO charge",
        flush=True
    )

except Exception as e:

    print(
        f"[IA] ERREUR chargement YOLO : {e}",
        flush=True
    )

    model = None


# ============================================================
# 6. CAMERA
# ============================================================

def ouvrir_camera():

    """
    /dev/video0 = flux webcam.
    /dev/video1 peut correspondre aux metadonnees
    sur certaines webcams USB.
    """

    print(
        f"[CAMERA] Ouverture /dev/video{CAMERA_INDEX}",
        flush=True
    )

    cam = cv2.VideoCapture(
        CAMERA_INDEX,
        cv2.CAP_V4L2
    )

    if not cam.isOpened():

        print(
            "[CAMERA] ERREUR : impossible "
            "d'ouvrir la webcam",
            flush=True
        )

        return cam

    # Format MJPEG
    cam.set(
        cv2.CAP_PROP_FOURCC,
        cv2.VideoWriter_fourcc(
            *"MJPG"
        )
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
        cam.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
    )

    hauteur = int(
        cam.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
    )

    fps = cam.get(
        cv2.CAP_PROP_FPS
    )

    fourcc_int = int(
        cam.get(
            cv2.CAP_PROP_FOURCC
        )
    )

    fourcc = "".join(
        chr(
            (fourcc_int >> (8 * i))
            & 0xFF
        )
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
        f"[CAMERA] Resolution : "
        f"{largeur} x {hauteur}",
        flush=True
    )

    print(
        f"[CAMERA] FPS : {fps}",
        flush=True
    )

    return cam


camera = ouvrir_camera()


# ============================================================
# 7. FLUX VIDEO + YOLO
# ============================================================

def generer_images():

    global camera

    last_alert_time = 0

    consecutive_errors = 0

    frame_counter = 0

    # Résultat de la dernière inférence YOLO
    last_person_found = False

    # Dernières boîtes détectées
    last_boxes = []

    print(
        "[VIDEO] Connexion au flux MJPEG",
        flush=True
    )

    while True:

        # ----------------------------------------------------
        # LECTURE CAMERA
        # ----------------------------------------------------

        with camera_lock:

            if (
                camera is None
                or not camera.isOpened()
            ):

                print(
                    "[CAMERA] Reouverture "
                    "de la webcam...",
                    flush=True
                )

                if camera is not None:

                    try:
                        camera.release()
                    except Exception:
                        pass

                camera = ouvrir_camera()

            if (
                camera is not None
                and camera.isOpened()
            ):

                success, frame = (
                    camera.read()
                )

            else:

                success = False
                frame = None


        # ----------------------------------------------------
        # GESTION ERREURS CAMERA
        # ----------------------------------------------------

        if (
            not success
            or frame is None
        ):

            consecutive_errors += 1

            if consecutive_errors == 1:

                print(
                    "[CAMERA] Echec lecture image",
                    flush=True
                )

            if consecutive_errors >= 10:

                print(
                    "[CAMERA] Trop d'erreurs : "
                    "reinitialisation",
                    flush=True
                )

                with camera_lock:

                    if camera is not None:

                        try:
                            camera.release()
                        except Exception:
                            pass

                    camera = ouvrir_camera()

                consecutive_errors = 0

            time.sleep(0.5)

            continue

        consecutive_errors = 0

        frame_counter += 1


        # ====================================================
        # DETECTION YOLO
        # ====================================================

        person_found = last_person_found


        # YOLO seulement une frame sur N
        if (
            model is not None
            and frame_counter
            % YOLO_FRAME_INTERVAL
            == 0
        ):

            person_found = False

            current_boxes = []

            try:

                results = model(
                    frame,
                    verbose=False,
                    conf=YOLO_CONFIDENCE,
                    classes=[0],
                    imgsz=YOLO_IMAGE_SIZE
                )[0]


                for box in results.boxes:

                    confidence = float(
                        box.conf[0]
                    )

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )

                    current_boxes.append(
                        (
                            x1,
                            y1,
                            x2,
                            y2,
                            confidence
                        )
                    )

                    person_found = True


                last_person_found = (
                    person_found
                )

                last_boxes = (
                    current_boxes
                )


            except Exception as e:

                print(
                    f"[IA] Erreur detection : {e}",
                    flush=True
                )


        # ----------------------------------------------------
        # DESSIN DES DERNIERES DETECTIONS
        # ----------------------------------------------------

        if last_person_found:

            for (
                x1,
                y1,
                x2,
                y2,
                confidence
            ) in last_boxes:

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 0, 255),
                    2
                )

                label = (
                    "PERSONNE DETECTEE "
                    f"{int(confidence * 100)}%"
                )

                cv2.putText(
                    frame,
                    label,
                    (
                        x1,
                        max(
                            25,
                            y1 - 10
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2
                )


        # ====================================================
        # ACTUALISATION ETAT IA
        # ====================================================

        with etat_lock:

            etat_station[
                "ia_humain"
            ] = person_found

            alarme_est_active = (
                alarme_active
            )


        # ====================================================
        # ALERTE MQTT
        # ====================================================

        now = time.time()

        if (
            person_found
            and alarme_est_active
            and (
                now
                - last_alert_time
            ) > ALERT_COOLDOWN
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
                    "[IA] Personne detectee : "
                    "alerte ESP envoyee",
                    flush=True
                )

                last_alert_time = now

            else:

                print(
                    "[IA] Alerte non envoyee : "
                    "MQTT deconnecte",
                    flush=True
                )


        # ====================================================
        # JPEG DASHBOARD
        # ====================================================

        encode_param = [
            int(
                cv2.IMWRITE_JPEG_QUALITY
            ),
            80
        ]

        success_jpeg, buffer = (
            cv2.imencode(
                ".jpg",
                frame,
                encode_param
            )
        )

        if not success_jpeg:

            print(
                "[VIDEO] Erreur encodage JPEG",
                flush=True
            )

            time.sleep(0.1)

            continue


        image_bytes = (
            buffer.tobytes()
        )


        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: "
            + str(
                len(image_bytes)
            ).encode("ascii")
            + b"\r\n\r\n"
            + image_bytes
            + b"\r\n"
        )


        # Limitation de la fréquence du flux
        time.sleep(
            1.0 / CAMERA_FPS
        )


# ============================================================
# 8. ROUTES FLASK
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ------------------------------------------------------------
# VIDEO MJPEG
# ------------------------------------------------------------

@app.route("/video_feed")
def video_feed():

    response = Response(
        generer_images(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )

    response.headers[
        "Cache-Control"
    ] = (
        "no-cache, no-store, "
        "must-revalidate"
    )

    response.headers[
        "Pragma"
    ] = "no-cache"

    response.headers[
        "Expires"
    ] = "0"

    response.headers[
        "X-Accel-Buffering"
    ] = "no"

    return response


# ------------------------------------------------------------
# STATUS
# ------------------------------------------------------------

@app.route(
    "/api/v1/status",
    methods=["GET"]
)
def envoyer_status():

    with etat_lock:

        data = (
            etat_station.copy()
        )

        data[
            "alarme_active"
        ] = alarme_active

    return jsonify(
        data
    )


# ------------------------------------------------------------
# CONTROLE ALARME
# ------------------------------------------------------------

@app.route(
    "/api/v1/control",
    methods=["POST"]
)
def controle_alarme():

    global alarme_active

    donnees = (
        request.get_json(
            silent=True
        )
        or {}
    )

    action = donnees.get(
        "action"
    )

    if action != "toggle":

        return jsonify({
            "error":
                "Action invalide"
        }), 400


    if not mqtt_client.is_connected():

        return jsonify({
            "error":
                "Broker MQTT indisponible"
        }), 503


    with etat_lock:

        alarme_active = (
            not alarme_active
        )

        nouvel_etat = (
            alarme_active
        )


    # Commande envoyée à l'ESP
    payload = json.dumps({
        "alarme_active":
            nouvel_etat
    })


    mqtt_client.publish(
        MQTT_TOPIC_CONTROL,
        payload
    )


    print(
        "[ALARME] Etat : "
        f"{'ACTIVE' if nouvel_etat else 'DESACTIVEE'}",
        flush=True
    )


    return jsonify({
        "status": "ok",
        "alarme_active":
            nouvel_etat
    })


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({
        "status": "ok",
        "mqtt":
            mqtt_client.is_connected(),
        "camera":
            camera is not None
            and camera.isOpened(),
        "yolo":
            model is not None
    })


# ============================================================
# 9. EXECUTION DIRECTE
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=False,
        threaded=True
    )
