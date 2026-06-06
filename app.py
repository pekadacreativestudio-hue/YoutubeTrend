"""
YouTube Top Program Analysis — Web Interface
Hardcord Ad Targeting Tool for 6-Second Commercial Placements

Tab 1: Program Comparison (channel -> programs -> compare -> ad placement)
Tab 2: Trending Channels (region-wide rankings)
"""

import os
import io
import re
from collections import defaultdict
from datetime import datetime, date, timedelta
from math import log10

import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_api_keys():
    keys = []
    for name in ("YOUTUBE_API_KEY", "YOUTUBE_API_KEY2", "YOUTUBE_API_KEY3"):
        val = st.secrets.get(name, os.getenv(name, "")) if hasattr(st, "secrets") else os.getenv(name, "")
        if val and val not in keys:
            keys.append(val)
    return keys

API_KEYS = _load_api_keys()
YOUTUBE_API_KEY = API_KEYS[0] if API_KEYS else ""
YT_API_BASE = "https://www.googleapis.com/youtube/v3"

CATEGORY_NAMES = {
    "": "All Categories",
    "24": "Entertainment",
    "25": "News & Politics",
    "10": "Music",
    "17": "Sports",
    "22": "People & Blogs",
    "23": "Comedy",
    "20": "Gaming",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "1":  "Film & Animation",
}

REGIONS = {
    "Sri Lanka 🇱🇰": "LK",
    "India 🇮🇳": "IN",
    "United States 🇺🇸": "US",
    "United Kingdom 🇬🇧": "GB",
    "Australia 🇦🇺": "AU",
    "Pakistan 🇵🇰": "PK",
    "Bangladesh 🇧🇩": "BD",
}

# ---------------------------------------------------------------------------
# Curated Sri Lankan channels — verified IDs, grouped by type
# ---------------------------------------------------------------------------

