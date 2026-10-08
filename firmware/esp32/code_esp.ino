
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <DHT.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <time.h>

#include "secrets.h"
#include "mqtt_ca.h"

// ============================================================
// SENTINEL-X - ESP32
// MQTT securise TLS sur le port 8883
// ============================================================

// --- Configuration Wi-Fi ---
Preferences prefs;

String ssid = WIFI_SSID;
String password = WIFI_PASSWORD;

// --- Configuration materielle ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

#define DHTPIN 5
#define DHTTYPE DHT22

#define PIR_PIN 34
#define BUZZER_PIN 23
#define MQ2_PIN 32
#define LED_PIN 26

Adafruit_SSD1306 display(
  SCREEN_WIDTH,
  SCREEN_HEIGHT,
  &Wire,
  -1
);

DHT dht(DHTPIN, DHTTYPE);

// --- Configuration MQTT ---
const uint16_t MQTT_PORT = 8883;

const char* MQTT_CLIENT_ID = "Sentinel-Node";
const char* MQTT_TOPIC_SENSORS = "sentinel/sensors";
const char* MQTT_TOPIC_CONTROL = "sentinel/control";

// --- Objets reseau ---
WiFiUDP udp;

WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);

IPAddress brokerIP;

bool brokerTrouve = false;
bool heureValide = false;

unsigned long dernierEssaiMQTT = 0;
unsigned long dernierEssaiNTP = 0;

// --- Variables d'etat ---
int etatPrecedent = LOW;
bool alarmeActive = true;

bool alarmeIA = false;
unsigned long tempsAlarmeIA = 0;

// --- Variables de temps ---
unsigned long tempsPrecedent = 0;
const unsigned long intervalleDHT = 2000;

bool forcerEnvoi = false;

unsigned long tempsPrecedentLED = 0;
bool etatLED = LOW;

const unsigned long intervalleClignotement = 100;

// ============================================================
// RECEPTION DES COMMANDES MQTT
// ============================================================

void callbackMQTT(
  char* topic,
  byte* payload,
  unsigned int length
) {
  String message = "";

  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("[MQTT] Message recu : ");
  Serial.println(message);

  if (String(topic) == MQTT_TOPIC_CONTROL) {

    // Activer ou desactiver l'alarme globale
    if (
      message.indexOf("\"alarme_active\":true") >= 0 ||
      message.indexOf("\"alarme_active\": true") >= 0
    ) {
      alarmeActive = true;
      Serial.println("[ALARME] Activee");

    } else if (
      message.indexOf("\"alarme_active\":false") >= 0 ||
      message.indexOf("\"alarme_active\": false") >= 0
    ) {
      alarmeActive = false;
      Serial.println("[ALARME] Desactivee");
    }

    // Alarme envoyee par YOLO
    if (
      message.indexOf("\"force_alarme\":true") >= 0 ||
      message.indexOf("\"force_alarme\": true") >= 0
    ) {
      alarmeIA = true;
      tempsAlarmeIA = millis();

      Serial.println("[IA] Alerte intrusion recue");
    }
  }
}

// ============================================================
// CONFIGURATION DU WI-FI VIA LE MONITEUR SERIE
// ============================================================

String lireLigneSerie(const char* question) {
  Serial.println(question);

  String s = "";

  while (s.length() == 0) {
    while (!Serial.available()) {
      delay(10);
    }

    s = Serial.readStringUntil('\n');
    s.trim();
  }

  return s;
}

void chargerWifi() {

  // Identifiants sauvegardes en NVS
  prefs.begin("wifi", true);

  String s = prefs.getString("ssid", "");
  String p = prefs.getString("pass", "");

  prefs.end();

  if (s.length() > 0) {
    ssid = s;
    password = p;
  }

  Serial.println(
    "Appuie sur une touche + Entree "
    "pour changer le Wi-Fi..."
  );

  unsigned long debut = millis();

  while (millis() - debut < 5000) {

    if (Serial.available()) {
      delay(200);

      while (Serial.available()) {
        Serial.read();
      }

      String nouveauSsid = lireLigneSerie(
        "Nom du Wi-Fi (ou RESET) :"
      );

      if (nouveauSsid == "RESET") {
        prefs.begin("wifi", false);
        prefs.clear();
        prefs.end();

        Serial.println(
          "Retour aux identifiants de secrets.h"
        );

        delay(500);
        ESP.restart();
      }

      String nouveauPass = lireLigneSerie(
        "Mot de passe :"
      );

      prefs.begin("wifi", false);

      prefs.putString("ssid", nouveauSsid);
      prefs.putString("pass", nouveauPass);

      prefs.end();

      Serial.println(
        "Configuration sauvegardee. Redemarrage..."
      );

      delay(500);
      ESP.restart();
    }

    delay(10);
  }
}

