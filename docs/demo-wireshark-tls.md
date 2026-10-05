# Sentinel-X — Scénario de preuve TLS (Wireshark)

## Ce qu'on montre au jury

Une capture Wireshark sur le port **8883** pendant que l'ESP8266 publie des données de capteurs :
- le handshake TLS est visible (ClientHello / ServerHello / échange de certificats)
- le payload applicatif (JSON des capteurs) est **illisible**, chiffré

Contraste avec le port **1883** (phase 1, avant fermeture) : le même payload y est lisible en clair — c'est ce contraste qui rend la preuve parlante pour un jury non technique.

## Préparation (avant la démo)

1. Lancer Wireshark sur le PC Serveur Local, interface réseau de la table
2. Filtre d'affichage : `tcp.port == 8883` (et `tcp.port == 1883` pour la capture de contraste, si encore disponible en phase 1)
3. S'assurer que l'ESP8266 publie en continu (`sentinel/telemetry`) pour avoir du trafic à capturer pendant la démo
4. Pré-enregistrer une capture de secours (`.pcapng`) au cas où le live échoue devant le jury

## Déroulé pendant les 5 minutes de démo live

| Temps | Action | Ce qu'on dit |
|---|---|---|
| ~30s | Ouvrir Wireshark, filtre `tcp.port == 8883` | "Voici le trafic MQTT entre l'ESP8266 et le broker, sur le port TLS." |
| ~20s | Pointer le handshake TLS (ClientHello/ServerHello/Certificate) | "On voit l'échange de certificats — c'est la validation `setTrustAnchors` côté ESP8266." |
| ~20s | Ouvrir un paquet applicatif, montrer les données chiffrées | "Le contenu est illisible : impossible de lire les relevés de capteurs en clair." |
| ~20s (si 1883 encore ouvert) | Montrer la même capture sur 1883 | "À titre de comparaison, voici le même type de message sans TLS — le JSON est lisible directement." |

Durée totale : ~90 secondes, à intégrer dans le créneau "Axe 2 : Technicité, Innovation & Sécurité" de la soutenance (preuve matérielle du chiffrement, 4 pts).

## Rendu attendu

- Capture `.pcapng` sur port 8883 (chiffré)
- Capture `.pcapng` sur port 1883 (clair, si réalisée pendant la phase 1 avant fermeture)
- Les deux fichiers rejoignent le rapport d'audit post-pentest (dossier technique final)

## Risques identifiés

- Si le 1883 est déjà fermé au moment de la démo (phase 2 activée), la capture de contraste doit être faite **avant** mercredi/jeudi et conservée en fichier `.pcapng`, pas en live
- Prévoir un filtre Wireshark pré-configuré en favori pour ne pas perdre de temps à le retaper devant le jury
