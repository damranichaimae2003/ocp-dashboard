import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
import random
import math
import logging
from datetime import datetime, timezone, timedelta

# ──────────────────────────────────────────────────────────────────
# CONFIGURATION GLOBALE
# ──────────────────────────────────────────────────────────────────
DB_PATH = ocp_visionlink.db

logging.basicConfig(
    level=logging.INFO,
    format=%(asctime)s [%(levelname)s] %(message)s,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# CATALOGUE DES ENGINS — Flotte simulée OCP Benguerir
# ──────────────────────────────────────────────────────────────────
FLEET_CATALOG = [
    {
        "assetId" :      "CAT-785D-001",
        "serialNumber" : "SN-OCP-001",
        "model" :   "CAT 785D",
        "assetType" :   "Dumper Minier",
        # Position de base + légère variation aléatoire à la génération
        base_lat     32.2310,
        base_lon     -7.9530,
        # Heures SMH initiales (plausibles pour un dumper en mine)
        init_hours   12_400,
        init_fuel_total 185_000,    # Litres cumulés
    },
    {
        "assetId" :      "CAT-390F-002",
        "serialNumber" : "SN-OCP-002",
        "model" :       "CAT 390F",
        "assetType" :   "Pelle Hydraulique",
        base_lat     32.2295,
        base_lon     -7.9505,
        init_hours   9_870,
        init_fuel_total 142_000,
    },
    {
        "assetId" :      "CAT-992K-003",
        "serialNumber"  :"SN-OCP-003",
        "model" :        "CAT 992K",
        "assetType" :  "Chargeuse sur Pneus",
        base_lat     32.2325,
        base_lon     -7.9560,
        init_hours   7_210,
        init_fuel_total 98_000,
    },
    {
        "assetId"  :   "CAT-D10T-004",
        "serialNumber" : "SN-OCP-004",
        "model"  :      "CAT D10T",
        "assetType" : "Bulldozer",
        base_lat     32.2280,
        base_lon     -7.9490,
        init_hours   15_630,
        init_fuel_total 221_000,
    },
    {
        "assetId" :     "CAT-16M-005",
        "serialNumber" : "SN-OCP-005",
        "model" :        "CAT 16M",
        "assetType"  :  "Niveleuse Motorisée",
        base_lat     32.2340,
        base_lon     -7.9545,
        init_hours   5_890,
        init_fuel_total 67_000,
    },
]

# Codes DTC réalistes pour engins CAT (SPN  FMI  Description)
DTC_CATALOG = [
    {spn 91,   fmi 8,  description Capteur position pédale d'accélérateur — signal hors plage},
    {spn 100,  fmi 1,  description Pression huile moteur faible — capteur dessous seuil critique},
    {spn 110,  fmi 0,  description Température liquide refroidissement moteur — seuil haut dépassé},
    {spn 174,  fmi 0,  description Température carburant moteur — seuil haut dépassé},
    {spn 190,  fmi 2,  description Vitesse moteur irrégulière — données erratiques},
    {spn 629,  fmi 12, description ECM — défaillance matérielle interne},
    {spn 1569, fmi 31, description Derate moteur actif — protection thermique engagée},
    {spn 3216, fmi 16, description NOx en sortie SCR — niveau élevé (post-traitement)},
    {spn 5246, fmi 0,  description Filtre à particules DPF — niveau de suie élevé},
    {spn 641,  fmi 5,  description Actionneur vanne turbo (VGT) — circuit ouvert},
]


# ══════════════════════════════════════════════════════════════════
# SECTION 1 — COUCHE SIMULATION (remplace les appels API réels)
# ══════════════════════════════════════════════════════════════════

def simulate_asset_list() - list
    Retourne le catalogue complet des engins simulés.
    return FLEET_CATALOG


def simulate_metrics(asset dict, hours_offset float = 0.0) - dict
    
    Génère des métriques cumulatives réalistes pour un engin.
    hours_offset permet de décaler dans le temps pour l'historique.
    
    return {
        engineHours   asset[init_hours] + hours_offset,
        totalFuelUsed asset[init_fuel_total] + hours_offset  random.uniform(28, 42),
    }


def simulate_status(asset dict, phase str = travail) - dict
    
    Génère l'état opérationnel temps réel selon la phase de travail.
    Phases  'travail', 'ralenti', 'arret'
    
    if phase == travail
        rpm      = random.randint(1_400, 1_950)
        temp     = random.uniform(78, 98)   # °C normal en charge
        fuel_pct = random.uniform(40, 95)
    elif phase == ralenti
        rpm      = random.randint(600, 800)
        temp     = random.uniform(65, 80)
        fuel_pct = random.uniform(25, 50)
    else  # arret
        rpm      = 0
        temp     = random.uniform(30, 45)
        fuel_pct = random.uniform(20, 90)

    return {
        engineRPM          rpm,
        coolantTemperature round(temp, 1),
        fuelLevelPercent   round(fuel_pct, 1),
    }


def simulate_location(asset dict, time_offset_h float = 0.0) - dict
    
    Simule un déplacement réaliste autour du point de base de l'engin.
    Le déplacement suit une trajectoire pseudo-aléatoire bornée (~mine).
    
    # Rayon de déplacement max  ~300 m en coordonnées degrés
    radius = 0.003
    # Mouvement sinusoïdal pour simuler des trajectoires cohérentes
    angle  = (time_offset_h  0.7 + random.uniform(0, 0.05)) % (2  math.pi)
    drift  = random.uniform(0.0001, 0.0003)
    lat    = asset[base_lat] + radius  math.sin(angle) + random.uniform(-drift, drift)
    lon    = asset[base_lon] + radius  math.cos(angle) + random.uniform(-drift, drift)
    return {latitude round(lat, 6), longitude round(lon, 6)}


def simulate_fault_codes(asset_id str) - list
    
    Génère aléatoirement 0 à 2 codes DTC par engin.
    Probabilité de 35 % d'avoir au moins un DTC (réaliste en mine).
    
    faults = []
    if random.random()  0.35
        nb_faults = random.randint(1, 2)
        selected  = random.sample(DTC_CATALOG, nb_faults)
        for fault in selected
            faults.append({
                fault,
                timestamp datetime.now(timezone.utc).isoformat()
            })
    return faults


# ══════════════════════════════════════════════════════════════════
# SECTION 2 — BASE DE DONNÉES SQLite
# ══════════════════════════════════════════════════════════════════

def get_connection() - sqlite3.Connection
    Retourne une connexion SQLite avec foreign keys activées.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(PRAGMA foreign_keys = ON)
    return conn


def init_database()
    
    Crée le schéma de la base de données si les tables n'existent pas.
    Idempotente  peut être appelée à chaque démarrage sans risque.
    
    conn   = get_connection()
    cursor = conn.cursor()

    # ── Table principale des engins ─────────────────────────────
    cursor.execute(
        CREATE TABLE IF NOT EXISTS engins (
            id_engin        TEXT PRIMARY KEY,
            numero_serie    TEXT NOT NULL,
            modele          TEXT,
            type_engin      TEXT,
            site            TEXT DEFAULT 'Benguerir',
            date_ajout      TEXT DEFAULT (datetime('now'))
        )
    )

    # ── Table des relevés télémétriques (time-series) ───────────
    cursor.execute(
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
        )
    )

    # ── Table des codes défauts DTC ──────────────────────────────
    cursor.execute(
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
        )
    )

    conn.commit()
    conn.close()
    logger.info(Schéma base de données initialisé.)


