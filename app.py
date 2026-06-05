"""
YouTube Top Program Analysis — Web Interface
Hardcord Ad Targeting Tool for 6-Second Commercial Placements

Tab 1: Trending Channels (region-wide rankings)
Tab 2: Program Comparison (channel -> programs -> compare -> ad placement)
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

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", os.getenv("YOUTUBE_API_KEY", ""))
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

# Used for the channel comparison table in Tab 1 / Program Comparison Step 1
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
    # ── Gaming Channels ──────────────────────────────────────────────────
    "Master Brothers FF":     ("UCnLDg6H44ShnTB3TWLw_R0A", "🎮 Gaming"),
    "Gaming With Kaniya":     ("UCAYGhFThlHe-3ugwJaUE0sA", "🎮 Gaming"),
    "DLP Gaming":             ("UC0-UFP1d6OeVtl2VXYSquIA", "🎮 Gaming"),
}

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="YouTube Program Analyzer — Hardcord Targeting",
    page_icon="📺",
    layout="wide",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.8rem; border-radius: 12px; margin-bottom: 1.2rem; text-align: center;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 1.9rem; }
    .main-header p  { color: #a8b2d8; margin: 0.4rem 0 0; font-size: 0.95rem; }
    .metric-card {
        background: #16213e; border: 1px solid #0f3460;
        border-radius: 10px; padding: 0.9rem; text-align: center;
    }
    .metric-card h2 { color: #e94560; margin: 0; font-size: 1.7rem; }
    .metric-card p  { color: #a8b2d8; margin: 0; font-size: 0.8rem; }
    .prog-card {
        background: #16213e; border-left: 4px solid #e94560;
        border-radius: 8px; padding: 0.7rem 1rem; margin-bottom: 0.5rem;
    }
    .stButton > button {
        background: linear-gradient(135deg, #e94560, #0f3460);
        color: white; border: none; border-radius: 8px;
        padding: 0.45rem 1rem; font-weight: bold; width: 100%;
    }
    .step-badge {
        background: #e94560; color: #fff; border-radius: 50%;
        padding: 2px 10px; font-weight: bold; margin-right: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(endpoint, params):
    params["key"] = YOUTUBE_API_KEY
    resp = requests.get(f"{YT_API_BASE}/{endpoint}", params=params, timeout=30)
    if resp.status_code == 403:
        st.error("⚠️ API quota exceeded or key invalid. Try again later or reduce the date range / scan depth.")
        st.stop()
    resp.raise_for_status()
    return resp.json()


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
# Trending (Tab 1)
# ---------------------------------------------------------------------------

def fetch_trending_videos(region_code, max_results, category_id=None):
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


# ---------------------------------------------------------------------------
# Program detection (Tab 2)
# ---------------------------------------------------------------------------

def extract_program_name(title):
    """Extract the series/program name from an episode title."""
    t = title.strip()
    for dl in ["|", "–", "—", ":", "#"]:
        if dl in t:
            t = t.split(dl)[0]
            break
    t = re.sub(r"(?i)\bepisode\b.*", "", t)
    t = re.sub(r"(?i)\bep\.?\s*\d.*", "", t)
    t = re.sub(r"\d{2,}.*", "", t)            # trailing episode numbers / dates
    t = re.sub(r"[\(\[].*?[\)\]]", "", t)     # bracketed extras (keep core name)
    t = t.strip(" -–—|.")
    return t.strip()


# Keyword sets for program classification
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
    """Classify a program as Teledrama / News / Reality / Music / Talk / Other."""
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
    """Fetch stats for all curated Sri Lankan channels."""
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
    """
    Pull a channel's uploads within a date range, group into programs/series.
    Returns dict: program_name -> {episodes: [...], total_views, avg_views, ...}
    Each episode: {title, date, views, likes, comments, engagement, url}
    """
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

    # Fetch full stats
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
    """Compute analysis metrics for a single program."""
    eps = prog["episodes"]
    count = len(eps)
    total_views = prog["total_views"]
    avg_views = prog["avg_views"]
    highest = max(eps, key=lambda e: e["views"])
    lowest = min(eps, key=lambda e: e["views"])
    avg_eng = round(sum(e["engagement"] for e in eps) / max(count, 1), 2)

    # Trend: last 5 vs first 5 by date
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
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h1>📺 YouTube Program Analyzer</h1>
    <p>Hardcord Ad Targeting — Compare Programs & Find the Best Episodes for 6-Second Ad Placement</p>
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
    st.session_state.compare = []   # list of program names (within selected channel)

tab1, tab2 = st.tabs(["🎭 Program Comparison", "📊 Trending Channels"])

# ===========================================================================
# TAB 1 — Program Comparison (the main reworked tool)
# ===========================================================================

with tab1:
    # ---- Date range (drives all episode data) ----
    st.markdown("#### 📅 Date Range")
    dc1, dc2, dc3 = st.columns([1, 1, 1])
    with dc1:
        date_from = st.date_input("From", value=date.today() - timedelta(days=30), key="date_from")
    with dc2:
        date_to = st.date_input("To", value=date.today(), key="date_to")
    with dc3:
        max_scan = st.select_slider("Scan depth (uploads to check)",
                                    options=[200, 500, 1000, 1500, 2500], value=1000)
    if date_from > date_to:
        st.error("'From' date must be before 'To' date.")
        st.stop()

    st.markdown("---")

    # ---- STEP 1: Channel Comparison ----
    st.markdown('<h4><span class="step-badge">1</span>Channel Comparison</h4>', unsafe_allow_html=True)
    st.caption("Sri Lankan channels ranked by total views. Click a row to select a channel.")

    with st.spinner("Loading channels..."):
        chan_stats = get_curated_channel_stats()

    # Type filter for channel table
    all_ch_types = sorted({c["Type"] for c in chan_stats})
    sel_types = st.multiselect("Filter channel type", all_ch_types, default=all_ch_types, key="ch_type_filter")
    filtered_chans = [c for c in chan_stats if c["Type"] in sel_types]

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
            st.session_state.compare = []   # reset comparison on channel change

    if not st.session_state.selected_channel_id:
        st.info("👆 Click a channel above to load its programs.")
        st.stop()

    st.success(f"Selected channel: **{st.session_state.selected_channel_name}**")
    st.markdown("---")

    # ---- STEP 2: Program list for selected channel ----
    st.markdown('<h4><span class="step-badge">2</span>Programs in Date Range</h4>', unsafe_allow_html=True)
    st.caption(f"Top programs on **{st.session_state.selected_channel_name}** "
               f"from {date_from} to {date_to}, ranked by views. Add up to 4 to compare.")

    with st.spinner("Fetching & grouping programs (this can take a moment)..."):
        programs = get_channel_programs(
            st.session_state.selected_channel_id,
            date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d"), max_scan,
        )

    if not programs:
        st.warning("No uploads found in this date range. Try widening the range or increasing scan depth.")
        st.stop()

    ranked_programs = sorted(programs.items(), key=lambda x: x[1]["total_views"], reverse=True)

    # Queued cards
    if st.session_state.compare:
        st.markdown("**🗂️ Queued for comparison:**")
        qcols = st.columns(4)
        for i, pname in enumerate(st.session_state.compare):
            with qcols[i]:
                st.markdown(f'<div class="prog-card">🎬 <b>{pname[:28]}</b></div>', unsafe_allow_html=True)
                if st.button("✖ Remove", key=f"rm_{i}"):
                    st.session_state.compare.remove(pname)
                    st.rerun()
        st.markdown("")

    # Optional category filter
    all_types = sorted({p["category"] for _, p in ranked_programs})
    type_filter = st.multiselect("Filter by type", all_types, default=all_types)

    # Program list with Add buttons (top 25 after filter)
    filtered = [(n, p) for n, p in ranked_programs if p["category"] in type_filter]
    for idx, (pname, pdata) in enumerate(filtered[:25]):
        c1, c2, c3, c4, c5 = st.columns([3.4, 1.5, 1.3, 1.1, 1.3])
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
                st.rerun()

    if not st.session_state.compare:
        st.info("➕ Add at least one program above to see the comparison.")
        st.stop()

    st.markdown("---")

    # ---- STEP 3: Comparison Dashboard ----
    st.markdown('<h4><span class="step-badge">3</span>Comparison Dashboard</h4>', unsafe_allow_html=True)

    analyses = [analyze_program(p, programs[p]) for p in st.session_state.compare if p in programs]

    # Hardcord priority ranking
    ranked_analyses = sorted(analyses, key=lambda a: a["hardcord"], reverse=True)

    st.markdown("##### 🏆 Hardcord Priority Ranking (best → worst for ad placement)")
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
    max_hc = max((a["hardcord"] for a in analyses), default=1)
    st.dataframe(
        rank_df, use_container_width=True, hide_index=True,
        column_config={"Hardcord Score": st.column_config.ProgressColumn(
            "Hardcord Score", min_value=0, max_value=max_hc, format="%.0f")},
    )

    # Comparison charts
    cc1, cc2 = st.columns([3, 2])

    with cc1:
        st.markdown("##### 📈 Episode Views Trend (all programs)")
        frames = []
        for a in analyses:
            df = pd.DataFrame(a["episodes"])[["date", "views"]].copy()
            df["date"] = pd.to_datetime(df["date"])
            df = df.groupby("date")["views"].mean().rename(a["name"][:25])
            frames.append(df)
        combined = pd.concat(frames, axis=1).sort_index()
        st.line_chart(combined, use_container_width=True)
        st.caption("Higher line = more viewers. Peaks = best episodes to embed your 6-sec ad.")

    with cc2:
        st.markdown("##### 📊 Avg Views per Episode")
        bar_df = pd.DataFrame({
            "Program": [a["name"][:22] for a in ranked_analyses],
            "Avg Views": [a["avg_views"] for a in ranked_analyses],
        }).set_index("Program")
        st.bar_chart(bar_df, use_container_width=True)

    st.markdown("---")

    # Per-program detail
    st.markdown("##### 🔍 Per-Program Detail & Ad-Placement Guide")
    for a in ranked_analyses:
        with st.expander(f"{a['trend_icon']} {a['name']} · {a['category']} — {format_number(a['avg_views'])} avg views/ep · {a['trend']}", expanded=True):
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.markdown(f'<div class="metric-card"><h2>{a["episode_count"]}</h2><p>Episodes</p></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-card"><h2>{format_number(a["total_views"])}</h2><p>Total Views</p></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-card"><h2>{format_number(a["avg_views"])}</h2><p>Avg / Episode</p></div>', unsafe_allow_html=True)
            m4.markdown(f'<div class="metric-card"><h2>{a["avg_engagement"]}%</h2><p>Engagement</p></div>', unsafe_allow_html=True)
            m5.markdown(f'<div class="metric-card"><h2>{a["trend_icon"]}</h2><p>{a["trend"]} ({a["trend_change"]:+.0f}%)</p></div>', unsafe_allow_html=True)

            hc1, hc2 = st.columns(2)
            hc1.markdown(f"🔺 **Highest episode:** {format_number(a['highest']['views'])} views — "
                         f"[{a['highest']['title'][:55]}]({a['highest']['url']})")
            hc2.markdown(f"🔻 **Lowest episode:** {format_number(a['lowest']['views'])} views — "
                         f"[{a['lowest']['title'][:55]}]({a['lowest']['url']})")

            # Per-program viewership line
            pdf = pd.DataFrame(a["episodes"])[["date", "views"]].copy()
            pdf["date"] = pd.to_datetime(pdf["date"])
            st.line_chart(pdf.set_index("date")["views"], use_container_width=True)

            # Top 3 ad-placement episodes
            top3 = sorted(a["episodes"], key=lambda e: e["views"], reverse=True)[:3]
            st.markdown("**🎯 Best episodes to place your ad (highest viewership):**")
            for e in top3:
                st.markdown(f"- **{format_number(e['views'])} views** · {e['date']} · "
                            f"[{e['title'][:60]}]({e['url']})")

            # Episode table + download
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
            st.download_button(f"⬇️ Download '{a['name'][:20]}' episodes (CSV)", csv_buf.getvalue(),
                               file_name=f"{re.sub(r'[^A-Za-z0-9]+','_',a['name'])[:30]}_{date_to}.csv",
                               mime="text/csv", key=f"dl_{a['name']}")


# ===========================================================================
# TAB 2 — Trending Channels
# ===========================================================================

with tab2:
    st.sidebar.title("⚙️ Trending Settings")
    region_label = st.sidebar.selectbox("📍 Region", list(REGIONS.keys()), index=0)
    region_code = REGIONS[region_label]
    category_label = st.sidebar.selectbox("🎬 Category", list(CATEGORY_NAMES.values()), index=0)
    category_id = {v: k for k, v in CATEGORY_NAMES.items()}.get(category_label, "")
    max_results = st.sidebar.slider("📊 Videos to Analyze", 10, 50, 50, 10)
    top_n = st.sidebar.slider("🏆 Top Channels", 5, 50, 20, 5)
    local_only = st.sidebar.toggle("🇱🇰 Local Channels Only", value=False)
    run_btn = st.sidebar.button("🚀 Run Trending Analysis")

    if run_btn:
        with st.spinner(f"Fetching trending videos for {region_label}..."):
            videos = fetch_trending_videos(region_code, max_results, category_id or None)
        if not videos:
            st.warning("No trending videos found.")
            st.stop()
        with st.spinner("Fetching channel details..."):
            cids = list({v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")})
            cdetails = fetch_channel_details(cids)
        ranked = aggregate_channel_data(videos, cdetails, local_only=local_only)
        if not ranked:
            st.warning("No local channels in today's trending list. Turn off the local filter.")
            st.stop()

        max_score = ranked[0]["Hardcord Score"] if ranked else 1
        disp = pd.DataFrame([{
            "Rank": f"#{r['Rank']}", "🇱🇰": r["🇱🇰"], "Channel": r["Channel"],
            "Category": r["Category"], "Subscribers": format_number(r["Subscribers"]),
            "Total Views": format_number(r["Total Views"]),
            "Engagement %": f"{r['Engagement %']}%", "Hardcord Score": r["Hardcord Score"],
        } for r in ranked[:top_n]])
        st.subheader(f"🏆 Top Channels — {region_label} | {category_label}")
        st.dataframe(disp, use_container_width=True, hide_index=True,
                     column_config={"Hardcord Score": st.column_config.ProgressColumn(
                         "Hardcord Score", min_value=0, max_value=max_score, format="%.4f")})
        buf = io.StringIO()
        pd.DataFrame(ranked[:top_n]).to_csv(buf, index=False)
        st.download_button("⬇️ Download CSV", buf.getvalue(),
                           file_name=f"trending_{region_code}_{date.today()}.csv", mime="text/csv")
    else:
        st.info("👈 Configure settings in the sidebar and click **Run Trending Analysis**.")
