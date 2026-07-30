#!/usr/bin/env python3
import os
import time
import math
import threading
from typing import Optional, Dict, Any, List

import pandas as pd
import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.exceptions import SpotifyException

# -------------------------
# File paths / Constants
# -------------------------
FAVICON_PATH = "Favicon.png"
LOGO_PATH = "logo.png"

# -------------------------
# Page setup
# -------------------------
st.set_page_config(
    page_title="PULSR",
    page_icon=FAVICON_PATH if os.path.exists(FAVICON_PATH) else "🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------
# Styling (kept, but removed full-viewport spinner overlay)
# -------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&display=swap');

    html, body, [data-testid="stAppViewContainer"], .stApp {
        background-color: #0A0D14 !important;
        color: #E2E8F0 !important;
        font-family: 'Poppins', sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Poppins', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
    }

    .st-emotion-cache-1h9937a, .st-expander {
        background: #111827 !important;
        border: 1px solid rgba(255, 255, 255, 0.07) !important;
        border-radius: 12px !important;
        margin-bottom: 8px !important;
        font-family: 'Poppins', sans-serif !important;
    }

    .stSelectbox div[data-baseweb="select"] {
        background-color: #1E293B !important;
        border-radius: 10px !important;
        border: 1px solid #334155 !important;
        color: #F8FAFC !important;
        font-family: 'Poppins', sans-serif !important;
    }

    [data-testid="stDataFrame"] {
        background-color: #0F172A !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        padding: 8px;
        font-family: 'Poppins', sans-serif !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #1E293B !important;
        border-radius: 8px 8px 0 0 !important;
        color: #94A3B8 !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: #10B981 !important;
        color: #000000 !important;
    }

    /* Reduced/safer spinner styling — no full-viewport overlay that blocks rendering */
    .pulsr-spinner {
        display: inline-block;
        width: 40px;
        height: 40px;
        border: 4px solid rgba(255, 255, 255, 0.15);
        border-top: 4px solid #10B981;
        border-radius: 50%;
        animation: pulsr-spin 0.75s linear infinite;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.2);
    }

    @keyframes pulsr-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Branding (safe)
# -------------------------
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=160)
else:
    st.title("PULSR")

st.markdown("---")

# -------------------------
# Credentials: read from env or Streamlit secrets (do NOT hardcode)
# -------------------------
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID") or st.secrets.get("SPOTIFY_CLIENT_ID", None)
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET") or st.secrets.get("SPOTIFY_CLIENT_SECRET", None)

if not CLIENT_ID or not CLIENT_SECRET:
    st.warning(
        "Spotify credentials not found. Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
        "to Streamlit Secrets (⚙️ Settings -> Secrets) or export them in your shell."
    )

# -------------------------
# Spotify client factory (cached resource)
# -------------------------
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
        # requests_timeout ensures the client doesn't hang indefinitely
        return spotipy.Spotify(auth_manager=auth_manager, requests_timeout=8)
    except Exception as e:
        st.error(f"⚠️ Spotify Auth Error: {e}")
        return None


sp = get_spotify_client()

