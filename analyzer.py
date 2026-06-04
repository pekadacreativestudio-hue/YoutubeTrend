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

import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
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

console = Console()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def build_youtube_client(api_key: str):
    """Build and return the YouTube Data API v3 client."""
    return build("youtube", "v3", developerKey=api_key)


def fetch_trending_videos(
    youtube,
    region_code: str = "LK",
    max_results: int = 50,
    category_id: str | None = None,
) -> list[dict]:
    """
    Fetch trending videos for the given region (and optional category).
    Handles pagination to collect up to max_results videos.
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

        try:
            response = youtube.videos().list(**params).execute()
        except HttpError as exc:
            if exc.resp.status == 403:
                console.print(
                    "[bold red]API quota exceeded or key invalid. "
                    "Check your YOUTUBE_API_KEY and daily quota.[/bold red]"
                )
                sys.exit(1)
            raise

        items = response.get("items", [])
        videos.extend(items)
        remaining -= len(items)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def fetch_channel_details(youtube, channel_ids: list[str]) -> dict[str, dict]:
    """
    Fetch snippet + statistics for a list of channel IDs (batched in 50s).
    Returns a dict keyed by channel_id.
    """
    details: dict[str, dict] = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        try:
            response = (
                youtube.channels()
                .list(
                    part="snippet,statistics",
                    id=",".join(batch),
                )
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status == 403:
                console.print(
                    "[bold red]API quota exceeded while fetching channel details.[/bold red]"
                )
                sys.exit(1)
            raise

        for item in response.get("items", []):
            details[item["id"]] = item

    return details


# ---------------------------------------------------------------------------
# Scoring & aggregation
# ---------------------------------------------------------------------------


def safe_int(value, default: int = 0) -> int:
    """Convert a string/None to int safely."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def compute_hardcord_score(
    views: int, likes: int, subscribers: int
) -> float:
    """
    Hardcord Score formula:
        score = (views / 1_000_000)
                * (likes / max(views, 1) * 100)
                * log10(max(subscribers, 1))

    Higher score = better ad-placement candidate.
    """
    engagement_rate = (likes / max(views, 1)) * 100
    score = (views / 1_000_000) * engagement_rate * log10(max(subscribers, 1))
    return round(score, 4)


def aggregate_channel_data(
    videos: list[dict], channel_details: dict[str, dict]
) -> list[dict]:
    """
    Aggregate per-video stats up to the channel level.
    If a channel has multiple trending videos their stats are combined.
    Returns a list of channel-level dicts ready for ranking.
    """
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
                "channel_name": ch_snippet.get(
                    "title", snippet.get("channelTitle", "Unknown")
                ),
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
        score = compute_hardcord_score(
            ch["total_views"], ch["total_likes"], ch["subscribers"]
        )
        engagement_rate = round(
            (ch["total_likes"] / max(ch["total_views"], 1)) * 100, 4
        )

        result.append(
            {
                "channel_id": ch["channel_id"],
                "channel_name": ch["channel_name"],
                "category": ch["category"],
                "subscribers": ch["subscribers"],
                "total_views": ch["total_views"],
                "avg_likes": avg_likes,
                "engagement_rate": engagement_rate,
                "hardcord_score": score,
                "trending_video_count": video_count,
            }
        )

    # Sort descending by hardcord score
    result.sort(key=lambda x: x["hardcord_score"], reverse=True)
    for rank, row in enumerate(result, start=1):
        row["rank"] = rank

    return result


# ---------------------------------------------------------------------------
# Output: Rich CLI table
# ---------------------------------------------------------------------------


