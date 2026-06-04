"""
YouTube Top Program Analysis — Web Interface
Hardcord Ad Targeting Tool for 6-Second Commercial Placements
"""

import os
import csv
import io
from datetime import datetime
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
# API helpers
# ---------------------------------------------------------------------------

def api_get(endpoint, params):
    params["key"] = YOUTUBE_API_KEY
    resp = requests.get(f"{YT_API_BASE}/{endpoint}", params=params, timeout=30)
    if resp.status_code == 403:
        st.error("API quota exceeded or key invalid. Please try again later.")
        st.stop()
    resp.raise_for_status()
    return resp.json()


def fetch_trending_videos(region_code, max_results, category_id=None):
    videos = []
    next_page_token = None
    remaining = max_results

    while remaining > 0:
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": min(remaining, 50),
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


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_hardcord_score(views, likes, subscribers):
    engagement_rate = (likes / max(views, 1)) * 100
    return round((views / 1_000_000) * engagement_rate * log10(max(subscribers, 1)), 4)


def aggregate_channel_data(videos, channel_details):
    channels = {}
    for video in videos:
        snippet = video.get("snippet", {})
        stats = video.get("statistics", {})
        channel_id = snippet.get("channelId", "")
        if not channel_id:
            continue

        views = safe_int(stats.get("viewCount"))
        likes = safe_int(stats.get("likeCount"))
        category_id = snippet.get("categoryId", "")
        category_name = CATEGORY_NAMES.get(category_id, f"Category {category_id}")

        if channel_id not in channels:
            ch = channel_details.get(channel_id, {})
            ch_snippet = ch.get("snippet", {})
            ch_stats = ch.get("statistics", {})
            channels[channel_id] = {
                "channel_id": channel_id,
                "channel_name": ch_snippet.get("title", snippet.get("channelTitle", "Unknown")),
                "channel_url": f"https://youtube.com/channel/{channel_id}",
                "subscribers": safe_int(ch_stats.get("subscriberCount")),
                "category": category_name,
                "total_views": 0,
                "total_likes": 0,
                "video_count": 0,
            }

        channels[channel_id]["total_views"] += views
        channels[channel_id]["total_likes"] += likes
        channels[channel_id]["video_count"] += 1

    result = []
    for ch in channels.values():
        avg_likes = ch["total_likes"] // max(ch["video_count"], 1)
        score = compute_hardcord_score(ch["total_views"], ch["total_likes"], ch["subscribers"])
        engagement_rate = round((ch["total_likes"] / max(ch["total_views"], 1)) * 100, 2)
        result.append({
            "Rank": 0,
            "Channel": ch["channel_name"],
            "Channel URL": ch["channel_url"],
            "Category": ch["category"],
            "Subscribers": ch["subscribers"],
            "Total Views": ch["total_views"],
            "Avg Likes": avg_likes,
            "Engagement %": engagement_rate,
            "Hardcord Score": score,
            "Trending Videos": ch["video_count"],
        })

    result.sort(key=lambda x: x["Hardcord Score"], reverse=True)
    for i, row in enumerate(result, start=1):
        row["Rank"] = i
    return result


