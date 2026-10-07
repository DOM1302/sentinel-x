"""
Sentinel-X - Historique PostgreSQL

Les ecritures passent par une file et un thread dedie : une base indisponible ne
doit jamais ralentir la detection video ni bloquer la reception MQTT.
Connexion avec le role "sentinel_app" (SELECT/INSERT uniquement).
Variables d'environnement : PG_HOST, PG_PORT, PG_DB, PG_USER, PG_APP_PASSWORD.
"""

import os
import queue
import threading
import time

import psycopg2
from psycopg2.extras import Json


def _dsn():
    return {
        "host": os.getenv("PG_HOST", "127.0.0.1"),
        "port": int(os.getenv("PG_PORT", "5432")),
        "dbname": os.getenv("PG_DB", "sentinel"),
        "user": os.getenv("PG_USER", "sentinel_app"),
        "password": os.getenv("PG_APP_PASSWORD", ""),
        "connect_timeout": 3,
    }


_file = queue.Queue(maxsize=1000)
_derniere_erreur = 0.0


def _signaler(message):
    """Affiche au plus une erreur par minute pour ne pas noyer les logs."""
    global _derniere_erreur
    if time.time() - _derniere_erreur > 60:
        _derniere_erreur = time.time()
        print(f"[DB] {message}", flush=True)


def _ecrivain():
    conn = None
    while True:
        sql, params = _file.get()
        try:
            if conn is None or conn.closed:
                conn = psycopg2.connect(**_dsn())
                conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
        except Exception as e:
            _signaler(f"ecriture impossible : {e}")
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            conn = None


threading.Thread(target=_ecrivain, daemon=True).start()


def _ajouter(sql, params):
    try:
        _file.put_nowait((sql, params))
    except queue.Full:
        _signaler("file d'ecriture pleine, ecriture ignoree")


def _nombre(valeur, type_):
    try:
        return type_(valeur)
    except (TypeError, ValueError):
        return None


def log_measure(temperature, humidite, gaz, pir, device_id="esp32-01"):
    _ajouter(
        "INSERT INTO measures (device_id, temperature, humidity, gas, pir) "
        "VALUES (%s, %s, %s, %s, %s)",
        (device_id, _nombre(temperature, float), _nombre(humidite, float),
         _nombre(gaz, int), bool(pir)),
    )


def log_event(source, kind, detail=None):
    _ajouter(
        "INSERT INTO events (source, kind, detail) VALUES (%s, %s, %s)",
        (source, kind, Json(detail) if detail is not None else None),
    )


def log_command(action, origin, alarm_active):
    _ajouter(
        "INSERT INTO commands (action, origin, alarm_active) VALUES (%s, %s, %s)",
        (action, origin, bool(alarm_active)),
    )


def _lire(sql, params):
    conn = psycopg2.connect(**_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def fetch_measures(minutes=30, limit=500):
    lignes = _lire(
        "SELECT ts, temperature, humidity, gas, pir FROM measures "
        "WHERE ts > now() - make_interval(mins => %s) ORDER BY ts DESC LIMIT %s",
        (minutes, limit),
    )
    return [{"ts": r[0].isoformat(), "temperature": r[1], "humidite": r[2],
             "gaz": r[3], "pir": r[4]} for r in lignes]


def fetch_events(limit=50):
    lignes = _lire(
        "SELECT ts, source, kind, detail FROM events ORDER BY ts DESC LIMIT %s",
        (limit,),
    )
    return [{"ts": r[0].isoformat(), "source": r[1], "kind": r[2], "detail": r[3]}
            for r in lignes]