SRI_LANKA_LOCAL_CHANNELS = {
    # ── TV / Broadcast Channels ──────────────────────────────────────────
    "TV Derana":              ("UCRDDfbYPHX_GUJ4lcQYTc8A", "📺 TV Channel"),
    "Hiru TV":                ("UCOtYyt7W5PmPnwQjWWF_Z-Q", "📺 TV Channel"),
    "Sirasa TV":              ("UCn0XmAUFv6d2tofMFEesSNw", "📺 TV Channel"),
    "Swarnavahini TV":        ("UCaIc6SgS90ud_RgMSC6hW_w", "📺 TV Channel"),
    "Swarnavahini Digital":   ("UCAH7R88V7gz7RqJv78nNOzg", "📺 TV Channel"),
    "ITN Network":            ("UCAGQUfHzdsgxJ1pq2XDS2TQ", "📺 TV Channel"),
    "Sri Lanka Rupavahini":   ("UCT83ymyAGm7Gnk_4ifxjxIA", "📺 TV Channel"),
    "TV 1 Sri Lanka":         ("UCoQXpCWew0Q3qz6buZYOAFg", "📺 TV Channel"),
    "Shakthi TV":             ("UCjm7vbOwssao7Bhm9wX3-bw", "📺 TV Channel"),
    "TNL Tv":                 ("UCgFK94EtfymL9AvhxQucaTw", "📺 TV Channel"),
    "Siyatha TV":             ("UCc30sTBdN9LRSxEuHaXV_bQ", "📺 TV Channel"),
    "Ada Derana (News)":      ("UCCK3OZi788Ok44K97WAhLKQ", "📺 TV Channel"),
    # ── Content Creators ─────────────────────────────────────────────────
    "Chanux Bro":             ("UCETxOvOv9_44-CUzsPlzyxQ", "🎥 Creator"),
    "Lochi":                  ("UCYFn7BOOlmL21iNJ6q5IDfg", "🎥 Creator"),
    "Janai Priyai":           ("UCfYQW_0xEVwKfePgWRxTYhg", "🎥 Creator"),
    "Ratta":                  ("UCJbxRq_IlWyzvB9KK0Mrs8A", "🎥 Creator"),
    "Wasthi Productions":     ("UCMQYRNX1Fg-HJ8Ey7Z3WPrA", "🎥 Creator"),
    "Mokka Commentry":        ("UC3Y7OyuS9jNdZy3ZadrAbWQ", "🎥 Creator"),
    "Sarith and Surith":      ("UCLEa0khmFIbpyjFqb90RBOA", "🎥 Creator"),
    "Roshan Fernando":        ("UCNbhBaSxzjD4Yr7bRVKiWaw", "🎥 Creator"),
    "Dhanith Sri":            ("UCyCNFZZpmyZQEgtar98I8tA", "🎥 Creator"),
    "DilShan L Silva":        ("UC5A7foGvdlddb0b6iHaqUBg", "🎥 Creator"),
    "Thiwanka Dilshan":       ("UCmr1WFY6P4PCmPlbic02iRA", "🎥 Creator"),
    "Siril Ayya":             ("UCms4dlxLWI7SZNWPTxzDr-A", "🎥 Creator"),
    "Vini Productions":       ("UCGkzF25IZBE1SF9ykM64xEA", "🎥 Creator"),
    # ── Music Artists ────────────────────────────────────────────────────
    "IRAJ":                   ("UCNO4dUilYfOikKlcbk5uBTg", "🎵 Music"),
    "Bathiya N Santhush":     ("UCvivK4AwTrkPBnmrObTFxaQ", "🎵 Music"),
    "WAYO":                   ("UCO_gVqYTbIRbBV6enNVov3Q", "🎵 Music"),
    "UMARIA":                 ("UCWYXLMuL0m10w53wnMaUf3g", "🎵 Music"),
    "Ridma Weerawardena":     ("UC1mrGdQz5KP3fnm4J9gRx7A", "🎵 Music"),
    "Dinuli Damsandi":        ("UCU9IoKqQvxERkoxwB-L9VwQ", "🎵 Music"),
    "Mihiran":                ("UC6wvfVVgmnsMUlhfYCv64Gw", "🎵 Music"),
    "Senanga Dissanayake":    ("UCQwGtvsdORhNh5l0F5fZf0Q", "🎵 Music"),
    "Sirasa Lakshapathi":     ("UCfnZtEDnl84njUQgtF186cA", "🎵 Music"),
    "SANUKA":                 ("UCdvasaXV8gpoJOe-5BDI2gA", "🎵 Music"),
    "Kanchana Anuradhi":      ("UCNdPhHla8uFW4Ah6jhGy6bg", "🎵 Music"),
    "Yohani":                 ("UCh9qXeL8eP3Txra2908xksg", "🎵 Music"),
    "Raini Charuka":          ("UCdpzqsUZde5hl1jyFKhBJkw", "🎵 Music"),
    "Kaizer Kaiz":            ("UCGq0n1SMca7vFN7FRvtlApw", "🎵 Music"),
    # ── News Channels ────────────────────────────────────────────────────
    "Newsfirst Sri Lanka":    ("UCgnFSj7jQffD5V5m05j4dPw", "📰 News"),
    "Hiru News":              ("UCckltLEhFLv8Xz_lQhYfwmg", "📰 News"),
    "Ada Derana News":        ("UCW_rA_jb-_vbZtU4cTpnT5Q", "📰 News"),
    # ── Reality / Talent Shows ───────────────────────────────────────────
    "Hiru Star":              ("UCcbOsE5_4LEjtQi8X2PFxDw", "🎤 Reality"),
    "The Voice Sri Lanka":    ("UCmqflTSJ6911aCrnaWIXxsA", "🎤 Reality"),
    # ── Radio Channels ───────────────────────────────────────────────────
    "Hiru FM":                ("UC8AMm5NxsMra2cjlewCb8QA", "📻 Radio"),
    "Y FM":                   ("UCsExZudI-3Bfi2ubAdwcgHw", "📻 Radio"),
    # ── Gaming Channels ──────────────────────────────────────────────────
    "Master Brothers FF":     ("UCnLDg6H44ShnTB3TWLw_R0A", "🎮 Gaming"),
    "Gaming With Kaniya":     ("UCAYGhFThlHe-3ugwJaUE0sA", "🎮 Gaming"),
    "DLP Gaming":             ("UC0-UFP1d6OeVtl2VXYSquIA", "🎮 Gaming"),
    "ManiYa Streams":         ("UCo0bp6-iNDJmExq6kp6PYcg", "🎮 Gaming"),
    "Allen K S L":            ("UCWrJW5qgCKGpYAxyMCp5Hxg", "🎮 Gaming"),
    # ── Vlog / Travel ────────────────────────────────────────────────────
    "Travel With Chatura":    ("UCwXfRdTtVeVnXXF4poaYw0Q", "🎥 Creator"),
    # ── Expanded set ─────────────────────────────────────────────────────
    "ITN Sri Lanka":          ("UCQTcNhAZidy1i9wwmdgf2Lw", "📰 News"),
    "Sinhala Fairy Tales":    ("UC4j_fc1OaX2Up6UtizVmNKQ", "🧒 Kids"),
    "SL Animation Cartoon":   ("UCVOZ_y2K3fnUOmuMtnxLk1Q", "🧒 Kids"),
    "Lakai Sikai":            ("UCkuoWSLw-SNu8dvVCU0MjMQ", "🎥 Creator"),
    "Rj Chandru Menaka":      ("UC9Slp55-nJIx-q1g_TJEY3Q", "🎥 Creator"),
    "Meanwhile in SL":        ("UC5IDHX2sg9Hg_FPkXGUj_gw", "🎥 Creator"),
    "Heshan Vlog":            ("UCiOEgWwAKbfrVb795hqQc9A", "🎥 Creator"),
    "MCC Prime":              ("UC5R7F4Mw_ZV1c4tYe4UKLIg", "🎥 Creator"),
    "ElaKiri":                ("UC-RZIjGh-BMEfzY1gb3XCCg", "🎥 Creator"),
    "Dilip Kanakarathna":     ("UCOcVy09yuWmrbZnm_flr18A", "🎥 Creator"),
    "Sri Lanka Cricket Vlog": ("UCiaD_MM6omMaxjTANcNPIeQ", "🎥 Creator"),
    "SK VLOG":                ("UCR4TNhT3Bers8lIfmIucY7Q", "🎥 Creator"),
    "SL VLOG":                ("UCo51bjbXU1YxOkv7EIlTi1g", "🎥 Creator"),
    "Thamath Adare Nathnam":  ("UCxPInZUzPis7B5UWJN3ZXLA", "🎥 Creator"),
    "දෙයියා (Deyya)":          ("UC4c_aCuQ9hfqHQJxdwRHlRA", "🎥 Creator"),
    "Ape kama TV":            ("UCaPEESxxEokUiwxEJqD2U7w", "🎥 Creator"),
    "iCrazeTech සිංහල":        ("UCHas-PlfQmgkcJK_JwLn_AA", "💻 Tech"),
    "Sashika Nisansala":      ("UCFkXBw7ilY4pr7noFVK4S8Q", "🎵 Music"),
    "Mihindu Ariyaratne":     ("UCOpRwp8jY6lAZRcTB_FbTuA", "🎵 Music"),
    "Dushyanth Weeraman":     ("UClEUyN3C6oIAMOkc8TEN8Xg", "🎵 Music"),
    "Torana Video Movies":    ("UCOiMY00_ZLijPF6InrCl0TA", "🎵 Music"),
    "Ruwan Hettiarachchi":    ("UCsfvxX_dsfWS0Kker_HefQg", "🎵 Music"),
    "Samitha Mudunkotuwa":    ("UCM575NP1NdR9SvgEtrcgfTg", "🎵 Music"),
    "Ravi Royster":           ("UCZKBrRLW4o3J92VS3xSSDgw", "🎵 Music"),
    "Siyatha FM":             ("UCHhk9EHspPZejY9PnR1PLVg", "📻 Radio"),
    # ── Expanded set 2 (to 100) ──────────────────────────────────────────
    "Sri Lanka Cricket":      ("UCJA-NQ4MtcRIog66wziD8fA", "⚽ Sports"),
    "Apé Amma":               ("UC4UaWbUUwVvCxWNqhb4f16Q", "🎥 Creator"),
    "Traditional Me":         ("UCfCw8GGyGpXmtxDTNJ7J5VA", "🎥 Creator"),
    "Poorna - Nature Girl":   ("UCtVDQNGBmS8DTP5fPzM_GmQ", "🎥 Creator"),
    "Blok & Dino":            ("UCTcATaNqlaCF4zkZp29BJRQ", "🎥 Creator"),
    "Village Kitchen":        ("UC3DxQF4wzjUjRlsLZxxkOLA", "🎥 Creator"),
    "Oshan Liyanage Dance":   ("UCwrJnrHM2qRjjiSVk1nlx4Q", "🎥 Creator"),
    "Raamuwa":                ("UCUFYmdx-eTBO0-s2qTG6cDw", "🎥 Creator"),
    "Travel With Wife":       ("UCiJfplrc7idtWYpDsI325yQ", "🎥 Creator"),
    "Cosmo Beauty Studio":    ("UCsF6mvxEdYLDrYNOj4aykPw", "🎥 Creator"),
    "VIDU":                   ("UCgPL5V2N_KEDSyWvMwHt2nw", "🎥 Creator"),
    "Travel Today":           ("UCEHs7ymn9hxSJMHLlcFLj0w", "🎥 Creator"),
    "Trip Pisso":             ("UC7hqTC-ChL-_PUKhctTt50A", "🎥 Creator"),
    "Jayspot Productions":    ("UC3CpNSEEj5KWOeaJ00ZHKcA", "🎥 Creator"),
    "RaMoD with COOL STEPS":  ("UCMBCoqwqNVVKwGDMcOraXBA", "🎥 Creator"),
    "beauty with sumu":       ("UCa151heZf71ui28zh5OnhsA", "🎥 Creator"),
    "The Sailor":             ("UCTi36zetYBtNR4MW2zSmPjQ", "🎥 Creator"),
    "Magic Compass":          ("UCJL33sl0UYzAgAc0g3Yq5LQ", "🎥 Creator"),
    "The Voice Kids LK":      ("UCtBhlCYSLlz2TO9hK93micg", "🎤 Reality"),
    "Desawana Remix":         ("UCnGcBhZNMIm490OrdkI0JIg", "🎵 Music"),
    "Mohan Palliyaguru":      ("UC7Gw2ithc7T3ZvGA4AOgOsg", "🎵 Music"),
    "Science With Ruchira":   ("UCR5y9OV23c0jJ4RGwDvGnLw", "💻 Tech"),
    "B I L L A":              ("UC1dfhQyj962rwYPVLi3OHLg", "🎮 Gaming"),
}

# ---------------------------------------------------------------------------
# Page config & modern dark/green theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="YouTube Program Analyzer — Hardcord Targeting",
    page_icon="📺",
    layout="wide",
)

