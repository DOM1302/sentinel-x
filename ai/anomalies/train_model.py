# train model 

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

# Fixer seed pour avoir des résultats identiques à chaque lancement
np.random.seed(42)

# Génération des données normales 
# Caractéristiques : [température, humidité, gaz_ppm, variation_temp, variation_gaz]
n_samples = 2000

normal_temp = np.random.normal(loc=22.0, scale=1.0, size=n_samples)      
normal_humidity = np.random.normal(loc=50.0, scale=2.0, size=n_samples)  
normal_gas = np.random.uniform(750.0, 800.0, size=n_samples)             
normal_d_temp = np.random.normal(loc=0.0, scale=0.1, size=n_samples)     
normal_d_gas = np.random.normal(loc=0.0, scale=1.0, size=n_samples)      

# Assemblage du tableau des données normales
X_normal = np.column_stack([normal_temp, normal_humidity, normal_gas, normal_d_temp, normal_d_gas])

# Génération des anomalies 
n_anomalies = 100

anomaly_temp = np.random.uniform(32.0, 45.0, size=n_anomalies)          # Température élevée (surchauffe)
anomaly_humidity = np.random.uniform(25.0, 40.0, size=n_anomalies)      # Chute d'humidité (assèchement)
anomaly_gas = np.random.uniform(1200.0, 2500.0, size=n_anomalies)       # Forte hausse de gaz (fuite)
anomaly_d_temp = np.random.uniform(0.3, 0.8, size=n_anomalies)          # Hausse rapide de la température
anomaly_d_gas = np.random.uniform(5.0, 20.0, size=n_anomalies)          # Hausse rapide du niveau de gaz

# Assemblage du tableau des anomalies
X_anomalies = np.column_stack([anomaly_temp, anomaly_humidity, anomaly_gas, anomaly_d_temp, anomaly_d_gas])

# Fusion des données normales et des anomalies
X_train = np.vstack([X_normal, X_anomalies])

# Normalisation des données pour l'apprentissage de l'IA
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# Entraînement du modèle Isolation Forest
model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
model.fit(X_scaled)

# Sauvegarde des fichiers entraînés
joblib.dump(model, "isolation_forest.joblib")
joblib.dump(scaler, "scaler.joblib")

print("Modèle entraîné avec succès ! Fichiers sauvegardés : isolation_forest.joblib, scaler.joblib")