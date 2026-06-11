import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import random
import time
from datetime import datetime, timezone, timedelta
import logging

# --- CONFIGURATION GLOBALE ---
st.set_page_config(
    page_title="OCP Fleet Supervision",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DONNÉES ET CATALOGUES ---
# Base de données simulée des engins - Flotte simulée OCP Benguerir
ENGINS = {
    "CAT 785D": {
        "assetId": "CAT-785D-001",
        "serialNumber": "SN-OCP-001",
        "model": "CAT 785D",
        "assetType": "Bulldozer",
        "init_hours": 12450.5,
        "init_fuel_total": 85400,
        "lat": 32.2215,
        "lon": -7.9285
    },
    "CAT 16M": {
        "assetId": "CAT-16M-005",
        "serialNumber": "SN-OCP-005",
        "model": "CAT 16M",
        "assetType": "Niveleuse Motorisée",
        "init_hours": 8970.2,
        "init_fuel_total": 62100,
        "lat": 32.2260,
        "lon": -7.9320
    },
    "CAT 992K": {
        "assetId": "CAT-992K-002",
        "serialNumber": "SN-OCP-002",
        "model": "CAT 992K",
        "assetType": "Chargeuse sur pneus",
        "init_hours": 15600.8,
        "init_fuel_total": 112000,
        "lat": 32.2180,
        "lon": -7.9210
    }
}

# Codes DTC réalistes pour engins CAT (SPN, FMI, Description)
DTC_CATALOG = [
    {"spn": 91, "fmi": 8, "description": "Capteur position pédale d'accélérateur – signal hors plage"},
    {"spn": 100, "fmi": 1, "description": "Pression huile moteur faible – capteur dessous seuil critique"},
    {"st.markdown": 110, "fmi": 0, "description": "Température liquide refroidissement moteur – seuil haut dépassé"},
    {"spn": 174, "fmi": 0, "description": "Température carburant moteur – seuil haut dépassé"},
    {"spn": 190, "fmi": 2, "description": "Vitesse moteur irrégulière – données erratiques"},
    {"spn": 629, "fmi": 12, "description": "ECM – défaillance matérielle interne"},
    {"spn": 1569, "fmi": 31, "description": "Derate moteur actif – protection thermique engagée"},
    {"spn": 3216, "fmi": 16, "description": "NOx en sortie SCR – niveau élevé (post-traitement)"},
    {"spn": 5246, "fmi": 0, "description": "Filtre à particules DPF – niveau de suie élevé"},
    {"spn": 641, "fmi": 5, "description": "Actionneur vanne turbo (VGT) – circuit ouvert"}
]

# --- FONCTIONS DE SIMULATION (COUCHE APPLICATION) ---
def simulate_metrics(asset: dict, hours_offset: float = 0.0) -> dict:
    # Génère des métriques cumulatives réalistes pour un engin.
    # hours_offset permet de décaler dans le temps pour l'historique.
    return {
        "engineHours": asset["init_hours"] + hours_offset,
        "totalFuelUsed": asset["init_fuel_total"] + hours_offset * random.uniform(20, 30)
    }

# Barre latérale - Sélection de l'engin
st.sidebar.markdown("# ⚙️ PARAMÈTRES")
selected_model = st.sidebar.selectbox("Sélectionner un engin :", list(ENGINS.keys()))
asset_data = ENGINS[selected_model]

st.sidebar.markdown("---")
st.sidebar.markdown("# 📡 Acquisition")
btn_refresh = st.sidebar.button("🚀 Simuler une remontée 4G")

st.sidebar.markdown("---")
st.sidebar.markdown("### Engin Sélectionné:")
st.sidebar.write(f"**Modèle:** {asset_data['model']}")
st.sidebar.write(f"**Type:** {asset_data['assetType']}")
st.sidebar.write(f"**ID:** {asset_data['assetId']}")

# Titre Principal
st.title("🚜 SUPERVISION FLOTTE CATERPILLAR – OCP BENGUERIR / GANTOUR")
st.caption("Données télémétriques VisionLink – Service Électronique OCP • PFE Génie Mécatronique")

# Calcul des métriques actuelles
metrics = simulate_metrics(asset_data)

# Section Indicateurs Temps Réel
st.markdown("### 📊 INDICATEURS TEMPS RÉEL")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Heures de marche", f"{metrics['engineHours']:.1f} h", "↑ Cumulées")
with col2:
    temp = random.uniform(78, 92) if not btn_refresh else random.uniform(85, 102)
    status_temp = "Normal" if temp < 98 else "Surchauffe !"
    st.metric("Temp. Refroidissement", f"{temp:.1f} °C", status_temp, delta_color="inverse" if temp > 98 else "normal")
with col3:
    rpm = random.randint(1200, 1600) if not btn_refresh else random.randint(1800, 2100)
    st.metric("Régime Moteur", f"{rpm} tr/min", "Stable")
with col4:
    fuel_level = random.uniform(65, 85)
    st.metric("Niveau Carburant", f"{fuel_level:.1f} %", "Autonomie OK")
with col5:
    dtc_count = 0 if temp < 98 else random.randint(1, 2)
    st.metric("DTC Actifs", f"{dtc_count}", "↑ Codes défaut" if dtc_count > 0 else "✓ Pas d'anomalie")

st.markdown("---")

# Section Cartographie et Graphiques
col_map, col_graph = st.columns([1, 1])

with col_map:
    st.markdown("### 🗺️ LOCALISATION GPS EN DIRECT")
    df_map = pd.DataFrame([{
        'lat': asset_data['lat'] + random.uniform(-0.001, 0.001),
        'lon': asset_data['lon'] + random.uniform(-0.001, 0.001),
        'name': asset_data['assetId']
    }])
    st.map(df_map, zoom=14)

with col_graph:
    st.markdown("### 📈 CONSOMMATION ET HISTORIQUE (24H)")
    times = [datetime.now(timezone.utc) - timedelta(hours=i) for i in range(24, 0, -1)]
    fuel_history = [metrics['totalFuelUsed'] - (24-i)*random.uniform(22, 28) for i in range(24)]
    
    df_hist = pd.DataFrame({"Temps": times, "Carburant Total (L)": fuel_history})
    fig_fuel = px.line(df_hist, x="Temps", y="Carburant Total (L)", title="Évolution de la consommation globale")
    fig_fuel.update_layout(font_color='#FFFFFF', height=350)
    st.plotly_chart(fig_fuel, use_container_width=True)

# Affichage des pannes DTC si existantes
if dtc_count > 0:
    st.markdown("---")
    st.error("### ⚠️ ALERTES CODES DÉFAUT (DTC) DÉTECTÉS")
    active_dtcs = random.sample(DTC_CATALOG, dtc_count)
    for dtc in active_dtcs:
        st.write(f"**[SPN {dtc['spn']} - FMI {dtc['fmi']}]** : {dtc['description']}")
