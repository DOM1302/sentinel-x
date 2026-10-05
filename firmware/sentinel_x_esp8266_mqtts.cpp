/*
 * Sentinel-X - ESP8266 MQTTS (TLS) - Preuve de compatibilite
 * Ticket CYBER [P1] Etudier compatibilite TLS ESP8266
 *
 * Connecte l'ESP8266 au broker Mosquitto en MQTTS (port 8883) via BearSSL,
 * en utilisant setTrustAnchors() avec le certificat CA du projet (pas le
 * magasin de certificats publics - inutile sur un reseau ferme qu'on controle).
 *
 * Affiche sur le port serie (115200 bauds) :
 *   - la RAM libre (heap) avant / apres le handshake TLS
 *   - la duree totale de connexion (TCP + TLS + MQTT CONNECT)
 *
 * Bibliotheque requise (Library Manager) : PubSubClient (Nick O'Leary)
 * ESP8266WiFi et WiFiClientSecure font partie du core ESP8266 Arduino.
 */

#include <ESP8266WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// --- A adapter au reseau de table ---
const char* WIFI_SSID     = "SENTINEL-X-TABLE";
const char* WIFI_PASSWORD = "changeme";
const char* MQTT_HOST     = "192.168.10.10";  // IP du PC Serveur Local

// Adressage statique de l'ESP8266 (plus fiable qu'un bail DHCP pour la demo)
IPAddress LOCAL_IP(192, 168, 10, 20);
IPAddress GATEWAY(192, 168, 10, 1);   // a confirmer avec INFRA (Dome) selon la topologie reseau
IPAddress SUBNET(255, 255, 255, 0);
const uint16_t MQTT_PORT  = 8883;             // listener MQTTS (TLS)
const char* DEVICE_ID     = "esp8266-01";

// Certificat CA genere pour le broker (voir note TLS CYBER : openssl req -x509 ...)
// Remplacer le contenu ci-dessous par celui de ca.crt genere pour Mosquitto.
static const char CA_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
REMPLACER_PAR_LE_CONTENU_DE_ca.crt
-----END CERTIFICATE-----
)EOF";

BearSSL::X509List caCert(CA_CERT);
WiFiClientSecure secureClient;
PubSubClient mqttClient(secureClient);

void connectWiFi() {
  Serial.printf("WiFi: connexion a %s...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  if (!WiFi.config(LOCAL_IP, GATEWAY, SUBNET)) {
    Serial.println("Echec configuration IP statique (verifier GATEWAY avec INFRA)");
  }
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.printf("\nWiFi OK - IP: %s\n", WiFi.localIP().toString().c_str());
}

void syncTime() {
  // BearSSL valide la date de validite du certificat ; l'ESP8266 n'a pas
  // d'horloge RTC par defaut, donc la date doit venir du NTP avant le handshake.
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Synchronisation NTP");
  time_t now = time(nullptr);
  while (now < 100000) {
    delay(200);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println(" OK");
}

void connectMQTTS() {
  secureClient.setTrustAnchors(&caCert);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);

  uint32_t heapBefore = ESP.getFreeHeap();
  uint32_t t0 = millis();

  // LWT : si le device se deconnecte sans prevenir, le broker publie
  // automatiquement "offline" (retain=true) sur ce topic.
  String willTopic = String("sentinel-x/") + DEVICE_ID + "/status";
  bool connected = mqttClient.connect(
      DEVICE_ID,
      willTopic.c_str(), 1, true, "offline"
  );

  uint32_t elapsedMs = millis() - t0;
  uint32_t heapAfter = ESP.getFreeHeap();

  if (connected) {
    Serial.println("MQTTS: connexion etablie");
    mqttClient.publish(willTopic.c_str(), "online", true);
  } else {
    Serial.printf("MQTTS: echec, state=%d\n", mqttClient.state());
  }

  Serial.println("--- Mesures de preuve (ticket P1) ---");
  Serial.printf("Duree connexion (TCP+TLS+MQTT)  : %lu ms\n", elapsedMs);
  Serial.printf("Heap libre avant handshake       : %lu octets\n", heapBefore);
  Serial.printf("Heap libre apres handshake        : %lu octets\n", heapAfter);
  Serial.printf("Heap consomme par le TLS          : %lu octets\n", heapBefore - heapAfter);
  Serial.println("---------------------------------------");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  connectWiFi();
  syncTime();
  connectMQTTS();
}

void loop() {
  if (!mqttClient.connected()) {
    Serial.println("MQTTS deconnecte, tentative de reconnexion...");
    connectMQTTS();
    delay(2000);
    return;
  }
  mqttClient.loop();
}
