# Sentinel-X — Connexion MQTTS de l'ESP8266

## Méthode retenue

`WiFiClientSecure` (bibliothèque BearSSL, incluse dans le core ESP8266 Arduino), couplée à `PubSubClient` pour le protocole MQTT.

## Port

**8883** (MQTTS — MQTT over TLS). Listener dédié sur Mosquitto, distinct du 1883 en clair (fermé en phase d'activation définitive, voir `docs/tls.md`).

## Méthode de validation du certificat

`setTrustAnchors()` avec un certificat CA unique (`ca.crt`, généré par `scripts/generate-certs.sh`) — pas le magasin de certificats publics, inutile sur un réseau fermé qu'on contrôle entièrement.

Trois méthodes BearSSL étaient possibles :

| Méthode | Principe | Retenue ? |
|---|---|---|
| `setInsecure()` | Désactive toute vérification du certificat | Non — aucune protection contre une attaque MITM, contredit le chiffrement obligatoire du sujet |
| `setFingerprint()` | Vérifie une empreinte SHA-1 figée du certificat serveur | Non — doit être régénérée à chaque renouvellement de certificat, fragile en période de sprint |
| `setTrustAnchors()` | Valide la chaîne de confiance contre un CA | **Oui** — un seul CA à distribuer, résiste au renouvellement du certificat serveur |

## Identification du certificat CA

`ca.crt` (généré via `scripts/generate-certs.sh`) est embarqué directement dans le firmware, en `PROGMEM`, au format PEM.

## Contrainte RAM

BearSSL consomme une part significative de la RAM disponible (~80 Ko au total sur l'ESP8266). Le sketch de preuve mesure cette consommation avant/après le handshake TLS.

## Preuve de fonctionnement

`firmware/sentinel_x_esp8266_mqtts.cpp` :
1. Connexion Wi-Fi (adressage statique, voir le firmware)
2. Synchronisation NTP — requise car BearSSL vérifie la date d'expiration du certificat, et l'ESP8266 n'a pas d'horloge RTC par défaut
3. Connexion au broker en MQTTS via `setTrustAnchors()`
4. Affichage sur le port série : RAM libre avant/après handshake, durée totale de connexion

Ce document et le sketch fonctionnel constituent ensemble la preuve de compatibilité TLS demandée par le ticket.