# -------------------------
# Rate-limit / retry safe wrapper for sp.search calls
# -------------------------
def safe_search(q: str, type: str = "track", market: Optional[str] = None, limit: int = 5, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """
    Wrapper around sp.search with retries and handling for 429 responses.
    Returns the parsed result or None on failure.
    """
    if not sp:
        return None

    backoff_base = 0.5
    for attempt in range(max_retries):
        try:
            if market:
                res = sp.search(q=q, type=type, limit=limit, market=market)
            else:
                res = sp.search(q=q, type=type, limit=limit)
            return res
        except SpotifyException as e:
            # Try to detect rate-limiting
            try:
                status = getattr(e, "http_status", None)
                headers = getattr(e, "headers", {}) or {}
                if status == 429:
                    retry_after = int(headers.get("Retry-After", 1))
                    sleep_for = retry_after + 0.1
                    time.sleep(sleep_for)
                    continue
            except Exception:
                pass
            # For other Spotify errors, break early
            st.warning(f"Spotify API error (attempt {attempt + 1}): {e}")
            time.sleep(backoff_base * (2 ** attempt))
        except Exception as exc:
            # Network or unexpected error, exponential backoff
            time.sleep(backoff_base * (2 ** attempt))
    return None

# -------------------------
# Genre taxonomy & countries
# -------------------------
country_dict = {
    "United Kingdom (GB)": "GB",
    "United States (US)": "US",
    "Nigeria (NG)": "NG",
    "Brazil (BR)": "BR",
    "Japan (JP)": "JP",
    "France (FR)": "FR",
    "Germany (DE)": "DE",
    "Canada (CA)": "CA",
    "Australia (AU)": "AU",
}

GENRE_TAXONOMY = {
    "Hip-Hop & Rap": ["uk drill", "pluggnb", "melodic rap", "underground hip hop", "trap", "phonk"],
    "Pop": ["dance pop", "alt-z", "bedroom pop", "synthpop", "indie pop"],
    "Electronic & Dance": ["house", "amapiano", "gqom", "hyperpop", "drum and bass", "techno"],
    "Afrobeats & Global": ["afrobeats", "afropop", "azontobeats", "highlife"],
    "Alternative & Rock": ["shoegaze", "indie rock", "post-punk", "grungegaze"],
    "R&B & Soul": ["r&b", "neo soul", "alternative r&b", "trap soul"],
}
ALL_SUBGENRES = [sub for subs in GENRE_TAXONOMY.values() for sub in subs]

# -------------------------
# Minimal quick leaderboard (fast) — used for preview to keep initial render < 2s
# -------------------------
@st.cache_data(ttl=300, show_spinner=False)
def get_genre_leaderboard_quick(market: str) -> pd.DataFrame:
    """
    Quick, minimal API calls: 1 track per subgenre to get a fast approximate score.
    This keeps initial UI rendering very fast.
    """
    if not sp:
        return pd.DataFrame()

    genre_data = []
    for main_genre, subgenres in GENRE_TAXONOMY.items():
        total_momentum = 0
        count = 0
        top_artists = []
        for sub in subgenres:
            res = safe_search(sub, type="track", market=market, limit=1)
            tracks = res.get("tracks", {}).get("items", []) if res else []
            if tracks:
                p = tracks[0].get("popularity", 0)
                total_momentum += p
                count += 1
                if tracks[0].get("artists"):
                    art_name = tracks[0]["artists"][0].get("name")
                    if art_name and art_name not in top_artists:
                        top_artists.append(art_name)
            # very small delay to avoid aggressive burst
            time.sleep(0.02)
        avg_pop = round(total_momentum / count, 1) if count else 0.0
        top_3 = ", ".join(top_artists[:3]) if top_artists else "N/A"
        genre_data.append({
            "Main_Genre": main_genre,
            "Subgenres": subgenres,
            "Popularity Index": total_momentum,
            "Avg Track Popularity": avg_pop,
            "Top 3 Artists": top_3,
        })

    df = pd.DataFrame(genre_data)
    if not df.empty:
        df = df.sort_values(by="Popularity Index", ascending=False).reset_index(drop=True)
        df.index += 1
        df["Rank"] = df.index
    return df

# -------------------------
# Full leaderboard (slower, more thorough)
# -------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def get_genre_leaderboard_full(market: str) -> pd.DataFrame:
    """
    Full scan: uses more tracks per subgenre for a more accurate score.
    This is invoked only on-demand (button press).
    """
    if not sp:
        return pd.DataFrame()

    genre_data = []
    for main_genre, subgenres in GENRE_TAXONOMY.items():
        total_momentum = 0
        all_track_pops = []
        top_artists = []
        for sub in subgenres:
            res = safe_search(sub, type="track", market=market, limit=5)
            tracks = res.get("tracks", {}).get("items", []) if res else []
            for t in tracks:
                p = t.get("popularity", 0)
                all_track_pops.append(p)
                total_momentum += p
                if t.get("artists"):
                    art_name = t["artists"][0].get("name")
                    if art_name and art_name not in top_artists:
                        top_artists.append(art_name)
            # Polite delay to respect rate limits
            time.sleep(0.05)
        avg_pop = round(sum(all_track_pops) / len(all_track_pops), 1) if all_track_pops else 0.0
        top_3 = ", ".join(top_artists[:3]) if top_artists else "N/A"
        genre_data.append({
            "Main_Genre": main_genre,
            "Subgenres": subgenres,
            "Popularity Index": total_momentum,
            "Avg Track Popularity": avg_pop,
            "Top 3 Artists": top_3,
        })

    df = pd.DataFrame(genre_data)
    if not df.empty:
        df = df.sort_values(by="Popularity Index", ascending=False).reset_index(drop=True)
        df.index += 1
        df["Rank"] = df.index
    return df

# -------------------------
# Fetch top artists helper
# -------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_top_10_artists(subgenre_key: str) -> List[Dict[str, Any]]:
    if not sp:
        return []
    res = safe_search(subgenre_key, type="artist", limit=10)
    items = res.get("artists", {}).get("items", []) if res else []
    artist_report = []
    for art in items:
        artist_report.append({
            "Artist Name": art.get("name", "Unknown Artist"),
            "Total Followers": art.get("followers", {}).get("total", 0),
            "Popularity Index": art.get("popularity", 0),
            "Spotify Profile": art.get("external_urls", {}).get("spotify", "#"),
        })
    return sorted(artist_report, key=lambda x: x["Popularity Index"], reverse=True)

# -------------------------
# Global top 50 subgenres (expensive) — only run on-demand
# -------------------------
@st.cache_data(ttl=86400, show_spinner=False)
def get_top_50_subgenres_global() -> pd.DataFrame:
    if not sp:
        return pd.DataFrame()

    results = []
    for sub in ALL_SUBGENRES:
        best_country = "Unknown"
        highest_score = -1
        sample_artist = "N/A"
        for c_name, c_code in country_dict.items():
            res = safe_search(sub, type="track", limit=3, market=c_code)
            tracks = res.get("tracks", {}).get("items", []) if res else []
            if tracks:
                score = sum(t.get("popularity", 0) for t in tracks)
                if score > highest_score:
                    highest_score = score
                    best_country = c_name
                if sample_artist == "N/A" and tracks[0].get("artists"):
                    sample_artist = tracks[0]["artists"][0].get("name", "N/A")
            time.sleep(0.03)
        results.append({
            "Subgenre": sub.title(),
            "Stream Score (Popularity Index)": highest_score,
            "Most Popular Country": best_country,
            "Lead Artist Sample": sample_artist,
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="Stream Score (Popularity Index)", ascending=False).reset_index(drop=True)
        df = df.head(50)
        df.index += 1
        df["Rank"] = df.index
    return df

# -------------------------
# UI: Tabs
# -------------------------
tab1, tab2 = st.tabs(["Top Genres", "Top 50 Subgenres"])

with tab1:
    col_control, _ = st.columns([1, 2])
    with col_control:
        selected_country_label = st.selectbox("", list(country_dict.keys()))
        country_code = country_dict[selected_country_label]

    st.markdown("### 📈 Genre Momentum Leaderboard — " + selected_country_label)
    st.caption("Use Quick Preview for a fast approximate leaderboard or Load Full Leaderboard for a thorough scan (slower).")

    # Buttons to control fetching
    btn_quick = st.button("Quick Preview (fast)")
    btn_full = st.button("Load Full Leaderboard (slower)")

    # For immediate fast UI we render the quick cached preview if available; otherwise instruct user to click
    df_preview = None
    if "leaderboard_quick" not in st.session_state:
        # Do not block rendering — show hint instead of fetching automatically
        st.info("Click 'Quick Preview' to fetch lightweight telemetry (fast).")
    else:
        df_preview = st.session_state.get("leaderboard_quick")

    if btn_quick:
        with st.spinner("Fetching quick leaderboard..."):
            df_preview = get_genre_leaderboard_quick(country_code)
            st.session_state["leaderboard_quick"] = df_preview

    if btn_full:
        with st.spinner("Fetching full leaderboard (may take a minute)..."):
            df_full = get_genre_leaderboard_full(country_code)
            st.session_state["leaderboard_full"] = df_full
            df_preview = df_full

    if df_preview is not None and not df_preview.empty:
        # Render rows
        h1, h2, h3, h4, h5 = st.columns([0.8, 2.5, 2.5, 2.0, 3.5])
        h1.markdown("**RANK**")
        h2.markdown("**GENRE**")
        h3.markdown("**POPULARITY INDEX**")
        h4.markdown("**AVG SCORE**")
        h5.markdown("**TOP 3 ARTISTS**")
        st.markdown("---")

        for _, row in df_preview.iterrows():
            rank_num = row["Rank"]
            main_g = row["Main_Genre"]
            pop_idx = row["Popularity Index"]
            avg_pop = row["Avg Track Popularity"]
            top_3 = row["Top 3 Artists"]
            subs = row["Subgenres"]

            c1, c2, c3, c4, c5 = st.columns([0.8, 2.5, 2.5, 2.0, 3.5])
            c1.markdown(f"### **#{rank_num}**")
            c2.markdown(f"**{main_g}**")
            c3.progress(min(pop_idx / 2500, 1.0), text=f"{pop_idx} pts")
            c4.markdown(f"**{avg_pop}** / 100")
            c5.caption(top_3)

            with st.expander(f"🔍 Drill into `{main_g}` Sub-genres & Roster"):
                st.write(f"#### Sub-genres in `{main_g}`")
                for sub in subs:
                    with st.expander(f"🎵 Sub-genre: {sub.title()}"):
                        artist_data = fetch_top_10_artists(sub)
                        df_artists = pd.DataFrame(artist_data)
                        if not df_artists.empty:
                            st.write(f"##### Top 10 Artists in `{sub.title()}`")
                            st.dataframe(df_artists, use_container_width=True, hide_index=True)
                        else:
                            st.warning(f"No telemetry retrieved for {sub}.")

            st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.05);'>", unsafe_allow_html=True)
    else:
        st.info("No leaderboard loaded. Use the buttons above to fetch a Quick Preview or a Full Leaderboard.")

with tab2:
    st.markdown("### 🌐 Global Top Subgenres Leaderboard")
    st.caption("This global scan is expensive — click Start Global Scan to run it (on-demand).")
    btn_global = st.button("Start Global Scan (expensive)")

    if btn_global:
        with st.spinner("Running global scan... this may take several minutes depending on rate limits."):
            df_top50 = get_top_50_subgenres_global()
            st.session_state["df_top50"] = df_top50

    df_top50 = st.session_state.get("df_top50")
    if df_top50 is not None and not df_top50.empty:
        st.dataframe(
            df_top50[[
                "Rank",
                "Subgenre",
                "Stream Score (Popularity Index)",
                "Most Popular Country",
                "Lead Artist Sample",
            ]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No global data yet. Click Start Global Scan to begin an on-demand run.")

# -------------------------
# Helpful footer
# -------------------------
st.markdown("---")
st.caption("Tip: On Streamlit Cloud set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET under Settings → Secrets. Locally export them as environment variables before running.")
