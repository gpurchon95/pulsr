#!/usr/bin/env python3
import os
import time
from typing import Optional, Dict, Any, List

import pandas as pd
import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.cache_handler import MemoryCacheHandler

# -------------------------
# Page Setup & Modern OLED Styling
# -------------------------
FAVICON_PATH = "Favicon.png"
LOGO_PATH = "logo.png"

st.set_page_config(
    page_title="PULSR | Music Telemetry & A&R Intelligence",
    page_icon=FAVICON_PATH if os.path.exists(FAVICON_PATH) else "⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background: radial-gradient(circle at top right, #0d1527, #070a11 80%) !important;
        color: #F1F5F9 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: #FFFFFF !important;
    }

    .st-emotion-cache-1h9937a, .st-expander, div[data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.65) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.36) !important;
    }

    .stSelectbox div[data-baseweb="select"] {
        background-color: #0F172A !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        color: #F8FAFC !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 6px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: rgba(30, 41, 59, 0.5) !important;
        border-radius: 10px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        color: #94A3B8 !important;
        padding: 10px 22px !important;
        font-weight: 600 !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: #000000 !important;
        font-weight: 700 !important;
        border: none !important;
    }

    .opportunity-badge {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid rgba(16, 185, 129, 0.5);
        color: #34D399;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        display: inline-block;
    }

    .signed-badge {
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.2);
        color: #94A3B8;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.76rem;
        font-weight: 600;
        display: inline-block;
    }

    .header-bar {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 12px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }

    .stButton>button {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        border-color: #10B981 !important;
        color: #10B981 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=170)
else:
    st.title("⚡ PULSR")

st.markdown("---")

# -------------------------
# Robust Credentials Helper
# -------------------------
def get_secret_var(key: str) -> Optional[str]:
    if os.getenv(key):
        return os.getenv(key)
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return None

CLIENT_ID = get_secret_var("SPOTIFY_CLIENT_ID") or get_secret_var("CLIENT_ID")
CLIENT_SECRET = get_secret_var("SPOTIFY_CLIENT_SECRET") or get_secret_var("CLIENT_SECRET")

with st.sidebar:
    st.markdown("### 🛠️ API Diagnostics")
    if not CLIENT_ID or not CLIENT_SECRET:
        st.error("❌ Missing Credentials in Secrets")
    else:
        st.caption(f"Client ID: `{CLIENT_ID[:6]}...`")

@st.cache_resource
def get_spotify_client() -> Optional[spotipy.Spotify]:
    if not CLIENT_ID or not CLIENT_SECRET:
        return None
    try:
        auth_manager = SpotifyClientCredentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            cache_handler=MemoryCacheHandler(),
        )
        return spotipy.Spotify(auth_manager=auth_manager, requests_timeout=3)
    except Exception:
        return None

sp = get_spotify_client()

with st.sidebar:
    if sp is not None:
        st.success("✅ Spotify API Status: Active")
    else:
        st.error("❌ Spotify API Auth Failed")

# -------------------------
# Fast Multi-Search Helper
# -------------------------
def safe_search(q: str, type: str = "track", market: Optional[str] = None, limit: int = 3) -> Optional[Dict[str, Any]]:
    if not sp:
        return None
    try:
        res = sp.search(q=q, type=type, limit=limit, market=market)
        if res and res.get(f"{type}s", {}).get("items"):
            return res
    except Exception:
        pass
    return None

# -------------------------
# A&R Label Logic
# -------------------------
DIY_DISTRIBUTORS = [
    "distrokid", "tunecore", "awal", "ditto", "cd baby", "unitedmasters",
    "amuse", "soundon", "onerpm", "symphonic", "stem", "landr",
    "routenote", "self-released", "independent", "unsigned"
]

WARNER_LABELS = [
    "warner", "wmg", "atlantic", "parlophone", "elektra", "asylum",
    "sire", "spinnin", "300 entertainment", "big beat", "roadrunner"
]

def analyze_label_status(label_name: str, artist_name: str) -> Dict[str, Any]:
    if not label_name or label_name == "Unknown":
        return {"label": "Independent / Self-Released", "is_warner_opportunity": True}

    label_lower = label_name.lower()
    artist_lower = artist_name.lower()

    if any(w in label_lower for w in WARNER_LABELS):
        return {"label": label_name, "is_warner_opportunity": False}

    is_diy = any(dist in label_lower for dist in DIY_DISTRIBUTORS)
    is_self_released = artist_lower in label_lower or "records" not in label_lower

    if is_diy or is_self_released:
        return {"label": label_name, "is_warner_opportunity": True}

    return {"label": label_name, "is_warner_opportunity": False}

# -------------------------
# Country & Taxonomy
# -------------------------
country_dict = {
    "United Kingdom (GB)": "GB",
    "United States (US)": "US",
    "Nigeria (NG)": "NG",
    "Brazil (BR)": "BR",
    "Japan (JP)": "JP",
}

GENRE_TAXONOMY = {
    "Hip-Hop & Rap": ["uk drill", "pluggnb", "melodic rap"],
    "Pop": ["dance pop", "alt-z", "bedroom pop"],
    "Electronic & Dance": ["house", "amapiano", "drum and bass"],
    "Afrobeats & Global": ["afrobeats", "afropop", "highlife"],
}