st.markdown("""
<style>
    /* ═══════════════════════════════════════════════════════════
       GOOGLE FONTS
    ═══════════════════════════════════════════════════════════ */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ═══════════════════════════════════════════════════════════
       BASE — clean white/light-grey
    ═══════════════════════════════════════════════════════════ */
    html, body, [data-testid="stApp"],
    [data-testid="stAppViewContainer"], .main, .block-container {
        background-color: #f4f5f7 !important;
        color: #1a1a2e !important;
        font-family: 'Inter', sans-serif !important;
    }
    [data-testid="block-container"] {
        padding-top: 0.8rem !important;
        max-width: 1280px !important;
    }
    [data-testid="stSidebar"],
    [data-testid="stSidebarContent"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }

    /* ═══════════════════════════════════════════════════════════
       HEADER BANNER — YouTube brand red gradient
    ═══════════════════════════════════════════════════════════ */
    .yt-header {
        background: linear-gradient(135deg, #FF0000 0%, #cc0000 40%, #990000 100%);
        border-radius: 16px; padding: 0; margin-bottom: 1.4rem;
        box-shadow: 0 8px 32px rgba(255,0,0,0.25);
        overflow: hidden; position: relative;
    }
    .yt-header-inner {
        display: flex; align-items: center; justify-content: center;
        gap: 20px; padding: 1.6rem 2rem;
    }
    .yt-logo-wrap {
        background: #ffffff; border-radius: 12px;
        padding: 8px 12px 6px; display: flex; align-items: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        flex-shrink: 0;
    }
    .yt-logo-wrap svg { display: block; }
    .yt-header-text { text-align: left; }
    .yt-header-text h1 {
        color: #ffffff !important; margin: 0;
        font-size: 1.85rem; font-weight: 800; letter-spacing: -0.5px;
        line-height: 1.1; text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    .yt-header-text p {
        color: rgba(255,255,255,0.88) !important; margin: 0.3rem 0 0;
        font-size: 0.9rem; font-weight: 400;
    }
    /* decorative circles */
    .yt-header::before {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 180px; height: 180px; border-radius: 50%;
        background: rgba(255,255,255,0.08);
    }
    .yt-header::after {
        content: ''; position: absolute; bottom: -30px; left: 60px;
        width: 120px; height: 120px; border-radius: 50%;
        background: rgba(255,255,255,0.06);
    }

    /* ═══════════════════════════════════════════════════════════
       SECTION HEADERS
    ═══════════════════════════════════════════════════════════ */
    .section-header {
        display: flex; align-items: center; gap: 10px;
        margin: 1.6rem 0 0.7rem; padding: 0;
    }
    .step-badge {
        background: linear-gradient(135deg, #FF0000, #cc0000);
        color: #fff; border-radius: 50%;
        width: 30px; height: 30px; display: inline-flex; align-items: center;
        justify-content: center; font-weight: 900; font-size: 0.82rem;
        flex-shrink: 0; box-shadow: 0 2px 6px rgba(255,0,0,0.35);
    }
    .section-title {
        color: #1a1a2e !important; font-size: 1.1rem;
        font-weight: 700; margin: 0;
    }

    /* ═══════════════════════════════════════════════════════════
       METRIC CARDS
    ═══════════════════════════════════════════════════════════ */
    .metric-card {
        background: #ffffff; border: 1px solid #e2e8f0;
        border-top: 3px solid #FF0000;
        border-radius: 12px; padding: 1.1rem 0.8rem; text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s, transform 0.2s;
    }
    .metric-card:hover {
        box-shadow: 0 6px 20px rgba(255,0,0,0.12);
        transform: translateY(-2px);
    }
    .metric-card h2 {
        color: #FF0000 !important; margin: 0;
        font-size: 1.75rem; font-weight: 800;
    }
    .metric-card p {
        color: #64748b !important; margin: 0.2rem 0 0;
        font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600;
    }

    /* ═══════════════════════════════════════════════════════════
       PROGRAM QUEUE CARDS
    ═══════════════════════════════════════════════════════════ */
    .prog-card {
        background: #fff5f5; border: 1px solid #fed7d7;
        border-left: 4px solid #FF0000;
        border-radius: 8px; padding: 0.65rem 1rem; margin-bottom: 0.4rem;
        color: #1a1a2e !important; font-size: 0.88rem;
        box-shadow: 0 1px 4px rgba(255,0,0,0.08);
    }

    /* ═══════════════════════════════════════════════════════════
       BUTTONS
    ═══════════════════════════════════════════════════════════ */
    .stButton > button {
        background: linear-gradient(135deg, #FF0000, #cc0000) !important;
        color: #ffffff !important; border: none !important;
        border-radius: 8px !important; padding: 0.5rem 1.4rem !important;
        font-weight: 700 !important; font-size: 0.9rem !important;
        letter-spacing: 0.3px; box-shadow: 0 3px 10px rgba(255,0,0,0.3) !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #e60000, #b30000) !important;
        box-shadow: 0 5px 16px rgba(255,0,0,0.45) !important;
        transform: translateY(-1px);
    }

    /* ═══════════════════════════════════════════════════════════
       TABS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stTabs"] [role="tablist"] {
        background: #ffffff !important;
        border-bottom: 2px solid #e2e8f0 !important;
        border-radius: 10px 10px 0 0;
        padding: 0 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    [data-testid="stTabs"] button[role="tab"] {
        color: #64748b !important; font-weight: 600 !important;
        font-size: 0.95rem !important; padding: 0.75rem 1.5rem !important;
        border: none !important; border-bottom: 3px solid transparent !important;
        background: transparent !important;
        transition: all 0.2s !important;
    }
    [data-testid="stTabs"] button[role="tab"]:hover {
        color: #FF0000 !important; background: #fff5f5 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #FF0000 !important; border-bottom: 3px solid #FF0000 !important;
        background: #fff5f5 !important; font-weight: 700 !important;
    }

    /* ═══════════════════════════════════════════════════════════
       FORM CONTROLS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stMultiSelect"] > div > div,
    [data-testid="stDateInput"] input {
        background-color: #ffffff !important;
        border: 1.5px solid #e2e8f0 !important;
        color: #1a1a2e !important; border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    }
    [data-testid="stSelectbox"] > div > div:focus-within,
    [data-testid="stMultiSelect"] > div > div:focus-within {
        border-color: #FF0000 !important;
        box-shadow: 0 0 0 3px rgba(255,0,0,0.12) !important;
    }
    [data-baseweb="popover"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12) !important;
        border-radius: 10px !important;
    }
    [data-baseweb="option"]:hover {
        background: #fff5f5 !important; color: #FF0000 !important;
    }
    [data-baseweb="option"][aria-selected="true"] {
        background: #fff0f0 !important; color: #FF0000 !important;
    }
    /* Multiselect tags */
    [data-baseweb="tag"] {
        background: #fff0f0 !important; border-color: #fca5a5 !important;
        color: #cc0000 !important; border-radius: 6px !important;
        font-weight: 600 !important;
    }
    /* Labels */
    [data-testid="stWidgetLabel"] p {
        color: #475569 !important; font-size: 0.8rem !important;
        font-weight: 600 !important; text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }

    /* ═══════════════════════════════════════════════════════════
       DATAFRAME
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDataFrame"] {
        border-radius: 12px !important; overflow: hidden !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
    }

    /* ═══════════════════════════════════════════════════════════
       EXPANDER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stExpander"] {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stExpander"] summary {
        color: #334155 !important; font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover { color: #FF0000 !important; }

    /* ═══════════════════════════════════════════════════════════
       ALERTS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stAlert"] {
        border-radius: 10px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }

    /* ═══════════════════════════════════════════════════════════
       DOWNLOAD BUTTON
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stDownloadButton"] button {
        background: #ffffff !important;
        border: 1.5px solid #FF0000 !important;
        color: #FF0000 !important; border-radius: 8px !important;
        font-weight: 600 !important; transition: all 0.2s !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: #fff0f0 !important;
        box-shadow: 0 3px 10px rgba(255,0,0,0.2) !important;
    }

    /* ═══════════════════════════════════════════════════════════
       DIVIDERS, CAPTIONS, GENERAL TEXT
    ═══════════════════════════════════════════════════════════ */
    hr { border: none !important; border-top: 1.5px solid #e2e8f0 !important; margin: 1.2rem 0 !important; }
    [data-testid="stCaption"] p { color: #94a3b8 !important; font-size: 0.8rem !important; }
    h1,h2,h3,h4,h5,h6 { color: #1a1a2e !important; }
    p, li { color: #334155 !important; }
    a { color: #FF0000 !important; }
    a:hover { color: #cc0000 !important; }
    progress { accent-color: #FF0000 !important; }

    /* ═══════════════════════════════════════════════════════════
       SPINNER
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stSpinner"] > div { border-top-color: #FF0000 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(endpoint, params):
    """GET with automatic failover across all configured API keys on quota (403)."""
    for key in (API_KEYS or [YOUTUBE_API_KEY]):
        params["key"] = key
        resp = requests.get(f"{YT_API_BASE}/{endpoint}", params=params, timeout=30)
        if resp.status_code == 403:
            continue
        resp.raise_for_status()
        return resp.json()
    st.error("⚠️ API quota exceeded on all keys. Try again after midnight US Pacific, "
             "or reduce the date range / scan depth.")
    st.stop()


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))


# ---------------------------------------------------------------------------
# Trending helpers (Tab 2)
# ---------------------------------------------------------------------------

def fetch_trending_videos(region_code, max_results, category_id=None):
    """Fetch YouTube mostPopular chart for a region."""
    videos, next_page_token, remaining = [], None, max_results
    while remaining > 0:
        params = {
            "part": "snippet,statistics", "chart": "mostPopular",
            "regionCode": region_code, "maxResults": min(remaining, 50),
        }
        if category_id:
            params["videoCategoryId"] = category_id
        if next_page_token:
            params["pageToken"] = next_page_token
        data = api_get("videos", params)
        items = data.get("items", [])
        videos.extend(items)
        remaining -= len(items)
        next_page_token = data.get("nextPageToken")
        if not next_page_token or not items:
            break
    return videos


def fetch_channel_details(channel_ids):
    details = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        data = api_get("channels", {"part": "snippet,statistics", "id": ",".join(batch)})
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


def compute_hardcord_score(views, likes, subscribers):
    engagement_rate = (likes / max(views, 1)) * 100
    return round((views / 1_000_000) * engagement_rate * log10(max(subscribers, 1)), 4)


def aggregate_channel_data(videos, channel_details, local_only=False):
    local_ids = {cid for cid, _ in SRI_LANKA_LOCAL_CHANNELS.values()}
    channels = {}
    for video in videos:
        snippet = video.get("snippet", {})
        stats = video.get("statistics", {})
        channel_id = snippet.get("channelId", "")
        if not channel_id:
            continue
        if local_only and channel_id not in local_ids:
            continue
        views = safe_int(stats.get("viewCount"))
        likes = safe_int(stats.get("likeCount"))
        category_name = CATEGORY_NAMES.get(snippet.get("categoryId", ""), "Other")
        if channel_id not in channels:
            ch = channel_details.get(channel_id, {})
            ch_stats = ch.get("statistics", {})
            channels[channel_id] = {
                "channel_name": ch.get("snippet", {}).get("title", snippet.get("channelTitle", "Unknown")),
                "subscribers": safe_int(ch_stats.get("subscriberCount")),
                "category": category_name, "is_local": channel_id in local_ids,
                "total_views": 0, "total_likes": 0, "video_count": 0,
            }
        channels[channel_id]["total_views"] += views
        channels[channel_id]["total_likes"] += likes
        channels[channel_id]["video_count"] += 1

    result = []
    for ch in channels.values():
        score = compute_hardcord_score(ch["total_views"], ch["total_likes"], ch["subscribers"])
        engagement = round((ch["total_likes"] / max(ch["total_views"], 1)) * 100, 2)
        result.append({
            "Rank": 0, "🇱🇰": "✅" if ch["is_local"] else "", "Channel": ch["channel_name"],
            "Category": ch["category"], "Subscribers": ch["subscribers"],
            "Total Views": ch["total_views"], "Engagement %": engagement,
            "Hardcord Score": score, "Trending Videos": ch["video_count"],
        })
    result.sort(key=lambda x: x["Hardcord Score"], reverse=True)
    for i, row in enumerate(result, start=1):
        row["Rank"] = i
    return result


@st.cache_data(show_spinner=False, ttl=3600)
def get_local_channel_trending_stats(days_back):
    """
    For 'Local Channels Only' mode: fetch recent video stats for all curated channels
    within the last `days_back` days and compute Hardcord Score from actual recent views.

    Uses the cheap uploads-playlist approach (playlistItems = 1 quota unit each)
    instead of search.list (100 units each), so the whole scan costs ~100 units
    rather than 10,000. Per-channel errors are skipped gracefully.
    """
    cutoff = (date.today() - timedelta(days=days_back))
    ids = [cid for cid, _ in SRI_LANKA_LOCAL_CHANNELS.values()]

    # One batched call set: snippet (sub count) + contentDetails (uploads playlist)
    details = {}
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        try:
            data = api_get("channels",
                           {"part": "statistics,contentDetails", "id": ",".join(batch)})
        except requests.exceptions.HTTPError:
            continue
        for item in data.get("items", []):
            details[item["id"]] = item

    rows = []
    for ch_name, (cid, ch_type) in SRI_LANKA_LOCAL_CHANNELS.items():
        d = details.get(cid, {})
        ch_stats = d.get("statistics", {})
        subscribers = safe_int(ch_stats.get("subscriberCount"))
        uploads = (d.get("contentDetails", {})
                    .get("relatedPlaylists", {})
                    .get("uploads"))
        if not uploads:
            continue

        # Recent uploads (1 page = 50 newest videos), filter to date window
        try:
            pl = api_get("playlistItems",
                         {"part": "contentDetails", "playlistId": uploads, "maxResults": 50})
        except requests.exceptions.HTTPError:
            continue

        video_ids = []
        for x in pl.get("items", []):
            vp = x["contentDetails"].get("videoPublishedAt", "")[:10]
            if not vp:
                continue
            try:
                vd = datetime.strptime(vp, "%Y-%m-%d").date()
            except ValueError:
                continue
            if vd >= cutoff:
                video_ids.append(x["contentDetails"]["videoId"])
        if not video_ids:
            continue

        total_views, total_likes, count = 0, 0, 0
        for j in range(0, len(video_ids), 50):
            try:
                vid_data = api_get("videos",
                                   {"part": "statistics", "id": ",".join(video_ids[j:j+50])})
            except requests.exceptions.HTTPError:
                continue
            for v in vid_data.get("items", []):
                s = v.get("statistics", {})
                total_views += safe_int(s.get("viewCount"))
                total_likes += safe_int(s.get("likeCount"))
                count += 1

        if count == 0:
            continue

        score = compute_hardcord_score(total_views, total_likes, subscribers)
        engagement = round((total_likes / max(total_views, 1)) * 100, 2)
        rows.append({
            "Rank": 0, "🇱🇰": "✅", "Channel": ch_name,
            "Type": ch_type,
            "Category": ch_type,
            "Subscribers": subscribers,
            "Total Views": total_views,
            "Engagement %": engagement,
            "Hardcord Score": score,
            "Recent Videos": count,
        })

    rows.sort(key=lambda x: x["Hardcord Score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["Rank"] = i
    return rows


# ---------------------------------------------------------------------------
# Program detection (Tab 1)
# ---------------------------------------------------------------------------

def extract_program_name(title):
    t = title.strip()
    for dl in ["|", "–", "—", ":", "#"]:
        if dl in t:
            t = t.split(dl)[0]
            break
    t = re.sub(r"(?i)\bepisode\b.*", "", t)
    t = re.sub(r"(?i)\bep\.?\s*\d.*", "", t)
    t = re.sub(r"\d{2,}.*", "", t)
    t = re.sub(r"[\(\[].*?[\)\]]", "", t)
    t = t.strip(" -–—|.")
    return t.strip()


_NEWS_KW = ["news", "paththare", "wartha", "prime time", "lunch time",
            "වාර්ත", "ප්‍රවෘත්ති", "පුවත්", "satana", "balaya", "aluth parlimentuwa"]
_REALITY_KW = ["star", "talent", "idol", "voice", "dancing", "dream", "champion",
               "got ", "reality", "super", "unlimited", "junior", "battle",
               "lakshapathi", "kotipathi", "derana 60", "hadawatha", "calendar"]
_MUSIC_KW = ["song", "sindu", "සිංදු", "ගීත", " music", "cover song", "acoustic",
             "music video", "musical"]
_TALK_KW = ["talk", "interview", "chat", "salakuna", "tharu walalla",
            "the hot seat", "live at", "diyatha"]


def classify_program(name, episodes):
    n = name.lower()
    cats = [e.get("category_id", "") for e in episodes]
    dom = max(set(cats), key=cats.count) if cats else ""

    if dom == "25" or any(k in n for k in _NEWS_KW):
        return "📰 News"
    if any(k in n for k in _REALITY_KW):
        return "🎤 Reality/Show"
    if any(k in n for k in _TALK_KW):
        return "🗣️ Talk Show"
    if dom == "10" or any(k in n for k in _MUSIC_KW):
        return "🎵 Music"
    if dom in ("24", "1") and len(episodes) >= 4:
        return "🎭 Teledrama"
    if len(episodes) >= 4:
        return "🎭 Teledrama"
    return "📺 Other"


@st.cache_data(show_spinner=False, ttl=3600)
def get_curated_channel_stats():
    ids = [cid for cid, _ in SRI_LANKA_LOCAL_CHANNELS.values()]
    details = fetch_channel_details(ids)
    rows = []
    for name, (cid, ch_type) in SRI_LANKA_LOCAL_CHANNELS.items():
        d = details.get(cid, {})
        stats = d.get("statistics", {})
        rows.append({
            "channel_id": cid,
            "Channel": name,
            "Type": ch_type,
            "Subscribers": safe_int(stats.get("subscriberCount")),
            "Total Views": safe_int(stats.get("viewCount")),
            "Total Videos": safe_int(stats.get("videoCount")),
        })
    rows.sort(key=lambda x: x["Total Views"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["Rank"] = i
    return rows


@st.cache_data(show_spinner=False, ttl=1800)
def get_channel_programs(channel_id, date_from_str, date_to_str, max_scan):
    date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
    date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date()

    ch = api_get("channels", {"part": "contentDetails", "id": channel_id})
    items = ch.get("items", [])
    if not items:
        return {}
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids, page, scanned = [], None, 0
    while scanned < max_scan:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = api_get("playlistItems", params)
        batch = data.get("items", [])
        if not batch:
            break
        stop = False
        for x in batch:
            scanned += 1
            vp = x["contentDetails"].get("videoPublishedAt", "")[:10]
            if not vp:
                continue
            vd = datetime.strptime(vp, "%Y-%m-%d").date()
            if vd < date_from:
                stop = True
                continue
            if vd > date_to:
                continue
            video_ids.append(x["contentDetails"]["videoId"])
        page = data.get("nextPageToken")
        if stop or not page:
            break

    stats = {}
    for i in range(0, len(video_ids), 50):
        data = api_get("videos", {"part": "snippet,statistics", "id": ",".join(video_ids[i:i+50])})
        for x in data.get("items", []):
            stats[x["id"]] = x

    groups = defaultdict(list)
    for vid, v in stats.items():
        snippet = v["snippet"]
        s = v["statistics"]
        name = extract_program_name(snippet["title"]) or "(Other / One-off)"
        views = safe_int(s.get("viewCount"))
        likes = safe_int(s.get("likeCount"))
        comments = safe_int(s.get("commentCount"))
        groups[name].append({
            "title": snippet["title"],
            "date": snippet["publishedAt"][:10],
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement": round((likes / max(views, 1)) * 100, 2),
            "category_id": snippet.get("categoryId", ""),
            "url": f"https://youtube.com/watch?v={vid}",
        })

    programs = {}
    for name, eps in groups.items():
        eps.sort(key=lambda e: e["date"])
        total_views = sum(e["views"] for e in eps)
        programs[name] = {
            "episodes": eps,
            "episode_count": len(eps),
            "total_views": total_views,
            "avg_views": total_views // max(len(eps), 1),
            "category": classify_program(name, eps),
        }
    return programs


def analyze_program(name, prog):
    eps = prog["episodes"]
    count = len(eps)
    total_views = prog["total_views"]
    avg_views = prog["avg_views"]
    highest = max(eps, key=lambda e: e["views"])
    lowest = min(eps, key=lambda e: e["views"])
    avg_eng = round(sum(e["engagement"] for e in eps) / max(count, 1), 2)

    if count >= 4:
        k = min(5, count // 2) or 1
        first = sum(e["views"] for e in eps[:k]) / k
        last = sum(e["views"] for e in eps[-k:]) / k
        change = ((last - first) / max(first, 1)) * 100
        if change > 15:
            trend, trend_icon, mult = "Growing", "📈", 1.10
        elif change < -15:
            trend, trend_icon, mult = "Declining", "📉", 0.90
        else:
            trend, trend_icon, mult = "Stable", "➡️", 1.00
    else:
        trend, trend_icon, mult, change = "Stable", "➡️", 1.00, 0.0

    hardcord = round((avg_views / 1000) * (1 + avg_eng / 100) * mult, 2)

    return {
        "name": name, "episode_count": count, "total_views": total_views,
        "avg_views": avg_views, "highest": highest, "lowest": lowest,
        "avg_engagement": avg_eng, "trend": trend, "trend_icon": trend_icon,
        "trend_change": round(change, 1), "hardcord": hardcord, "episodes": eps,
        "category": prog.get("category", "📺 Other"),
    }


# ---------------------------------------------------------------------------
# App Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="yt-header">
  <div class="yt-header-inner">
    <div class="yt-logo-wrap">
      <img src="https://logos-world.net/wp-content/uploads/2020/06/YouTube-Logo.png"
           alt="YouTube" height="36" style="display:block;">
    </div>
    <div class="yt-header-text">
      <h1>Program Analyzer</h1>
      <p>Hardcord Ad Targeting &nbsp;·&nbsp; Compare Programs &nbsp;·&nbsp; Find the Best Episodes for 6-Second Ad Placement</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if not YOUTUBE_API_KEY:
    st.error("YouTube API key not configured. Please contact the administrator.")
    st.stop()

# Session state init
if "selected_channel_id" not in st.session_state:
    st.session_state.selected_channel_id = None
    st.session_state.selected_channel_name = None
if "compare" not in st.session_state:
    st.session_state.compare = []

tab1, tab2 = st.tabs(["🎭 Program Comparison", "📊 Trending Channels"])


# ===========================================================================
# TAB 1 — Program Comparison
# ===========================================================================

PLOTLY_COLORS = ["#FF0000", "#0066FF", "#00AA44", "#FF8800", "#9900CC"]


def _plotly_line(analyses):
    """Interactive Plotly line chart — hover shows episode title + views."""
    fig = go.Figure()
    for i, a in enumerate(analyses):
        eps = sorted(a["episodes"], key=lambda e: e["date"])
        dates = [e["date"] for e in eps]
        views = [e["views"] for e in eps]
        titles = [e["title"][:60] for e in eps]
        fig.add_trace(go.Scatter(
            x=dates, y=views,
            mode="lines+markers",
            name=a["name"][:30],
            line=dict(color=PLOTLY_COLORS[i % len(PLOTLY_COLORS)], width=2.5),
            marker=dict(size=7, symbol="circle"),
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                "Views: <b>%{y:,}</b><br>"
                "Date: %{x}<extra>" + a["name"][:20] + "</extra>"
            ),
            customdata=titles,
        ))
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="#fafafa",
        font=dict(family="Inter, sans-serif", size=12, color="#1a1a2e"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0", title=""),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="Views",
                   tickformat=".2s"),
        hovermode="closest",
        margin=dict(l=10, r=10, t=40, b=10),
        height=320,
    )
    return fig


def _plotly_bar(ranked_analyses):
    """Interactive bar chart — avg views per program."""
    names = [a["name"][:28] for a in ranked_analyses]
    values = [a["avg_views"] for a in ranked_analyses]
    colors = [PLOTLY_COLORS[i % len(PLOTLY_COLORS)] for i in range(len(ranked_analyses))]
    fig = go.Figure(go.Bar(
        x=values, y=names, orientation="h",
        marker_color=colors,
        hovertemplate="<b>%{y}</b><br>Avg Views: <b>%{x:,}</b><extra></extra>",
        text=[format_number(v) for v in values],
        textposition="outside",
    ))
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="#fafafa",
        font=dict(family="Inter, sans-serif", size=12, color="#1a1a2e"),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0", tickformat=".2s"),
        yaxis=dict(showgrid=False),
        margin=dict(l=10, r=60, t=20, b=10),
        height=260,
    )
    return fig


def _plotly_radar(ranked_analyses):
    """Spider/radar chart comparing programs across 4 dimensions."""
    categories = ["Avg Views", "Engagement", "Episodes", "Trend Score"]
    fig = go.Figure()
    for i, a in enumerate(ranked_analyses):
        # Normalise each axis 0-100 relative to peers
        max_views = max(x["avg_views"] for x in ranked_analyses) or 1
        max_eng = max(x["avg_engagement"] for x in ranked_analyses) or 1
        max_eps = max(x["episode_count"] for x in ranked_analyses) or 1
        trend_map = {"Growing": 100, "Stable": 60, "Declining": 20}
        vals = [
            round(a["avg_views"] / max_views * 100, 1),
            round(a["avg_engagement"] / max_eng * 100, 1),
            round(a["episode_count"] / max_eps * 100, 1),
            trend_map.get(a["trend"], 60),
        ]
        vals_closed = vals + [vals[0]]
        cats_closed = categories + [categories[0]]
        fig.add_trace(go.Scatterpolar(
            r=vals_closed, theta=cats_closed,
            fill="toself", name=a["name"][:25],
            line=dict(color=PLOTLY_COLORS[i % len(PLOTLY_COLORS)], width=2),
            fillcolor=PLOTLY_COLORS[i % len(PLOTLY_COLORS)],
            opacity=0.18,
        ))
    fig.update_layout(
        polar=dict(
            bgcolor="#fafafa",
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9)),
        ),
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=11, color="#1a1a2e"),
        legend=dict(orientation="h", yanchor="top", y=-0.1),
        margin=dict(l=30, r=30, t=30, b=30),
        height=300,
        showlegend=True,
    )
    return fig


def _plotly_episode_detail(a):
    """Per-program interactive line with episode title on hover."""
    eps = sorted(a["episodes"], key=lambda e: e["date"])
    fig = go.Figure(go.Scatter(
        x=[e["date"] for e in eps],
        y=[e["views"] for e in eps],
        mode="lines+markers",
        line=dict(color="#FF0000", width=2.5),
        marker=dict(size=8, color="#FF0000",
                    line=dict(color="white", width=1.5)),
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "Views: <b>%{y:,}</b><br>"
            "Date: %{x}"
            "<extra></extra>"
        ),
        customdata=[e["title"][:65] for e in eps],
        fill="tozeroy",
        fillcolor="rgba(255,0,0,0.06)",
    ))
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="#fafafa",
        font=dict(family="Inter, sans-serif", size=11),
        xaxis=dict(showgrid=True, gridcolor="#f0f0f0", title=""),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f0",
                   tickformat=".2s", title="Views"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=240,
    )
    return fig


def render_program_comparison():
    # ── Date Range with quick preset pills ──────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">📅</span>
        <span class="section-title">Date Range & Scan Settings</span>
    </div>
    """, unsafe_allow_html=True)

    # Quick preset buttons
    preset_cols = st.columns(6)
    presets = {"7D": 7, "14D": 14, "30D": 30, "60D": 60, "90D": 90, "Custom": None}
    if "date_preset" not in st.session_state:
        st.session_state.date_preset = "30D"

    for col, (label, days) in zip(preset_cols, presets.items()):
        active = st.session_state.date_preset == label
        if col.button(
            label,
            key=f"preset_{label}",
            type="primary" if active else "secondary",
        ):
            st.session_state.date_preset = label
            st.rerun()

    # Date inputs — shown always; presets control defaults
    preset_days = presets.get(st.session_state.date_preset)
    default_from = (date.today() - timedelta(days=preset_days)) if preset_days else (date.today() - timedelta(days=30))

    dc1, dc2, dc3 = st.columns([1, 1, 1])
    with dc1:
        date_from = st.date_input("From", value=default_from, key="date_from")
    with dc2:
        date_to = st.date_input("To", value=date.today(), key="date_to")
    with dc3:
        max_scan = st.select_slider(
            "Scan depth",
            options=[200, 500, 1000, 1500, 2500], value=1000,
        )

    if date_from > date_to:
        st.error("'From' date must be before 'To' date.")
        return

    st.markdown("---")

    # ── STEP 1: Channel Selection ────────────────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">1</span>
        <span class="section-title">Select a Channel</span>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading channels..."):
        chan_stats = get_curated_channel_stats()
    st.toast(f"✅ Loaded {len(chan_stats)} Sri Lankan channels", icon="📺")

    # Live search bar
    search_q = st.text_input("🔍 Search channels", placeholder="Type a channel name…", key="chan_search")

    # Type filter chips (inline pills using columns)
    all_ch_types = sorted({c["Type"] for c in chan_stats})
    if "sel_types" not in st.session_state:
        st.session_state.sel_types = set(all_ch_types)

    chip_cols = st.columns(len(all_ch_types))
    for col, t in zip(chip_cols, all_ch_types):
        active = t in st.session_state.sel_types
        if col.button(t, key=f"chip_{t}", type="primary" if active else "secondary"):
            if active:
                st.session_state.sel_types.discard(t)
            else:
                st.session_state.sel_types.add(t)
            st.rerun()

    # Filter channels
    filtered_chans = [
        c for c in chan_stats
        if c["Type"] in st.session_state.sel_types
        and (not search_q or search_q.lower() in c["Channel"].lower())
    ]

    chan_df = pd.DataFrame([{
        "Rank": f"#{c['Rank']}",
        "Type": c["Type"],
        "Channel": c["Channel"],
        "Subscribers": format_number(c["Subscribers"]),
        "Total Views": format_number(c["Total Views"]),
        "Total Videos": f"{c['Total Videos']:,}",
    } for c in filtered_chans])

    event = st.dataframe(
        chan_df, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="chan_table",
    )

    sel_rows = event.selection.rows if hasattr(event, "selection") else []
    if sel_rows:
        chosen = filtered_chans[sel_rows[0]]
        if chosen["channel_id"] != st.session_state.selected_channel_id:
            st.session_state.selected_channel_id = chosen["channel_id"]
            st.session_state.selected_channel_name = chosen["Channel"]
            st.session_state.compare = []
            st.toast(f"📺 Selected: {chosen['Channel']}", icon="✅")

    if not st.session_state.selected_channel_id:
        st.info("👆 Click a channel row above to load its programs.")
        return

    st.success(f"**{st.session_state.selected_channel_name}** selected — showing programs from {date_from} → {date_to}")
    st.markdown("---")

    # ── STEP 2: Program List ─────────────────────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">2</span>
        <span class="section-title">Programs in Date Range</span>
    </div>
    """, unsafe_allow_html=True)

    prog_status = st.empty()
    prog_bar = st.progress(0, text="Fetching channel info…")
    prog_bar.progress(20, text="Scanning uploads…")
    with st.spinner(""):
        programs = get_channel_programs(
            st.session_state.selected_channel_id,
            date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"), max_scan,
        )
    prog_bar.progress(100, text="Done!")
    prog_bar.empty()

    if not programs:
        st.warning("No uploads found in this date range. Try widening the range or increasing scan depth.")
        return

    st.toast(f"✅ Found {len(programs)} programs on {st.session_state.selected_channel_name}", icon="🎬")

    ranked_programs = sorted(programs.items(), key=lambda x: x[1]["total_views"], reverse=True)

    # Queued comparison pills
    if st.session_state.compare:
        st.markdown("**🗂️ Queued for comparison:**")
        qcols = st.columns(4)
        for i, pname in enumerate(st.session_state.compare):
            with qcols[i]:
                st.markdown(f'<div class="prog-card">🎬 <b>{pname[:28]}</b></div>', unsafe_allow_html=True)
                if st.button("✖ Remove", key=f"rm_{i}"):
                    st.session_state.compare.remove(pname)
                    st.rerun()

    # Sort + type filter controls
    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    with ctrl1:
        sort_by = st.selectbox("Sort by", ["Most Views", "Best Engagement", "Most Episodes", "Growing Trend"], key="prog_sort")
    with ctrl2:
        all_prog_types = sorted({p["category"] for _, p in ranked_programs})
        type_filter = st.multiselect("Filter type", all_prog_types, default=all_prog_types, key="prog_type_filter")
    with ctrl3:
        prog_search = st.text_input("🔍 Search programs", placeholder="Name…", key="prog_search")

    # Apply sort
    def sort_key(item):
        _, p = item
        if sort_by == "Best Engagement":
            eps = p["episodes"]
            return sum(e["engagement"] for e in eps) / max(len(eps), 1)
        if sort_by == "Most Episodes":
            return p["episode_count"]
        if sort_by == "Growing Trend":
            eps = sorted(p["episodes"], key=lambda e: e["date"])
            if len(eps) >= 4:
                k = min(5, len(eps) // 2)
                first = sum(e["views"] for e in eps[:k]) / k
                last = sum(e["views"] for e in eps[-k:]) / k
                return (last - first) / max(first, 1)
            return 0
        return p["total_views"]

    filtered = [
        (n, p) for n, p in sorted(ranked_programs, key=sort_key, reverse=True)
        if p["category"] in type_filter
        and (not prog_search or prog_search.lower() in n.lower())
    ]

    # Program rows
    hdr = st.columns([3.2, 1.6, 1.4, 1.0, 1.4])
    for h, t in zip(hdr, ["Program", "Type", "Views", "Episodes", "Action"]):
        h.markdown(f"**{t}**")
    st.markdown("<hr style='margin:4px 0 8px'>", unsafe_allow_html=True)

    for idx, (pname, pdata) in enumerate(filtered[:30]):
        c1, c2, c3, c4, c5 = st.columns([3.2, 1.6, 1.4, 1.0, 1.4])
        c1.markdown(f"**{pname}**")
        c2.markdown(pdata["category"])
        c3.markdown(f"👁 {format_number(pdata['total_views'])}")
        c4.markdown(f"🎞 {pdata['episode_count']}")
        already = pname in st.session_state.compare
        full = len(st.session_state.compare) >= 4
        if already:
            c5.markdown("✅ Added")
        elif full:
            c5.markdown("—")
        else:
            if c5.button("➕ Add", key=f"add_{idx}"):
                st.session_state.compare.append(pname)
                st.toast(f"➕ Added: {pname[:30]}", icon="🎬")
                st.rerun()

    if not st.session_state.compare:
        st.info("➕ Add at least one program above to see the comparison.")
        return

    st.markdown("---")

    # ── STEP 3: Comparison Dashboard ────────────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">3</span>
        <span class="section-title">Comparison Dashboard</span>
    </div>
    """, unsafe_allow_html=True)

    analyses = [analyze_program(p, programs[p]) for p in st.session_state.compare if p in programs]
    ranked_analyses = sorted(analyses, key=lambda a: a["hardcord"], reverse=True)

    # ── 🎯 Ad Placement Recommendation Banner ─────────────────────────────
    best_ep = max(
        (e for a in analyses for e in a["episodes"]),
        key=lambda e: e["views"],
    )
    best_prog = next(a for a in analyses if best_ep in a["episodes"])
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #FF0000, #cc0000);
        border-radius: 14px; padding: 1.2rem 1.6rem; margin-bottom: 1rem;
        box-shadow: 0 6px 20px rgba(255,0,0,0.3); color: white;
    ">
        <div style="font-size:0.8rem; text-transform:uppercase; letter-spacing:1px; opacity:0.85; margin-bottom:4px;">
            🎯 Best Episode to Place Your Ad RIGHT NOW
        </div>
        <div style="font-size:1.4rem; font-weight:800; line-height:1.2; margin-bottom:6px;">
            {best_ep['title'][:70]}
        </div>
        <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:0.95rem; opacity:0.95;">
            <span>👁 <b>{format_number(best_ep['views'])}</b> views</span>
            <span>📺 <b>{best_prog['name'][:25]}</b></span>
            <span>📅 <b>{best_ep['date']}</b></span>
            <span>💬 <b>{best_ep['engagement']}%</b> engagement</span>
        </div>
        <div style="margin-top:8px;">
            <a href="{best_ep['url']}" target="_blank"
               style="color:white; text-decoration:underline; font-weight:600; font-size:0.9rem;">
                ▶ Watch Episode →
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Priority Ranking Table ─────────────────────────────────────────────
    st.markdown("##### 🏆 Hardcord Priority Ranking")
    max_hc = max((a["hardcord"] for a in analyses), default=1)
    rank_df = pd.DataFrame([{
        "Priority": f"#{i+1}",
        "Program": a["name"],
        "Type": a["category"],
        "Avg Views/Ep": format_number(a["avg_views"]),
        "Total Views": format_number(a["total_views"]),
        "Episodes": a["episode_count"],
        "Engagement %": f"{a['avg_engagement']}%",
        "Trend": f"{a['trend_icon']} {a['trend']}",
        "Hardcord Score": a["hardcord"],
    } for i, a in enumerate(ranked_analyses)])
    st.dataframe(
        rank_df, use_container_width=True, hide_index=True,
        column_config={"Hardcord Score": st.column_config.ProgressColumn(
            "Hardcord Score", min_value=0, max_value=max_hc, format="%.0f")},
    )

    # ── Interactive Charts ─────────────────────────────────────────────────
    st.markdown("##### 📈 Episode Views Trend — hover a point to see episode title")
    st.plotly_chart(_plotly_line(analyses), use_container_width=True)
    st.caption("Click legend items to show/hide programs. Drag to zoom. Double-click to reset.")

    ch_left, ch_right = st.columns([1, 1])
    with ch_left:
        st.markdown("##### 📊 Avg Views per Episode")
        st.plotly_chart(_plotly_bar(ranked_analyses), use_container_width=True)
    with ch_right:
        st.markdown("##### 🕸️ Program Comparison Radar")
        st.caption("Scores normalised to 100 across all compared programs.")
        st.plotly_chart(_plotly_radar(ranked_analyses), use_container_width=True)

    st.markdown("---")

    # ── Per-Program Detail ─────────────────────────────────────────────────
    st.markdown("##### 🔍 Per-Program Detail & Ad-Placement Guide")
    for a in ranked_analyses:
        with st.expander(
            f"{a['trend_icon']} {a['name']} · {a['category']} — "
            f"{format_number(a['avg_views'])} avg views/ep · {a['trend']}",
            expanded=True,
        ):
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.markdown(f'<div class="metric-card"><h2>{a["episode_count"]}</h2><p>Episodes</p></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-card"><h2>{format_number(a["total_views"])}</h2><p>Total Views</p></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-card"><h2>{format_number(a["avg_views"])}</h2><p>Avg / Episode</p></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-card"><h2>{a["avg_engagement"]}%</h2><p>Engagement</p></div>', unsafe_allow_html=True)
            m5.markdown(f'<div class="metric-card"><h2>{a["trend_icon"]}</h2><p>{a["trend"]} ({a["trend_change"]:+.0f}%)</p></div>', unsafe_allow_html=True)

            hc1, hc2 = st.columns(2)
            hc1.markdown(f"🔺 **Highest:** {format_number(a['highest']['views'])} views — "
                         f"[{a['highest']['title'][:55]}]({a['highest']['url']})")
            hc2.markdown(f"🔻 **Lowest:** {format_number(a['lowest']['views'])} views — "
                         f"[{a['lowest']['title'][:55]}]({a['lowest']['url']})")

            # Interactive per-program line
            st.plotly_chart(_plotly_episode_detail(a), use_container_width=True)

            top3 = sorted(a["episodes"], key=lambda e: e["views"], reverse=True)[:3]
            st.markdown("**🎯 Best episodes to place your ad:**")
            for e in top3:
                st.markdown(f"- **{format_number(e['views'])} views** · {e['date']} · "
                            f"[{e['title'][:60]}]({e['url']})")

            ep_disp = pd.DataFrame([{
                "Date": e["date"], "Episode": e["title"],
                "Views": format_number(e["views"]), "Likes": format_number(e["likes"]),
                "Comments": format_number(e["comments"]), "Engagement %": f"{e['engagement']}%",
                "Watch": e["url"],
            } for e in sorted(a["episodes"], key=lambda e: e["date"], reverse=True)])
            st.dataframe(ep_disp, use_container_width=True, hide_index=True,
                         column_config={"Watch": st.column_config.LinkColumn("▶️", display_text="Watch")})

            csv_buf = io.StringIO()
            pd.DataFrame(a["episodes"]).to_csv(csv_buf, index=False)
            st.download_button(
                f"⬇️ Download '{a['name'][:20]}' CSV", csv_buf.getvalue(),
                file_name=f"{re.sub(r'[^A-Za-z0-9]+','_',a['name'])[:30]}_{date_to}.csv",
                mime="text/csv", key=f"dl_{a['name']}",
            )


