# 🛡️ Sentinel-X

**Prototype IoT de surveillance intelligent et sécurisé**
Workshop EPSI BAC+4 · 2026 · Équipe de 5 personnes · Une semaine de réalisation

## Présentation

Sentinel-X associe des capteurs connectés, une caméra et une interface Web pour surveiller un environnement, détecter des événements inhabituels et déclencher des alertes.

Le projet vise à réaliser une chaîne complète : acquisition des données, transmission sécurisée, traitement local, visualisation en temps réel et commande des actionneurs.

**Notre priorité : une démonstration stable, reproductible et documentée.**

> Projet en cours de développement. Les éléments ci-dessous décrivent l’architecture cible et les objectifs à valider.

## Fonctionnalités prévues

*  Mesure de la température et de l’humidité avec un DHT22.
*  Surveillance des variations du capteur MQ-2.
*  Détection de mouvement avec un PIR.
*  Détection de personnes via une webcam USB et une IA locale.
*  Détection d’anomalies dans les données des capteurs.
*  Dashboard Web avec données et alertes en temps réel.
*  Commande de la LED et du buzzer depuis le dashboard.
*  Protection des échanges MQTT par TLS et authentification.
*  Déploiement des services avec Docker Compose.

Le MQ-2 est utilisé dans le cadre d’un prototype pédagogique : il ne constitue pas un dispositif certifié de sécurité incendie ou de mesure de concentration de gaz.

## Architecture cible

### Acquisition et supervision

**ESP8266 → MQTT/TLS → Mosquitto → FastAPI → WebSocket/API → Dashboard**

### Vision locale

**Webcam USB connectée au serveur → OpenCV/YOLO → Événement → Backend → Dashboard**

### Commande des actionneurs

**Dashboard → Backend → MQTT → ESP8266 → LED/Buzzer**

Le PC serveur local héberge les services applicatifs. Le traitement vidéo peut fonctionner directement sur l’hôte si cela simplifie l’accès à la webcam.

## Stack technique

| Composant                | Technologie prévue                          |
| ------------------------ | ------------------------------------------- |
| Microcontrôleur          | ESP8266                                     |
| Firmware                 | C++ · Arduino / PlatformIO                  |
| Capteurs                 | DHT22 · MQ-2 · PIR                          |
| Affichage et actionneurs | OLED · LED · Buzzer                         |
| Messagerie               | Mosquitto · MQTT / MQTTS                    |
| Backend                  | Python · FastAPI                            |
| Communication temps réel | WebSocket                                   |
| Dashboard                | HTML · CSS · JavaScript · Chart.js          |
| Vision                   | OpenCV · YOLO léger pré-entraîné            |
| Détection d’anomalies    | scikit-learn · IsolationForest              |
| Déploiement              | Docker Compose                              |
| Sécurité et audit        | TLS · UFW · SSH par clés · Nmap · Wireshark |

## Équipe

| Membre        | Responsabilité principale                                                                      |
| ------------- | ---------------------------------------------------------------------------------------------- |
| **Dome**      | Infrastructure, réseau, serveur local, Docker Compose, Mosquitto et disponibilité des services |
| **Axel**      | Sécurité des protocoles, TLS/MQTTS, certificats, authentification et analyse Wireshark         |
| **Filda**     | Hardening serveur, pare-feu, SSH, sécurité Docker, audit et pentest                            |
| **Krithika**  | Webcam, détection de personnes, analyse des données et détection d’anomalies                   |
| **Hortellio** | Firmware ESP8266, capteurs, actionneurs, FastAPI, WebSocket et dashboard                       |

L’intégration, les tests, la documentation, le boîtier, la vidéo et la soutenance sont réalisés collectivement. Axel et Filda collaborent sur les décisions de sécurité.

## Organisation prévue du dépôt

| Répertoire ou fichier | Contenu                                           |
| --------------------- | ------------------------------------------------- |
| `firmware/`           | Code ESP8266 et configuration matérielle          |
| `backend/`            | API, intégration MQTT et WebSocket                |
| `dashboard/`          | Interface Web                                     |
| `ai/`                 | Vision et détection d’anomalies                   |
| `infra/`              | Configuration Mosquitto et déploiement            |
| `docs/`               | Architecture, installation, sécurité et livrables |
| `tests/`              | Tests et scénarios de validation                  |
| `compose.yaml`        | Définition des services Docker Compose            |
| `.env.example`        | Exemple de configuration sans secrets             |
| `.gitignore`          | Exclusions Git                                    |
| `README.md`           | Présentation du projet                            |

