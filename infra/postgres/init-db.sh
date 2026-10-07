#!/bin/bash
# Sentinel-X - initialisation PostgreSQL (executee une seule fois, au premier demarrage du conteneur)
# Cree le role applicatif a droits minimaux (SELECT/INSERT) et les tables d'historique.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE ROLE sentinel_app LOGIN PASSWORD '${APP_DB_PASSWORD}';

CREATE TABLE measures (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id   TEXT NOT NULL DEFAULT 'esp32-01',
  temperature REAL,
  humidity    REAL,
  gas         INTEGER,
  pir         BOOLEAN
);
CREATE INDEX idx_measures_ts ON measures (ts DESC);

CREATE TABLE events (
  id      BIGSERIAL PRIMARY KEY,
  ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
  source  TEXT NOT NULL,
  kind    TEXT NOT NULL,
  detail  JSONB
);
CREATE INDEX idx_events_ts ON events (ts DESC);

CREATE TABLE commands (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT now(),
  action        TEXT NOT NULL,
  origin        TEXT,
  alarm_active  BOOLEAN
);

GRANT SELECT, INSERT ON measures, events, commands TO sentinel_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sentinel_app;
EOSQL