# -------------------------
# Fast Telemetry Fetchers
# -------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_genre_data(market: str) -> pd.DataFrame:
    rows = []
    for main_genre, subgenres in GENRE_TAXONOMY.items():
        score = 0
        artists = []
        
        for sub in subgenres:
            res = safe_search(sub, type="track", market=market, limit=2)
            tracks = res.get("tracks", {}).get("items", []) if res else []
            for t in tracks:
                score += t.get("popularity", 0)
                if t.get("artists"):
                    art_name = t["artists"][0].get("name")
                    if art_name and art_name not in artists:
                        artists.append(art_name)

        top_3 = ", ".join(artists[:3]) if artists else "N/A"
        avg_score = round(score / 6, 1) if score > 0 else 0.0

        rows.append({
            "Main_Genre": main_genre,
            "Subgenres": subgenres,
            "Popularity Index": score,
            "Avg Track Popularity": avg_score,
            "Top 3 Artists": top_3,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(by="Popularity Index", ascending=False).reset_index(drop=True)
    df.index += 1
    df["Rank"] = df.index
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_artist_roster(subgenre: str) -> List[Dict[str, Any]]:
    roster = []
    res = safe_search(subgenre, type="artist", limit=3)
    items = res.get("artists", {}).get("items", []) if res else []
    
    for art in items:
        label_name = "Independent"
        try:
            top = sp.artist_top_tracks(art["id"]) if sp else None
            if top and top.get("tracks"):
                album_id = top["tracks"][0]["album"]["id"]
                full_album = sp.album(album_id)
                label_name = full_album.get("label", "Independent")
        except Exception:
            pass

        analysis = analyze_label_status(label_name, art.get("name", ""))
        roster.append({
            "Artist Name": art.get("name", "Unknown"),
            "Record Label": analysis["label"],
            "Popularity Index": art.get("popularity", 0),
            "Total Followers": f"{art.get('followers', {}).get('total', 0):,}",
            "Is Opportunity": analysis["is_warner_opportunity"],
            "Spotify Profile": art.get("external_urls", {}).get("spotify", "#")
        })

    return sorted(roster, key=lambda x: x["Popularity Index"], reverse=True)

# -------------------------
# UI Rendering
# -------------------------
tab1, tab2 = st.tabs(["🔥 Top Genres", "🌐 Top 50 Subgenres"])

with tab1:
    col_control, col_btn = st.columns([2, 1])
    with col_control:
        selected_country_label = st.selectbox("", list(country_dict.keys()))
        country_code = country_dict[selected_country_label]

    with col_btn:
        st.write("")
        btn_refresh = st.button("🔄 Refresh Data", use_container_width=True)

    if btn_refresh:
        st.cache_data.clear()

    st.markdown("### 📈 Genre Momentum Leaderboard — " + selected_country_label)

    with st.spinner("Streaming Spotify market telemetry..."):
        df_leaderboard = fetch_genre_data(country_code)

    max_score = max(df_leaderboard["Popularity Index"].max(), 1)
    
    st.markdown(
        """
        <div class='header-bar'>
            <div style='display: flex; justify-content: space-between; font-weight: 700; font-size: 0.82rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;'>
                <span style='width: 8%;'>Rank</span>
                <span style='width: 25%;'>Genre Family</span>
                <span style='width: 25%;'>Momentum Score</span>
                <span style='width: 15%;'>Avg Score</span>
                <span style='width: 27%;'>Top Roster</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    for _, row in df_leaderboard.iterrows():
        rank_num = row["Rank"]
        main_g = row["Main_Genre"]
        pop_idx = row["Popularity Index"]
        avg_pop = row["Avg Track Popularity"]
        top_3 = row["Top 3 Artists"]
        subs = row["Subgenres"]

        c1, c2, c3, c4, c5 = st.columns([0.8, 2.5, 2.5, 1.5, 2.7])
        c1.markdown(f"### **#{rank_num}**")
        c2.markdown(f"**{main_g}**")
        c3.progress(min(pop_idx / max_score, 1.0), text=f"{pop_idx} pts")
        c4.markdown(f"**{avg_pop}** / 100")
        c5.caption(top_3)

        # High-Speed Lazy Load Expander
        with st.expander(f"🔍 Drill into `{main_g}` Sub-genres & Label Telemetry"):
            for sub in subs:
                # Secondary expander prevents running API calls until clicked
                with st.expander(f"🎵 Sub-genre Roster: **{sub.title()}**"):
                    with st.spinner(f"Loading roster for {sub.title()}..."):
                        artist_data = fetch_artist_roster(sub)

                    if artist_data:
                        dh1, dh2, dh3, dh4, dh5 = st.columns([2.5, 2.5, 1.5, 1.5, 3.0])
                        dh1.caption("**ARTIST**")
                        dh2.caption("**LABEL / DISTRIBUTOR**")
                        dh3.caption("**POPULARITY**")
                        dh4.caption("**FOLLOWERS**")
                        dh5.caption("**A&R STATUS**")

                        for art in artist_data:
                            r1, r2, r3, r4, r5 = st.columns([2.5, 2.5, 1.5, 1.5, 3.0])
                            r1.markdown(f"[{art['Artist Name']}]({art['Spotify Profile']})")
                            r2.markdown(f"🏷️ `{art['Record Label']}`")
                            r3.markdown(f"🔥 `{art['Popularity Index']}/100`")
                            r4.caption(art["Total Followers"])

                            if art["Is Opportunity"]:
                                r5.markdown("<span class='opportunity-badge'>🎯 WARNER OPPORTUNITY</span>", unsafe_allow_html=True)
                            else:
                                r5.markdown("<span class='signed-badge'>🔒 Signed</span>", unsafe_allow_html=True)
                    else:
                        st.warning(f"No artist data returned for {sub}.")

        st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.03);'>", unsafe_allow_html=True)

with tab2:
    st.markdown("### 🌐 Global Top Subgenres Leaderboard")
    st.info("Select Tab 1 to view live country and label analysis.")

st.markdown("---")
st.caption("PULSR Intelligence Engine | Powered by Spotipy & Streamlit")
