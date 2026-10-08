#!/bin/bash
G="\e[32m"; R="\e[31m"; Y="\e[33m"; N="\e[0m"
ok(){ echo -e "${G}[OK]${N}  $1"; }
ko(){ echo -e "${R}[KO]${N}  $1"; }
wn(){ echo -e "${Y}[!!]${N}  $1"; }

echo "=========================================="
echo "   AUDIT SECURITE SENTINEL-X ($(date +%H:%M))"
echo "=========================================="

# --- Pare-feu ---
ufw status | grep -q "Status: active" && ok "UFW actif" || ko "UFW INACTIF"
ufw status verbose | grep -q "deny (incoming)" && ok "UFW: deny incoming par defaut" || ko "UFW: pas de deny par defaut"

# --- SSH ---
sshd -T 2>/dev/null | grep -qx "passwordauthentication no" && ok "SSH: mot de passe desactive (cles only)" || ko "SSH: mot de passe encore autorise"
sshd -T 2>/dev/null | grep -qx "permitrootlogin no" && ok "SSH: login root desactive" || wn "SSH: PermitRootLogin pas sur 'no'"

# --- fail2ban ---
systemctl is-active --quiet fail2ban && ok "fail2ban actif" || ko "fail2ban INACTIF"
fail2ban-client status sshd >/dev/null 2>&1 && ok "fail2ban: jail sshd active" || ko "fail2ban: jail sshd absente"

# --- ufw-docker ---
iptables -L DOCKER-USER -n 2>/dev/null | grep -q "ufw-user-forward" && ok "ufw-docker actif (Docker soumis a UFW)" || ko "ufw-docker non actif (Docker contourne UFW)"

# --- HTTPS / TLS ---
curl -ksI https://127.0.0.1 2>/dev/null | head -1 | grep -qE "200|301|302" && ok "HTTPS repond sur 443" || ko "HTTPS ne repond pas"
TLSV=$(curl -ksvI https://127.0.0.1 2>&1 | grep -oE "TLSv1\.[23]" | head -1)
[ -n "$TLSV" ] && ok "Chiffrement TLS actif ($TLSV)" || wn "Version TLS non detectee"

# --- Exposition des ports ---
ss -tlnp 2>/dev/null | grep -q "0.0.0.0:8000" && ko "Backend 8000 EXPOSE au LAN" || ok "Backend 8000 non expose"
ss -tlnp 2>/dev/null | grep -q "0.0.0.0:5000" && ko "Port 5000 EXPOSE au LAN (HTTP clair)" || ok "Port 5000 non expose au LAN"
ss -tlnp 2>/dev/null | grep -qE "0.0.0.0:(2375|2376)" && ko "Daemon Docker EXPOSE" || ok "Daemon Docker non expose"

# --- Conteneurs ---
PRIV=$(docker ps -q 2>/dev/null | xargs -r docker inspect --format '{{.Name}} {{.HostConfig.Privileged}}' 2>/dev/null | grep -i " true")
[ -z "$PRIV" ] && ok "Aucun conteneur en mode privilegie" || ko "Conteneur privilegie: $PRIV"

# --- MQTT acces anonyme ---
if command -v mosquitto_sub >/dev/null 2>&1; then
  timeout 3 mosquitto_sub -h 127.0.0.1 -p 1883 -t 'sentinel/#' -C 1 >/dev/null 2>&1 \
    && wn "MQTT 1883: acces anonyme POSSIBLE (a securiser via MQTTS/ACL)" \
    || ok "MQTT 1883: acces anonyme refuse (ou broker protege)"
else
  wn "MQTT: mosquitto-clients non installe, test anonyme ignore"
fi

echo "=========================================="
