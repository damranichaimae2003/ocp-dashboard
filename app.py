import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import random
from datetime import datetime, timezone, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="OCP Fleet Supervision",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DESIGN & STYLE CSS (ÉLÉGANT & SOMBRE) ---
st.markdown("""
<style>
    /* Fond global de l'application */
    .stApp {
        background-color: #08121e;
        color: #e2e8f0;
    }
    
    /* Style de la barre latérale */
    section[data-testid="stSidebar"] {
        background-color: #0c1928 !important;
        border-right: 1px solid #1e293b;
    }
    
    /* Titres */
    h1, h2, h3 {
        color: #f39c12 !important; /* Jaune OCP élégant, pas trop agressif */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 600 !important;
    }
    
    /* Bouton de simulation */
    .stButton>button {
        background-color: #f39c12 !important;
        color: #08121e !important;
        border-radius: 6px !important;
        border: none !important;
        font-weight: bold !important;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #e67e22 !important;
        transform: translateY(-2px);
    }
    
    /* Cartes de métriques personnalisées */
    div[data-testid="metric-container"] {
        background-color: #101f30;
        border: 1px solid #1e2a3a;
        padding: 15px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
</style>
""", unsafe_allowed_html=True)

# --- BASE DE DONNÉES DE LA FLOTTE (BENGUERIR / GANTOUR) ---
if 'fleet_data' not in st.session_state:
    st.session_state.fleet_data = {
        "CAT-785D-001": {"modele": "CAT 785D", "type": "Dumper Minier", "init_hours": 5968.0, "lat": 32.2215, "lon": -7.9285, "color": "#f39c12"},
        "CAT-390F-002": {"modele": "CAT 390F", "type": "Pelle Hydraulique", "init_hours": 8420.5, "lat": 32.2260, "lon": -7.9320, "color": "#1abc9c"},
        "CAT-992K-003": {"modele": "CAT 992K", "type": "Chargeuse sur Pneus", "init_hours": 12150.2, "lat": 32.2180, "lon": -7.9210, "color": "#3498db"},
        "CAT-D10T-004": {"modele": "CAT D10T", "type": "Bulldozer", "init_hours": 3110.8, "lat": 32.2295, "lon": -7.9415, "color": "#9b59b6"},
        "CAT-16M-005": {"modele": "CAT 16M", "type": "Niveleuse Motorisée", "init_hours": 4670.4, "lat": 32.2140, "lon": -7.9150, "color": "#e74c3c"}
    }

# Catalogue étendu de codes défauts (DTC)
DTC_CATALOG = [
    {"spn": 91, "fmi": 8, "description": "Capteur position pédale d'accélérateur – signal hors plage"},
    {"spn": 5246, "fmi": 0, "description": "Filtre à particules DPF – niveau de suie élevé"},
    {"spn": 629, "fmi": 12, "description": "ECM Moteur – défaillance matérielle interne"},
    {"spn": 110, "fmi": 0, "description": "Température liquide refroidissement – seuil critique dépassé"},
    {"spn": 100, "fmi": 1, "description": "Pression d'huile moteur – niveau bas détecté"}
]

# --- BARRE LATÉRALE (SIDEBAR) ---
st.sidebar.markdown("### ⚙️ PARAMÈTRES FLOTTE")

# Choix de la machine par son ID unique
asset_options = list(st.session_state.fleet_data.keys())
selected_id = st.sidebar.selectbox("Sélectionner un engin :", asset_options)
selected_asset = st.session_state.fleet_data[selected_id]

st.sidebar.markdown("---")
st.sidebar.markdown("### 📡 ACQUISITION DATA")
btn_refresh = st.sidebar.button("Simuler une remontée 4G")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 ENGIN SÉLECTIONNÉ")
st.sidebar.info(f"""
* **ID:** `{selected_id}`
* **Modèle:** {selected_asset['modele']}
* **Type:** {selected_asset['type']}
""")

# --- EN-TÊTE PRINCIPAL ---
st.title("🚜 SUPERVISION FLOTTE CATERPILLAR – OCP BENGUERIR / GANTOUR")
st.caption("Données télémétriques de l'interface VisionLink API — Système embarqué J1939 — PFE Génie Mécatronique")
st.markdown("---")

