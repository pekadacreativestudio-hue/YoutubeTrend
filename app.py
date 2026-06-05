"""
YouTube Top Program Analysis — Web Interface
Hardcord Ad Targeting Tool for 6-Second Commercial Placements
"""

import os
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

# Curated list of major Sri Lankan YouTube channels
SRI_LANKA_LOCAL_CHANNELS = {
    "Derana":            "UCuBBHFSEtxHiSMGFMcNsHiA",
    "Hiru TV":           "UCwVEBsRBb8GJTB0yxWBzqCQ",
    "Sirasa TV":         "UCjHPxk7H4TKqBFSx5BWCQKQ",
    "Swarnavahini":      "UCvpN3a28MaXQfyAeKkp8G7g",
    "ITN Sri Lanka":     "UC6jHRJJfXIEMz3YNQR4JSJA",
    "Rupavahini":        "UCYblNXqDBcMkAn4QpNFg4jQ",
    "TV1 Sri Lanka":     "UCOJKpnJLJAhAGHPcf3FaBdA",
    "Shakthi TV":        "UCqnhcPRjEkf_h8bBkrOFyXg",
    "TNL TV":            "UCXzFPP2MCaL8n9Eq5Bz4bYA",
    "The Voice Sri Lanka": "UCmqflTSJ6911aCrnaWIXxsA",
    "Mokka Commentry":   "UC3Y7OyuS9jNdZy3ZadrAbWQ",
    "Dhanith Sri":       "UCyCNFZZpmyZQEgtar98I8tA",
    "DilShan L Silva":   "UC5A7foGvdlddb0b6iHaqUBg",
    "Dinuli Damsandi":   "UCU9IoKqQvxERkoxwB-L9VwQ",
    "Mihiran":           "UC6wvfVVgmnsMUlhfYCv64Gw",
    "Music Update":      "UCK_mRBdCXMfDqOnnrP5_Ztg",
    "Sindu Lanka":       "UCLFgm4esTpsbX5B5TrZ_UCw",
    "Bus Sindu lk":      "UCvpNiAygI8AxEu88ejGkT0g",
    "Roshan Fernando":   "UCNbhBaSxzjD4Yr7bRVKiWaw",
}

