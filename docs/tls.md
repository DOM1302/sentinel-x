# Sentinel-X — Stratégie TLS (MQTTS)

## Architecture

```
ESP8266 --MQTTS :8883--> Mosquitto
```

Chiffrement de bout en bout entre l'IoT et la stack serveur — obligatoire d'après le cahier des charges.

## Fichiers (`infra/mosquitto/certs/`)

| Fichier | Rôle | Commit Git |
|---|---|---|
| `ca.crt` | Certificat de l'autorité locale — à distribuer sur l'ESP8266 (`setTrustAnchors`) et tout client MQTT | oui (public) |
| `ca.key` | Clé privée de la CA, signe les certificats | **jamais** — voir `.gitignore` |
| `server.crt` | Certificat du broker Mosquitto, signé par la CA | oui (public) |
| `server.key` | Clé privée du broker | **jamais** — voir `.gitignore` |

Génération : `./scripts/generate-certs.sh infra/mosquitto/certs`

> Le cahier des charges interdit tout secret ou clé en clair dans l'archive de code (`Code.zip`). `ca.key` et `server.key` restent hors du dépôt — `.gitignore` déjà en place dans `infra/mosquitto/certs/`.

## Configuration Mosquitto

**Phase 1 — aujourd'hui (préparation uniquement)** : le listener 8883 est ajouté et testé, le 1883 reste ouvert pour ne pas bloquer le développement DEV/IA en cours.

```
listener 1883        # temporaire, ferme en phase 2
listener 8883
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
require_certificate false
```

**Phase 2 — mercredi/jeudi (activation définitive)** : fermeture du 1883, tout le trafic MQTT passe par TLS.

```
listener 8883
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
require_certificate false
```

## Côté ESP8266

Connexion MQTTS via `BearSSL::X509List` + `setTrustAnchors(&caCert)`, avec le contenu de `ca.crt` embarqué dans le firmware — voir `sentinel_x_esp8266_mqtts.cpp`. Le sketch mesure la RAM libre et le temps de handshake pour servir de preuve au ticket [P1] Compatibilité TLS ESP8266.

## Statut

- [x] Architecture définie (ESP8266 → MQTTS :8883 → Mosquitto)
- [ ] Certificats générés (`./scripts/generate-certs.sh`)
- [ ] Listener 8883 ajouté à `mosquitto.conf` (coordination avec Dome / INFRA)
- [ ] Phase 2 : fermeture du 1883 (mercredi/jeudi)
