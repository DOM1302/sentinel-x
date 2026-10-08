# Détection de présence humaine à partir de la caméra
# et envoi d'alertes via MQTT avec YOLOv8 (optimisé)
import cv2
import json
import time
import paho.mqtt.client as mqtt 
from ultralytics import YOLO

# CONFIGURATION
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
ALERT_TOPIC = "sentinel/alerts/intrusion"

# Chargement du modèle IA et ouverture de la caméra (0 pour la webcam principale)
model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(1)

# Connexion au serveur Mosquitto
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.connect(MQTT_BROKER, MQTT_PORT)
client.loop_start()

last_alert_time = 0

print("Caméra active ! Appuyez sur 'q' pour quitter.")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Erreur de lecture de la caméra.")
        break

    start_time = time.time()

    # OPTIMISATION DU FLUX : Redimensionnement systématique en 640x480
    frame = cv2.resize(frame, (640, 480))

    # Détection d'objets sur la capture redimensionnée
    results = model(frame, verbose=False)[0]
    person_found = False

    # Vérification de chaque objet détecté (Classe 0 = Personne)
    for box in results.boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        if class_id == 0 and confidence > 0.50:
            person_found = True
            break

    # ENVOI DE L'ALERTE SI UNE PERSONNE EST DÉTECTÉE 
    now = time.time()
    if person_found and (now - last_alert_time) > 3.0:
        alert = {
            "event": "INTRUSION_ALERT",
            "source": "VISION_AI",
            "status": "CRITICAL",
            "message": "Présence humaine détectée !"
        }
        client.publish(ALERT_TOPIC, json.dumps(alert))
        print("ALERTE ENVOYÉE :", alert)
        last_alert_time = now

    # Calcul du temps de traitement par trame (cible < 100ms)
    processing_time_ms = (time.time() - start_time) * 1000

    #  AFFICHAGE DE LA VIDÉO EN DIRECT
    annotated_frame = results.plot()
    cv2.putText(annotated_frame, f"FPS/Latency: {processing_time_ms:.1f} ms", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imshow("Sentinel Vision Feed (640x480)", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# NETTOYAGE ET FERMETURE
cap.release()
cv2.destroyAllWindows()
client.loop_stop()
client.disconnect()