# ---------------------------------------------------------------------------
# Styling
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
        padding: 2rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center;
    }
    .main-header h1 { color: #e94560; margin: 0; font-size: 2rem; }
    .main-header p  { color: #a8b2d8; margin: 0.4rem 0 0; font-size: 0.95rem; }
    .metric-card {
        background: #16213e; border: 1px solid #0f3460;
        border-radius: 10px; padding: 1rem; text-align: center;
    }
    .metric-card h2 { color: #e94560; margin: 0; font-size: 1.8rem; }
    .metric-card p  { color: #a8b2d8; margin: 0; font-size: 0.82rem; }
    .stButton > button {
        background: linear-gradient(135deg, #e94560, #0f3460);
        color: white; border: none; border-radius: 8px;
        padding: 0.6rem 2rem; font-size: 1rem; font-weight: bold; width: 100%;
    }
    .tag-lk {
        background: #00d4aa; color: #000; padding: 2px 8px;
        border-radius: 10px; font-size: 0.75rem; font-weight: bold;
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
        st.error("API quota exceeded or key invalid. Please try again later.")
        st.stop()
    resp.raise_for_status()
    return resp.json()


def fetch_trending_videos(region_code, max_results, category_id=None):
    videos, next_page_token, remaining = [], None, max_results
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


def search_channel(query):
    """Search for a channel by name, return list of matches."""
    data = api_get("search", {
        "part": "snippet", "type": "channel", "q": query, "maxResults": 5
    })
    return data.get("items", [])


def search_videos_in_channel(channel_id, query, max_results=30):
    """Search for videos in a specific channel matching a query."""
    data = api_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "q": query,
        "type": "video",
        "order": "date",
        "maxResults": max_results,
    })
    return data.get("items", [])


def fetch_video_stats(video_ids):
    """Fetch statistics for a list of video IDs."""
    details = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        data = api_get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(batch)})
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


# ---------------------------------------------------------------------------
# Scoring & aggregation
# ---------------------------------------------------------------------------

def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_hardcord_score(views, likes, subscribers):
    engagement_rate = (likes / max(views, 1)) * 100
    return round((views / 1_000_000) * engagement_rate * log10(max(subscribers, 1)), 4)


def aggregate_channel_data(videos, channel_details, local_only=False):
    local_ids = set(SRI_LANKA_LOCAL_CHANNELS.values())
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
        category_id = snippet.get("categoryId", "")
        category_name = CATEGORY_NAMES.get(category_id, f"Category {category_id}")

        if channel_id not in channels:
            ch = channel_details.get(channel_id, {})
            ch_snippet = ch.get("snippet", {})
            ch_stats = ch.get("statistics", {})
            is_local = channel_id in local_ids
            channels[channel_id] = {
                "channel_id": channel_id,
                "channel_name": ch_snippet.get("title", snippet.get("channelTitle", "Unknown")),
                "channel_url": f"https://youtube.com/channel/{channel_id}",
                "subscribers": safe_int(ch_stats.get("subscriberCount")),
                "category": category_name,
                "is_local": is_local,
                "total_views": 0, "total_likes": 0, "video_count": 0,
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
            "🇱🇰": "✅" if ch["is_local"] else "",
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
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="main-header">
    <h1>📺 YouTube Trend Analyzer</h1>
    <p>Hardcord Ad Targeting — Identify Top Channels & Programs for 6-Second Commercial Placements</p>
</div>
""", unsafe_allow_html=True)

if not YOUTUBE_API_KEY:
    st.error("YouTube API key not configured. Please contact the administrator.")
    st.stop()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2 = st.tabs(["📊 Trending Channels", "🎭 Program / Series Analysis"])

# ===========================================================================
# TAB 1 — Trending Channels
# ===========================================================================

with tab1:
    st.sidebar.title("⚙️ Settings")

    region_label = st.sidebar.selectbox("📍 Region", list(REGIONS.keys()), index=0)
    region_code = REGIONS[region_label]

    category_label = st.sidebar.selectbox("🎬 Category", list(CATEGORY_NAMES.values()), index=0)
    category_id = {v: k for k, v in CATEGORY_NAMES.items()}.get(category_label, "")

    max_results = st.sidebar.slider("📊 Videos to Analyze", 10, 50, 50, 10)
    top_n = st.sidebar.slider("🏆 Top Channels to Show", 5, 50, 20, 5)

    local_only = st.sidebar.toggle("🇱🇰 Show Sri Lankan Local Channels Only", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Sri Lankan Local Channels tracked:**")
    for name in SRI_LANKA_LOCAL_CHANNELS:
        st.sidebar.markdown(f"• {name}")

    run_btn = st.sidebar.button("🚀 Run Analysis")

    if run_btn:
        with st.spinner(f"Fetching trending videos for {region_label}..."):
            videos = fetch_trending_videos(region_code, max_results, category_id or None)

        if not videos:
            st.warning("No trending videos found. Try a different category or region.")
            st.stop()

        with st.spinner("Fetching channel details..."):
            channel_ids = list({v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")})
            channel_details = fetch_channel_details(channel_ids)

        with st.spinner("Computing Hardcord Scores..."):
            ranked = aggregate_channel_data(videos, channel_details, local_only=local_only)

        if not ranked:
            st.warning("No local Sri Lankan channels found in today's trending list. Turn off the local filter to see all channels.")
            st.stop()

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        local_count = sum(1 for r in ranked if r["🇱🇰"] == "✅")
        with col1:
            st.markdown(f'<div class="metric-card"><h2>{len(videos)}</h2><p>Trending Videos Analyzed</p></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="metric-card"><h2>{len(ranked)}</h2><p>Unique Channels Found</p></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="metric-card"><h2>{local_count}</h2><p>🇱🇰 Local LK Channels</p></div>', unsafe_allow_html=True)
        with col4:
            top_ch = ranked[0]["Channel"] if ranked else "-"
            st.markdown(f'<div class="metric-card"><h2 style="font-size:1rem">{top_ch}</h2><p>#1 Hardcord Target</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Build display dataframe
        max_score = ranked[0]["Hardcord Score"] if ranked else 1
        display_data = []
        for r in ranked[:top_n]:
            display_data.append({
                "Rank": f"#{r['Rank']}",
                "🇱🇰": r["🇱🇰"],
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
        label = "🇱🇰 Local Sri Lankan Channels Only" if local_only else f"{region_label} | {category_label}"
        st.subheader(f"🏆 Top {min(top_n, len(ranked))} Channels — {label}")
        st.caption(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "Hardcord Score": st.column_config.ProgressColumn(
                    "Hardcord Score", help="Higher = better for 6-sec ad placement",
                    min_value=0, max_value=max_score, format="%.4f",
                ),
                "🇱🇰": st.column_config.TextColumn("🇱🇰 Local", width="small"),
                "Rank": st.column_config.TextColumn("Rank", width="small"),
            }
        )

        # Downloads
        st.markdown("### 📥 Download Report")
        c1, c2 = st.columns(2)
        csv_buf = io.StringIO()
        pd.DataFrame(ranked[:top_n]).to_csv(csv_buf, index=False)
        c1.download_button("⬇️ Download CSV", csv_buf.getvalue(),
            file_name=f"hardcord_{region_code}_{datetime.now().strftime('%Y-%m-%d')}.csv", mime="text/csv")

        # HTML
        rows_html = ""
        for r in ranked[:top_n]:
            s = r["Hardcord Score"]
            if s >= max_score * 0.66:
                badge = f'<span style="background:#00d4aa;color:#000;padding:2px 8px;border-radius:12px">{s:.4f}</span>'
            elif s >= max_score * 0.33:
                badge = f'<span style="background:#ffd700;color:#000;padding:2px 8px;border-radius:12px">{s:.4f}</span>'
            else:
                badge = f'<span style="background:#ff6b6b;color:#fff;padding:2px 8px;border-radius:12px">{s:.4f}</span>'
            local_tag = '<span style="background:#00d4aa;color:#000;padding:1px 6px;border-radius:8px;font-size:0.75rem">🇱🇰 Local</span>' if r["🇱🇰"] else ""
            rows_html += f"<tr><td>#{r['Rank']}</td><td><a href='{r['Channel URL']}' target='_blank'>{r['Channel']}</a> {local_tag}</td><td>{r['Category']}</td><td>{format_number(r['Subscribers'])}</td><td>{format_number(r['Total Views'])}</td><td>{r['Engagement %']}%</td><td>{badge}</td></tr>"

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Hardcord Report</title>
        <style>body{{font-family:Arial;background:#0f0f1a;color:#eee;padding:20px}}h1{{color:#e94560;text-align:center}}
        table{{width:100%;border-collapse:collapse;margin-top:20px}}th{{background:#16213e;color:#e94560;padding:12px;text-align:left}}
        td{{padding:10px;border-bottom:1px solid #1a1a2e}}tr:hover{{background:#16213e}}a{{color:#00d4aa;text-decoration:none}}</style>
        </head><body><h1>📺 YouTube Trend Analysis — Hardcord Targeting</h1>
        <p style="text-align:center;color:#a8b2d8">Region: {region_label} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <table><thead><tr><th>Rank</th><th>Channel</th><th>Category</th><th>Subscribers</th><th>Total Views</th><th>Engagement %</th><th>Score</th></tr></thead>
        <tbody>{rows_html}</tbody></table></body></html>"""
        c2.download_button("⬇️ Download HTML", html,
            file_name=f"hardcord_{region_code}_{datetime.now().strftime('%Y-%m-%d')}.html", mime="text/html")

        st.markdown("---")
        st.info("**Hardcord Score** = (Views ÷ 1M) × Engagement% × log10(Subscribers). Higher = better target for your 6-second ad placements.")

    else:
        st.info("👈 Configure settings in the sidebar and click **Run Analysis**.")
        st.markdown("""
        ### Features:
        - 📊 **Trending Channel Rankings** — ranked by Hardcord Score
        - 🇱🇰 **Local Channels Filter** — toggle to show only Sri Lankan channels
        - 📥 **Download Reports** — CSV or HTML for your team
        - 🎭 **Program Analysis** — use the second tab to deep-dive into a specific series
        """)


# ===========================================================================
# TAB 2 — Program / Series Analysis
# ===========================================================================

with tab2:
    st.subheader("🎭 Program / Series Deep Analysis")
    st.markdown("Search for a specific teledrama or series to see episode-by-episode performance and hardcord potential.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        channel_query = st.text_input("📺 Channel Name", placeholder="e.g. Swarnavahini, Hiru TV, Derana")

    with col_b:
        program_query = st.text_input("🎬 Program / Series Name", placeholder="e.g. Natath Ayek Sura Mathin")

    max_episodes = st.slider("Maximum episodes to fetch", 10, 50, 30, 5)

    # Quick-select local channels
    st.markdown("**Or pick a local channel directly:**")
    local_cols = st.columns(5)
    selected_local = None
    for i, name in enumerate(SRI_LANKA_LOCAL_CHANNELS):
        if local_cols[i % 5].button(name, key=f"lc_{name}"):
            selected_local = name
            channel_query = name

    search_btn = st.button("🔍 Search Program", key="search_program")

    if search_btn and channel_query and program_query:
        # Step 1: Find the channel
        with st.spinner(f"Searching for channel: {channel_query}..."):
            # Check if it's a known local channel first
            known_id = SRI_LANKA_LOCAL_CHANNELS.get(channel_query)
            if known_id:
                channel_id = known_id
                channel_name = channel_query
            else:
                results = search_channel(channel_query)
                if not results:
                    st.error("Channel not found. Try a different name.")
                    st.stop()
                channel_id = results[0]["id"]["channelId"]
                channel_name = results[0]["snippet"]["title"]

        st.success(f"✅ Found channel: **{channel_name}**")

        # Step 2: Search for program episodes
        with st.spinner(f"Searching for episodes of '{program_query}'..."):
            search_results = search_videos_in_channel(channel_id, program_query, max_results=max_episodes)

        if not search_results:
            st.warning("No videos found for that program name. Try different keywords.")
            st.stop()

        video_ids = [item["id"]["videoId"] for item in search_results if item.get("id", {}).get("videoId")]

        # Step 3: Fetch full stats
        with st.spinner("Fetching episode statistics..."):
            video_stats = fetch_video_stats(video_ids)

        # Step 4: Build episode table
        episodes = []
        for item in search_results:
            vid_id = item.get("id", {}).get("videoId")
            if not vid_id or vid_id not in video_stats:
                continue
            detail = video_stats[vid_id]
            stats = detail.get("statistics", {})
            snippet = detail.get("snippet", {})
            views = safe_int(stats.get("viewCount"))
            likes = safe_int(stats.get("likeCount"))
            comments = safe_int(stats.get("commentCount"))
            pub_date = snippet.get("publishedAt", "")[:10]
            engagement = round((likes / max(views, 1)) * 100, 2)

            episodes.append({
                "Title": snippet.get("title", "Unknown"),
                "Published": pub_date,
                "Views": views,
                "Likes": likes,
                "Comments": comments,
                "Engagement %": engagement,
                "Video URL": f"https://youtube.com/watch?v={vid_id}",
                "Views_raw": views,
            })

        if not episodes:
            st.warning("Could not load episode data.")
            st.stop()

        episodes.sort(key=lambda x: x["Published"], reverse=True)

        # Metrics
        total_views = sum(e["Views"] for e in episodes)
        avg_views = total_views // len(episodes)
        avg_engagement = round(sum(e["Engagement %"] for e in episodes) / len(episodes), 2)
        top_ep = max(episodes, key=lambda x: x["Views"])

        st.markdown(f"### 📊 '{program_query}' on {channel_name}")
        st.caption(f"{len(episodes)} episodes found")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="metric-card"><h2>{len(episodes)}</h2><p>Episodes Found</p></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="metric-card"><h2>{format_number(total_views)}</h2><p>Total Views</p></div>', unsafe_allow_html=True)
        with m3:
            st.markdown(f'<div class="metric-card"><h2>{format_number(avg_views)}</h2><p>Avg Views / Episode</p></div>', unsafe_allow_html=True)
        with m4:
            st.markdown(f'<div class="metric-card"><h2>{avg_engagement}%</h2><p>Avg Engagement Rate</p></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Trend chart
        chart_df = pd.DataFrame(episodes)[["Published", "Views_raw"]].rename(columns={"Views_raw": "Views"})
        chart_df = chart_df.sort_values("Published")
        chart_df["Published"] = pd.to_datetime(chart_df["Published"])
        st.markdown("#### 📈 Episode Views Trend")
        st.line_chart(chart_df.set_index("Published")["Views"], use_container_width=True)

        # Hardcord recommendation
        if avg_views > 500_000:
            rec_color = "#00d4aa"
            rec = "🟢 EXCELLENT — High priority for hardcord placement"
        elif avg_views > 100_000:
            rec_color = "#ffd700"
            rec = "🟡 GOOD — Suitable for hardcord placement"
        else:
            rec_color = "#ff6b6b"
            rec = "🔴 LOW — Monitor for growth before placing ads"

        st.markdown(f"""
        <div style="background:#16213e;border-left:4px solid {rec_color};padding:1rem;border-radius:8px;margin:1rem 0">
            <strong>Hardcord Recommendation:</strong> {rec}<br>
            <small>Average {format_number(avg_views)} views/episode | {avg_engagement}% engagement</small>
        </div>
        """, unsafe_allow_html=True)

        # Episode table
        st.markdown("#### 🎬 Episode Breakdown")
        display_eps = []
        for e in episodes:
            display_eps.append({
                "Title": e["Title"],
                "Published": e["Published"],
                "Views": format_number(e["Views"]),
                "Likes": format_number(e["Likes"]),
                "Comments": format_number(e["Comments"]),
                "Engagement %": f"{e['Engagement %']}%",
                "Watch": e["Video URL"],
                "Views_raw": e["Views"],
            })

        ep_df = pd.DataFrame(display_eps)
        max_ep_views = max(e["Views_raw"] for e in episodes) if episodes else 1

        st.dataframe(
            ep_df.drop(columns=["Views_raw"]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Watch": st.column_config.LinkColumn("▶️ Watch", display_text="Watch"),
                "Title": st.column_config.TextColumn("Episode Title", width="large"),
            }
        )

        # Download
        csv_ep = io.StringIO()
        pd.DataFrame(episodes).drop(columns=["Views_raw"]).to_csv(csv_ep, index=False)
        st.download_button("⬇️ Download Episode Report (CSV)", csv_ep.getvalue(),
            file_name=f"{program_query[:30]}_{datetime.now().strftime('%Y-%m-%d')}.csv", mime="text/csv")

    elif search_btn:
        st.warning("Please enter both a channel name and a program/series name.")
    else:
        st.markdown("""
        **How to use:**
        1. Enter the **Channel Name** (e.g. `Swarnavahini`) or click a local channel button
        2. Enter the **Program Name** (e.g. `Natath Ayek Sura Mathin` or `නටත් අයෙක් සුරා මතින්`)
        3. Click **Search Program**
        4. See episode-by-episode views, engagement, and hardcord recommendation

        **Works with:** Sinhala names, English names, or partial names
        """)
