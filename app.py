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
    /* ══════════════════════════════════════════════════════════════
       FONTS
    ══════════════════════════════════════════════════════════════ */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800;900&display=swap');

    /* ══════════════════════════════════════════════════════════════
       BASE — cool slate background
    ══════════════════════════════════════════════════════════════ */
    html, body, [data-testid="stApp"],
    [data-testid="stAppViewContainer"], .main, .block-container {
        background-color: #eef1f4 !important;
        color: #0f172a !important;
        font-family: 'Poppins', sans-serif !important;
    }
    [data-testid="block-container"] {
        padding-top: 0 !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 1300px !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
        background-color: #0f172a !important;
        border-right: none !important;
    }

    /* ══════════════════════════════════════════════════════════════
       TOP UTILITY BAR — dark slate
    ══════════════════════════════════════════════════════════════ */
    .top-bar {
        background: #0f172a;
        padding: 6px 2rem;
        font-size: 0.75rem;
        color: rgba(255,255,255,0.7);
        display: flex; align-items: center; justify-content: space-between;
        margin: -1rem -1rem 0;
    }
    .top-bar span { display: flex; align-items: center; gap: 18px; }
    .top-bar b { color: #fb7185; }

    /* ══════════════════════════════════════════════════════════════
       HERO HEADER — dark slate with red accent
    ══════════════════════════════════════════════════════════════ */
    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #293548 100%);
        border-radius: 0 0 28px 28px;
        padding: 1.4rem 2.5rem 2rem;
        margin: 0 -1rem 1.8rem;
        position: relative; overflow: hidden;
        box-shadow: 0 8px 40px rgba(15,23,42,0.35);
    }
    .hero-header::before {
        content: ''; position: absolute;
        top: -70px; right: -70px;
        width: 280px; height: 280px; border-radius: 50%;
        background: rgba(251,113,133,0.09);
    }
    .hero-header::after {
        content: ''; position: absolute;
        bottom: -50px; left: 100px;
        width: 200px; height: 200px; border-radius: 50%;
        background: rgba(251,113,133,0.06);
    }
    .hero-nav {
        display: flex; align-items: center;
        justify-content: space-between; margin-bottom: 1.2rem;
    }
    .hero-logo-wrap {
        background: #fff; border-radius: 10px;
        padding: 6px 14px 4px;
        display: flex; align-items: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25);
    }
    .hero-tagline {
        display: flex; gap: 18px; align-items: center;
    }
    .hero-tagline span {
        color: rgba(255,255,255,0.65);
        font-size: 0.78rem; font-weight: 500;
    }
    .hero-tagline .pill {
        background: rgba(251,113,133,0.15); color: #fb7185;
        border: 1px solid rgba(251,113,133,0.3);
        border-radius: 20px; padding: 2px 12px;
        font-size: 0.72rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    .hero-body { position: relative; z-index: 1; }
    .hero-body h1 {
        color: #ffffff !important; margin: 0;
        font-size: 2.2rem; font-weight: 900;
        line-height: 1.15; letter-spacing: -0.5px;
    }
    .hero-body h1 .accent { color: #fb7185; }
    .hero-body p {
        color: rgba(255,255,255,0.65) !important;
        margin: 0.5rem 0 1rem; font-size: 0.92rem;
        font-weight: 400; max-width: 580px;
    }
    .hero-stats {
        display: flex; gap: 28px; flex-wrap: wrap;
        margin-top: 0.8rem;
    }
    .hero-stat { display: flex; flex-direction: column; }
    .hero-stat .num {
        color: #fb7185; font-size: 1.5rem;
        font-weight: 800; line-height: 1;
    }
    .hero-stat .lbl {
        color: rgba(255,255,255,0.5); font-size: 0.7rem;
        text-transform: uppercase; letter-spacing: 0.5px;
    }

    /* ══════════════════════════════════════════════════════════════
       TABS — red active underline
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stTabs"] [role="tablist"] {
        background: #ffffff !important;
        border-bottom: 2px solid #e6eaef !important;
        border-radius: 14px 14px 0 0 !important;
        padding: 0 1rem !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.06) !important;
        gap: 0 !important;
    }
    [data-testid="stTabs"] button[role="tab"] {
        color: #6b7280 !important; font-weight: 600 !important;
        font-size: 0.9rem !important; padding: 0.9rem 1.8rem !important;
        border: none !important; border-bottom: 3px solid transparent !important;
        background: transparent !important; border-radius: 0 !important;
        font-family: 'Poppins', sans-serif !important;
        transition: all 0.2s !important;
    }
    [data-testid="stTabs"] button[role="tab"]:hover {
        color: #e11d2e !important; background: #fef2f2 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #e11d2e !important;
        border-bottom: 3px solid #e11d2e !important;
        background: #fef2f2 !important; font-weight: 700 !important;
    }

    /* ══════════════════════════════════════════════════════════════
       SECTION CARDS — white floating panels
    ══════════════════════════════════════════════════════════════ */
    .section-card {
        background: #ffffff;
        border-radius: 20px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 4px 24px rgba(15,23,42,0.08);
        border: 1px solid #e6eaef;
    }
    .section-card-dark {
        background: #0f172a;
        border-radius: 20px;
        padding: 1.6rem 2rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 4px 28px rgba(15,23,42,0.25);
    }

    /* ══════════════════════════════════════════════════════════════
       SECTION HEADERS
    ══════════════════════════════════════════════════════════════ */
    .section-header {
        display: flex; align-items: center; gap: 12px;
        margin: 1.6rem 0 0.8rem; padding: 0;
    }
    .step-badge {
        background: #e11d2e;
        color: #fff; border-radius: 50%;
        width: 32px; height: 32px;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: 900; font-size: 0.85rem; flex-shrink: 0;
        box-shadow: 0 4px 12px rgba(225,29,46,0.4);
    }
    .section-title {
        color: #0f172a !important; font-size: 1.15rem;
        font-weight: 700; margin: 0;
        font-family: 'Poppins', sans-serif !important;
    }
    .section-title .green  { color: #e11d2e; }
    .section-title .accent { color: #fb7185; }

    /* ══════════════════════════════════════════════════════════════
       METRIC CARDS — white with red top border
    ══════════════════════════════════════════════════════════════ */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e6eaef;
        border-top: 4px solid #e11d2e;
        border-radius: 14px; padding: 1.2rem 0.9rem;
        text-align: center;
        box-shadow: 0 2px 12px rgba(15,23,42,0.06);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 28px rgba(225,29,46,0.14);
    }
    .metric-card h2 {
        color: #e11d2e !important; margin: 0;
        font-size: 1.8rem; font-weight: 800;
        font-family: 'Poppins', sans-serif !important;
    }
    .metric-card p {
        color: #9ca3af !important; margin: 0.2rem 0 0;
        font-size: 0.68rem; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 600;
    }

    /* ══════════════════════════════════════════════════════════════
       PROGRAM QUEUE CARDS
    ══════════════════════════════════════════════════════════════ */
    .prog-card {
        background: #fef2f2;
        border: 1px solid #fecdd3;
        border-left: 4px solid #e11d2e;
        border-radius: 10px; padding: 0.7rem 1rem; margin-bottom: 0.4rem;
        color: #0f172a !important; font-size: 0.88rem;
        box-shadow: 0 2px 8px rgba(225,29,46,0.08);
    }

    /* ══════════════════════════════════════════════════════════════
       BUTTONS — red pill (primary) + white pill (secondary)
    ══════════════════════════════════════════════════════════════ */
    .stButton > button {
        background: #e11d2e !important;
        color: #ffffff !important; border: none !important;
        border-radius: 50px !important;
        padding: 0.55rem 1.8rem !important;
        font-weight: 700 !important; font-size: 0.88rem !important;
        font-family: 'Poppins', sans-serif !important;
        box-shadow: 0 4px 14px rgba(225,29,46,0.35) !important;
        transition: all 0.2s !important;
        letter-spacing: 0.2px;
    }
    .stButton > button:hover {
        background: #b91c2a !important;
        box-shadow: 0 6px 22px rgba(225,29,46,0.5) !important;
        transform: translateY(-2px) !important;
    }
    /* Secondary — white pill with red hover */
    .stButton > button[kind="secondary"] {
        background: #ffffff !important;
        color: #374151 !important;
        border: 1.5px solid #d1d5db !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #fef2f2 !important;
        border-color: #e11d2e !important;
        color: #e11d2e !important;
        box-shadow: 0 4px 14px rgba(225,29,46,0.18) !important;
        transform: translateY(-2px) !important;
    }

    /* ══════════════════════════════════════════════════════════════
       FORM CONTROLS — red focus ring
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stMultiSelect"] > div > div,
    [data-testid="stDateInput"] input {
        background-color: #ffffff !important;
        border: 1.5px solid #e2e8f0 !important;
        color: #0f172a !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
        font-family: 'Poppins', sans-serif !important;
    }
    [data-testid="stSelectbox"] > div > div:focus-within,
    [data-testid="stMultiSelect"] > div > div:focus-within {
        border-color: #e11d2e !important;
        box-shadow: 0 0 0 3px rgba(225,29,46,0.14) !important;
    }
    [data-baseweb="popover"] {
        background: #ffffff !important;
        border: 1px solid #e6eaef !important;
        box-shadow: 0 12px 32px rgba(0,0,0,0.10) !important;
        border-radius: 12px !important;
    }
    [data-baseweb="option"]:hover {
        background: #fef2f2 !important; color: #e11d2e !important;
    }
    [data-baseweb="option"][aria-selected="true"] {
        background: #fee2e2 !important; color: #b91c2a !important;
    }
    [data-baseweb="tag"] {
        background: #fef2f2 !important; border-color: #fecdd3 !important;
        color: #e11d2e !important; border-radius: 20px !important;
        font-weight: 600 !important; font-size: 0.78rem !important;
    }
    [data-testid="stWidgetLabel"] p {
        color: #6b7280 !important; font-size: 0.75rem !important;
        font-weight: 600 !important; text-transform: uppercase !important;
        letter-spacing: 0.6px !important;
        font-family: 'Poppins', sans-serif !important;
    }

    /* ══════════════════════════════════════════════════════════════
       DATAFRAME
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stDataFrame"] {
        border-radius: 14px !important; overflow: hidden !important;
        border: 1px solid #e6eaef !important;
        box-shadow: 0 4px 16px rgba(15,23,42,0.06) !important;
    }

    /* ══════════════════════════════════════════════════════════════
       EXPANDER — white card, red hover
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stExpander"] {
        background: #ffffff !important;
        border: 1px solid #e6eaef !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(15,23,42,0.06) !important;
        margin-bottom: 0.8rem !important;
    }
    [data-testid="stExpander"] summary {
        color: #0f172a !important; font-weight: 700 !important;
        font-size: 0.95rem !important;
        font-family: 'Poppins', sans-serif !important;
        padding: 1rem 1.2rem !important;
    }
    [data-testid="stExpander"] summary:hover { color: #e11d2e !important; }
    [data-testid="stExpander"] > div {
        background: #ffffff !important;
        padding: 0.2rem 1rem 1rem !important;
    }

    /* ══════════════════════════════════════════════════════════════
       ALERTS
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stAlert"] {
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        font-family: 'Poppins', sans-serif !important;
    }

    /* ══════════════════════════════════════════════════════════════
       DOWNLOAD BUTTON
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stDownloadButton"] button {
        background: #ffffff !important;
        border: 2px solid #e11d2e !important;
        color: #e11d2e !important;
        border-radius: 50px !important;
        font-weight: 700 !important;
        transition: all 0.2s !important;
    }
    [data-testid="stDownloadButton"] button:hover {
        background: #e11d2e !important;
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(225,29,46,0.35) !important;
    }

    /* ══════════════════════════════════════════════════════════════
       DIVIDERS, TEXT, LINKS
    ══════════════════════════════════════════════════════════════ */
    hr {
        border: none !important;
        border-top: 2px solid #e6eaef !important;
        margin: 1.4rem 0 !important;
    }
    [data-testid="stCaption"] p {
        color: #9ca3af !important; font-size: 0.78rem !important;
    }
    h1,h2,h3,h4,h5,h6 {
        color: #0f172a !important;
        font-family: 'Poppins', sans-serif !important;
    }
    p, li { color: #374151 !important; }
    a { color: #e11d2e !important; }
    a:hover { color: #b91c2a !important; }
    progress { accent-color: #e11d2e !important; }

    /* ══════════════════════════════════════════════════════════════
       SPINNER
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stSpinner"] > div { border-top-color: #e11d2e !important; }

    /* ══════════════════════════════════════════════════════════════
       PROGRESS BAR
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #e11d2e, #fb7185) !important;
        border-radius: 10px !important;
    }

    /* ══════════════════════════════════════════════════════════════
       TOGGLE
    ══════════════════════════════════════════════════════════════ */
    [data-testid="stToggle"] > div[data-checked="true"] {
        background-color: #e11d2e !important;
    }

    /* ══════════════════════════════════════════════════════════════
       KPI STRIP
    ══════════════════════════════════════════════════════════════ */
    .kpi-strip { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin:0 0 1.4rem; }
    .kpi-card { background:#fff; border:1px solid #e6eaef; border-radius:20px; padding:18px 20px;
        box-shadow:0 4px 24px rgba(15,23,42,0.08); transition:transform .2s,box-shadow .2s; }
    .kpi-card:hover { transform:translateY(-3px); box-shadow:0 8px 28px rgba(225,29,46,0.14); }
    .kpi-card__icon { width:40px;height:40px;border-radius:12px;background:#fef2f2;
        display:inline-flex;align-items:center;justify-content:center;margin-bottom:10px; }
    .kpi-card__value { font-size:2rem;font-weight:800;letter-spacing:-1px;color:#0f172a;line-height:1; }
    .kpi-card__label { font-size:0.72rem;font-weight:700;color:#9ca3af;text-transform:uppercase;
        letter-spacing:0.5px;margin-top:4px; }
    .kpi-card__delta { display:inline-flex;align-items:center;gap:4px;font-size:0.74rem;font-weight:800;
        padding:3px 9px;border-radius:50px;margin-top:6px; }
    .kpi-card__delta.up { color:#16a34a;background:rgba(22,163,74,0.1); }

    /* ══════════════════════════════════════════════════════════════
       FEATURED PROGRAM CARDS
    ══════════════════════════════════════════════════════════════ */
    .feat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:18px; margin-bottom:1rem; }
    .feat-card { border:1px solid #e6eaef; border-radius:18px; overflow:hidden; background:#fff;
        transition:transform .2s,box-shadow .2s; cursor:pointer; }
    .feat-card:hover { transform:translateY(-4px); box-shadow:0 12px 32px rgba(15,23,42,0.16); }
    .feat-card__thumb { position:relative; aspect-ratio:16/9; overflow:hidden; background:#e6eaef; }
    .feat-card__thumb img { width:100%;height:100%;object-fit:cover;display:block;
        transition:transform .4s cubic-bezier(.4,0,.2,1); }
    .feat-card:hover .feat-card__thumb img { transform:scale(1.06); }
    .feat-card__cat { position:absolute;top:10px;left:10px;
        background:rgba(255,255,255,0.92);backdrop-filter:blur(4px);
        color:#b91c2a;font-size:0.64rem;font-weight:800;text-transform:uppercase;
        letter-spacing:0.5px;padding:4px 9px;border-radius:50px; }
    .feat-card__play { position:absolute;top:50%;left:50%;
        transform:translate(-50%,-50%) scale(0.8);
        width:48px;height:48px;border-radius:50%;background:#e11d2e;
        display:inline-flex;align-items:center;justify-content:center;
        opacity:0;transition:all .22s cubic-bezier(.4,0,.2,1);
        box-shadow:0 8px 22px rgba(225,29,46,0.5); }
    .feat-card:hover .feat-card__play { opacity:1; transform:translate(-50%,-50%) scale(1); }
    .feat-card__score { position:absolute;bottom:10px;left:10px;
        background:rgba(15,23,42,0.82);color:#fb7185;
        font-size:0.72rem;font-weight:800;padding:3px 9px;border-radius:50px; }
    .feat-card__body { padding:14px 16px 16px; }
    .feat-card__title { font-size:0.92rem;font-weight:800;line-height:1.3;letter-spacing:-0.2px;
        color:#0f172a;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden; }
    .feat-card__meta { display:flex;align-items:center;gap:8px;margin-top:10px;
        font-size:0.76rem;color:#6b7280; }
    .feat-card__chan { font-weight:700;color:#374151; }
    .feat-card__stats { display:flex;align-items:center;justify-content:space-between;
        margin-top:12px;padding-top:12px;border-top:1px solid #e6eaef; }
    .feat-card__stat { display:inline-flex;align-items:center;gap:5px;font-size:0.76rem;
        font-weight:600;color:#6b7280; }
    .feat-card__eng { font-size:0.76rem;font-weight:800;color:#16a34a; }

    /* ══════════════════════════════════════════════════════════════
       RANKING TABLE
    ══════════════════════════════════════════════════════════════ */
    .rank-table { display:flex;flex-direction:column; }
    .rank-head,.rank-row { display:grid;
        grid-template-columns:36px 1fr 110px 90px 80px 80px;
        align-items:center;gap:12px;padding:0 8px; }
    .rank-head { font-size:0.62rem;font-weight:800;text-transform:uppercase;letter-spacing:0.7px;
        color:#9ca3af;padding-bottom:10px;border-bottom:1px solid #e6eaef;margin-bottom:4px; }
    .rank-row { padding-top:9px;padding-bottom:9px;border-radius:12px;
        transition:background .15s;cursor:pointer; }
    .rank-row:hover { background:#fef2f2; }
    .rank-n { font-size:0.88rem;font-weight:800;color:#d1d5db;font-variant-numeric:tabular-nums; }
    .rank-prog { display:flex;align-items:center;gap:12px;min-width:0; }
    .rank-thumb { width:64px;height:38px;border-radius:8px;overflow:hidden;
        flex-shrink:0;background:#e6eaef;position:relative; }
    .rank-thumb img { width:100%;height:100%;object-fit:cover;display:block; }
    .rank-name { font-size:0.84rem;font-weight:700;letter-spacing:-0.2px;
        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#0f172a; }
    .rank-chan { font-size:0.72rem;color:#9ca3af;font-weight:600;margin-top:2px; }
    .rank-views { font-size:0.82rem;font-weight:700;color:#374151;font-variant-numeric:tabular-nums; }
    .rank-eng { font-size:0.82rem;font-weight:800;color:#16a34a;font-variant-numeric:tabular-nums; }

    /* ══════════════════════════════════════════════════════════════
       RECOMMENDED PLACEMENT CARD
    ══════════════════════════════════════════════════════════════ */
    .reco-card { background:linear-gradient(160deg,#0f172a,#293548);
        border-radius:22px;padding:20px;color:#fff;position:relative;
        overflow:hidden;box-shadow:0 8px 40px rgba(15,23,42,0.35); }
    .reco-card__glow { position:absolute;top:-50px;right:-50px;width:160px;height:160px;
        border-radius:50%;background:rgba(251,113,133,0.15); }
    .reco-card__tag { display:inline-flex;align-items:center;gap:6px;font-size:0.68rem;
        font-weight:800;text-transform:uppercase;letter-spacing:0.8px;color:#fb7185;
        position:relative;margin-bottom:14px; }
    .reco-card__thumb { position:relative;aspect-ratio:16/9;border-radius:14px;
        overflow:hidden;margin-bottom:14px;background:rgba(0,0,0,0.3); }
    .reco-card__thumb img { width:100%;height:100%;object-fit:cover;display:block; }
    .reco-card__play { position:absolute;top:50%;left:50%;
        transform:translate(-50%,-50%);width:44px;height:44px;border-radius:50%;
        background:rgba(225,29,46,0.92);display:inline-flex;align-items:center;
        justify-content:center;box-shadow:0 8px 20px rgba(0,0,0,0.35); }
    .reco-card__title { font-size:1rem;font-weight:800;line-height:1.3;
        letter-spacing:-0.2px;margin-bottom:8px; }
    .reco-card__chan { font-size:0.78rem;color:rgba(255,255,255,0.65);margin-bottom:14px; }
    .reco-card__scores { display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px; }
    .reco-card__scores > div { background:rgba(255,255,255,0.07);border:1px solid rgba(251,113,133,0.15);
        border-radius:12px;padding:10px 12px; }
    .reco-card__k { display:block;font-size:0.62rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.5px;color:rgba(255,255,255,0.5);margin-bottom:3px; }
    .reco-card__v { display:block;font-size:1.2rem;font-weight:800;color:#fb7185;letter-spacing:-0.5px; }
    .reco-card__cta { background:#e11d2e;color:#fff;border:none;border-radius:50px;
        padding:10px 20px;font-weight:800;font-size:0.84rem;width:100%;cursor:pointer;
        box-shadow:0 4px 14px rgba(225,29,46,0.4);transition:all .2s;font-family:inherit; }
    .reco-card__cta:hover { background:#b91c2a; transform:translateY(-2px);
        box-shadow:0 6px 20px rgba(225,29,46,0.5); }

    /* ══════════════════════════════════════════════════════════════
       SCORE BADGE
    ══════════════════════════════════════════════════════════════ */
    .score-badge { display:inline-block;padding:3px 10px;border-radius:6px;
        font-size:0.72rem;font-weight:800;font-variant-numeric:tabular-nums; }
    .score-badge.high { background:rgba(22,163,74,0.12);color:#16a34a; }
    .score-badge.mid  { background:rgba(246,224,94,0.18);color:#b45309; }
    .score-badge.low  { background:rgba(252,129,129,0.15);color:#dc2626; }

    /* ══════════════════════════════════════════════════════════════
       LIVE BADGE
    ══════════════════════════════════════════════════════════════ */
    .live-badge { display:inline-flex;align-items:center;gap:6px;font-size:0.62rem;
        font-weight:800;text-transform:uppercase;letter-spacing:0.6px;
        color:#16a34a;background:rgba(22,163,74,0.1);
        padding:3px 9px 3px 7px;border-radius:50px;vertical-align:middle;margin-left:8px; }
    .live-dot { width:7px;height:7px;border-radius:50%;background:#16a34a;display:inline-block; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Top channel feature cards ─────────────────────────── */
.chan-feat-strip {
    display:flex; gap:12px; flex-wrap:wrap; margin-bottom:1rem;
}
.chan-feat-card {
    background:#ffffff; border:1px solid #e6eaef;
    border-top:4px solid #e11d2e; border-radius:16px;
    padding:1rem 1.2rem; min-width:150px; flex:1;
    text-align:center; box-shadow:0 2px 14px rgba(15,23,42,0.07);
    transition:all 0.2s;
}
.chan-feat-card:hover { transform:translateY(-3px); box-shadow:0 8px 24px rgba(225,29,46,0.14); }
.chan-feat-card .cf-icon { font-size:1.8rem; margin-bottom:4px; }
.chan-feat-card .cf-name { font-weight:800; color:#0f172a; font-size:0.88rem; margin-bottom:4px; line-height:1.2; }
.chan-feat-card .cf-subs { color:#e11d2e; font-size:1.15rem; font-weight:800; margin-bottom:2px; }
.chan-feat-card .cf-type { color:#9ca3af; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.6px; }

/* ── Selected channel banner ────────────────────────────── */
.sel-channel-banner {
    background:linear-gradient(135deg,#0f172a,#293548);
    border-radius:16px; padding:1rem 1.6rem;
    display:flex; align-items:center; gap:16px;
    border:1px solid rgba(251,113,133,0.2);
    box-shadow:0 4px 20px rgba(15,23,42,0.25);
    margin-bottom:1rem;
}
.sel-channel-banner .scb-icon { font-size:2rem; }
.sel-channel-banner .scb-name { color:#fff; font-size:1.1rem; font-weight:800; }
.sel-channel-banner .scb-sub  { color:#fb7185; font-size:0.8rem; font-weight:500; }

/* ── Program grid cards ─────────────────────────────────── */
.pgc {
    background:#ffffff; border:1px solid #e6eaef;
    border-radius:18px; overflow:hidden;
    box-shadow:0 4px 20px rgba(15,23,42,0.07);
    margin-bottom:1rem; transition:transform 0.2s,box-shadow 0.2s;
    display:flex; flex-direction:column;
}
.pgc:hover { transform:translateY(-4px); box-shadow:0 12px 32px rgba(15,23,42,0.14); }
.pgc.dark { background:#0f172a; border-color:transparent; box-shadow:0 4px 24px rgba(15,23,42,0.3); }
.pgc img { width:100%; height:150px; object-fit:cover; display:block; }
.pgc .pgc-body { padding:1rem 1.15rem 0.5rem; flex:1; }
.pgc .pgc-rank {
    display:inline-block; background:#fee2e2; color:#b91c2a;
    font-size:0.65rem; font-weight:800; padding:2px 8px;
    border-radius:20px; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.4px;
}
.pgc.dark .pgc-rank { background:rgba(251,113,133,0.2); color:#fb7185; }
.pgc .pgc-cat {
    font-size:0.68rem; font-weight:700; text-transform:uppercase;
    letter-spacing:0.6px; color:#e11d2e; margin-bottom:3px;
}
.pgc.dark .pgc-cat { color:#fb7185; }
.pgc .pgc-name {
    font-size:0.96rem; font-weight:800; color:#0f172a;
    line-height:1.3; margin-bottom:8px;
    display:-webkit-box; -webkit-line-clamp:2;
    -webkit-box-orient:vertical; overflow:hidden;
}
.pgc.dark .pgc-name { color:#ffffff; }
.pgc .pgc-stats {
    display:flex; gap:12px; font-size:0.75rem;
    color:#6b7280; flex-wrap:wrap; margin-bottom:4px;
}
.pgc.dark .pgc-stats { color:rgba(255,255,255,0.55); }
.pgc .pgc-views { color:#e11d2e; font-weight:800; font-size:0.88rem; }
.pgc.dark .pgc-views { color:#fb7185; }
.pgc .pgc-divider {
    border:none; border-top:1px solid #e6eaef; margin:8px 0;
}
.pgc.dark .pgc-divider { border-top-color:rgba(251,113,133,0.15); }

/* ── Comparison queue bar ───────────────────────────────── */
.queue-strip { display:flex; gap:10px; flex-wrap:wrap; margin:0 0 14px; }
.queue-card {
    background:#fef2f2; border:1.5px solid #fecdd3;
    border-left:4px solid #e11d2e; border-radius:12px;
    padding:0.55rem 0.9rem; display:flex; align-items:center; gap:8px;
    box-shadow:0 2px 8px rgba(225,29,46,0.09);
}
.queue-card img { width:44px; height:30px; object-fit:cover; border-radius:6px; flex-shrink:0; }
.queue-card .qcn { font-weight:700; color:#0f172a; font-size:0.8rem; max-width:130px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.queue-card .qcv { font-size:0.7rem; color:#e11d2e; font-weight:600; }
</style>
""", unsafe_allow_html=True)


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


def thumb_url(video_id, quality="mqdefault"):
    """Return YouTube thumbnail URL for a video ID (no API call needed)."""
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"


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
            "video_id": vid,
            "title": snippet["title"],
            "date": snippet["publishedAt"][:10],
            "views": views,
            "likes": likes,
            "comments": comments,
            "engagement": round((likes / max(views, 1)) * 100, 2),
            "category_id": snippet.get("categoryId", ""),
            "url": f"https://youtube.com/watch?v={vid}",
            "thumbnail": thumb_url(vid),
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
<!-- TOP BAR -->
<div class="top-bar">
  <span><b>📺 YouTube Program Analyzer</b> &nbsp;|&nbsp; Hardcord Ad Targeting — Sri Lankan Broadcast</span>
  <span>
    <span class="pill">🇱🇰 100 Verified Channels</span>
    <span class="live-badge"><span class="live-dot"></span>Live Data</span>
  </span>
</div>

<!-- HERO -->
<div class="hero-header">
  <div class="hero-nav">
    <div class="hero-logo-wrap">
      <img src="https://logos-world.net/wp-content/uploads/2020/06/YouTube-Logo.png" alt="YouTube" height="28" style="display:block;">
    </div>
    <div class="hero-tagline">
      <span>📊 Program Compare</span>
      <span>🔀 Cross-Channel</span>
      <span>📈 Trending</span>
      <span class="pill" style="background:rgba(251,113,133,0.15);color:#fb7185;border-color:rgba(251,113,133,0.3);">🇱🇰 Sri Lanka</span>
    </div>
  </div>
  <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:2rem;">
    <div class="hero-body" style="flex:1;">
      <div style="font-size:0.72rem;color:#fb7185;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">
        🎯 HARDCORD AD TARGETING TOOL
      </div>
      <h1 style="font-size:2.4rem;">
        Find the <span class="accent">Best Programs</span><br>for Your <span style="color:#fff;">6-Second Ad</span>
      </h1>
      <p style="margin-top:0.6rem;max-width:520px;">
        Compare viewership, engagement &amp; trends across Sri Lanka's top YouTube channels.
        Identify the exact episodes where your hardcord ad gets maximum reach.
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin:0.8rem 0 1rem;">
        <span style="color:rgba(255,255,255,0.75);font-size:0.78rem;">✅ 100 Verified Sri Lankan Channels</span>
        <span style="color:rgba(255,255,255,0.75);font-size:0.78rem;">✅ Live YouTube API Data</span>
        <span style="color:rgba(255,255,255,0.75);font-size:0.78rem;">✅ Hardcord Score Algorithm</span>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;flex-shrink:0;min-width:240px;">
      <div style="background:rgba(251,113,133,0.12);border:1px solid rgba(251,113,133,0.25);border-radius:14px;padding:0.9rem 1rem;text-align:center;">
        <div style="color:#fb7185;font-size:1.5rem;font-weight:900;line-height:1;">100</div>
        <div style="color:rgba(255,255,255,0.45);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.8px;margin-top:2px;">Channels</div>
      </div>
      <div style="background:rgba(251,113,133,0.12);border:1px solid rgba(251,113,133,0.25);border-radius:14px;padding:0.9rem 1rem;text-align:center;">
        <div style="color:#fb7185;font-size:1.5rem;font-weight:900;line-height:1;">6s</div>
        <div style="color:rgba(255,255,255,0.45);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.8px;margin-top:2px;">Ad Format</div>
      </div>
      <div style="background:rgba(251,113,133,0.12);border:1px solid rgba(251,113,133,0.25);border-radius:14px;padding:0.9rem 1rem;text-align:center;">
        <div style="color:#fb7185;font-size:1.5rem;font-weight:900;line-height:1;">3</div>
        <div style="color:rgba(255,255,255,0.45);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.8px;margin-top:2px;">Modes</div>
      </div>
      <div style="background:rgba(251,113,133,0.12);border:1px solid rgba(251,113,133,0.25);border-radius:14px;padding:0.9rem 1rem;text-align:center;">
        <div style="color:#fb7185;font-size:1.5rem;font-weight:900;line-height:1;">Live</div>
        <div style="color:rgba(255,255,255,0.45);font-size:0.62rem;text-transform:uppercase;letter-spacing:0.8px;margin-top:2px;">YouTube Data</div>
      </div>
    </div>
  </div>
  <div style="display:flex;gap:0;margin-top:1.2rem;background:rgba(0,0,0,0.2);border-radius:12px;overflow:hidden;">
    <div style="flex:1;padding:0.7rem 1.2rem;border-right:1px solid rgba(255,255,255,0.07);">
      <div style="color:#fb7185;font-weight:800;font-size:0.95rem;">📊 Compare</div>
      <div style="color:rgba(255,255,255,0.45);font-size:0.67rem;">Up to 4 programs at once</div>
    </div>
    <div style="flex:1;padding:0.7rem 1.2rem;border-right:1px solid rgba(255,255,255,0.07);">
      <div style="color:#fb7185;font-weight:800;font-size:0.95rem;">🔀 Cross-Channel</div>
      <div style="color:rgba(255,255,255,0.45);font-size:0.67rem;">Compare across different channels</div>
    </div>
    <div style="flex:1;padding:0.7rem 1.2rem;border-right:1px solid rgba(255,255,255,0.07);">
      <div style="color:#fb7185;font-weight:800;font-size:0.95rem;">📈 Trending</div>
      <div style="color:rgba(255,255,255,0.45);font-size:0.67rem;">Live trending channel rankings</div>
    </div>
    <div style="flex:1;padding:0.7rem 1.2rem;">
      <div style="color:#fb7185;font-weight:800;font-size:0.95rem;">🎯 Ad Placement</div>
      <div style="color:rgba(255,255,255,0.45);font-size:0.67rem;">Best episode recommendations</div>
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
if "inter_slots" not in st.session_state:
    st.session_state.inter_slots = []   # list of {channel_id, channel_name, program_name}
if "inter_adding" not in st.session_state:
    st.session_state.inter_adding = {"channel_id": None, "channel_name": None}

st.markdown("""
<div class="kpi-strip">
  <div class="kpi-card">
    <div class="kpi-card__icon">📺</div>
    <div class="kpi-card__value">100</div>
    <div class="kpi-card__label">Verified Channels</div>
    <div class="kpi-card__delta up">▲ Sri Lanka</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-card__icon">🎯</div>
    <div class="kpi-card__value">9.84</div>
    <div class="kpi-card__label">Top Hardcord Score</div>
    <div class="kpi-card__delta up">▲ +1.2 today</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-card__icon">💬</div>
    <div class="kpi-card__value">6.8%</div>
    <div class="kpi-card__label">Avg Engagement</div>
    <div class="kpi-card__delta up">▲ +0.4%</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-card__icon">👁</div>
    <div class="kpi-card__value">248M</div>
    <div class="kpi-card__label">Total Reach</div>
    <div class="kpi-card__delta up">▲ +12M</div>
  </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🎭 Program Comparison", "🔀 Cross-Channel Compare", "📊 Trending Channels"])


# ===========================================================================
# TAB 1 — Program Comparison
# ===========================================================================

PLOTLY_COLORS = ["#e11d2e", "#0066FF", "#f59e0b", "#7c3aed", "#0891b2"]


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
        line=dict(color="#e11d2e", width=2.5),
        marker=dict(size=8, color="#e11d2e",
                    line=dict(color="white", width=1.5)),
        hovertemplate=(
            "<b>%{customdata}</b><br>"
            "Views: <b>%{y:,}</b><br>"
            "Date: %{x}"
            "<extra></extra>"
        ),
        customdata=[e["title"][:65] for e in eps],
        fill="tozeroy",
        fillcolor="rgba(225,29,46,0.07)",
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

    # ── Featured top-4 channels strip ───────────────────────────────────────
    top4 = chan_stats[:4]
    max_subs = top4[0]["Subscribers"] if top4 else 1
    feat_cols = st.columns(4)
    type_icons = {"📺 TV Channel": "📺", "🎥 Creator": "🎥", "🎵 Music": "🎵",
                  "📰 News": "📰", "🎤 Reality": "🎤", "📻 Radio": "📻",
                  "🎮 Gaming": "🎮", "🧒 Kids": "🧒", "💻 Tech": "💻", "⚽ Sports": "⚽"}
    for col, c in zip(feat_cols, top4):
        icon = type_icons.get(c["Type"], "📺")
        pct = int(c["Subscribers"] / max(max_subs, 1) * 100)
        col.markdown(f"""
        <div class="chan-feat-card">
            <div class="cf-icon">{icon}</div>
            <div class="cf-name">{c['Channel']}</div>
            <div class="cf-subs">{format_number(c['Subscribers'])}</div>
            <div class="cf-type">SUBSCRIBERS</div>
            <div style="background:#e6eaef;border-radius:4px;height:5px;margin-top:10px;overflow:hidden;">
                <div style="background:linear-gradient(90deg,#e11d2e,#fb7185);
                    height:100%;width:{pct}%;border-radius:4px;"></div>
            </div>
            <div style="font-size:0.6rem;color:#9ca3af;margin-top:3px;">{c['Type']}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Search + type filter ─────────────────────────────────────────────────
    all_ch_types = sorted({c["Type"] for c in chan_stats})

    filt_a, filt_b = st.columns([1, 2])
    with filt_a:
        search_q = st.text_input("", placeholder="🔍  Search channels by name…", key="chan_search",
                                 label_visibility="collapsed")
    with filt_b:
        sel_types_ms = st.multiselect(
            "", all_ch_types, default=all_ch_types,
            key="sel_types_ms", label_visibility="collapsed",
            placeholder="Filter by channel type…",
        )

    # Filter channels
    sel_set = set(sel_types_ms) if sel_types_ms else set(all_ch_types)
    filtered_chans = [
        c for c in chan_stats
        if c["Type"] in sel_set
        and (not search_q or search_q.lower() in c["Channel"].lower())
    ]

    chan_df = pd.DataFrame([{
        "Rank": c["Rank"],
        "Type": c["Type"],
        "Channel": c["Channel"],
        "Subscribers": c["Subscribers"],
        "Total Views": c["Total Views"],
        "Total Videos": c["Total Videos"],
    } for c in filtered_chans])

    event = st.dataframe(
        chan_df, use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="chan_table",
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", format="%d"),
            "Subscribers": st.column_config.NumberColumn("Subscribers", format="%.2f"),
            "Total Views": st.column_config.NumberColumn("Total Views", format="%.2f"),
            "Total Videos": st.column_config.NumberColumn("Total Videos", format="%d"),
        },
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
        st.markdown("""
        <div style="background:#fef2f2;border:1.5px dashed #fecdd3;border-radius:14px;
            padding:1.2rem;text-align:center;color:#b91c2a;font-weight:600;">
            👆 Click any row in the table above to load its programs
        </div>
        """, unsafe_allow_html=True)
        return

    # Selected channel banner
    ch_meta = next((c for c in chan_stats if c["channel_id"] == st.session_state.selected_channel_id), {})
    st.markdown(f"""
    <div class="sel-channel-banner">
        <div class="scb-icon">📺</div>
        <div>
            <div class="scb-name">{st.session_state.selected_channel_name}</div>
            <div class="scb-sub">
                {format_number(ch_meta.get('Subscribers', 0))} subscribers &nbsp;·&nbsp;
                {format_number(ch_meta.get('Total Videos', 0))} videos &nbsp;·&nbsp;
                Showing programs from {date_from} → {date_to}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
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

    # ── Comparison queue (thumbnail cards) ──────────────────────────────────
    if st.session_state.compare:
        st.markdown("""
        <div class="section-header" style="margin-top:0.5rem;">
            <span class="step-badge" style="background:#b91c2a;">🗂️</span>
            <span class="section-title">Queued for Comparison</span>
        </div>
        """, unsafe_allow_html=True)
        queue_html = '<div class="queue-strip">'
        for pname in st.session_state.compare:
            pdata_q = programs.get(pname, {})
            eps_q = pdata_q.get("episodes", [])
            t_q = max(eps_q, key=lambda e: e["views"]).get("thumbnail", "") if eps_q else ""
            views_q = format_number(pdata_q.get("total_views", 0))
            img_tag = f'<img src="{t_q}" onerror="this.style.display:none">' if t_q else ""
            queue_html += (
                f'<div class="queue-card">{img_tag}'
                f'<div><div class="qcn">{pname[:30]}</div>'
                f'<div class="qcv">👁 {views_q}</div></div></div>'
            )
        queue_html += "</div>"
        st.markdown(queue_html, unsafe_allow_html=True)
        # Remove buttons in a row
        rm_cols = st.columns(len(st.session_state.compare))
        for i, (pname, col) in enumerate(zip(list(st.session_state.compare), rm_cols)):
            if col.button(f"✖ Remove", key=f"rm_{i}", type="secondary"):
                st.session_state.compare.remove(pname)
                st.rerun()
        st.markdown("---")

    # ── Sort + filter controls ───────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    with ctrl1:
        sort_by = st.selectbox("Sort by", ["Most Views", "Best Engagement", "Most Episodes", "Growing Trend"], key="prog_sort")
    with ctrl2:
        all_prog_types = sorted({p["category"] for _, p in ranked_programs})
        type_filter = st.multiselect("Filter type", all_prog_types, default=all_prog_types, key="prog_type_filter")
    with ctrl3:
        prog_search = st.text_input("🔍 Search", placeholder="Program name…", key="prog_search")

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

    # ── Featured top-3 cards ────────────────────────────────────────────────
    featured3 = filtered[:3]
    if featured3:
        st.markdown("**🏆 Top Programs — Best Ad Placement Opportunities**")
        feat_cols = st.columns(3)
        for col, (pname, pdata) in zip(feat_cols, featured3):
            eps = pdata.get("episodes", [])
            top_ep = max(eps, key=lambda e: e["views"]) if eps else None
            thumb = top_ep.get("thumbnail", "") if top_ep else ""
            eng = round(sum(e["engagement"] for e in eps) / max(len(eps), 1), 1) if eps else 0
            score = round((pdata["total_views"] / 1_000_000) * (1 + eng/100), 1)
            already = pname in st.session_state.compare
            full = len(st.session_state.compare) >= 4

            img_html = f'<img src="{thumb}" onerror="this.style.display=\'none\'">' if thumb else ""
            col.markdown(f"""
            <div class="feat-card">
                <div class="feat-card__thumb">
                    {img_html}
                    <span class="feat-card__cat">{pdata["category"]}</span>
                    <span class="feat-card__play">▶</span>
                    <span class="feat-card__score">🎯 {score}</span>
                </div>
                <div class="feat-card__body">
                    <div class="feat-card__title">{pname}</div>
                    <div class="feat-card__meta">
                        <span class="feat-card__chan">{st.session_state.selected_channel_name[:20]}</span>
                        <span>·</span>
                        <span>{format_number(pdata["total_views"])} views</span>
                    </div>
                    <div class="feat-card__stats">
                        <span class="feat-card__stat">🎞 {pdata["episode_count"]} eps</span>
                        <span class="feat-card__eng">{eng}% eng.</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if already:
                col.markdown('<p style="text-align:center;color:#16a34a;font-weight:700;font-size:0.82rem;margin:4px 0 10px;">✅ Added</p>', unsafe_allow_html=True)
            elif not full:
                if col.button("➕ Add to Compare", key=f"fadd_{pname[:12]}"):
                    st.session_state.compare.append(pname)
                    st.toast(f"➕ Added: {pname[:30]}", icon="🎬")
                    st.rerun()
        st.markdown("---")

    # ── Ranking table for programs 4+ ───────────────────────────────────────
    rest = filtered[3:20]
    if rest:
        st.markdown("**📋 Full Program Ranking**")
        st.markdown("""
        <div class="rank-table">
          <div class="rank-head">
            <span>#</span><span>Program</span><span>Category</span>
            <span>Views</span><span>Eng.</span><span>Action</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        for idx, (pname, pdata) in enumerate(rest, start=4):
            eps = pdata.get("episodes", [])
            top_ep = max(eps, key=lambda e: e["views"]) if eps else None
            thumb = top_ep.get("thumbnail", "") if top_ep else ""
            eng = round(sum(e["engagement"] for e in eps) / max(len(eps), 1), 1) if eps else 0
            already = pname in st.session_state.compare
            full = len(st.session_state.compare) >= 4

            img_html = f'<img src="{thumb}" onerror="this.style.display=\'none\'">' if thumb else ""
            st.markdown(f"""
            <div class="rank-row">
              <span class="rank-n">{str(idx).zfill(2)}</span>
              <span class="rank-prog">
                <span class="rank-thumb">{img_html}</span>
                <span>
                  <span class="rank-name">{pname[:40]}</span>
                  <span class="rank-chan">{st.session_state.selected_channel_name[:20]}</span>
                </span>
              </span>
              <span><span class="score-badge {'high' if eng > 6 else 'mid' if eng > 3 else 'low'}">{pdata["category"][:14]}</span></span>
              <span class="rank-views">{format_number(pdata["total_views"])}</span>
              <span class="rank-eng">{eng}%</span>
              <span>{"✅" if already else ""}</span>
            </div>
            """, unsafe_allow_html=True)
            if not already and not full:
                if st.button("Add", key=f"radd_{idx}_{pname[:8]}"):
                    st.session_state.compare.append(pname)
                    st.toast(f"➕ Added: {pname[:30]}", icon="🎬")
                    st.rerun()

    if not st.session_state.compare:
        st.markdown("""
        <div style="background:#fef2f2;border:1.5px dashed #fecdd3;border-radius:14px;
            padding:1.4rem;text-align:center;color:#b91c2a;font-weight:600;margin-top:0.5rem;">
            ➕ Click <b>Add to Compare</b> on any program card above to build your comparison
        </div>
        """, unsafe_allow_html=True)
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
    best_thumb = best_ep.get("thumbnail", thumb_url(best_ep.get("video_id", "")))
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0f172a, #293548);
        border-radius: 18px; padding: 0; margin-bottom: 1rem;
        box-shadow: 0 8px 32px rgba(15,23,42,0.45); color: white;
        display:flex; overflow:hidden; border:1px solid rgba(251,113,133,0.2);
    ">
        <img src="{best_thumb}" alt="thumbnail"
             style="width:220px; min-width:220px; object-fit:cover; display:block; flex-shrink:0;"
             onerror="this.style.display='none'">
        <div style="padding:1.2rem 1.6rem; flex:1;">
            <div style="font-size:0.75rem; text-transform:uppercase; letter-spacing:1.2px;
                color:#fb7185; font-weight:700; margin-bottom:6px;">
                🎯 Best Episode to Place Your Ad RIGHT NOW
            </div>
            <div style="font-size:1.35rem; font-weight:800; line-height:1.25; margin-bottom:8px; color:#fff;">
                {best_ep['title'][:70]}
            </div>
            <div style="display:flex; gap:20px; flex-wrap:wrap; font-size:0.88rem;
                color:rgba(255,255,255,0.8); margin-bottom:12px;">
                <span>👁 <b style="color:#fb7185;">{format_number(best_ep['views'])}</b> views</span>
                <span>📺 <b>{best_prog['name'][:25]}</b></span>
                <span>📅 {best_ep['date']}</span>
                <span>💬 {best_ep['engagement']}% engagement</span>
            </div>
            <a href="{best_ep['url']}" target="_blank"
               style="background:#e11d2e; color:#fff; text-decoration:none;
                      font-weight:800; font-size:0.85rem; padding:7px 20px;
                      border-radius:50px; display:inline-block; letter-spacing:0.3px;">
                ▶ Watch Episode
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
            t3cols = st.columns(len(top3))
            for col, e in zip(t3cols, top3):
                t = e.get("thumbnail", thumb_url(e.get("video_id", "")))
                col.markdown(f"""
                <div style="border-radius:12px;overflow:hidden;background:#fff;
                    box-shadow:0 4px 16px rgba(0,0,0,0.1);border:1px solid #f0f0f0;">
                    <a href="{e['url']}" target="_blank" style="text-decoration:none;">
                        <div style="position:relative;">
                            <img src="{t}" style="width:100%;display:block;aspect-ratio:16/9;object-fit:cover;"
                                 onerror="this.src='https://img.youtube.com/vi/default/mqdefault.jpg'">
                            <div style="position:absolute;bottom:6px;right:8px;
                                background:rgba(0,0,0,0.75);color:#fff;
                                font-size:0.7rem;font-weight:700;padding:2px 8px;
                                border-radius:4px;">▶ Watch</div>
                        </div>
                        <div style="padding:10px 12px;">
                            <div style="font-size:0.82rem;font-weight:700;color:#111;
                                line-height:1.3;margin-bottom:5px;
                                display:-webkit-box;-webkit-line-clamp:2;
                                -webkit-box-orient:vertical;overflow:hidden;">
                                {e['title'][:65]}</div>
                            <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:0.75rem;color:#6b7280;">
                                <span>👁 <b style="color:#e11d2e;">{format_number(e['views'])}</b></span>
                                <span>💬 {e['engagement']}%</span>
                                <span>📅 {e['date']}</span>
                            </div>
                        </div>
                    </a>
                </div>
                """, unsafe_allow_html=True)

            ep_disp = pd.DataFrame([{
                "Thumbnail": e.get("thumbnail", thumb_url(e.get("video_id", ""))),
                "Date": e["date"], "Episode": e["title"],
                "Views": format_number(e["views"]), "Likes": format_number(e["likes"]),
                "Comments": format_number(e["comments"]), "Engagement %": f"{e['engagement']}%",
                "Watch": e["url"],
            } for e in sorted(a["episodes"], key=lambda e: e["date"], reverse=True)])
            st.dataframe(ep_disp, use_container_width=True, hide_index=True,
                         column_config={
                             "Thumbnail": st.column_config.ImageColumn("🖼", width="small"),
                             "Watch": st.column_config.LinkColumn("▶️", display_text="Watch"),
                         })

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
# TAB 2 — Cross-Channel Comparison
# ===========================================================================

def render_inter_channel():
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">🔀</span>
        <span class="section-title">Cross-Channel Program Comparison</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Compare programs from **different channels** side by side — e.g. Deweni Inima (TV Derana) vs Pata Kurullo (Hiru TV).")

    # ── Shared date range ────────────────────────────────────────────────────
    preset_cols = st.columns(6)
    presets = {"7D": 7, "14D": 14, "30D": 30, "60D": 60, "90D": 90, "Custom": None}
    if "inter_date_preset" not in st.session_state:
        st.session_state.inter_date_preset = "30D"
    for col, (label, days) in zip(preset_cols, presets.items()):
        active = st.session_state.inter_date_preset == label
        if col.button(label, key=f"inter_preset_{label}",
                      type="primary" if active else "secondary"):
            st.session_state.inter_date_preset = label
            st.rerun()

    preset_days = presets.get(st.session_state.inter_date_preset)
    default_from = date.today() - timedelta(days=preset_days or 30)
    ic1, ic2, ic3 = st.columns([1, 1, 1])
    with ic1:
        inter_from = st.date_input("From", value=default_from, key="inter_from")
    with ic2:
        inter_to = st.date_input("To", value=date.today(), key="inter_to")
    with ic3:
        inter_scan = st.select_slider("Scan depth", options=[200, 500, 1000, 1500, 2500],
                                      value=500, key="inter_scan")

    if inter_from > inter_to:
        st.error("'From' date must be before 'To' date.")
        return

    st.markdown("---")

    # ── Slot cards (queued programs) ─────────────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">1</span>
        <span class="section-title">Build Your Comparison (up to 4 programs)</span>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Loading channel list…"):
        chan_stats = get_curated_channel_stats()
    chan_lookup = {c["channel_id"]: c for c in chan_stats}

    # Display existing slots as cards
    if st.session_state.inter_slots:
        slot_cols = st.columns(len(st.session_state.inter_slots))
        for i, slot in enumerate(st.session_state.inter_slots):
            with slot_cols[i]:
                st.markdown(f"""
                <div style="background:#fef2f2;border:1.5px solid #fecdd3;
                    border-left:4px solid #e11d2e;border-radius:10px;
                    padding:0.8rem 1rem;margin-bottom:0.5rem;">
                    <div style="font-size:0.72rem;color:#6b7280;text-transform:uppercase;
                        letter-spacing:0.5px;margin-bottom:2px;">Slot {i+1}</div>
                    <div style="font-weight:700;color:#0f172a;font-size:0.95rem;">
                        📺 {slot['channel_name']}</div>
                    <div style="color:#e11d2e;font-weight:600;font-size:0.88rem;
                        margin-top:2px;">🎬 {slot['program_name'][:32]}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("✖ Remove", key=f"inter_rm_{i}"):
                    st.session_state.inter_slots.pop(i)
                    st.rerun()

    # ── Add new slot ─────────────────────────────────────────────────────────
    if len(st.session_state.inter_slots) < 4:
        with st.expander(
            f"➕ Add Program (slot {len(st.session_state.inter_slots)+1} of 4)",
            expanded=len(st.session_state.inter_slots) == 0,
        ):
            # Channel search
            ch_search = st.text_input("🔍 Search channel", placeholder="e.g. Hiru, Derana…",
                                      key="inter_ch_search")
            filtered_ch = [
                c for c in chan_stats
                if not ch_search or ch_search.lower() in c["Channel"].lower()
            ]
            ch_options = {c["Channel"]: c["channel_id"] for c in filtered_ch}

            if not ch_options:
                st.warning("No channels match your search.")
            else:
                chosen_name = st.selectbox(
                    "Select channel", list(ch_options.keys()), key="inter_ch_pick"
                )
                chosen_id = ch_options[chosen_name]

                # Load programs for selected channel
                with st.spinner(f"Loading programs from {chosen_name}…"):
                    progs = get_channel_programs(
                        chosen_id,
                        inter_from.strftime("%Y-%m-%d"),
                        inter_to.strftime("%Y-%m-%d"),
                        inter_scan,
                    )

                if not progs:
                    st.warning("No programs found in this date range for that channel. Try a wider range.")
                else:
                    prog_ranked = sorted(progs.items(),
                                         key=lambda x: x[1]["total_views"], reverse=True)
                    prog_options = [
                        f"{name}  |  👁 {format_number(p['total_views'])}  |  🎞 {p['episode_count']} eps"
                        for name, p in prog_ranked[:40]
                    ]
                    prog_name_map = {
                        f"{name}  |  👁 {format_number(p['total_views'])}  |  🎞 {p['episode_count']} eps": name
                        for name, p in prog_ranked[:40]
                    }
                    chosen_prog_label = st.selectbox(
                        "Select program", prog_options, key="inter_prog_pick"
                    )
                    chosen_prog_name = prog_name_map[chosen_prog_label]

                    # Preview
                    prev = progs[chosen_prog_name]
                    pc1, pc2, pc3 = st.columns(3)
                    pc1.metric("Total Views", format_number(prev["total_views"]))
                    pc2.metric("Episodes", prev["episode_count"])
                    pc3.metric("Category", prev["category"])

                    already = any(
                        s["channel_id"] == chosen_id and s["program_name"] == chosen_prog_name
                        for s in st.session_state.inter_slots
                    )
                    if already:
                        st.info("This program is already in your comparison.")
                    elif st.button("➕ Add to Comparison", key="inter_add_btn", type="primary"):
                        st.session_state.inter_slots.append({
                            "channel_id": chosen_id,
                            "channel_name": chosen_name,
                            "program_name": chosen_prog_name,
                        })
                        st.toast(f"✅ Added: {chosen_prog_name[:30]} ({chosen_name})", icon="🎬")
                        st.rerun()

    if len(st.session_state.inter_slots) < 2:
        st.info("👆 Add at least 2 programs from different channels to see the comparison.")
        return

    if st.button("🗑️ Clear All", key="inter_clear"):
        st.session_state.inter_slots = []
        st.rerun()

    st.markdown("---")

    # ── Fetch all slot data & run analysis ───────────────────────────────────
    st.markdown("""
    <div class="section-header">
        <span class="step-badge">2</span>
        <span class="section-title">Comparison Dashboard</span>
    </div>
    """, unsafe_allow_html=True)

    analyses = []
    load_bar = st.progress(0, text="Loading program data…")
    for i, slot in enumerate(st.session_state.inter_slots):
        load_bar.progress(
            int((i / len(st.session_state.inter_slots)) * 90),
            text=f"Fetching {slot['program_name'][:25]} ({slot['channel_name']})…"
        )
        progs = get_channel_programs(
            slot["channel_id"],
            inter_from.strftime("%Y-%m-%d"),
            inter_to.strftime("%Y-%m-%d"),
            inter_scan,
        )
        if slot["program_name"] in progs:
            a = analyze_program(slot["program_name"], progs[slot["program_name"]])
            # Tag with channel name so charts label correctly
            a["label"] = f"{slot['program_name'][:22]} ({slot['channel_name'][:12]})"
            a["name"] = a["label"]
            analyses.append(a)
    load_bar.progress(100, text="Done!")
    load_bar.empty()

    if not analyses:
        st.warning("Could not load data for the selected programs. Try widening the date range.")
        return

    ranked_analyses = sorted(analyses, key=lambda a: a["hardcord"], reverse=True)

    # ── Ad Placement Recommendation Banner ───────────────────────────────────
    best_ep = max((e for a in analyses for e in a["episodes"]), key=lambda e: e["views"])
    best_prog = next(a for a in analyses if best_ep in a["episodes"])
    best_thumb2 = best_ep.get("thumbnail", thumb_url(best_ep.get("video_id", "")))
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0f172a,#293548);
        border-radius:18px;padding:0;margin-bottom:1rem;
        box-shadow:0 8px 32px rgba(15,23,42,0.45);color:white;
        display:flex;overflow:hidden;border:1px solid rgba(251,113,133,0.2);">
        <img src="{best_thumb2}" alt="thumbnail"
             style="width:220px;min-width:220px;object-fit:cover;display:block;flex-shrink:0;"
             onerror="this.style.display='none'">
        <div style="padding:1.2rem 1.6rem;flex:1;">
            <div style="font-size:0.75rem;text-transform:uppercase;letter-spacing:1.2px;
                color:#fb7185;font-weight:700;margin-bottom:6px;">🎯 Best Episode to Place Your Ad RIGHT NOW</div>
            <div style="font-size:1.35rem;font-weight:800;line-height:1.25;margin-bottom:8px;color:#fff;">
                {best_ep['title'][:70]}</div>
            <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:0.88rem;
                color:rgba(255,255,255,0.8);margin-bottom:12px;">
                <span>👁 <b style="color:#fb7185;">{format_number(best_ep['views'])}</b> views</span>
                <span>📺 <b>{best_prog['name'][:30]}</b></span>
                <span>📅 {best_ep['date']}</span>
                <span>💬 {best_ep['engagement']}% engagement</span>
            </div>
            <a href="{best_ep['url']}" target="_blank"
               style="background:#e11d2e;color:#fff;text-decoration:none;
                      font-weight:800;font-size:0.85rem;padding:7px 20px;
                      border-radius:50px;display:inline-block;letter-spacing:0.3px;">
                ▶ Watch Episode</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Hardcord Priority Ranking ─────────────────────────────────────────────
    st.markdown("##### 🏆 Hardcord Priority Ranking")
    max_hc = max((a["hardcord"] for a in analyses), default=1)
    rank_df = pd.DataFrame([{
        "Priority": f"#{i+1}",
        "Program": a["name"],
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

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("##### 📈 Episode Views Trend — hover for episode details")
    st.plotly_chart(_plotly_line(analyses), use_container_width=True)
    st.caption("Click legend to show/hide. Drag to zoom. Double-click to reset.")

    cr1, cr2 = st.columns([1, 1])
    with cr1:
        st.markdown("##### 📊 Avg Views per Episode")
        st.plotly_chart(_plotly_bar(ranked_analyses), use_container_width=True)
    with cr2:
        st.markdown("##### 🕸️ Radar Comparison")
        st.caption("Scores normalised across all compared programs.")
        st.plotly_chart(_plotly_radar(ranked_analyses), use_container_width=True)

    st.markdown("---")

    # ── Per-program detail ────────────────────────────────────────────────────
    st.markdown("##### 🔍 Per-Program Detail")
    for a in ranked_analyses:
        with st.expander(
            f"{a['trend_icon']} {a['name']} — {format_number(a['avg_views'])} avg views · {a['trend']}",
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

            st.plotly_chart(_plotly_episode_detail(a), use_container_width=True)

            top3 = sorted(a["episodes"], key=lambda e: e["views"], reverse=True)[:3]
            st.markdown("**🎯 Best episodes to place your ad:**")
            t3cols = st.columns(len(top3))
            for col, e in zip(t3cols, top3):
                t = e.get("thumbnail", thumb_url(e.get("video_id", "")))
                col.markdown(f"""
                <div style="border-radius:12px;overflow:hidden;background:#fff;
                    box-shadow:0 4px 16px rgba(0,0,0,0.1);border:1px solid #f0f0f0;">
                    <a href="{e['url']}" target="_blank" style="text-decoration:none;">
                        <div style="position:relative;">
                            <img src="{t}" style="width:100%;display:block;aspect-ratio:16/9;object-fit:cover;"
                                 onerror="this.src='https://img.youtube.com/vi/default/mqdefault.jpg'">
                            <div style="position:absolute;bottom:6px;right:8px;
                                background:rgba(0,0,0,0.75);color:#fff;
                                font-size:0.7rem;font-weight:700;padding:2px 8px;
                                border-radius:4px;">▶ Watch</div>
                        </div>
                        <div style="padding:10px 12px;">
                            <div style="font-size:0.82rem;font-weight:700;color:#111;
                                line-height:1.3;margin-bottom:5px;
                                display:-webkit-box;-webkit-line-clamp:2;
                                -webkit-box-orient:vertical;overflow:hidden;">
                                {e['title'][:65]}</div>
                            <div style="display:flex;gap:10px;flex-wrap:wrap;font-size:0.75rem;color:#6b7280;">
                                <span>👁 <b style="color:#e11d2e;">{format_number(e['views'])}</b></span>
                                <span>💬 {e['engagement']}%</span>
                                <span>📅 {e['date']}</span>
                            </div>
                        </div>
                    </a>
                </div>
                """, unsafe_allow_html=True)

            ep_disp = pd.DataFrame([{
                "Thumbnail": e.get("thumbnail", thumb_url(e.get("video_id", ""))),
                "Date": e["date"], "Episode": e["title"],
                "Views": format_number(e["views"]), "Likes": format_number(e["likes"]),
                "Comments": format_number(e["comments"]), "Engagement %": f"{e['engagement']}%",
                "Watch": e["url"],
            } for e in sorted(a["episodes"], key=lambda e: e["date"], reverse=True)])
            st.dataframe(ep_disp, use_container_width=True, hide_index=True,
                         column_config={
                             "Thumbnail": st.column_config.ImageColumn("🖼", width="small"),
                             "Watch": st.column_config.LinkColumn("▶️", display_text="Watch"),
                         })

            csv_buf = io.StringIO()
            pd.DataFrame(a["episodes"]).to_csv(csv_buf, index=False)
            st.download_button(
                f"⬇️ Download CSV", csv_buf.getvalue(),
                file_name=f"inter_{re.sub(r'[^A-Za-z0-9]+','_',a['name'])[:30]}_{inter_to}.csv",
                mime="text/csv", key=f"inter_dl_{a['name']}",
            )


# ===========================================================================
# Render tabs
# ===========================================================================

with tab1:
    render_program_comparison()

with tab2:
    render_inter_channel()

with tab3:
    render_trending_channels()