# --- SIMULATION DES VALEURS COURANTES ---
if btn_refresh:
    fuel_level = random.uniform(45.0, 64.7)
    engine_temp = random.uniform(88.0, 94.5)
    engine_rpm = random.randint(1750, 1850)
    dtc_count = random.choice([0, 1, 3])
else:
    fuel_level = 64.7
    engine_temp = 89.8
    engine_rpm = 1816
    dtc_count = 3

# --- 1. INDICATEURS TEMPS RÉEL (METRICS) ---
st.markdown("### 📊 INDICATEURS TEMPS RÉEL")
m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

with m_col1:
    st.metric("Heures de marche", f"{selected_asset['init_hours']:.1f} h", "⚡ Cumulées (SMH)")
with m_col2:
    st.metric("Temp. Refroidissement", f"{engine_temp:.1f} °C", "✓ Normal" if engine_temp < 95 else "⚠️ Élevée")
with m_col3:
    st.metric("Régime Moteur", f"{engine_rpm} RPM", "En Charge")
with m_col4:
    st.metric("Niveau Carburant", f"{fuel_level:.1f} %", "⛽ OK")
with m_col5:
    st.metric("DTC Actifs", f"{dtc_count}", "Codes défauts" if dtc_count > 0 else "✓ RAS")

st.markdown("---")

# --- 2. JAUGES DE SURVEILLANCE (GAUGES) ---
st.markdown("### 🧭 JAUGES DE SURVEILLANCE")
g_col1, g_col2 = st.columns(2)

def create_gauge(title, value, min_val, max_val, suffix, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': suffix, 'font': {'color': '#ffffff', 'size': 24}},
        title={'text': title, 'font': {'color': '#a0aec0', 'size': 16}},
        gauge={
            'axis': {'range': [min_val, max_val], 'tickwidth': 1, 'tickcolor': "#4a5568"},
            'bar': {'color': color},
            'bgcolor': '#1a2635',
            'bordercolor': '#2d3748',
            'steps': [
                {'range': [min_val, max_val*0.2], 'color': 'rgba(231, 76, 60, 0.1)'},
                {'range': [max_val*0.2, max_val], 'color': 'rgba(46, 204, 113, 0.05)'}
            ]
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=220,
        margin=dict(l=30, r=30, t=40, b=20)
    )
    return fig

with g_col1:
    st.plotly_chart(create_gauge("Niveau Carburant", fuel_level, 0, 100, "%", "#3498db"), use_container_width=True)
with g_col2:
    st.plotly_chart(create_gauge("Température Liquide", engine_temp, 0, 120, "°C", "#e74c3c"), use_container_width=True)

st.markdown("---")

# --- 3. ÉVOLUTION TEMPORELLE (COURBES SIMULÉES SUR 24H) ---
st.markdown("### 📈 ÉVOLUTION TEMPORELLE")
c_col1, c_col2 = st.columns(2)

times = [datetime.now(timezone.utc) - timedelta(minutes=30*i) for i in range(24, 0, -1)]

with c_col1:
    hours_series = [selected_asset['init_hours'] - (24-i)*0.4 for i in range(24)]
    df_hours = pd.DataFrame({"Temps": times, "Heures": hours_series})
    fig_h = px.line(df_hours, x="Temps", y="Heures", title="Heures de Marche Cumulées (SMH)")
    fig_h.update_traces(line_color="#f39c12", line_width=2)
    fig_h.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250)
    st.plotly_chart(fig_h, use_container_width=True)

with c_col2:
    temp_series = [engine_temp + random.uniform(-4, 4) for _ in range(24)]
    df_temp = pd.DataFrame({"Temps": times, "Temp": temp_series})
    fig_t = px.line(df_temp, x="Temps", y="Temp", title="Température Liquide de Refroidissement (°C)")
    fig_t.update_traces(line_color="#e74c3c", line_width=1.5)
    fig_t.add_hline(y=105, line_dash="dash", line_color="#c0392b", annotation_text="Seuil alerte 105°C")
    fig_t.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250)
    st.plotly_chart(fig_t, use_container_width=True)

