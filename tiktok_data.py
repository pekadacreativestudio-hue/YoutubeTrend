"""
TikTok data layer for the YouTube Program Analyzer (Hardcord Ad Targeting).

Uses yt-dlp (free, open-source) to pull PUBLIC TikTok profile + video stats —
no API key, no account ownership needed.

⚠️ Reliability note: TikTok aggressively rate-limits / blocks datacenter IPs.
This works most reliably from a residential / local machine. On cloud hosts
(Streamlit Cloud, etc.) TikTok may return empty results or block the request.
Every function degrades gracefully and returns partial/empty data instead of
raising, so the UI can show a helpful message rather than crash.
"""

from math import log10

# Curated Sri Lankan TikTok handles (broadcasters, creators, music).
# Handles are the @username without the leading @. Add/adjust freely.
SRI_LANKA_TIKTOK = {
    "TV Derana":            ("tvderana",            "📺 TV Channel"),
    "Hiru TV":              ("hirutv",              "📺 TV Channel"),
    "Sirasa TV":            ("sirasatv",            "📺 TV Channel"),
    "Ada Derana":           ("adaderana",           "📰 News"),
    "News First":           ("newsfirst.lk",        "📰 News"),
    "Wasthi Productions":   ("wasthi",              "🎥 Creator"),
    "Chanux Bro":           ("chanuxbro",           "🎥 Creator"),
    "Yohani":               ("yohanimusic",         "🎵 Music"),
    "Sarith & Surith":      ("sarithsurith",        "🎥 Creator"),
    "Gindara":              ("gindara.lk",          "🎥 Creator"),
}


def _ydl_opts(max_videos):
    return {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "playlistend": max_videos,
        "ignoreerrors": True,
        "noplaylist": False,
    }


def fetch_tiktok_channel(handle, max_videos=15):
    """Fetch a TikTok profile's recent videos + stats via yt-dlp.

    Returns a dict:
        {
          "handle": str, "followers": int, "videos": [ {video dicts} ],
          "error": None | str
        }
    On failure returns the same shape with error set and videos empty.
    """
    try:
        import yt_dlp
    except ImportError:
        return {"handle": handle, "followers": 0, "videos": [],
                "error": "yt-dlp is not installed. Add `yt-dlp` to requirements.txt."}

    url = f"https://www.tiktok.com/@{handle}"
    try:
        with yt_dlp.YoutubeDL(_ydl_opts(max_videos)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001 — yt-dlp raises many extractor errors
        return {"handle": handle, "followers": 0, "videos": [],
                "error": f"Could not fetch @{handle}: {type(e).__name__}. "
                         f"TikTok may be blocking this host."}

    if not info:
        return {"handle": handle, "followers": 0, "videos": [],
                "error": f"No data returned for @{handle} (blocked or empty)."}

    followers = (info.get("channel_follower_count")
                 or info.get("follower_count") or 0)

    entries = info.get("entries") or ([info] if info.get("id") else [])
    videos = []
    for e in entries:
        if not e:
            continue
        views = int(e.get("view_count") or 0)
        likes = int(e.get("like_count") or 0)
        comments = int(e.get("comment_count") or 0)
        reposts = int(e.get("repost_count") or 0)
        vid = e.get("id", "")
        videos.append({
            "video_id": vid,
            "title": (e.get("title") or e.get("description") or "")[:120],
            "url": e.get("webpage_url") or f"https://www.tiktok.com/@{handle}/video/{vid}",
            "thumbnail": e.get("thumbnail", ""),
            "date": _fmt_date(e.get("upload_date")),
            "views": views,
            "likes": likes,
            "comments": comments,
            "reposts": reposts,
            "engagement": round((likes + comments + reposts) / max(views, 1) * 100, 2),
        })

    return {"handle": handle, "followers": int(followers), "videos": videos, "error": None}


def _fmt_date(yyyymmdd):
    """yt-dlp gives upload_date as 'YYYYMMDD'; return 'YYYY-MM-DD' or ''."""
    if yyyymmdd and len(yyyymmdd) == 8:
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return ""


def tiktok_hardcord_score(total_views, total_engagement_pct, followers):
    """Mirror the YouTube Hardcord Score for TikTok:
       (views / 1M) * engagement% * log10(followers)."""
    return round((total_views / 1_000_000) * max(total_engagement_pct, 0.01)
                 * log10(max(followers, 1)), 4)


def summarize_channel(name, ch_type, data):
    """Roll a fetched channel dict into a ranking-row summary."""
    videos = data.get("videos", [])
    total_views = sum(v["views"] for v in videos)
    total_likes = sum(v["likes"] for v in videos)
    total_comments = sum(v["comments"] for v in videos)
    total_reposts = sum(v["reposts"] for v in videos)
    eng = round((total_likes + total_comments + total_reposts)
                / max(total_views, 1) * 100, 2)
    followers = data.get("followers", 0)
    return {
        "Channel": name,
        "Type": ch_type,
        "handle": data.get("handle", ""),
        "Followers": followers,
        "Total Views": total_views,
        "Videos": len(videos),
        "Engagement %": eng,
        "Hardcord Score": tiktok_hardcord_score(total_views, eng, followers),
        "videos": videos,
        "error": data.get("error"),
    }