# ===========================================================================
# TAB 2 — Trending Channels
# (All settings are INLINE here — no sidebar — to avoid bleed into Tab 1)
# ===========================================================================

def render_trending_channels():
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">⚙️</span>
        <span class="section-title">Trending Settings</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        ts1, ts2, ts3 = st.columns([1, 1, 1])
        with ts1:
            region_label = st.selectbox("📍 Region", list(REGIONS.keys()), index=0, key="t_region")
            region_code = REGIONS[region_label]
            category_label = st.selectbox("🎬 Category", list(CATEGORY_NAMES.values()), index=0, key="t_cat")
            category_id = {v: k for k, v in CATEGORY_NAMES.items()}.get(category_label, "")
        with ts2:
            period_options = {
                "Last 7 days": 7,
                "Last 14 days": 14,
                "Last 30 days": 30,
                "Last 90 days": 90,
            }
            period_label = st.selectbox("📅 Period", list(period_options.keys()), index=2, key="t_period")
            days_back = period_options[period_label]
            max_results = st.slider("📊 Videos to Analyze", 10, 50, 50, 10, key="t_max")
        with ts3:
            top_n = st.slider("🏆 Top Channels to Show", 5, 50, 20, 5, key="t_topn")
            local_only = st.toggle("🇱🇰 Local SL Channels Only", value=False, key="t_local")
            st.markdown("")
            run_btn = st.button("🚀 Run Trending Analysis", key="t_run")

    # ── How does this work? ──────────────────────────────────────────────────
    with st.expander("ℹ️ How is the Trending Channel list obtained?"):
        if local_only:
            st.markdown("""
**Local SL Channels mode** uses our curated list of **100 verified Sri Lankan channels**.
For each channel, we pull their most recent videos published in the selected period and
compute a **Hardcord Score** based on actual views, likes, and subscriber count.

This gives a much more accurate picture than YouTube's global trending chart, which
rarely features local Sri Lankan TV channels or creators.
""")
        else:
            st.markdown(f"""
**Global Trending mode** calls the **YouTube Data API v3** —
`videos.list(chart="mostPopular", regionCode="{region_code}")`.

YouTube itself decides which videos appear in this list based on views, shares, comments,
and watch time in that region over the past ~48 hours. We then group those videos by channel,
sum the views/likes, and compute a **Hardcord Score**:

> `Score = (total_views / 1M) × engagement_rate% × log10(subscribers)`

A higher score = better ROI for placing your 6-second hardcord ad.

**Note:** Sri Lankan local TV channels and creators rarely appear in YouTube's global
trending chart. Use **Local SL Channels Only** toggle to see a curated Sri Lankan ranking instead.
""")

    if run_btn:
        if local_only:
            with st.spinner(f"Scanning {len(SRI_LANKA_LOCAL_CHANNELS)} local channels for the past {days_back} days..."):
                ranked = get_local_channel_trending_stats(days_back)
            if not ranked:
                st.warning("No data found for local channels in this period.")
                return

            st.subheader(f"🏆 Local SL Channels — {period_label}")
            st.caption(f"Ranked by Hardcord Score based on recent video performance ({period_label})")

            max_score = ranked[0]["Hardcord Score"] if ranked else 1
            disp = pd.DataFrame([{
                "Rank": f"#{r['Rank']}", "🇱🇰": "✅", "Channel": r["Channel"],
                "Type": r["Type"],
                "Subscribers": format_number(r["Subscribers"]),
                "Total Views": format_number(r["Total Views"]),
                "Engagement %": f"{r['Engagement %']}%",
                "Hardcord Score": r["Hardcord Score"],
                "Recent Videos": r["Recent Videos"],
            } for r in ranked[:top_n]])
            st.dataframe(
                disp, use_container_width=True, hide_index=True,
                column_config={"Hardcord Score": st.column_config.ProgressColumn(
                    "Hardcord Score", min_value=0, max_value=max_score, format="%.4f")},
            )

        else:
            with st.spinner(f"Fetching trending videos for {region_label}..."):
                videos = fetch_trending_videos(region_code, max_results, category_id or None)
            if not videos:
                st.warning("No trending videos found.")
                return
            with st.spinner("Fetching channel details..."):
                cids = list({v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")})
                cdetails = fetch_channel_details(cids)
            ranked = aggregate_channel_data(videos, cdetails, local_only=False)
            if not ranked:
                st.warning("No channels found.")
                return

            st.subheader(f"🏆 Trending Channels — {region_label} | {category_label}")
            max_score = ranked[0]["Hardcord Score"] if ranked else 1
            disp = pd.DataFrame([{
                "Rank": f"#{r['Rank']}", "🇱🇰": r["🇱🇰"], "Channel": r["Channel"],
                "Category": r["Category"], "Subscribers": format_number(r["Subscribers"]),
                "Total Views": format_number(r["Total Views"]),
                "Engagement %": f"{r['Engagement %']}%", "Hardcord Score": r["Hardcord Score"],
            } for r in ranked[:top_n]])
            st.dataframe(
                disp, use_container_width=True, hide_index=True,
                column_config={"Hardcord Score": st.column_config.ProgressColumn(
                    "Hardcord Score", min_value=0, max_value=max_score, format="%.4f")},
            )

        buf = io.StringIO()
        pd.DataFrame(ranked[:top_n]).to_csv(buf, index=False)
        st.download_button(
            "⬇️ Download CSV", buf.getvalue(),
            file_name=f"trending_{region_code}_{date.today()}.csv", mime="text/csv",
            key="t_download",
        )
    else:
        st.info("👆 Configure settings above and click **Run Trending Analysis**.")


# ===========================================================================
# Render tabs
# ===========================================================================

with tab1:
    render_program_comparison()

with tab2:
    render_trending_channels()