// ============================================================
// SYNCHRONISATION DE L'HORLOGE POUR TLS
// ============================================================

bool synchroniserHeure() {

  Serial.println("[NTP] Synchronisation de l'heure...");

  configTime(
    0,
    0,
    "pool.ntp.org",
    "time.google.com"
  );

  unsigned long debut = millis();

  // Attente maximale de 15 secondes
  while (
    time(nullptr) < 1700000000 &&
    millis() - debut < 15000
  ) {
    delay(250);
  }

  if (time(nullptr) < 1700000000) {
    Serial.println(
      "[NTP] ECHEC : heure invalide"
    );

    return false;
  }

  Serial.println("[NTP] Heure synchronisee");

  return true;
}

// ============================================================
// DECOUVERTE AUTOMATIQUE DU BROKER
// ============================================================

void rechercherBroker() {

  Serial.println("[UDP] Recherche du serveur Sentinel-X");

  display.clearDisplay();
  display.setCursor(0, 10);
  display.println("Recherche Broker...");
  display.display();

  udp.begin(5555);

  while (!brokerTrouve) {

    int packetSize = udp.parsePacket();

    if (packetSize > 0) {

      char incomingPacket[256];

      int len = udp.read(
        incomingPacket,
        sizeof(incomingPacket) - 1
      );

      if (len > 0) {

        incomingPacket[len] = '\0';

        String msg = String(incomingPacket);

        if (msg == "SENTINEL_HERE") {

          brokerIP = udp.remoteIP();

          // Validation du certificat serveur
          espClient.setCACert(MQTT_CA_CERT);

          // MQTT chiffre TLS
          mqttClient.setServer(
            brokerIP,
            MQTT_PORT
          );

          mqttClient.setCallback(callbackMQTT);

          brokerTrouve = true;

          Serial.print("[MQTTS] Broker trouve : ");
          Serial.println(brokerIP);

          Serial.print("[MQTTS] Port : ");
          Serial.println(MQTT_PORT);
        }
      }
    }

    delay(100);
  }

  udp.stop();
}

// ============================================================
// CONNEXION MQTT SECURISEE
// ============================================================

void connecterMQTT() {

  if (mqttClient.connected()) {
    return;
  }

  if (!brokerTrouve) {
    return;
  }

  if (!heureValide) {

    // Reessayer NTP sans bloquer la boucle en permanence
    if (millis() - dernierEssaiNTP >= 30000) {

      dernierEssaiNTP = millis();
      heureValide = synchroniserHeure();
    }

    if (!heureValide) {
      return;
    }
  }

  if (millis() - dernierEssaiMQTT < 5000) {
    return;
  }

  dernierEssaiMQTT = millis();

  Serial.print("[MQTTS] Connexion a ");
  Serial.print(brokerIP);
  Serial.print(":");
  Serial.println(MQTT_PORT);

  if (mqttClient.connect(MQTT_CLIENT_ID)) {

    Serial.println(
      "[MQTTS] Connexion TLS etablie"
    );

    if (mqttClient.subscribe(MQTT_TOPIC_CONTROL)) {
      Serial.println(
        "[MQTTS] Abonne a sentinel/control"
      );
    } else {
      Serial.println(
        "[MQTTS] Echec abonnement"
      );
    }

  } else {

    Serial.print("[MQTTS] Echec connexion, etat MQTT : ");
    Serial.println(mqttClient.state());

    // Le code MQTT ne donne pas toujours le detail
    // d'une erreur de verification TLS.
    char erreurTLS[160];

    int codeTLS = espClient.lastError(
      erreurTLS,
      sizeof(erreurTLS)
    );

    if (codeTLS != 0) {
      Serial.print("[TLS] ");
      Serial.println(erreurTLS);
    }
  }
}

// ============================================================
// INITIALISATION
// ============================================================

