import os
import time
import pandas as pd
import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.cache_handler import MemoryCacheHandler

# File Paths
FAVICON_PATH = "Favicon.png"
LOGO_PATH = "logo.png"

# Page Setup
st.set_page_config(
    page_title="PULSR",
    page_icon=FAVICON_PATH if os.path.exists(FAVICON_PATH) else "🎲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
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

    /* ---------------------------------------------------
       🌟 SINGLE CSS SPINNER & 10% BLUR OVERLAY
       --------------------------------------------------- */
    [data-testid="stSpinner"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        background: rgba(10, 13, 20, 0.25) !important;
        backdrop-filter: blur(3px) !important;
        -webkit-backdrop-filter: blur(3px) !important;
        z-index: 999999 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    [data-testid="stSpinner"] > * {
        display: none !important;
    }

    [data-testid="stSpinner"]::before {
        content: "" !important;
        display: block !important;
        width: 52px !important;
        height: 52px !important;
        border: 4px solid rgba(255, 255, 255, 0.15) !important;
        border-top: 4px solid #10B981 !important;
        border-radius: 50% !important;
        animation: pulsr-single-spin 0.75s linear infinite !important;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.3) !important;
    }

    @keyframes pulsr-single-spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 🖼️ BRANDING
# ---------------------------------------------------------
if os.path.exists(LOGO_PATH):
    st.logo(LOGO_PATH)

if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=160)

st.markdown("---")

# Spotify API Credentials
CLIENT_ID = "B93af62ec78b41418101daec048d46f8"
CLIENT_SECRET = "523cf24ac8a047b38ea538300ed245a1"


@st.cache_resource
def get_spotify_client():
    try:
        # Use MemoryCacheHandler to prevent stale token file locks
        auth_manager = SpotifyClientCredentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            cache_handler=MemoryCacheHandler()
        )
        return spotipy.Spotify(
            auth_manager=auth_manager, requests_timeout=10
        )
    except Exception as e:
        st.error(f"⚠️ Spotify Auth Error: {e}")
        return None


sp = get_spotify_client()

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
    "Hip-Hop & Rap": [
        "uk drill",
        "pluggnb",
        "melodic rap",
        "underground hip hop",
        "trap",
        "phonk",
    ],
    "Pop": ["dance pop", "alt-z", "bedroom pop", "synthpop", "indie pop"],
    "Electronic & Dance": [
        "house",
        "amapiano",
        "gqom",
        "hyperpop",
        "drum and bass",
        "techno",
    ],
    "Afrobeats & Global": ["afrobeats", "afropop", "azontobeats", "highlife"],
    "Alternative & Rock": [
        "shoegaze",
        "indie rock",
        "post-punk",
        "grungegaze",
    ],
    "R&B & Soul": ["r&b", "neo soul", "alternative r&b", "trap soul"],
}

ALL_SUBGENRES = [sub for subs in GENRE_TAXONOMY.values() for sub in subs]


# ---------------------------------------------------------
# Helper Functions (Rate-Limit Safe Sequential Fetching)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_genre_leaderboard(market):
    if not sp:
        return pd.DataFrame()

    genre_data = []

    for main_genre, subgenres in GENRE_TAXONOMY.items():
        total_momentum = 0
        all_track_pops = []
        top_artists = []

        for sub in subgenres:
            try:
                res = sp.search(q=sub, type="track", limit=5, market=market)
                tracks = res.get("tracks", {}).get("items", []) if res else []
                for t in tracks:
                    p = t.get("popularity", 0)
                    all_track_pops.append(p)
                    total_momentum += p
                    if t.get("artists"):
                        art_name = t["artists"][0].get("name")
                        if art_name and art_name not in top_artists:
                            top_artists.append(art_name)
                # Polite delay to respect Spotify rate limits
                time.sleep(0.05)
            except Exception:
                pass

        avg_pop = (
            round(sum(all_track_pops) / len(all_track_pops), 1)
            if all_track_pops
            else 0.0
        )
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
        df = df.sort_values(by="Popularity Index", ascending=False).reset_index(
            drop=True
        )
        df.index += 1
        df["Rank"] = df.index
    return df


@st.cache_data(ttl=3600)
def fetch_top_10_artists(subgenre_key):
    if not sp:
        return []

    try:
        res = sp.search(q=subgenre_key, type="artist", limit=10)
        items = res.get("artists", {}).get("items", []) if res else []

        artist_report = []
        for art in items:
            art_name = art.get("name", "Unknown Artist")
            art_url = art.get("external_urls", {}).get("spotify", "#")
            followers = art.get("followers", {}).get("total", 0)
            popularity = art.get("popularity", 0)

            artist_report.append({
                "Artist Name": art_name,
                "Total Followers": followers,
                "Popularity Index": popularity,
                "Spotify Profile": art_url,
            })

        return sorted(
            artist_report, key=lambda x: x["Popularity Index"], reverse=True
        )
    except Exception:
        return []