def upsert_engin(conn sqlite3.Connection, asset dict)
    Insère ou met à jour un engin dans la table engins.
    conn.execute(
        INSERT OR REPLACE INTO engins
            (id_engin, numero_serie, modele, type_engin, site)
        VALUES (, , , , 'Benguerir')
    , (
        asset[assetId],
        asset[serialNumber],
        asset[model],
        asset[assetType],
    ))


def insert_telemetrie(conn sqlite3.Connection, asset_id str,
                      metrics dict, status dict, location dict,
                      timestamp str = None)
    
    Insère un relevé télémétriques dans la table telemetrie.
    Si timestamp n'est pas fourni, utilise l'heure UTC courante.
    
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    conn.execute(
        INSERT INTO telemetrie
            (id_engin, horodatage, heures_marche, conso_carburant,
             niveau_carburant, regime_moteur, temp_refroid,
             latitude, longitude)
        VALUES (, , , , , , , , )
    , (
        asset_id,
        ts,
        metrics.get(engineHours),
        metrics.get(totalFuelUsed),
        status.get(fuelLevelPercent),
        status.get(engineRPM),
        status.get(coolantTemperature),
        location.get(latitude),
        location.get(longitude),
    ))


def insert_fault_codes(conn sqlite3.Connection,
                       asset_id str, fault_codes list)
    
    Insère les codes défauts actifs.
    Doublons ignorés via INSERT OR IGNORE.
    
    for fault in fault_codes
        conn.execute(
            INSERT OR IGNORE INTO codes_defauts
                (id_engin, spn, fmi, description, horodatage, statut)
            VALUES (, , , , , 'ACTIF')
        , (
            asset_id,
            fault.get(spn),
            fault.get(fmi),
            fault.get(description),
            fault.get(timestamp, datetime.now(timezone.utc).isoformat()),
        ))