c_col3, c_col4 = st.columns(2)
with c_col3:
    rpm_series = [engine_rpm + random.randint(-150, 150) for _ in range(24)]
    df_rpm = pd.DataFrame({"Temps": times, "RPM": rpm_series})
    fig_r = px.line(df_rpm, x="Temps", y="RPM", title="Régime Moteur (RPM)")
    fig_r.update_traces(line_color="#2ecc71", line_width=1.5)
    fig_r.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250)
    st.plotly_chart(fig_r, use_container_width=True)

with c_col4:
    fuel_series = [fuel_level + (24-i)*0.5 + random.uniform(-1, 1) for i in range(24)]
    df_fuel = pd.DataFrame({"Temps": times, "Fuel": fuel_series})
    fig_f = px.line(df_fuel, x="Temps", y="Fuel", title="Évolution Niveau Carburant (%)")
    fig_f.update_traces(line_color="#3498db", line_width=2)
    fig_f.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250)
    st.plotly_chart(fig_f, use_container_width=True)

st.markdown("---")

# --- 4. CODES DÉFAUTS ACTIFS (DTC) ---
st.markdown("### ⚠️ CODES DÉFAUTS ACTIFS (DTC)")
if dtc_count > 0:
    active_dtcs = DTC_CATALOG[:dtc_count]
    df_dtc = pd.DataFrame(active_dtcs)
    df_dtc["Horodatage"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_dtc["Statut"] = "ACTIF"
    st.dataframe(df_dtc, use_container_width=True, hide_index=True)
else:
    st.success("Aucun code défaut actif transmis par l'ECM.")

st.markdown("---")

# --- 5. GÉOLOCALISATION DE LA FLOTTE ---
st.markdown("### 🗺️ GÉOLOCALISATION DE LA FLOTTE - SITE BENGUERIR")
df_map_list = []
for k, v in st.session_state.fleet_data.items():
    df_map_list.append({
        "ID Engin": k,
        "Modèle": v["modele"],
        "Type": v["type"],
        "latitude": v["lat"] + (random.uniform(-0.002, 0.002) if btn_refresh else 0),
        "longitude": v["lon"] + (random.uniform(-0.002, 0.002) if btn_refresh else 0),
    })
df_map = pd.DataFrame(df_map_list)

st.map(df_map, latitude="latitude", longitude="longitude", size=40, zoom=13)

with st.expander("📂 Tableau des positions GPS"):
    st.dataframe(df_map, use_container_width=True, hide_index=True)

st.markdown("---")

# --- 6. STATISTIQUES GLOBALES DE LA FLOTTE ---
st.markdown("### 📊 STATISTIQUES GLOBALES DE LA FLOTTE")
st_col1, st_col2 = st.columns(2)

with st_col1:
    bar_data = pd.DataFrame({
        "Modèle": [v["modele"] for v in st.session_state.fleet_data.values()],
        "Heures cumulées": [v["init_hours"] for v in st.session_state.fleet_data.values()],
        "Type": [v["type"] for v in st.session_state.fleet_data.values()]
    })
    fig_bar = px.bar(bar_data, x="Modèle", y="Heures cumulées", color="Type", title="Heures de Marche par Engin (SMH)")
    fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=300)
    st.plotly_chart(fig_bar, use_container_width=True)

with st_col2:
    scatter_data = pd.DataFrame({
        "Modèle": [v["modele"] for v in st.session_state.fleet_data.values()],
        "Temp. moyenne (°C)": [85, 89, 74, 91, 80],
        "Carburant moyen (%)": [70, 64, 82, 50, 58],
        "Type": [v["type"] for v in st.session_state.fleet_data.values()]
    })
    fig_scat = px.scatter(scatter_data, x="Temp. moyenne (°C)", y="Carburant moyen (%)", text="Modèle", color="Type", size=[30,30,30,30,30], title="Temp. Moy. vs Niveau Carburant Moyen")
    fig_scat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=300)
    st.plotly_chart(fig_scat, use_container_width=True)

st.markdown("---")
st.caption("OCP Benguerir / Gantour • Service Électronique — Dashboard de Démonstration Réseau Connecté")
