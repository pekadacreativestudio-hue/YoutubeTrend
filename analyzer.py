"""
YouTube Top Program Analysis Tool
For hardcord/ad placement business — identifies best trending YouTube channels
and programs to target for 6-second commercial placements.
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from math import log10

import requests
import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich import box

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATEGORY_NAMES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "18": "Short Movies",
    "19": "Travel & Events",
    "20": "Gaming",
    "21": "Videoblogging",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}

YT_API_BASE = "https://www.googleapis.com/youtube/v3"

console = Console()


# ---------------------------------------------------------------------------
# API helpers (using requests directly)
# ---------------------------------------------------------------------------


def api_get(endpoint: str, api_key: str, params: dict) -> dict:
    """Make a GET request to the YouTube Data API v3."""
    params["key"] = api_key
    url = f"{YT_API_BASE}/{endpoint}"
    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code == 403:
        console.print(
            "[bold red]API quota exceeded or key invalid. "
            "Check your YOUTUBE_API_KEY and daily quota.[/bold red]"
        )
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def fetch_trending_videos(
    api_key: str,
    region_code: str = "LK",
    max_results: int = 50,
    category_id: str | None = None,
) -> list[dict]:
    """
    Fetch trending videos for the given region (and optional category).
    Returns a list of raw video resource dicts.
    """
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
            params["videoCategoryId"] = str(category_id)
        if next_page_token:
            params["pageToken"] = next_page_token

        data = api_get("videos", api_key, params)
        items = data.get("items", [])
        videos.extend(items)
        remaining -= len(items)
        next_page_token = data.get("nextPageToken")
        if not next_page_token or not items:
            break

    return videos


def fetch_channel_details(api_key: str, channel_ids: list[str]) -> dict[str, dict]:
    """
    Fetch snippet + statistics for a list of channel IDs (batched in 50s).
    Returns a dict keyed by channel_id.
    """
    details: dict[str, dict] = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        params = {
            "part": "snippet,statistics",
            "id": ",".join(batch),
        }
        data = api_get("channels", api_key, params)
        for item in data.get("items", []):
            details[item["id"]] = item
    return details


# ---------------------------------------------------------------------------
# Scoring & aggregation
# ---------------------------------------------------------------------------


def safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_hardcord_score(views: int, likes: int, subscribers: int) -> float:
    """
    Hardcord Score = (views / 1M) * engagement_rate% * log10(subscribers)
    Higher = better ad-placement candidate.
    """
    engagement_rate = (likes / max(views, 1)) * 100
    score = (views / 1_000_000) * engagement_rate * log10(max(subscribers, 1))
    return round(score, 4)


def aggregate_channel_data(
    videos: list[dict], channel_details: dict[str, dict]
) -> list[dict]:
    """Aggregate per-video stats to channel level, compute scores, sort."""
    channels: dict[str, dict] = {}

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
            ch_detail = channel_details.get(channel_id, {})
            ch_snippet = ch_detail.get("snippet", {})
            ch_stats = ch_detail.get("statistics", {})
            channels[channel_id] = {
                "channel_id": channel_id,
                "channel_name": ch_snippet.get("title", snippet.get("channelTitle", "Unknown")),
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
        video_count = ch["video_count"]
        avg_likes = ch["total_likes"] // max(video_count, 1)
        score = compute_hardcord_score(ch["total_views"], ch["total_likes"], ch["subscribers"])
        engagement_rate = round((ch["total_likes"] / max(ch["total_views"], 1)) * 100, 4)
        result.append({
            "channel_id": ch["channel_id"],
            "channel_name": ch["channel_name"],
            "category": ch["category"],
            "subscribers": ch["subscribers"],
            "total_views": ch["total_views"],
            "avg_likes": avg_likes,
            "engagement_rate": engagement_rate,
            "hardcord_score": score,
            "trending_video_count": video_count,
        })

    result.sort(key=lambda x: x["hardcord_score"], reverse=True)
    for rank, row in enumerate(result, start=1):
        row["rank"] = rank
    return result


# ---------------------------------------------------------------------------
# Output: Rich CLI table
# ---------------------------------------------------------------------------


def print_rich_table(channels: list[dict], top_n: int = 20) -> None:
    table = Table(
        title="[bold cyan]YouTube Trend Analysis — Hardcord Targeting Report[/bold cyan]\n"
              "[dim]Top Channels for 6-Second Ad Placement[/dim]",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
    )
    table.add_column("Rank", style="bold yellow", justify="right", width=5)
    table.add_column("Channel Name", style="bold white", min_width=25)
    table.add_column("Category", style="cyan", min_width=18)
    table.add_column("Total Views", justify="right", style="green", min_width=13)
    table.add_column("Avg Likes", justify="right", style="blue", min_width=10)
    table.add_column("Subscribers", justify="right", style="yellow", min_width=12)
    table.add_column("Hardcord Score", justify="right", style="bold red", min_width=14)

    for ch in channels[:top_n]:
        table.add_row(
            str(ch["rank"]),
            ch["channel_name"],
            ch["category"],
            f"{ch['total_views']:,}",
            f"{ch['avg_likes']:,}",
            f"{ch['subscribers']:,}",
            f"{ch['hardcord_score']:.4f}",
        )

    console.print()
    console.print(table)
    console.print(
        f"\n[dim]Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        f"Showing top {min(top_n, len(channels))} of {len(channels)} channels[/dim]\n"
    )


# ---------------------------------------------------------------------------
# Output: HTML report
# ---------------------------------------------------------------------------


def render_html_report(channels: list[dict], region_code: str, output_path: str, top_n: int = 20) -> None:
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        template = env.get_template("report_template.html")
    except Exception as exc:
        console.print(f"[bold red]Template error: {exc}[/bold red]")
        sys.exit(1)

    scores = [ch["hardcord_score"] for ch in channels[:top_n]]
    max_score = max(scores) if scores else 1
    rendered = template.render(
        channels=channels[:top_n],
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        region_code=region_code,
        high_threshold=max_score * 0.66,
        mid_threshold=max_score * 0.33,
        total_channels=len(channels),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    console.print(f"[bold green]HTML report saved to:[/bold green] {output_path}")


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------


def save_csv_report(channels: list[dict], output_path: str) -> None:
    if not channels:
        console.print("[yellow]No data to save to CSV.[/yellow]")
        return
    fieldnames = ["rank", "channel_name", "category", "subscribers", "total_views",
                  "avg_likes", "engagement_rate", "hardcord_score", "trending_video_count", "channel_id"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(channels)
    console.print(f"[bold green]CSV report saved to:[/bold green] {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="YouTube Top Program Analysis — Hardcord Ad Targeting Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyzer.py
  python analyzer.py --region LK --max-results 50
  python analyzer.py --category 24
  python analyzer.py --region US --category 25 --output html
  python analyzer.py --output csv
  python analyzer.py --top 10

Category IDs:
  24 = Entertainment    25 = News & Politics
  26 = Howto & Style    10 = Music
  17 = Sports           20 = Gaming
  27 = Education        28 = Science & Technology
        """,
    )
    parser.add_argument("--region", default=None, help="ISO region code (default from .env or LK)")
    parser.add_argument("--max-results", type=int, default=None, help="Videos to fetch (default 50)")
    parser.add_argument("--category", default=None, help="Category ID filter (e.g. 24=Entertainment)")
    parser.add_argument("--output", choices=["html", "csv", "both"], default="both")
    parser.add_argument("--top", type=int, default=20, help="Top N channels to display (default 20)")
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        console.print(
            "[bold red]Error:[/bold red] YOUTUBE_API_KEY is not set.\n"
            "Copy [bold].env.example[/bold] to [bold].env[/bold] and add your API key."
        )
        sys.exit(1)

    region_code = (args.region or os.getenv("REGION_CODE", "LK")).upper()
    max_results = args.max_results or int(os.getenv("MAX_RESULTS", "50"))
    max_results = max(1, min(max_results, 200))
    category_id = args.category
    top_n = args.top

    console.print(
        f"\n[bold cyan]YouTube Trend Analyzer[/bold cyan] — Hardcord Targeting\n"
        f"Region: [yellow]{region_code}[/yellow]  |  "
        f"Max results: [yellow]{max_results}[/yellow]  |  "
        f"Category: [yellow]{category_id or 'All'}[/yellow]\n"
    )

    console.print(f"[dim]Fetching trending videos for region {region_code}...[/dim]")
    videos = fetch_trending_videos(api_key, region_code=region_code, max_results=max_results, category_id=category_id)

    if not videos:
        console.print("[bold yellow]No trending videos found for the given parameters.[/bold yellow]")
        sys.exit(0)

    console.print(f"[green]Fetched {len(videos)} trending videos.[/green]")

    channel_ids = list({v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")})
    console.print(f"[dim]Fetching details for {len(channel_ids)} unique channels...[/dim]")
    channel_details = fetch_channel_details(api_key, channel_ids)

    console.print("[dim]Computing Hardcord Scores...[/dim]")
    ranked_channels = aggregate_channel_data(videos, channel_details)

    if not ranked_channels:
        console.print("[bold yellow]No channel data could be aggregated.[/bold yellow]")
        sys.exit(0)

    print_rich_table(ranked_channels, top_n=top_n)

    date_str = datetime.now().strftime("%Y-%m-%d")
    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.output in ("html", "both"):
        render_html_report(ranked_channels, region_code, os.path.join(base_dir, f"report_{date_str}.html"), top_n=top_n)

    if args.output in ("csv", "both"):
        save_csv_report(ranked_channels, os.path.join(base_dir, f"report_{date_str}.csv"))

    console.print("\n[bold green]Analysis complete.[/bold green]\n")


if __name__ == "__main__":
    main()