def is_db_empty() - bool
    Vérifie si la table engins est vide (première exécution).
    try
        conn = get_connection()
        row  = conn.execute(SELECT COUNT() FROM engins).fetchone()
        conn.close()
        return row[0] == 0
    except Exception
        return True


# ══════════════════════════════════════════════════════════════════
# SECTION 3 — INITIALISATION AVEC HISTORIQUE SIMULÉ
# ══════════════════════════════════════════════════════════════════

def populate_historical_data(nb_relevés int = 72)
    
    Peuple la base avec un historique simulé.
    nb_relevés  nombre de points par engin (défaut 72 = 3 jours × 24h).
    Chaque point est espacé d'environ 1 heure en arrière dans le temps.
    
    conn   = get_connection()
    assets = simulate_asset_list()
    now    = datetime.now(timezone.utc)

    for asset in assets
        upsert_engin(conn, asset)

        for i in range(nb_relevés, 0, -1)
            # Recule dans le temps (i heures avant maintenant)
            ts             = (now - timedelta(hours=i)).isoformat()
            hours_offset   = (nb_relevés - i)  random.uniform(0.8, 1.1)
            phase          = random.choices(
                [travail, ralenti, arret],
                weights=[0.65, 0.20, 0.15]
            )[0]

            metrics  = simulate_metrics(asset, hours_offset)
            status   = simulate_status(asset, phase)
            location = simulate_location(asset, time_offset_h=float(nb_relevés - i))

            insert_telemetrie(conn, asset[assetId],
                              metrics, status, location, timestamp=ts)

        # Quelques DTC initiaux (pas systématiques)
        if random.random()  0.6
            faults = simulate_fault_codes(asset[assetId])
            insert_fault_codes(conn, asset[assetId], faults)

    conn.commit()
    conn.close()
    logger.info(fHistorique peuplé  {nb_relevés} relevés × {len(assets)} engins.)


# ══════════════════════════════════════════════════════════════════
# SECTION 4 — CYCLE D'ACQUISITION (remontée 4G simulée)
# ══════════════════════════════════════════════════════════════════

def run_acquisition_cycle()
    
    Simule un cycle complet d'acquisition VisionLink 
    récupère les engins, génère un nouveau relevé pour chacun et
    le persiste en base.  Appelé manuellement via le bouton Sidebar.
    
    conn   = get_connection()
    assets = simulate_asset_list()

    for asset in assets
        asset_id = asset[assetId]
        try
            # Calcul de l'offset d'heures depuis le dernier relevé
            row = conn.execute(
                SELECT heures_marche FROM telemetrie
                WHERE id_engin = 
                ORDER BY horodatage DESC LIMIT 1
            , (asset_id,)).fetchone()
            last_hours     = row[0] if row else asset[init_hours]
            new_hours_diff = random.uniform(0.20, 0.28)   # ~15 min de travail

            metrics  = {
                engineHours   last_hours + new_hours_diff,
                totalFuelUsed asset[init_fuel_total] + last_hours  35,
            }
            phase    = random.choices(
                [travail, ralenti, arret],
                weights=[0.70, 0.20, 0.10]
            )[0]
            status   = simulate_status(asset, phase)
            location = simulate_location(asset)
            faults   = simulate_fault_codes(asset_id)

            upsert_engin(conn, asset)
            insert_telemetrie(conn, asset_id, metrics, status, location)
            insert_fault_codes(conn, asset_id, faults)
            conn.commit()
            logger.info(fCycle 4G simulé — Engin {asset_id} mis à jour.)

        except Exception as exc
            logger.warning(fErreur cycle engin {asset_id}  {exc})

    conn.close()