Cette structure sera mise en place au fil du développement.

## Installation et lancement

La procédure complète sera publiée après validation du premier déploiement.

### Prérequis prévus

* Un PC serveur local avec Docker Engine et Docker Compose.
* Un ESP8266 et les composants électroniques du prototype.
* Une webcam USB connectée directement au serveur.
* Un réseau local accessible au serveur et à l’ESP8266.
* PlatformIO ou Arduino IDE pour compiler et charger le firmware.

La documentation devra préciser la configuration réseau, les variables d’environnement, les certificats, le chargement du firmware et les commandes de lancement.

## Sécurité

Les mesures prévues comprennent :

* Chiffrement des échanges MQTT avec TLS.
* Authentification des clients et restriction des topics par ACL.
* Désactivation de l’accès MQTT anonyme.
* Limitation des ports exposés.
* Configuration du pare-feu UFW et de SSH par clés.
* Vérification des services avec Nmap.
* Vérification du chiffrement des échanges avec Wireshark.

**Aucun mot de passe, fichier `.env` contenant des secrets ou clé privée ne doit être versionné.** Les exemples de configuration utilisent uniquement des valeurs fictives.

Les audits sont réalisés sur les équipements du projet, dans un périmètre autorisé.

## Scénarios de démonstration

| Scénario          | Résultat attendu                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------------------- |
| Température       | Une variation mesurée apparaît dans le dashboard ; une anomalie détectée génère une alerte         |
| Gaz               | Une variation du MQ-2 déclenche une alerte selon la règle configurée et active la LED ou le buzzer |
| Intrusion         | Un mouvement PIR ou une personne détectée par la webcam génère un événement visible                |
| Commande distante | Une commande du dashboard entraîne une action sur la LED ou le buzzer                              |
| Sécurité          | Les captures réseau et l’audit montrent le chiffrement et la limitation des accès                  |

## Validation du prototype

Le prototype sera considéré comme prêt lorsque les points suivants auront été vérifiés :

* [ ] L’ESP8266 transmet les données des capteurs au broker.
* [ ] Le backend reçoit et traite les messages MQTT.
* [ ] Le dashboard affiche les données en temps réel.
* [ ] Les commandes du dashboard atteignent les actionneurs.
* [ ] La webcam produit des événements de détection.
* [ ] Le traitement des anomalies produit des alertes exploitables.
* [ ] Les échanges MQTT sont sécurisés.
* [ ] Le déploiement peut être reproduit à partir de la documentation.
* [ ] Les scénarios de démonstration sont testés et répétables.

## Organisation du travail

* **P0 — Critique :** chaîne capteurs, MQTT, backend, dashboard, IA et commandes.
* **P1 — Important :** sécurité, audit, robustesse et documentation.
* **P2 — Bonus :** améliorations visuelles et fonctions secondaires.

Les modifications sont développées dans des branches dédiées et intégrées après vérification. Une version stable est conservée pour la démonstration.

## Plans de secours

| Difficulté                              | Solution de secours                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------ |
| YOLO trop lent                          | Réduire la résolution et la fréquence d’analyse, puis évaluer OpenCV/HOG                   |
| Webcam difficile à utiliser dans Docker | Exécuter la vision directement sur l’hôte                                                  |
| Dashboard trop complexe                 | Conserver une interface HTML/JavaScript minimale                                           |
| TLS bloque l’intégration                | Diagnostiquer sur un réseau isolé avec MQTT temporaire, puis rétablir TLS avant validation |
| Régression du firmware                  | Revenir à la dernière version validée                                                      |
| Capteur instable                        | Utiliser des données simulées clairement identifiées pour diagnostiquer la chaîne          |

## Livrables

* Prototype fonctionnel et boîtier Fablab.
* Code source et configuration de déploiement.
* Documentation d’installation et d’exploitation.
* Rapport de sécurité avec preuves de tests.
* Dossier technique PDF.
* Présentation PowerPoint.
* Vidéo **Sentinel Drop — 60 secondes**.
* Démonstration finale.

---

Projet pédagogique réalisé dans le cadre du **Workshop EPSI BAC+4 — Mission Sentinel-X**.