def format_number(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="YouTube Trend Analyzer — Hardcord Targeting",
    page_icon="📺",
    layout="wide",
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 2.2rem; }
    .main-header p  { color: #a8b2d8; margin: 0.5rem 0 0; font-size: 1rem; }

    .metric-card {
        background: #16213e;
        border: 1px solid #0f3460;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .metric-card h2 { color: #e94560; margin: 0; font-size: 2rem; }
    .metric-card p  { color: #a8b2d8; margin: 0; font-size: 0.85rem; }

    .score-high { color: #00d4aa; font-weight: bold; }
    .score-mid  { color: #ffd700; font-weight: bold; }
    .score-low  { color: #ff6b6b; font-weight: bold; }

    div[data-testid="stDataFrame"] { border-radius: 10px; }
    .stButton > button {
        background: linear-gradient(135deg, #e94560, #0f3460);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-size: 1rem;
        font-weight: bold;
        width: 100%;
    }
    .stButton > button:hover { opacity: 0.9; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h1>📺 YouTube Trend Analyzer</h1>
    <p>Hardcord Ad Targeting — Identify Top Channels for 6-Second Commercial Placements</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------

st.sidebar.image("https://img.icons8.com/color/96/youtube-play.png", width=80)
st.sidebar.title("Analysis Settings")

region_label = st.sidebar.selectbox("📍 Region", list(REGIONS.keys()), index=0)
region_code = REGIONS[region_label]

category_label = st.sidebar.selectbox("🎬 Category", list(CATEGORY_NAMES.values()), index=0)
category_id = {v: k for k, v in CATEGORY_NAMES.items()}.get(category_label, "")

max_results = st.sidebar.slider("📊 Videos to Analyze", min_value=10, max_value=50, value=50, step=10)
top_n = st.sidebar.slider("🏆 Top Channels to Show", min_value=5, max_value=50, value=20, step=5)

st.sidebar.markdown("---")
st.sidebar.markdown("**Category Guide for Hardcording:**")
st.sidebar.markdown("- 🎭 **Entertainment** — Teledrama, shows")
st.sidebar.markdown("- 🎵 **Music** — Music videos")
st.sidebar.markdown("- 📰 **News & Politics** — News channels")
st.sidebar.markdown("- 👥 **People & Blogs** — Creator content")

run_btn = st.sidebar.button("🚀 Run Analysis")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if not YOUTUBE_API_KEY:
    st.error("YouTube API key not configured. Please contact the administrator.")
    st.stop()

if run_btn:
    with st.spinner(f"Fetching trending videos for {region_label}..."):
        videos = fetch_trending_videos(region_code, max_results, category_id or None)

    if not videos:
        st.warning("No trending videos found for the selected filters. Try a different category or region.")
        st.stop()

    with st.spinner("Fetching channel details..."):
        channel_ids = list({v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")})
        channel_details = fetch_channel_details(channel_ids)

    with st.spinner("Computing Hardcord Scores..."):
        ranked = aggregate_channel_data(videos, channel_details)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><h2>{len(videos)}</h2><p>Trending Videos Analyzed</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><h2>{len(ranked)}</h2><p>Unique Channels Found</p></div>', unsafe_allow_html=True)
    with col3:
        top_channel = ranked[0]["Channel"] if ranked else "-"
        st.markdown(f'<div class="metric-card"><h2 style="font-size:1.1rem">{top_channel}</h2><p>#1 Hardcord Target</p></div>', unsafe_allow_html=True)
    with col4:
        total_views = sum(r["Total Views"] for r in ranked)
        st.markdown(f'<div class="metric-card"><h2>{format_number(total_views)}</h2><p>Total Views (All Channels)</p></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Build display dataframe
    display_data = []
    max_score = ranked[0]["Hardcord Score"] if ranked else 1
    for r in ranked[:top_n]:
        score = r["Hardcord Score"]
        display_data.append({
            "Rank": f"#{r['Rank']}",
            "Channel": r["Channel"],
            "Category": r["Category"],
            "Subscribers": format_number(r["Subscribers"]),
            "Total Views": format_number(r["Total Views"]),
            "Avg Likes": format_number(r["Avg Likes"]),
            "Engagement %": f"{r['Engagement %']}%",
            "Hardcord Score": r["Hardcord Score"],
            "Trending Videos": r["Trending Videos"],
        })

    df = pd.DataFrame(display_data)

    st.subheader(f"🏆 Top {min(top_n, len(ranked))} Channels — {region_label} | {category_label}")
    st.markdown(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Hardcord Score": st.column_config.ProgressColumn(
                "Hardcord Score",
                help="Higher = better target for 6-sec ad placement",
                min_value=0,
                max_value=max_score,
                format="%.4f",
            ),
            "Rank": st.column_config.TextColumn("Rank", width="small"),
        }
    )

    # Download buttons
    st.markdown("### 📥 Download Report")
    col_dl1, col_dl2 = st.columns(2)

    # CSV download
    csv_buffer = io.StringIO()
    full_df = pd.DataFrame(ranked[:top_n])
    full_df.to_csv(csv_buffer, index=False)
    col_dl1.download_button(
        label="⬇️ Download CSV",
        data=csv_buffer.getvalue(),
        file_name=f"hardcord_report_{region_code}_{datetime.now().strftime('%Y-%m-%d')}.csv",
        mime="text/csv",
    )

    # HTML download
    html_rows = ""
    for r in ranked[:top_n]:
        score = r["Hardcord Score"]
        if score >= max_score * 0.66:
            badge = f'<span style="background:#00d4aa;color:#000;padding:2px 8px;border-radius:12px;font-weight:bold">{score:.4f}</span>'
        elif score >= max_score * 0.33:
            badge = f'<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:12px;font-weight:bold">{score:.4f}</span>'
        else:
            badge = f'<span style="background:#ff6b6b;color:#fff;padding:2px 8px;border-radius:12px;font-weight:bold">{score:.4f}</span>'

        html_rows += f"""<tr>
            <td>#{r['Rank']}</td>
            <td><a href="{r['Channel URL']}" target="_blank">{r['Channel']}</a></td>
            <td>{r['Category']}</td>
            <td>{format_number(r['Subscribers'])}</td>
            <td>{format_number(r['Total Views'])}</td>
            <td>{r['Avg Likes']:,}</td>
            <td>{r['Engagement %']}%</td>
            <td>{badge}</td>
        </tr>"""

    html_report = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>Hardcord Report {datetime.now().strftime('%Y-%m-%d')}</title>
    <style>
        body{{font-family:Arial,sans-serif;background:#0f0f1a;color:#eee;margin:0;padding:20px}}
        h1{{color:#e94560;text-align:center}}
        p{{text-align:center;color:#a8b2d8}}
        table{{width:100%;border-collapse:collapse;margin-top:20px}}
        th{{background:#16213e;color:#e94560;padding:12px;text-align:left}}
        td{{padding:10px;border-bottom:1px solid #1a1a2e}}
        tr:hover{{background:#16213e}}
        a{{color:#00d4aa;text-decoration:none}}
    </style></head><body>
    <h1>📺 YouTube Trend Analysis — Hardcord Targeting Report</h1>
    <p>Region: {region_label} | Category: {category_label} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <table><thead><tr>
        <th>Rank</th><th>Channel</th><th>Category</th><th>Subscribers</th>
        <th>Total Views</th><th>Avg Likes</th><th>Engagement %</th><th>Hardcord Score</th>
    </tr></thead><tbody>{html_rows}</tbody></table>
    <p style="margin-top:40px;font-size:0.8rem">Generated by YoutubeTrend Analyzer | pekadacreativestudio.com</p>
    </body></html>"""

    col_dl2.download_button(
        label="⬇️ Download HTML Report",
        data=html_report,
        file_name=f"hardcord_report_{region_code}_{datetime.now().strftime('%Y-%m-%d')}.html",
        mime="text/html",
    )

    # Score explanation
    st.markdown("---")
    st.markdown("""
    **ℹ️ Hardcord Score Formula:**
    `Score = (Total Views ÷ 1M) × Engagement Rate% × log10(Subscribers)`
    Higher score = more views, better engagement, larger audience = better target for your 6-second ad placements.
    """)

else:
    st.info("👈 Select your settings in the sidebar and click **Run Analysis** to get started.")
    st.markdown("""
    ### How it works:
    1. **Select Region** — Choose Sri Lanka or any other country
    2. **Select Category** — Entertainment for Teledrama, Music for music channels, etc.
    3. **Click Run Analysis** — Fetches live YouTube trending data
    4. **View Results** — Ranked channels with Hardcord Score
    5. **Download Report** — CSV or HTML report for your team

    ### Hardcord Score:
    The **Hardcord Score** ranks channels based on views, engagement, and audience size.
    **Higher score = better channel to place your 6-second commercial in.**
    """)