@st.cache_data(ttl=3600)
def get_top_50_subgenres_global():
    if not sp:
        return pd.DataFrame()

    results = []
    for sub in ALL_SUBGENRES:
        best_country = "Unknown"
        highest_score = -1
        sample_artist = "N/A"

        for c_name, c_code in country_dict.items():
            try:
                res = sp.search(q=sub, type="track", limit=3, market=c_code)
                tracks = res.get("tracks", {}).get("items", []) if res else []
                if tracks:
                    score = sum(t.get("popularity", 0) for t in tracks)
                    if score > highest_score:
                        highest_score = score
                        best_country = c_name
                    if sample_artist == "N/A" and tracks[0].get("artists"):
                        sample_artist = tracks[0]["artists"][0].get("name", "N/A")
                time.sleep(0.02)
            except Exception:
                pass

        results.append({
            "Subgenre": sub.title(),
            "Stream Score (Popularity Index)": highest_score,
            "Most Popular Country": best_country,
            "Lead Artist Sample": sample_artist,
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(
            by="Stream Score (Popularity Index)", ascending=False
        ).reset_index(drop=True)
        df = df.head(50)
        df.index += 1
        df["Rank"] = df.index
    return df


# ---------------------------------------------------------
# 🗂️ NAVIGATION TABS
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["Top Genres", "Top 50 Subgenres"])

# Tab 1: Top Genres
with tab1:
    col_control, _ = st.columns([1, 2])
    with col_control:
        selected_country_label = st.selectbox("", list(country_dict.keys()))
        country_code = country_dict[selected_country_label]

    with st.spinner("Loading..."):
        df_leaderboard = get_genre_leaderboard(country_code)

    st.markdown(f"### 📈 Genre Momentum Leaderboard — {selected_country_label}")
    st.caption(
        "💡 Click any genre row to expand its sub-genres ➔ Click a sub-genre to"
        " reveal its Top 10 Artists"
    )

    h1, h2, h3, h4, h5 = st.columns([0.8, 2.5, 2.5, 2.0, 3.5])
    h1.markdown("**RANK**")
    h2.markdown("**GENRE**")
    h3.markdown("**POPULARITY INDEX**")
    h4.markdown("**AVG SCORE**")
    h5.markdown("**TOP 3 ARTISTS**")
    st.markdown("---")

    if not df_leaderboard.empty:
        for _, row in df_leaderboard.iterrows():
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
                            st.write(
                                f"##### Top 10 Artists in `{sub.title()}`"
                            )
                            st.dataframe(
                                df_artists,
                                column_config={
                                    "Artist Name": st.column_config.TextColumn(
                                        "Artist Name"
                                    ),
                                    "Total Followers": (
                                        st.column_config.NumberColumn(
                                            "Total Followers", format="%d 👤"
                                        )
                                    ),
                                    "Popularity Index": (
                                        st.column_config.ProgressColumn(
                                            "Popularity Index",
                                            min_value=0,
                                            max_value=100,
                                            format="%d/100",
                                        )
                                    ),
                                    "Spotify Profile": (
                                        st.column_config.LinkColumn(
                                            "Spotify Link",
                                            display_text="Open Profile 🔗",
                                        )
                                    ),
                                },
                                use_container_width=True,
                                hide_index=True,
                            )
                        else:
                            st.warning(f"No telemetry retrieved for {sub}.")

            st.markdown(
                "<hr style='margin: 8px 0; border-color:"
                " rgba(255,255,255,0.05);'>",
                unsafe_allow_html=True,
            )
    else:
        st.warning(
            "⚠️ Spotify rate limit hit or bad credentials. Please clear cache"
            " (`☰ -> Clear cache`) or paste a fresh Client Secret."
        )

# Tab 2: Global Top 50 Subgenres
with tab2:
    st.markdown("### 🌐 Global Top Subgenres Leaderboard")
    st.caption(
        "Unfiltered global scan ranking subgenres by stream popularity index"
        " and identifying their primary market stronghold."
    )

    with st.spinner("Loading..."):
        df_top50 = get_top_50_subgenres_global()

    if not df_top50.empty:
        st.dataframe(
            df_top50[[
                "Rank",
                "Subgenre",
                "Stream Score (Popularity Index)",
                "Most Popular Country",
                "Lead Artist Sample",
            ]],
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", format="#%d"),
                "Subgenre": st.column_config.TextColumn("Subgenre Name"),
                "Stream Score (Popularity Index)": (
                    st.column_config.ProgressColumn(
                        "Stream Score",
                        min_value=0,
                        max_value=500,
                        format="%d pts",
                    )
                ),
                "Most Popular Country": st.column_config.TextColumn(
                    "Market Stronghold 🌐"
                ),
                "Lead Artist Sample": st.column_config.TextColumn(
                    "Notable Artist"
                ),
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("⚠️ No global data retrieved. Clear Streamlit cache to retry.")