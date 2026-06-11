import streamlit as st
import pandas as pd
import sqlite3
import random
import math
from datetime import datetime, timedelta, timezone
import plotly.graph_objects as go
import plotly.express as px
import logging

# Configuration du logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "ocp_fleet.db"

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION DE LA PAGE (OBLIGATOIREMENT EN PREMIER)
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="OCP Benguerir — Supervision Flotte CAT",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style CSS — CORRECTION : suppression du sélecteur "~" invalide sous Python 3.14
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;600;700&display=swap');
    html, body { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #08121e; color: #e2e8f0; }

    /* Style de la barre latérale */
    section[data-testid="stSidebar"] {
        background-color: #0c1928 !important;
        border-right: 1px solid #1e293b;
    }

    .ocp-header {
        background: linear-gradient(135deg, #0a192f 0%, #0f2647 60%, #173b6c 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        border: 1px solid #1e3a5f;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }
    .ocp-header h1 {
        color: #f39c12 !important;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.5rem;
        margin: 0;
        font-weight: 700;
    }
    .ocp-header p { color: #8892b0; margin: 5px 0 0 0; font-size: 0.88rem; }

    /* Cartes de métriques personnalisées */
    div[data-testid="metric-container"] {
        background-color: #101f30;
        border: 1px solid #1e2a3a;
        padding: 15px !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }

    h2 {
        color: #f39c12 !important;
        font-size: 1.2rem !important;
        text-transform: uppercase;
        font-family: 'IBM Plex Mono', monospace;
        margin-top: 1.5rem !important;
    }

    /* Bouton de simulation */
    div.stButton > button {
        background: linear-gradient(135deg, #f39c12, #d35400) !important;
        color: #08121e !important;
        font-weight: 700 !important;
        border-radius: 6px !important;
        border: none !important;
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(243, 156, 18, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# DATA CATALOGS (FLEET & DTC EXTENDED)
# ══════════════════════════════════════════════════════════════════

FLEET_CATALOG = [
    {"assetId": "CAT-785D-001", "serialNumber": "SN-OCP-001", "model": "CAT 785D", "assetType": "Dumper Minier", "init_hours": 14200.0, "init_fuel_total": 450000.0, "base_lat": 32.2215, "base_lon": -7.9285},
    {"assetId": "CAT-390F-002", "serialNumber": "SN-OCP-002", "model": "CAT 390F", "assetType": "Pelle Hydraulique", "init_hours": 8420.5, "init_fuel_total": 310000.0, "base_lat": 32.2260, "base_lon": -7.9320},
    {"assetId": "CAT-992K-003", "serialNumber": "SN-OCP-003", "model": "CAT 992K", "assetType": "Chargeuse sur Pneus", "init_hours": 12150.2, "init_fuel_total": 390000.0, "base_lat": 32.2180, "base_lon": -7.9210},
    {"assetId": "CAT-D10T-004", "serialNumber": "SN-OCP-004", "model": "CAT D10T", "assetType": "Bulldozer", "init_hours": 3110.8, "init_fuel_total": 120000.0, "base_lat": 32.2295, "base_lon": -7.9415},
    {"assetId": "CAT-16M-005", "serialNumber": "SN-OCP-005", "model": "CAT 16M", "assetType": "Niveleuse Motorisée", "init_hours": 8900.0, "init_fuel_total": 210000.0, "base_lat": 32.2140, "base_lon": -7.9150}
]

DTC_CATALOG = [
    {"spn": 91, "fmi": 8, "description": "Capteur position pédale d'accélérateur – signal hors plage"},
    {"spn": 100, "fmi": 1, "description": "Pression huile moteur faible – capteur dessous seuil critique"},
    {"spn": 110, "fmi": 0, "description": "Température liquide refroidissement moteur – seuil haut dépassé"},
    {"spn": 174, "fmi": 0, "description": "Température carburant moteur – seuil haut dépassé"},
    {"spn": 190, "fmi": 2, "description": "Vitesse moteur irrégulière – données erratiques"},
    {"spn": 629, "fmi": 12, "description": "ECM – défaillance matérielle interne"},
    {"spn": 1569, "fmi": 31, "description": "Derate moteur actif – protection thermique engagée"},
    {"spn": 3216, "fmi": 16, "description": "NOx en sortie SCR – niveau élevé (post-traitement)"},
    {"spn": 5246, "fmi": 0, "description": "Filtre à particules DPF – niveau de suie élevé"},
    {"spn": 641, "fmi": 5, "description": "Actionneur vanne turbo (VGT) – circuit ouvert"}
]

# ══════════════════════════════════════════════════════════════════
# SECTION 1 — SIMULATEUR DE DONNÉES
# ══════════════════════════════════════════════════════════════════

def simulate_asset_list() -> list:
    return FLEET_CATALOG

def simulate_metrics(asset: dict, hours_offset: float = 0.0) -> dict:
    return {
        "engineHours": asset["init_hours"] + hours_offset,
        "totalFuelUsed": asset["init_fuel_total"] + hours_offset * random.uniform(28, 42),
    }

def simulate_status(asset: dict, phase: str = "travail") -> dict:
    if phase == "travail":
        rpm = random.randint(1400, 1950)
        temp = random.uniform(78, 98)
        fuel_pct = random.uniform(40, 95)
    elif phase == "ralenti":
        rpm = random.randint(600, 800)
        temp = random.uniform(65, 80)
        fuel_pct = random.uniform(25, 50)
    else:
        rpm = 0
        temp = random.uniform(30, 45)
        fuel_pct = random.uniform(20, 90)

    return {
        "engineRPM": rpm,
        "coolantTemperature": round(temp, 1),
        "fuelLevelPercent": round(fuel_pct, 1),
    }

def simulate_location(asset: dict, time_offset_h: float = 0.0) -> dict:
    radius = 0.003
    angle = (time_offset_h * 0.7 + random.uniform(0, 0.05)) % (2 * math.pi)
    drift = random.uniform(0.0001, 0.0003)
    lat = asset["base_lat"] + radius * math.sin(angle) + random.uniform(-drift, drift)
    lon = asset["base_lon"] + radius * math.cos(angle) + random.uniform(-drift, drift)
    return {"latitude": round(lat, 6), "longitude": round(lon, 6)}

def simulate_fault_codes(asset_id: str) -> list:
    faults = []
    if random.random() < 0.35:
        nb_faults = random.randint(1, 2)
        selected = random.sample(DTC_CATALOG, nb_faults)
        for fault in selected:
            faults.append({
                "spn": fault["spn"],
                "fmi": fault["fmi"],
                "description": fault["description"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    return faults

# ══════════════════════════════════════════════════════════════════
# SECTION 2 — BASE DE DONNÉES SQLite
# ══════════════════════════════════════════════════════════════════

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engins (
            id_engin        TEXT PRIMARY KEY,
            numero_serie    TEXT NOT NULL,
            modele          TEXT,
            type_engin      TEXT,
            site            TEXT DEFAULT 'Benguerir',
            date_ajout      TEXT DEFAULT (datetime('now'))
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetrie (
            id_releve        INTEGER PRIMARY KEY AUTOINCREMENT,
            id_engin         TEXT NOT NULL,
            horodatage       TEXT NOT NULL,
            heures_marche    REAL,
            conso_carburant  REAL,
            niveau_carburant REAL,
            regime_moteur    INTEGER,
            temp_refroid     REAL,
            latitude         REAL,
            longitude        REAL,
            FOREIGN KEY (id_engin) REFERENCES engins(id_engin)
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS codes_defauts (
            id_defaut   INTEGER PRIMARY KEY AUTOINCREMENT,
            id_engin    TEXT NOT NULL,
            spn         INTEGER,
            fmi         INTEGER,
            description TEXT,
            occurrences INTEGER DEFAULT 1,
            horodatage  TEXT NOT NULL,
            statut      TEXT DEFAULT 'ACTIF',
            FOREIGN KEY (id_engin) REFERENCES engins(id_engin)
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Schéma base de données initialisé.")

def upsert_engin(conn: sqlite3.Connection, asset: dict):
    conn.execute("""
        INSERT OR REPLACE INTO engins (id_engin, numero_serie, modele, type_engin, site)
        VALUES (?, ?, ?, ?, 'Benguerir');
    """, (asset["assetId"], asset["serialNumber"], asset["model"], asset["assetType"]))

def insert_telemetrie(conn: sqlite3.Connection, asset_id: str, metrics: dict, status: dict, location: dict, timestamp: str = None):
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO telemetrie
            (id_engin, horodatage, heures_marche, conso_carburant,
             niveau_carburant, regime_moteur, temp_refroid, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        asset_id, ts, metrics.get("engineHours"), metrics.get("totalFuelUsed"),
        status.get("fuelLevelPercent"), status.get("engineRPM"),
        status.get("coolantTemperature"), location.get("latitude"), location.get("longitude")
    ))

def insert_fault_codes(conn: sqlite3.Connection, asset_id: str, fault_codes: list):
    for fault in fault_codes:
        conn.execute("""
            INSERT OR IGNORE INTO codes_defauts (id_engin, spn, fmi, description, horodatage, statut)
            VALUES (?, ?, ?, ?, ?, 'ACTIF');
        """, (
            asset_id, fault.get("spn"), fault.get("fmi"), fault.get("description"),
            fault.get("timestamp", datetime.now(timezone.utc).isoformat())
        ))

def is_db_empty() -> bool:
    try:
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) FROM engins;").fetchone()
        conn.close()
        return row[0] == 0
    except Exception:
        return True

# ══════════════════════════════════════════════════════════════════
# SECTION 3 — INITIALISATION HISTORIQUE
# ══════════════════════════════════════════════════════════════════

def populate_historical_data(nb_releves: int = 72):
    conn = get_connection()
    assets = simulate_asset_list()
    now = datetime.now(timezone.utc)

    for asset in assets:
        upsert_engin(conn, asset)
        for i in range(nb_releves, 0, -1):
            ts = (now - timedelta(hours=i)).isoformat()
            hours_offset = (nb_releves - i) * random.uniform(0.8, 1.1)
            phase = random.choices(["travail", "ralenti", "arret"], weights=[0.65, 0.20, 0.15])[0]

            metrics = simulate_metrics(asset, hours_offset)
            status = simulate_status(asset, phase)
            location = simulate_location(asset, time_offset_h=float(nb_releves - i))

            insert_telemetrie(conn, asset["assetId"], metrics, status, location, timestamp=ts)

        if random.random() < 0.6:
            faults = simulate_fault_codes(asset["assetId"])
            insert_fault_codes(conn, asset["assetId"], faults)

    conn.commit()
    conn.close()

def run_acquisition_cycle():
    conn = get_connection()
    assets = simulate_asset_list()

    for asset in assets:
        asset_id = asset["assetId"]
        try:
            row = conn.execute("""
                SELECT heures_marche FROM telemetrie
                WHERE id_engin = ?
                ORDER BY horodatage DESC LIMIT 1;
            """, (asset_id,)).fetchone()

            last_hours = row[0] if row else asset["init_hours"]
            new_hours_diff = random.uniform(0.20, 0.28)

            metrics = {
                "engineHours": last_hours + new_hours_diff,
                "totalFuelUsed": asset["init_fuel_total"] + last_hours * 35,
            }
            phase = random.choices(["travail", "ralenti", "arret"], weights=[0.70, 0.20, 0.10])[0]
            status = simulate_status(asset, phase)
            location = simulate_location(asset)
            faults = simulate_fault_codes(asset_id)

            upsert_engin(conn, asset)
            insert_telemetrie(conn, asset_id, metrics, status, location)
            insert_fault_codes(conn, asset_id, faults)
            conn.commit()
        except Exception as exc:
            logger.warning(f"Erreur acquisition cycle: {exc}")
    conn.close()

def query_db(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

@st.cache_resource
def bootstrap():
    init_database()
    if is_db_empty():
        populate_historical_data(nb_releves=72)
    return True

bootstrap()

# ══════════════════════════════════════════════════════════════════
# HEADER INTERFACE
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="ocp-header">
    <h1>SUPERVISION FLOTTE CATERPILLAR — OCP BENGUERIR / GANTOUR</h1>
    <p>Données télémétriques VisionLink — Service Électronique OCP &nbsp;&nbsp;•&nbsp;&nbsp; PFE Génie Mécatronique</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# SIDEBAR BARRE LATÉRALE
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Paramètres")
    engins_df = query_db("SELECT id_engin, modele, type_engin FROM engins ORDER BY id_engin;")

    if engins_df.empty:
        st.warning("Aucun engin en base.")
        st.stop()

    id_to_model = dict(zip(engins_df["id_engin"], engins_df["modele"]))
    engin_selec = st.selectbox(
        "Sélectionner un engin :",
        options=engins_df["id_engin"].tolist(),
        format_func=lambda x: f"{id_to_model.get(x, x)}"
    )

    st.markdown("---")
    st.markdown("### 🛰️ Acquisition")
    if st.button("📡 Simuler une remontée 4G"):
        with st.spinner("Interrogation VisionLink..."):
            run_acquisition_cycle()
        st.success("Remontée 4G effectuée !")
        st.rerun()

    st.markdown("---")
    row_engin = engins_df[engins_df["id_engin"] == engin_selec].iloc[0]
    st.markdown(f"""
    **Engin Sélectionné :**
    - Modèle : `{row_engin['modele']}`
    - Type : `{row_engin['type_engin']}`
    - ID : `{row_engin['id_engin']}`
    """)

# Recupération des données temps réel de l'engin sélectionné
last_releve = query_db("SELECT * FROM telemetrie WHERE id_engin = ? ORDER BY horodatage DESC LIMIT 1;", (engin_selec,))
nb_dtc = query_db("SELECT COUNT(*) as nb FROM codes_defauts WHERE id_engin = ? AND statut = 'ACTIF';", (engin_selec,))["nb"].values[0]

if last_releve.empty:
    st.warning("Aucun relevé disponible.")
    st.stop()

lr = last_releve.iloc[0]

# ══════════════════════════════════════════════════════════════════
# SECTION 1 — KPI TEMPS RÉEL
# ══════════════════════════════════════════════════════════════════
st.markdown("## 📊 Indicateurs Temps Réel")
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Heures de marche", f"{lr['heures_marche']:.1f} h", "⚡ Cumulées (SMH)")
col2.metric("Temp. Refroidissement", f"{lr['temp_refroid']:.1f} °C", "✓ Normal" if lr['temp_refroid'] < 95 else "⚠️ Alerte Seuil")
col3.metric("Régime Moteur", f"{int(lr['regime_moteur'])} RPM", "En Charge")
col4.metric("Niveau Carburant", f"{lr['niveau_carburant']:.1f} %", "⛽ OK")
col5.metric("DTC Actifs", int(nb_dtc), "Codes défauts")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# SECTION 2 — JAUGES DE SURVEILLANCE
# ══════════════════════════════════════════════════════════════════
st.markdown("## 🌡️ Jauges de Surveillance")
gauge_col1, gauge_col2 = st.columns(2)

def create_gauge(title, value, min_val, max_val, suffix, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': suffix, 'font': {'color': '#ffffff', 'size': 24}},
        title={'text': title, 'font': {'color': '#a0aec0', 'size': 15}},
        gauge={
            'axis': {'range': [min_val, max_val], 'tickwidth': 1, 'tickcolor': "#4a5568"},
            'bar': {'color': color},
            'bgcolor': '#101f30',
            'bordercolor': '#1e2a3a',
            'steps': [
                {'range': [min_val, max_val * 0.2], 'color': 'rgba(231, 76, 60, 0.1)'},
                {'range': [max_val * 0.2, max_val], 'color': 'rgba(46, 204, 113, 0.05)'}
            ]
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        height=240,
        margin=dict(l=30, r=30, t=40, b=20)
    )
    return fig

with gauge_col1:
    st.plotly_chart(create_gauge("Niveau Carburant", lr["niveau_carburant"], 0, 100, "%", "#3498db"), use_container_width=True)
with gauge_col2:
    st.plotly_chart(create_gauge("Température Liquide de Refroidissement", lr["temp_refroid"], 0, 120, "°C", "#e74c3c"), use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# SECTION 3 — ÉVOLUTION TEMPORELLE
# ══════════════════════════════════════════════════════════════════
st.markdown("## 📈 Évolution Temporelle (Historique Récent)")
history_df = query_db("""
    SELECT horodatage, heures_marche, temp_refroid, regime_moteur, niveau_carburant
    FROM telemetrie WHERE id_engin = ?
    ORDER BY horodatage ASC;
""", (engin_selec,))

if not history_df.empty:
    c_col1, c_col2 = st.columns(2)

    with c_col1:
        fig_h = px.line(history_df, x="horodatage", y="heures_marche", title="Heures de Marche Cumulées (SMH)")
        fig_h.update_traces(line_color="#f39c12", line_width=2)
        fig_h.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_h, use_container_width=True)

    with c_col2:
        fig_t = px.line(history_df, x="horodatage", y="temp_refroid", title="Température Liquide de Refroidissement (°C)")
        fig_t.update_traces(line_color="#e74c3c", line_width=1.5)
        fig_t.add_hline(y=95, line_dash="dash", line_color="#c0392b", annotation_text="Seuil Alerte")
        fig_t.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_t, use_container_width=True)

    c_col3, c_col4 = st.columns(2)

    with c_col3:
        fig_r = px.line(history_df, x="horodatage", y="regime_moteur", title="Régime Moteur (RPM)")
        fig_r.update_traces(line_color="#2ecc71", line_width=1.5)
        fig_r.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_r, use_container_width=True)

    with c_col4:
        fig_f = px.line(history_df, x="horodatage", y="niveau_carburant", title="Évolution Niveau Carburant (%)")
        fig_f.update_traces(line_color="#3498db", line_width=2)
        fig_f.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=250, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_f, use_container_width=True)
else:
    st.info("Historique insuffisant pour générer les graphiques.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# SECTION 4 — CODES DÉFAUTS ACTIFS (DTC)
# ══════════════════════════════════════════════════════════════════
st.markdown("## ⚠️ Codes Défauts Actifs (DTC)")
dtc_df = query_db("SELECT spn, fmi, description, horodatage, statut FROM codes_defauts WHERE id_engin = ? ORDER BY horodatage DESC;", (engin_selec,))

if not dtc_df.empty:
    st.dataframe(dtc_df, use_container_width=True, hide_index=True)
else:
    st.success("✓ Aucun code défaut actif transmis par l'ECM.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# SECTION 5 — GÉOLOCALISATION
# ══════════════════════════════════════════════════════════════════
st.markdown("## 🗺️ Géolocalisation de la Flotte - Site Benguerir")
map_data = query_db("""
    SELECT t.id_engin, e.modele, e.type_engin, t.latitude, t.longitude
    FROM telemetrie t
    JOIN engins e ON t.id_engin = e.id_engin
    WHERE t.id_releve IN (SELECT MAX(id_releve) FROM telemetrie GROUP BY id_engin);
""")

if not map_data.empty:
    st.map(map_data, latitude="latitude", longitude="longitude", size=40, zoom=13)

    with st.expander("📂 Tableau des positions GPS complètes"):
        st.dataframe(map_data, use_container_width=True, hide_index=True)
else:
    st.warning("Données GPS indisponibles.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════
# SECTION 6 — STATISTIQUES GLOBALES DE LA FLOTTE
# ══════════════════════════════════════════════════════════════════
st.markdown("## 📊 Statistiques Globales de la Flotte")
stats_col1, stats_col2 = st.columns(2)

global_df = query_db("""
    SELECT t.id_engin, e.modele, e.type_engin, t.heures_marche, t.temp_refroid, t.niveau_carburant
    FROM telemetrie t
    JOIN engins e ON t.id_engin = e.id_engin
    WHERE t.id_releve IN (SELECT MAX(id_releve) FROM telemetrie GROUP BY id_engin);
""")

with stats_col1:
    if not global_df.empty:
        fig_bar = px.bar(global_df, x="modele", y="heures_marche", color="type_engin", title="Heures de Marche Totales par Engin (SMH)")
        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=300, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_bar, use_container_width=True)

with stats_col2:
    if not global_df.empty:
        fig_scat = px.scatter(global_df, x="temp_refroid", y="niveau_carburant", text="modele", color="type_engin", size=[30] * len(global_df), title="Analyse Température vs Niveau Carburant Actuel")
        fig_scat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#a0aec0', height=300, margin=dict(t=40, b=20, l=20, r=20))
        st.plotly_chart(fig_scat, use_container_width=True)

# Pied de page
st.markdown("---")
st.caption("OCP Benguerir / Gantour • Service Électronique — Dashboard de Supervision")
