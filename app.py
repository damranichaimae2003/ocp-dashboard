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
# DATA CATALOGS (FLEET & DTC)
# ══════════════════════════════════════════════════════════════════

FLEET_CATALOG = [
    {
        "assetId": "CAT-785D-001",
        "serialNumber": "SN-OCP-001",
        "model": "CAT 785D",
        "assetType": "Bulldozer",
        "init_hours": 14200.0,
        "init_fuel_total": 450000.0,
        "base_lat": 32.2310,
        "base_lon": -7.9530
    },
    {
        "assetId": "CAT-16M-005",
        "serialNumber": "SN-OCP-005",
        "model": "CAT 16M",
        "assetType": "Niveleuse Motorisée",
        "init_hours": 8900.0,
        "init_fuel_total": 210000.0,
        "base_lat": 32.2340,
        "base_lon": -7.9560
    }
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
# SECTION 1 — SIMULATEUR DE DONNÉES (VisionLink API)
# ══════════════════════════════════════════════════════════════════

def simulate_asset_list() -> list:
    """Retourne le catalogue complet des engins simulés."""
    return FLEET_CATALOG


def simulate_metrics(asset: dict, hours_offset: float = 0.0) -> dict:
    """Génère des métriques cumulatives réalistes pour un engin."""
    return {
        "engineHours": asset["init_hours"] + hours_offset,
        "totalFuelUsed": asset["init_fuel_total"] + hours_offset * random.uniform(28, 42),
    }


def simulate_status(asset: dict, phase: str = "travail") -> dict:
    """Génère l'état opérationnel temps réel selon la phase de travail."""
    if phase == "travail":
        rpm = random.randint(1400, 1950)
        temp = random.uniform(78, 98)   # °C normal en charge
        fuel_pct = random.uniform(40, 95)
    elif phase == "ralenti":
        rpm = random.randint(600, 800)
        temp = random.uniform(65, 80)
        fuel_pct = random.uniform(25, 50)
    else:  # arret
        rpm = 0
        temp = random.uniform(30, 45)
        fuel_pct = random.uniform(20, 90)

    return {
        "engineRPM": rpm,
        "coolantTemperature": round(temp, 1),
        "fuelLevelPercent": round(fuel_pct, 1),
    }


def simulate_location(asset: dict, time_offset_h: float = 0.0) -> dict:
    """Simule un déplacement réaliste autour du point de base de l'engin."""
    radius = 0.003
    angle = (time_offset_h * 0.7 + random.uniform(0, 0.05)) % (2 * math.pi)
    drift = random.uniform(0.0001, 0.0003)
    lat = asset["base_lat"] + radius * math.sin(angle) + random.uniform(-drift, drift)
    lon = asset["base_lon"] + radius * math.cos(angle) + random.uniform(-drift, drift)
    return {"latitude": round(lat, 6), "longitude": round(lon, 6)}


def simulate_fault_codes(asset_id: str) -> list:
    """Génère aléatoirement 0 à 2 codes DTC par engin."""
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
    """Retourne une connexion SQLite avec foreign keys activées."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database():
    """Crée le schéma de la base de données si les tables n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    # ── Table principale des engins ─────────────────────────────
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

    # ── Table des relevés télémétriques (time-series) ───────────
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

    # ── Table des codes défauts DTC ──────────────────────────────
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
    """Insère ou met à jour un engin dans la table engins."""
    conn.execute("""
        INSERT OR REPLACE INTO engins (id_engin, numero_serie, modele, type_engin, site)
        VALUES (?, ?, ?, ?, 'Benguerir');
    """, (
        asset["assetId"],
        asset["serialNumber"],
        asset["model"],
        asset["assetType"],
    ))


def insert_telemetrie(conn: sqlite3.Connection, asset_id: str,
                     metrics: dict, status: dict, location: dict,
                     timestamp: str = None):
    """Insère un relevé télémétrique dans la table telemetrie."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO telemetrie
            (id_engin, horodatage, heures_marche, conso_carburant,
             niveau_carburant, regime_moteur, temp_refroid, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        asset_id,
        ts,
        metrics.get("engineHours"),
        metrics.get("totalFuelUsed"),
        status.get("fuelLevelPercent"),
        status.get("engineRPM"),
        status.get("coolantTemperature"),
        location.get("latitude"),
        location.get("longitude"),
    ))


def insert_fault_codes(conn: sqlite3.Connection, asset_id: str, fault_codes: list):
    """Insère les codes défauts actifs. Doublons ignorés."""
    for fault in fault_codes:
        conn.execute("""
            INSERT OR IGNORE INTO codes_defauts (id_engin, spn, fmi, description, horodatage, statut)
            VALUES (?, ?, ?, ?, ?, 'ACTIF');
        """, (
            asset_id,
            fault.get("spn"),
            fault.get("fmi"),
            fault.get("description"),
            fault.get("timestamp", datetime.now(timezone.utc).isoformat()),
        ))


def is_db_empty() -> bool:
    """Vérifie si la table engins est vide (première exécution)."""
    try:
        conn = get_connection()
        row = conn.execute("SELECT COUNT(*) FROM engins;").fetchone()
        conn.close()
        return row[0] == 0
    except Exception:
        return True


# ══════════════════════════════════════════════════════════════════
# SECTION 3 — INITIALISATION AVEC HISTORIQUE SIMULÉ
# ══════════════════════════════════════════════════════════════════

def populate_historical_data(nb_relevés: int = 72):
    """Peuple la base avec un historique simulé d'environ 3 jours."""
    conn = get_connection()
    assets = simulate_asset_list()
    now = datetime.now(timezone.utc)

    for asset in assets:
        upsert_engin(conn, asset)

        for i in range(nb_relevés, 0, -1):
            ts = (now - timedelta(hours=i)).isoformat()
            hours_offset = (nb_relevés - i) * random.uniform(0.8, 1.1)
            phase = random.choices(
                ["travail", "ralenti", "arret"],
                weights=[0.65, 0.20, 0.15]
            )[0]

            metrics = simulate_metrics(asset, hours_offset)
            status = simulate_status(asset, phase)
            location = simulate_location(asset, time_offset_h=float(nb_relevés - i))

            insert_telemetrie(conn, asset["assetId"], metrics, status, location, timestamp=ts)

        if random.random() < 0.6:
            faults = simulate_fault_codes(asset["assetId"])
            insert_fault_codes(conn, asset["assetId"], faults)

    conn.commit()
    conn.close()
    logger.info(f"Historique peuplé : {nb_relevés} relevés × {len(assets)} engins.")


# ══════════════════════════════════════════════════════════════════
# SECTION 4 — CYCLE D'ACQUISITION (remontée 4G simulée)
# ══════════════════════════════════════════════════════════════════

def run_acquisition_cycle():
    """Simule un cycle d'acquisition en direct."""
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
            phase = random.choices(
                ["travail", "ralenti", "arret"],
                weights=[0.70, 0.20, 0.10]
            )[0]
            status = simulate_status(asset, phase)
            location = simulate_location(asset)
            faults = simulate_fault_codes(asset_id)

            upsert_engin(conn, asset)
            insert_telemetrie(conn, asset_id, metrics, status, location)
            insert_fault_codes(conn, asset_id, faults)
            conn.commit()
            logger.info(f"Cycle 4G simulé — Engin {asset_id} mis à jour.")

        except Exception as exc:
            logger.warning(f"Erreur cycle engin {asset_id} : {exc}")

    conn.close()


# ══════════════════════════════════════════════════════════════════
# SECTION 5 — UTILITAIRES BASE DE DONNÉES
# ══════════════════════════════════════════════════════════════════

def query_db(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Exécute une requête SELECT et retourne un DataFrame pandas."""
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# ══════════════════════════════════════════════════════════════════
# SECTION 6 — INITIALISATION AU DÉMARRAGE
# ══════════════════════════════════════════════════════════════════

@st.cache_resource
def bootstrap():
    """Initialise le schéma SQLite et peuple les données historiques."""
    init_database()
    if is_db_empty():
        logger.info("Base vide détectée — population de l'historique...")
        populate_historical_data(nb_relevés=72)
    return True


# ══════════════════════════════════════════════════════════════════
# SECTION 7 — INTERFACE STREAMLIT (Dashboard)
# ══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="OCP Benguerir — Supervision Flotte CAT",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Style CSS pour le look industriel sombre de l'OCP
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #071520; }
    .ocp-header {
        background: linear-gradient(135deg, #00263A 0%, #004B6E 60%, #006D9C 100%);
        padding: 1.2rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,38,58,0.3);
    }
    .ocp-header h1 {
        color: #F5A623;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.3rem;
        margin: 0;
    }
    .ocp-header p { color: #A8D8F0; margin: 0; font-size: 0.82rem; }
    [data-testid="stMetric"] {
        background: #0F1C28;
        border: 1px solid #1E3A50;
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }
    h2 { color: #F5A623 !important; font-size: 1rem !important; text-transform: uppercase; }
    div.stButton > button {
        background: linear-gradient(135deg, #F5A623, #E07B00);
        color: #071520 !important;
        font-weight: 700;
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

bootstrap()

# Header
st.markdown("""
<div class="ocp-header">
    <h1>SUPERVISION FLOTTE CATERPILLAR — OCP BENGUERIR / GANTOUR</h1>
    <p>Données télémétriques VisionLink — Service Électronique OCP &nbsp;&nbsp;•&nbsp;&nbsp; PFE Génie Mécatronique</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# SIDEBAR
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

# ══════════════════════════════════════════════════════════════════
# SECTION 1 — KPI TEMPS RÉEL
# ══════════════════════════════════════════════════════════════════
st.markdown("## 📊 Indicateurs Temps Réel")
last_releve = query_db("SELECT * FROM telemetrie WHERE id_engin = ? ORDER BY horodatage DESC LIMIT 1;", (engin_selec,))
nb_dtc = query_db("SELECT COUNT(*) as nb FROM codes_defauts WHERE id_engin = ? AND statut = 'ACTIF';", (engin_selec,))["nb"].values[0]

if last_releve.empty:
    st.warning("Aucun relevé disponible.")
    st.stop()

lr = last_releve.iloc[0]
col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Heures de marche", f"{lr['heures_marche']:.1f} h", "Cumulées")
col2.metric("Temp. Refroidissement", f"{lr['temp_refroid']:.1f} °C", "Normal" if lr['temp_refroid'] < 95 else "Alerte Seuil")
col3.metric("Régime Moteur", f"{int(lr['regime_moteur'])} RPM")
col4.metric("Niveau Carburant", f"{lr['niveau_carburant']:.1f} %")
col5.metric("DTC Actifs", int(nb_dtc), "Codes défauts")

# ══════════════════════════════════════════════════════════════════
# SECTION 2 — JAUGES
# ══════════════════════════════════════════════════════════════════
st.markdown("## 🌡️ Jauges de Surveillance")
gauge_col1, gauge_col2 = st.columns(2)

with gauge_col1:
    fig_fuel = go.Figure(go.Indicator(
        mode="gauge+number", value=lr["niveau_carburant"],
        title={'text': "Niveau Carburant (%)", 'font': {'color': '#A8D8F0', 'size': 14}},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': '#2980b9'}, 'bgcolor': '#0F1C28'}
    ))
    fig_fuel.update_layout(paper_bgcolor='#071520', height=350)

