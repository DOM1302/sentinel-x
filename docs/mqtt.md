# Sentinel-X — Topics MQTT

Référence des 6 topics utilisés par le broker Mosquitto. Tous les payloads sont en JSON, timestamp au format ISO 8601 (UTC).

| Topic | Publisher | Subscriber | QoS | Retain |
|---|---|---|---|---|
| `sentinel/telemetry` | ESP8266 | Backend | 0 | non |
| `sentinel/status` | ESP8266 (LWT) | Backend, Dashboard | 1 | oui |
| `sentinel/alerts` | ESP8266 (seuils capteurs) | Backend | 1 | non |
| `sentinel/commands` | Backend / Dashboard | ESP8266 | 1 | non |
| `sentinel/vision` | Backend (relai du POST /api/v1/alerts) | Dashboard | 1 | non |
| `sentinel/anomaly` | Backend (maintenance prédictive) | Dashboard | 1 | non |

## `sentinel/telemetry`

Une lecture de capteur par message. Le champ `sensor` distingue le type de mesure.

```json
{
  "device_id": "esp8266-01",
  "sensor": "temperature",
  "value": 24.5,
  "unit": "C",
  "timestamp": "2026-10-05T14:32:10Z"
}
```

Valeurs possibles de `sensor` : `temperature` (°C), `humidity` (%), `gas` (ppm), `presence` (bool, pas de `unit`).

## `sentinel/status`

Alimenté par le Last Will and Testament MQTT de l'ESP8266 : publié automatiquement par le broker si le device se déconnecte sans prévenir.

```json
{ "device_id": "esp8266-01", "status": "online", "timestamp": "2026-10-05T14:32:10Z" }
```

`status` vaut `"online"` ou `"offline"`.

## `sentinel/alerts`

Alertes générées côté ESP8266 quand un capteur dépasse un seuil fixe (gaz, présence PIR). Distinct des détections vision, qui arrivent par `sentinel/vision`.

```json
{
  "device_id": "esp8266-01",
  "type": "gas_threshold",
  "value": 850,
  "threshold": 800,
  "timestamp": "2026-10-05T14:32:10Z"
}
```

## `sentinel/commands`

Commandes envoyées à l'ESP8266 pour piloter les actionneurs (buzzer, LEDs), déclenchées depuis le dashboard.

```json
{ "device_id": "esp8266-01", "actuator": "buzzer", "command": "on", "duration_ms": 3000 }
```

## `sentinel/vision`

Détections de présence humaine par le module IA (webcam). Le point d'entrée obligatoire côté IA reste `POST /api/v1/alerts` (HTTP) — le backend republie ensuite ici pour que le dashboard et les autres services puissent s'abonner en MQTT plutôt qu'en WebSocket.

```json
{
  "source": "vision",
  "type": "intrusion",
  "confidence": 0.87,
  "timestamp": "2026-10-05T14:32:10Z"
}
```

> **Point ouvert** : à confirmer avec DEV/INFRA — est-ce bien le backend qui fait le pont HTTP → MQTT sur ce topic, ou le script vision doit-il publier directement en MQTT en plus du POST HTTP ?

## `sentinel/anomaly`

Résultat du modèle de maintenance prédictive (Isolation Forest / Random Forest) tournant côté backend sur les séries temporelles de `sentinel/telemetry`. Non encore implémenté à ce stade — format proposé :

```json
{
  "device_id": "esp8266-01",
  "type": "anomaly_detected",
  "model": "isolation_forest",
  "score": -0.42,
  "related_sensors": ["temperature", "gas"],
  "timestamp": "2026-10-05T14:32:10Z"
}
```