void setup() {

  Serial.begin(115200);

  chargerWifi();

  dht.begin();

  pinMode(PIR_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);
  noTone(BUZZER_PIN);

  if (!display.begin(
    SSD1306_SWITCHCAPVCC,
    0x3C
  )) {
    Serial.println("[OLED] Erreur");

    while (true) {
      delay(1000);
    }
  }

  // --- Connexion Wi-Fi ---
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 10);
  display.println("Connexion Wi-Fi...");
  display.println(ssid);
  display.display();

  WiFi.begin(
    ssid.c_str(),
    password.c_str()
  );

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("[WiFi] Connecte");

  Serial.print("[WiFi] Adresse IP : ");
  Serial.println(WiFi.localIP());

  // --- Synchronisation NTP avant TLS ---
  heureValide = synchroniserHeure();
  dernierEssaiNTP = millis();

  if (!heureValide) {
    Serial.println(
      "[TLS] Connexion differee : NTP indisponible"
    );
  }

  // --- Recherche du broker ---
  rechercherBroker();

  // --- Demarrage normal ---
  display.clearDisplay();
  display.setCursor(0, 10);
  display.println("CIBLE VERROUILLEE");

  display.setCursor(0, 30);
  display.println(WiFi.localIP());

  display.display();

  digitalWrite(LED_PIN, HIGH);
  tone(BUZZER_PIN, 2000);

  delay(200);

  digitalWrite(LED_PIN, LOW);
  noTone(BUZZER_PIN);

  delay(2000);

  Serial.println("[SYSTEME] Sentinel-X pret");
}

// ============================================================
// BOUCLE PRINCIPALE
// ============================================================

void loop() {

  unsigned long tempsActuel = millis();

  // --- Gestion de la connexion MQTT ---
  if (!mqttClient.connected()) {
    connecterMQTT();
  } else {
    mqttClient.loop();
  }

  // --- Lecture des capteurs ---
  int etatActuel = digitalRead(PIR_PIN);
  int valeurGaz = analogRead(MQ2_PIN);

  if (etatActuel != etatPrecedent) {
    etatPrecedent = etatActuel;
    forcerEnvoi = true;
  }

  static bool alerteGaz = false;

  if (valeurGaz > 1000 && !alerteGaz) {

    alerteGaz = true;
    forcerEnvoi = true;

  } else if (valeurGaz <= 1000 && alerteGaz) {

    alerteGaz = false;
    forcerEnvoi = true;
  }

  // --- Arret automatique de l'alarme IA ---
  if (
    alarmeIA &&
    millis() - tempsAlarmeIA > 3000
  ) {
    alarmeIA = false;
  }

  // --- Synthese des menaces ---
  bool urgenceEnCours = (
    etatActuel == HIGH ||
    alerteGaz ||
    alarmeIA
  );

  // --- Buzzer ---
  if (urgenceEnCours && alarmeActive) {
    tone(BUZZER_PIN, 1000);
  } else {
    noTone(BUZZER_PIN);
  }

  // --- LED ---
  if (urgenceEnCours) {

    if (
      tempsActuel - tempsPrecedentLED >=
      intervalleClignotement
    ) {

      tempsPrecedentLED = tempsActuel;

      etatLED = (
        etatLED == LOW
      ) ? HIGH : LOW;

      digitalWrite(
        LED_PIN,
        etatLED
      );
    }

  } else {

    etatLED = LOW;
    digitalWrite(LED_PIN, LOW);
  }

  // --- Publication des donnees ---
  if (
    tempsActuel - tempsPrecedent >= intervalleDHT ||
    forcerEnvoi
  ) {

    tempsPrecedent = tempsActuel;
    forcerEnvoi = false;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (!isnan(h) && !isnan(t)) {

      // --- Affichage OLED ---
      display.clearDisplay();

      display.setTextSize(1);
      display.setCursor(0, 0);
      display.print("IP:");
      display.println(WiFi.localIP());

      display.setTextSize(2);
      display.setCursor(0, 12);
      display.print("T:");
      display.print(t, 1);
      display.print("C");

      display.setCursor(0, 30);
      display.print("H:");
      display.print(h, 1);
      display.print("%");

      display.setCursor(0, 48);
      display.print("G:");
      display.print(valeurGaz);

      if (alerteGaz) {
        display.print(" !");
      }

      display.display();

      // --- Publication MQTT TLS ---
      if (mqttClient.connected()) {

        String jsonPayload =
          "{\"temperature\": " + String(t) +
          ", \"humidite\": " + String(h) +
          ", \"gaz\": " + String(valeurGaz) +
          ", \"intrusion\": " +
          (etatActuel == HIGH ? "true" : "false") +
          "}";

        bool publie = mqttClient.publish(
          MQTT_TOPIC_SENSORS,
          jsonPayload.c_str()
        );

        if (!publie) {
          Serial.println(
            "[MQTTS] Echec publication capteurs"
          );
        }
      }
    }
  }

  delay(10);
}
