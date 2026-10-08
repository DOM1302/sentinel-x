
import csv
import joblib
import numpy as np

from datetime import datetime
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent

# Lecture des mesures reelles
donnees = []

with open(BASE / "mesures_entrainement.csv", newline="") as fichier:
    for ligne in csv.DictReader(fichier):
        try:
            donnees.append({
                "timestamp": datetime.fromisoformat(
                    ligne["recorded_at"]
                ).timestamp(),
                "temperature": float(ligne["temperature"]),
                "humidite": float(ligne["humidity"]),
                "gaz": float(ligne["gas"]),
                "intrusion": ligne["intrusion"].lower()
                in ("t", "true", "1"),
            })
        except (ValueError, TypeError):
            continue

# Construction de 5 caracteristiques :
# temperature, humidite, gaz, d_temp/dt, d_gaz/dt
X = []

for precedent, actuel in zip(donnees, donnees[1:]):
    # Exclure les periodes d'intrusion
    if precedent["intrusion"] or actuel["intrusion"]:
        continue

    dt = actuel["timestamp"] - precedent["timestamp"]

    # Exclure intervalles invalides et interruptions longues
    if not 0.1 <= dt <= 10:
        continue

    X.append([
        actuel["temperature"],
        actuel["humidite"],
        actuel["gaz"],
        (actuel["temperature"] - precedent["temperature"]) / dt,
        (actuel["gaz"] - precedent["gaz"]) / dt,
    ])

X = np.asarray(X, dtype=float)
X = X[np.isfinite(X).all(axis=1)]

if len(X) < 100:
    raise RuntimeError("Pas assez de mesures exploitables")

# Separation chronologique 80 % / 20 %
separation = int(len(X) * 0.8)

X_train = X[:separation]
X_test = X[separation:]

scaler = StandardScaler()
train_scaled = scaler.fit_transform(X_train)
test_scaled = scaler.transform(X_test)

model = IsolationForest(
    n_estimators=150,
    contamination=0.03,
    random_state=42,
    n_jobs=-1,
)

model.fit(train_scaled)

predictions = model.predict(test_scaled)
scores = model.decision_function(test_scaled)

nb_anomalies = int(np.sum(predictions == -1))
taux = 100 * nb_anomalies / len(X_test)

print(f"Mesures exploitables : {len(X)}")
print(f"Entrainement : {len(X_train)}")
print(f"Validation : {len(X_test)}")
print(f"Anomalies validation : {nb_anomalies}")
print(f"Taux anomalies : {taux:.2f}%")
print(f"Score moyen : {np.mean(scores):.4f}")

# Nouveaux fichiers : aucune modification des modeles originaux
joblib.dump(model, BASE / "isolation_forest_reel.joblib")
joblib.dump(scaler, BASE / "scaler_reel.joblib")

print("Nouveau modele sauvegarde")