# ══════════════════════════════════════════════════════════════════
# SECTION 5 — UTILITAIRES BASE DE DONNÉES POUR LE DASHBOARD
# ══════════════════════════════════════════════════════════════════

def query_db(sql str, params tuple = ()) - pd.DataFrame
    Exécute une requête SELECT et retourne un DataFrame pandas.
    conn = get_connection()
    df   = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


# ══════════════════════════════════════════════════════════════════
# SECTION 6 — INITIALISATION AU DÉMARRAGE DE L'APPLICATION
# ══════════════════════════════════════════════════════════════════

# Garde-fou  exécuté une seule fois via le cache Streamlit
@st.cache_resource
def bootstrap()
    
    Initialise le schéma SQLite et peuple les données historiques
    si la base est vide.  Exécuté une seule fois par session serveur.
    
    init_database()
    if is_db_empty()
        logger.info(Base vide détectée — population de l'historique simulé...)
        populate_historical_data(nb_relevés=72)
    return True


# ══════════════════════════════════════════════════════════════════
# SECTION 7 — INTERFACE STREAMLIT (Dashboard)
# ══════════════════════════════════════════════════════════════════

# ── Configuration de la page ────────────────────────────────────
st.set_page_config(
    page_title=OCP Benguerir — Supervision Flotte CAT,
 
    layout     =wide,
    initial_sidebar_state=expanded,
)

# ── CSS personnalisé ─────────────────────────────────────────────
st.markdown(
style
     Police principale 
    @import url('httpsfonts.googleapis.comcss2family=IBM+Plex+Monowght@400;600&family=Interwght@400;600;700&display=swap');

    html, body, [class=css] { font-family 'Inter', sans-serif; }

     Header OCP 
    .ocp-header {
        background linear-gradient(135deg, #00263A 0%, #004B6E 60%, #006D9C 100%);
        padding 1.2rem 2rem;
        border-radius 12px;
        margin-bottom 1.5rem;
        display flex;
        align-items center;
        gap 1rem;
        box-shadow 0 4px 20px rgba(0,38,58,0.3);
    }
    .ocp-header h1 {
        color #F5A623;
        font-family 'IBM Plex Mono', monospace;
        font-size 1.3rem;
        margin 0;
        letter-spacing 0.03em;
    }
    .ocp-header p  { color #A8D8F0; margin 0; font-size 0.82rem; }

     Tuiles KPI 
    [data-testid=stMetric] {
        background #0F1C28;
        border 1px solid #1E3A50;
        border-radius 10px;
        padding 1rem 1.2rem;
        box-shadow 0 2px 10px rgba(0,0,0,0.25);
    }
    [data-testid=stMetricLabel]  { color #7BB8D4 !important; font-size 0.78rem !important; }
    [data-testid=stMetricValue]  { color #F5A623 !important; font-size 1.7rem !important; font-weight 700 !important; }
    [data-testid=stMetricDelta]  { color #5DD3A0 !important; font-size 0.72rem !important; }

     Sidebar 
    section[data-testid=stSidebar] {
        background #071520 !important;
        border-right 1px solid #1E3A50;
    }
    section[data-testid=stSidebar] label { color #7BB8D4 !important; }

     Titres de section 
    h2 { color #F5A623 !important; font-size 1rem !important;
         letter-spacing 0.06em; text-transform uppercase; margin-top 1.5rem !important; }

     Bouton 4G 
    div.stButton  button {
        background linear-gradient(135deg, #F5A623, #E07B00);
        color #071520 !important;
        font-weight 700;
        border none;
        border-radius 8px;
        padding 0.6rem 1.2rem;
        width 100%;
        font-size 0.85rem;
        letter-spacing 0.04em;
        transition opacity 0.2s;
    }
    div.stButton  buttonhover { opacity 0.88; }

     Fond général 
    .stApp { background-color #071520; }
    .block-container { padding-top 1.5rem !important; }
style
, unsafe_allow_html=True)

# ── Bootstrap (initialisation BDD) ──────────────────────────────
bootstrap()

# ── Header ───────────────────────────────────────────────────────
st.markdown(
div class=ocp-header
  div
    h1 SUPERVISION FLOTTE CATERPILLAR — OCP BENGUERIR  GANTOURh1
    pDonnées télémétriques VisionLink — Service Électronique OCP &nbsp;&nbsp; PFE Génie Mécatroniquep
  div
div
, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# SIDEBAR — Sélecteur d'engin + Bouton remontée 4G
# ══════════════════════════════════════════════════════════════════
with st.sidebar
    st.markdown(##  Paramètres)

    engins_df = query_db(SELECT id_engin, modele, type_engin FROM engins ORDER BY id_engin)

    if engins_df.empty
        st.warning(Aucun engin en base.)
        st.stop()

    # Dictionnaire pour le format_func du selectbox
    id_to_model = dict(zip(engins_df[id_engin], engins_df[modele]))

    engin_selec = st.selectbox(
        Sélectionner un engin,
        options=engins_df[id_engin].tolist(),
        format_func=lambda x f{id_to_model.get(x, x)}
    )

    st.markdown(---)
    st.markdown(###  Acquisition)

    # ── BOUTON REMONTÉE 4G ────────────────────────────────────────
    if st.button( Simuler une remontée 4G, help=Génère un nouveau relevé pour tous les engins et rafraîchit le dashboard)
        with st.spinner(Interrogation VisionLink en cours…)
            run_acquisition_cycle()
        st.success( Remontée 4G simulée avec succès !)
        st.rerun()

    st.markdown(---)
    # Infos engin sélectionné
    row_engin = engins_df[engins_df[id_engin] == engin_selec].iloc[0]
    st.markdown(f
    Engin sélectionné
    - Modèle  `{row_engin['modele']}`
    - Type  `{row_engin['type_engin']}`
    - ID  `{row_engin['id_engin']}`
    )

    # Heure du dernier relevé
    last_ts = query_db(
        SELECT MAX(horodatage) as ts FROM telemetrie WHERE id_engin = 
    , (engin_selec,))[ts].values[0]
    if last_ts
        st.caption(f Dernier relevé  {last_ts[19].replace('T', ' ')} UTC)


# ══════════════════════════════════════════════════════════════════
# SECTION 1 — KPI TEMPS RÉEL
# ══════════════════════════════════════════════════════════════════
st.markdown(## Indicateurs Temps Réel)

last_releve = query_db(
    SELECT  FROM telemetrie
    WHERE id_engin = 
    ORDER BY horodatage DESC LIMIT 1
, (engin_selec,))

nb_dtc = query_db(
    SELECT COUNT() as nb FROM codes_defauts
    WHERE id_engin =  AND statut = 'ACTIF'
, (engin_selec,))[nb].values[0]

if last_releve.empty
    st.warning(Aucun relevé disponible pour cet engin.)
    st.stop()

lr = last_releve.iloc[0]

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric(
    label= Heures de marche,
    value=f{lr['heures_marche'],.0f} h,
    delta=Cumulées (SMH)
)
col2.metric(
    label= Temp. refroidissement,
    value=f{lr['temp_refroid'].1f} °C,
    delta= Seuil  105 °C if lr['temp_refroid']  95 else Normal
)
col3.metric(
    label= Régime moteur,
    value=f{int(lr['regime_moteur'])} RPM,
)
col4.metric(
    label= Niveau carburant,
    value=f{lr['niveau_carburant'].1f} %,
    delta= Bas if lr['niveau_carburant']  25 else OK
)
col5.metric(
    label= DTC Actifs,
    value=int(nb_dtc),
    delta=codes défauts
)

# ══════════════════════════════════════════════════════════════════
# SECTION 2 — JAUGES CARBURANT + TEMPÉRATURE
# ══════════════════════════════════════════════════════════════════
st.markdown(##  Jauges de Surveillance)

gauge_col1, gauge_col2 = st.columns(2)

with gauge_col1
    fig_fuel = go.Figure(go.Indicator(
        mode  =gauge+number+delta,
        value =lr[niveau_carburant],
        title ={text Niveau Carburant (%),
                font {color #A8D8F0, size 14}},
        number={font {color #F5A623, size 40}},
        delta ={reference 25, decreasing {color #e74c3c},
                increasing {color #2ecc71}},
        gauge ={
            axis      {range [0, 100],
                          tickcolor #A8D8F0, tickwidth 1},
            bar       {color #2980b9},
            bgcolor   #0F1C28,
            bordercolor #1E3A50,
            steps     [
                {range [0, 15],   color #4a0f0f},
                {range [15, 30],  color #4a3200},
                {range [30, 100], color #0f3320},
            ],
            threshold {
                line  {color #e74c3c, width 3},
                value 15
            }
        }
    ))
    fig_fuel.update_layout(
        paper_bgcolor=#071520, plot_bgcolor=#071520,
        height=280, margin=dict(t=40, b=10, l=10, r=10)
    )
    st.plotly_chart(fig_fuel, use_container_width=True)

with gauge_col2
    fig_temp = go.Figure(go.Indicator(
        mode  =gauge+number+delta,
        value =lr[temp_refroid],
        title ={text Température Refroidissement (°C),
                font {color #A8D8F0, size 14}},
        number={font {color #F5A623, size 40},
                suffix  °C},
        delta ={reference 95, increasing {color #e74c3c},
                decreasing {color #2ecc71}},
        gauge ={
            axis      {range [0, 130],
                          tickcolor #A8D8F0, tickwidth 1},
            bar       {color #c0392b},
            bgcolor   #0F1C28,
            bordercolor #1E3A50,
            steps     [
                {range [0, 70],   color #0f2040},
                {range [70, 95],  color #0f3320},
                {range [95, 105], color #4a3200},
                {range [105, 130],color #4a0f0f},
            ],
            threshold {
                line  {color #e74c3c, width 3},
                value 105
            }
        }
    ))
    fig_temp.update_layout(
        paper_bgcolor=#071520, plot_bgcolor=#071520,
        height=280, margin=dict(t=40, b=10, l=10, r=10)
    )
    st.plotly_chart(fig_temp, use_container_width=True)

# ══════════════════════════════════════════════════════════════════
# SECTION 3 — COURBES TEMPORELLES
# ══════════════════════════════════════════════════════════════════
st.markdown(##  Évolution Temporelle)

histo_df = query_db(
    SELECT horodatage, heures_marche, temp_refroid,
           niveau_carburant, regime_moteur
    FROM telemetrie
    WHERE id_engin = 
    ORDER BY horodatage ASC
    LIMIT 200
, (engin_selec,))

histo_df[horodatage] = pd.to_datetime(histo_df[horodatage])

chart_col1, chart_col2 = st.columns(2)

with chart_col1
    fig_hm = px.line(
        histo_df, x=horodatage, y=heures_marche,
        title=Heures de Marche Cumulées (SMH),
        labels={horodatage DateHeure UTC,
                heures_marche Heures (h)},
        color_discrete_sequence=[#F5A623]
    )
    fig_hm.update_layout(
        paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
        font_color=#A8D8F0,
        title_font_color=#F5A623,
        height=300,
        xaxis=dict(gridcolor=#1E3A50),
        yaxis=dict(gridcolor=#1E3A50),
    )
    st.plotly_chart(fig_hm, use_container_width=True)

with chart_col2
    fig_tc = px.line(
        histo_df, x=horodatage, y=temp_refroid,
        title=Température Liquide de Refroidissement (°C),
        labels={horodatage DateHeure UTC,
                temp_refroid Température (°C)},
        color_discrete_sequence=[#e74c3c]
    )
    fig_tc.add_hline(y=105, line_dash=dash, line_color=#FF6B6B,
                     annotation_text=Seuil alerte 105 °C,
                     annotation_font_color=#FF6B6B)
    fig_tc.update_layout(
        paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
        font_color=#A8D8F0,
        title_font_color=#e74c3c,
        height=300,
        xaxis=dict(gridcolor=#1E3A50),
        yaxis=dict(gridcolor=#1E3A50),
    )
    st.plotly_chart(fig_tc, use_container_width=True)

chart_col3, chart_col4 = st.columns(2)

with chart_col3
    fig_rpm = px.line(
        histo_df, x=horodatage, y=regime_moteur,
        title=Régime Moteur (RPM),
        labels={horodatage DateHeure UTC,
                regime_moteur RPM},
        color_discrete_sequence=[#2ecc71]
    )
    fig_rpm.update_layout(
        paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
        font_color=#A8D8F0,
        title_font_color=#2ecc71,
        height=280,
        xaxis=dict(gridcolor=#1E3A50),
        yaxis=dict(gridcolor=#1E3A50),
    )
    st.plotly_chart(fig_rpm, use_container_width=True)

with chart_col4
    fig_fuel_ev = px.area(
        histo_df, x=horodatage, y=niveau_carburant,
        title=Évolution Niveau Carburant (%),
        labels={horodatage DateHeure UTC,
                niveau_carburant Niveau (%)},
        color_discrete_sequence=[#2980b9]
    )
    fig_fuel_ev.add_hline(y=15, line_dash=dash, line_color=#e74c3c,
                          annotation_text=Seuil critique 15 %,
                          annotation_font_color=#e74c3c)
    fig_fuel_ev.update_layout(
        paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
        font_color=#A8D8F0,
        title_font_color=#2980b9,
        height=280,
        xaxis=dict(gridcolor=#1E3A50),
        yaxis=dict(gridcolor=#1E3A50, range=[0, 100]),
    )
    st.plotly_chart(fig_fuel_ev, use_container_width=True)

# ══════════════════════════════════════════════════════════════════
# SECTION 4 — CODES DÉFAUTS DTC
# ══════════════════════════════════════════════════════════════════
st.markdown(##  Codes Défauts Actifs (DTC))

dtc_df = query_db(
    SELECT spn, fmi, description, occurrences, horodatage, statut
    FROM codes_defauts
    WHERE id_engin =  AND statut = 'ACTIF'
    ORDER BY horodatage DESC
, (engin_selec,))

if dtc_df.empty
    st.success( Aucun code défaut actif sur cet engin.)
else
    # Formatage de l'horodatage pour lisibilité
    dtc_df[horodatage] = dtc_df[horodatage].str[19].str.replace(T,  )

    # Mise en forme conditionnelle
    def highlight_statut(val)
        if val == ACTIF
            return background-color #4a0f0f; color #FF8C8C; font-weight bold
        return 

    st.dataframe(
        dtc_df.style.map(highlight_statut, subset=[statut]),
        use_container_width=True,
        hide_index=True,
        column_config={
            spn         st.column_config.NumberColumn(SPN,        width=small),
            fmi         st.column_config.NumberColumn(FMI,        width=small),
            description st.column_config.TextColumn(Description,  width=large),
            occurrences st.column_config.NumberColumn(Nb occ.,    width=small),
            horodatage  st.column_config.TextColumn(Horodatage,   width=medium),
            statut      st.column_config.TextColumn(Statut,       width=small),
        }
    )

# ══════════════════════════════════════════════════════════════════
# SECTION 5 — GÉOLOCALISATION DE LA FLOTTE
# ══════════════════════════════════════════════════════════════════
st.markdown(##  Géolocalisation de la Flotte — Site Benguerir)

fleet_pos = query_db(
    SELECT e.id_engin, e.modele, e.type_engin,
           t.latitude, t.longitude, t.horodatage
    FROM engins e
    JOIN telemetrie t ON e.id_engin = t.id_engin
    WHERE t.id_releve IN (
        SELECT MAX(id_releve) FROM telemetrie GROUP BY id_engin
    )
    AND t.latitude IS NOT NULL
    AND t.longitude IS NOT NULL
)

if not fleet_pos.empty
    # ── Carte Plotly Scatter Mapbox (aucune dépendance externe) ──
    fig_map = px.scatter_mapbox(
        fleet_pos,
        lat=latitude,
        lon=longitude,
        hover_name=id_engin,
        hover_data={modele True, type_engin True,
                    horodatage True, latitude False, longitude False},
        color=type_engin,
        size_max=18,
        size=[18]  len(fleet_pos),
        color_discrete_sequence=[#F5A623, #2ecc71, #2980b9,
                                  #e74c3c, #9b59b6],
        zoom=13,
        center={lat 32.2310, lon -7.9530},
        mapbox_style=carto-darkmatter,
        title=Positions GPS — Dernière remontée 4G,
    )
    fig_map.update_layout(
        paper_bgcolor=#0F1C28,
        plot_bgcolor =#0F1C28,
        font_color   =#A8D8F0,
        title_font_color=#F5A623,
        legend=dict(bgcolor=#0F1C28, font_color=#A8D8F0),
        height=480,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # Tableau récapitulatif des positions
    with st.expander( Tableau des positions GPS)
        pos_display = fleet_pos.copy()
        pos_display[horodatage] = pos_display[horodatage].str[19].str.replace(T,  )
        pos_display.columns      = [ID Engin, Modèle, Type, Latitude, Longitude, Horodatage]
        st.dataframe(pos_display, use_container_width=True, hide_index=True)
else
    st.info(Aucune donnée GPS disponible.)

# ══════════════════════════════════════════════════════════════════
# SECTION 6 — STATISTIQUES FLOTTE GLOBALE
# ══════════════════════════════════════════════════════════════════
st.markdown(##  Statistiques Globales de la Flotte)

fleet_stats = query_db(
    SELECT e.modele, e.type_engin,
           MAX(t.heures_marche)    AS heures_max,
           AVG(t.temp_refroid)     AS temp_moy,
           AVG(t.niveau_carburant) AS fuel_moy,
           COUNT(t.id_releve)      AS nb_releves
    FROM engins e
    JOIN telemetrie t ON e.id_engin = t.id_engin
    GROUP BY e.id_engin
    ORDER BY heures_max DESC
)

if not fleet_stats.empty
    stat_col1, stat_col2 = st.columns(2)

    with stat_col1
        fig_bar = px.bar(
            fleet_stats,
            x=modele, y=heures_max,
            color=type_engin,
            title=Heures de Marche par Engin (SMH),
            labels={modele Modèle, heures_max Heures (h)},
            color_discrete_sequence=[#F5A623, #2ecc71, #2980b9,
                                      #e74c3c, #9b59b6],
        )
        fig_bar.update_layout(
            paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
            font_color=#A8D8F0, title_font_color=#F5A623,
            showlegend=False,
            xaxis=dict(gridcolor=#1E3A50),
            yaxis=dict(gridcolor=#1E3A50),
            height=320,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with stat_col2
        fig_scatter = px.scatter(
            fleet_stats,
            x=temp_moy, y=fuel_moy,
            size=heures_max,
            color=type_engin,
            hover_name=modele,
            title=Temp. Moy. vs Niveau Carburant Moy.,
            labels={temp_moy Temp. moy. (°C),
                    fuel_moy Carburant moy. (%)},
            color_discrete_sequence=[#F5A623, #2ecc71, #2980b9,
                                      #e74c3c, #9b59b6],
        )
        fig_scatter.update_layout(
            paper_bgcolor=#0F1C28, plot_bgcolor=#0F1C28,
            font_color=#A8D8F0, title_font_color=#F5A623,
            xaxis=dict(gridcolor=#1E3A50),
            yaxis=dict(gridcolor=#1E3A50),
            height=320,
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

# ══════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════
st.markdown(---)
st.markdown(
    div style=text-aligncenter; color#2E5370; font-size0.75rem;
    OCP Benguerir  Gantour — Service Électronique &nbsp;&nbsp;
    PFE Génie Mécatronique &nbsp;&nbsp;
    Données simulées à des fins de démonstration — VisionLink Trimble API
    div,
    unsafe_allow_html=True
)