def print_rich_table(channels: list[dict], top_n: int = 20) -> None:
    """Display top N channels as a styled Rich table in the terminal."""
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
        score = ch["hardcord_score"]
        score_str = f"{score:.4f}"

        table.add_row(
            str(ch["rank"]),
            ch["channel_name"],
            ch["category"],
            f"{ch['total_views']:,}",
            f"{ch['avg_likes']:,}",
            f"{ch['subscribers']:,}",
            score_str,
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


def render_html_report(
    channels: list[dict],
    region_code: str,
    output_path: str,
    top_n: int = 20,
) -> None:
    """Render a styled HTML report using the Jinja2 template."""
    template_dir = os.path.dirname(os.path.abspath(__file__))
    env = Environment(loader=FileSystemLoader(template_dir))

    try:
        template = env.get_template("report_template.html")
    except Exception as exc:
        console.print(f"[bold red]Template error: {exc}[/bold red]")
        sys.exit(1)

    # Determine score thresholds for color-coding
    scores = [ch["hardcord_score"] for ch in channels[:top_n]]
    max_score = max(scores) if scores else 1
    high_threshold = max_score * 0.66
    mid_threshold = max_score * 0.33

    rendered = template.render(
        channels=channels[:top_n],
        generated_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        region_code=region_code,
        high_threshold=high_threshold,
        mid_threshold=mid_threshold,
        total_channels=len(channels),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    console.print(f"[bold green]HTML report saved to:[/bold green] {output_path}")


# ---------------------------------------------------------------------------
# Output: CSV
# ---------------------------------------------------------------------------


def save_csv_report(channels: list[dict], output_path: str) -> None:
    """Save all channel data to a CSV file."""
    if not channels:
        console.print("[yellow]No data to save to CSV.[/yellow]")
        return

    fieldnames = [
        "rank",
        "channel_name",
        "category",
        "subscribers",
        "total_views",
        "avg_likes",
        "engagement_rate",
        "hardcord_score",
        "trending_video_count",
        "channel_id",
    ]

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
  24 = Entertainment
  25 = News & Politics
  26 = Howto & Style
  10 = Music
  17 = Sports
  20 = Gaming
  27 = Education
  28 = Science & Technology
        """,
    )
    parser.add_argument(
        "--region",
        default=None,
        help="ISO 3166-1 alpha-2 region code (default from .env or LK)",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Number of trending videos to fetch (default from .env or 50)",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="YouTube video category ID to filter by (e.g. 24 for Entertainment)",
    )
    parser.add_argument(
        "--output",
        choices=["html", "csv", "both"],
        default="both",
        help="Output format: html, csv, or both (default: both)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top channels to display/report (default: 20)",
    )
    return parser.parse_args()


def main():
    load_dotenv()

    args = parse_args()

    # Resolve config from args > env > defaults
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not api_key or api_key == "your_api_key_here":
        console.print(
            "[bold red]Error:[/bold red] YOUTUBE_API_KEY is not set.\n"
            "Copy [bold].env.example[/bold] to [bold].env[/bold] and add your API key.\n"
            "See README.md for instructions on obtaining a YouTube Data API key."
        )
        sys.exit(1)

    region_code = (args.region or os.getenv("REGION_CODE", "LK")).upper()
    max_results = args.max_results or int(os.getenv("MAX_RESULTS", "50"))
    max_results = max(1, min(max_results, 200))  # clamp to sane range
    category_id = args.category
    top_n = args.top

    console.print(
        f"\n[bold cyan]YouTube Trend Analyzer[/bold cyan] — Hardcord Targeting\n"
        f"Region: [yellow]{region_code}[/yellow]  |  "
        f"Max results: [yellow]{max_results}[/yellow]  |  "
        f"Category: [yellow]{category_id or 'All'}[/yellow]\n"
    )

    # Build API client
    console.print("[dim]Building YouTube API client...[/dim]")
    youtube = build_youtube_client(api_key)

    # Fetch trending videos
    console.print(f"[dim]Fetching trending videos for region {region_code}...[/dim]")
    videos = fetch_trending_videos(
        youtube,
        region_code=region_code,
        max_results=max_results,
        category_id=category_id,
    )

    if not videos:
        console.print(
            "[bold yellow]No trending videos found for the given parameters.[/bold yellow]"
        )
        sys.exit(0)

    console.print(f"[green]Fetched {len(videos)} trending videos.[/green]")

    # Collect unique channel IDs
    channel_ids = list(
        {v["snippet"]["channelId"] for v in videos if v.get("snippet", {}).get("channelId")}
    )
    console.print(f"[dim]Fetching details for {len(channel_ids)} unique channels...[/dim]")

    channel_details = fetch_channel_details(youtube, channel_ids)

    # Aggregate & score
    console.print("[dim]Computing Hardcord Scores...[/dim]")
    ranked_channels = aggregate_channel_data(videos, channel_details)

    if not ranked_channels:
        console.print("[bold yellow]No channel data could be aggregated.[/bold yellow]")
        sys.exit(0)

    # Display Rich table
    print_rich_table(ranked_channels, top_n=top_n)

    # Generate output files
    date_str = datetime.now().strftime("%Y-%m-%d")

    if args.output in ("html", "both"):
        html_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"report_{date_str}.html",
        )
        render_html_report(ranked_channels, region_code, html_path, top_n=top_n)

    if args.output in ("csv", "both"):
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"report_{date_str}.csv",
        )
        save_csv_report(ranked_channels, csv_path)

    console.print("\n[bold green]Analysis complete.[/bold green]\n")


if __name__ == "__main__":
    main()
