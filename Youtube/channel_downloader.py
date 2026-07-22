#!/usr/bin/env python3
"""
YouTube Channel Downloader
===========================
Downloads ALL videos from a YouTube channel in the BEST available quality
(Full HD 1080p or higher — no resolution downgrade).

Usage:
    python3 channel_downloader.py <channel_url>

Examples:
    python3 channel_downloader.py https://www.youtube.com/@ChannelName
    python3 channel_downloader.py https://www.youtube.com/c/ChannelName
    python3 channel_downloader.py https://www.youtube.com/channel/UC...

Requirements:
    pip3 install yt-dlp
    ffmpeg (must be installed on system)
"""

import sys
import os
import json
import time
import yt_dlp


# ─── Configuration ────────────────────────────────────────────────────────────

# Format: Best video (1080p or higher) + best audio, merged into mp4
# Falls back to best available single file if merge isn't possible
FORMAT_SELECTION = (
    "bestvideo[height>=1080]+bestaudio/best[height>=1080]/bestvideo+bestaudio/best"
)

# Output template: Channel Name / Video Title [ID].ext
OUTPUT_TEMPLATE = "%(channel)s/%(title)s [%(id)s].%(ext)s"

# Download archive file — tracks already downloaded videos to avoid re-downloading
ARCHIVE_FILE = "downloaded_archive.txt"

# ─── Colors for terminal output ───────────────────────────────────────────────

class Colors:
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║            🎬  YouTube Channel Downloader  🎬               ║
║          Full HD+ • No Resolution Downgrade                 ║
╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}"""
    print(banner)


def get_channel_videos(channel_url):
    """
    Extract the list of all videos from a YouTube channel.
    Returns a list of dicts with video info (title, url, duration, etc.)
    """
    print(f"\n{Colors.YELLOW}📡 Fetching video list from channel...{Colors.RESET}")
    print(f"{Colors.DIM}   This may take a while for channels with many videos.{Colors.RESET}\n")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,       # Don't download, just list
        "force_generic_extractor": False,
    }

    videos = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(channel_url, download=False)
        except yt_dlp.utils.DownloadError as e:
            print(f"{Colors.RED}✖ Error fetching channel: {e}{Colors.RESET}")
            sys.exit(1)

        if info is None:
            print(f"{Colors.RED}✖ Could not retrieve channel information.{Colors.RESET}")
            sys.exit(1)

        channel_name = info.get("channel", info.get("uploader", info.get("title", "Unknown")))

        # Handle playlists / channel tabs10277
        entries = info.get("entries", [])
        if entries is None:
            entries = []

        for entry in entries:
            if entry is None:
                continue

            # Some channels return nested playlists (tabs like Videos, Shorts, etc.)
            if entry.get("_type") == "playlist" or "entries" in entry:
                sub_entries = entry.get("entries", [])
                if sub_entries:
                    for sub in sub_entries:
                        if sub and sub.get("url"):
                            videos.append({
                                "id": sub.get("id", ""),
                                "title": sub.get("title", "Unknown Title"),
                                "url": sub.get("url", ""),
                                "duration": sub.get("duration"),
                            })
            elif entry.get("url"):
                videos.append({
                    "id": entry.get("id", ""),
                    "title": entry.get("title", "Unknown Title"),
                    "url": entry.get("url", ""),
                    "duration": entry.get("duration"),
                })

    return channel_name, videos


def format_duration(seconds):
    """Convert seconds to HH:MM:SS or MM:SS format."""
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def list_videos(videos):
    """Print a numbered list of all videos."""
    print(f"\n{Colors.BOLD}{'#':>4}  {'Duration':>10}  Title{Colors.RESET}")
    print(f"{'─' * 80}")

    for i, video in enumerate(videos, 1):
        duration = format_duration(video.get("duration"))
        title = video["title"]
        if len(title) > 58:
            title = title[:55] + "..."
        print(f"{Colors.CYAN}{i:>4}{Colors.RESET}  {Colors.DIM}{duration:>10}{Colors.RESET}  {title}")

    print(f"{'─' * 80}")
    print(f"{Colors.GREEN}{Colors.BOLD}Total: {len(videos)} videos{Colors.RESET}\n")


def download_progress_hook(d):
    """Progress hook for yt-dlp downloads."""
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "N/A")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")
        print(
            f"\r   {Colors.BLUE}⬇  {percent}  |  Speed: {speed}  |  ETA: {eta}{Colors.RESET}   ",
            end="",
            flush=True,
        )
    elif d["status"] == "finished":
        print(f"\r   {Colors.GREEN}✔ Download complete, merging...{Colors.RESET}                              ")


def download_videos(videos, channel_name):
    """
    Download all videos one by one in Full HD+ (best available quality).
    Skips already downloaded videos using the archive file.
    """
    total = len(videos)
    downloaded = 0
    skipped = 0
    failed = 0
    failed_videos = []

    ydl_opts = {
        "format": FORMAT_SELECTION,
        "outtmpl": OUTPUT_TEMPLATE,
        "merge_output_format": "mp4",          # Merge into mp4
        "download_archive": ARCHIVE_FILE,       # Skip already downloaded
        "progress_hooks": [download_progress_hook],
        "retries": 5,                           # Retry failed downloads
        "fragment_retries": 5,
        "continuedl": True,                     # Resume partial downloads
        "noplaylist": True,                     # Download single video, not playlist
        "writesubtitles": False,
        "writethumbnail": False,
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        # Ensure we get the absolute best quality
        "format_sort": ["res:2160", "res:1440", "res:1080"],
    }

    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}  🚀 Starting downloads — {total} videos from '{channel_name}'{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}\n")

    for i, video in enumerate(videos, 1):
        title = video["title"]
        if len(title) > 55:
            display_title = title[:52] + "..."
        else:
            display_title = title

        print(f"\n{Colors.YELLOW}[{i}/{total}]{Colors.RESET} {Colors.BOLD}{display_title}{Colors.RESET}")
        print(f"   {Colors.DIM}URL: https://www.youtube.com/watch?v={video['id']}{Colors.RESET}")

        video_url = video["url"]
        # Ensure we have a full URL
        if not video_url.startswith("http"):
            video_url = f"https://www.youtube.com/watch?v={video['id']}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([video_url])

            if result == 0:
                downloaded += 1
                print(f"   {Colors.GREEN}✔ Saved successfully{Colors.RESET}")
            else:
                # result != 0 but no exception — likely skipped (already in archive)
                skipped += 1
                print(f"   {Colors.DIM}⏭ Already downloaded (skipped){Colors.RESET}")

        except yt_dlp.utils.DownloadError as e:
            failed += 1
            failed_videos.append({"title": title, "error": str(e)})
            print(f"   {Colors.RED}✖ Failed: {e}{Colors.RESET}")
            continue
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⚠ Download interrupted by user.{Colors.RESET}")
            break
        except Exception as e:
            failed += 1
            failed_videos.append({"title": title, "error": str(e)})
            print(f"   {Colors.RED}✖ Unexpected error: {e}{Colors.RESET}")
            continue

    # ─── Summary ──────────────────────────────────────────────────────────
    print(f"\n\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}  📊  Download Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.RESET}")
    print(f"   {Colors.GREEN}✔ Downloaded : {downloaded}{Colors.RESET}")
    print(f"   {Colors.DIM}⏭ Skipped    : {skipped}{Colors.RESET}")
    print(f"   {Colors.RED}✖ Failed     : {failed}{Colors.RESET}")
    print(f"   {Colors.BOLD}  Total      : {total}{Colors.RESET}")

    if failed_videos:
        print(f"\n{Colors.RED}{Colors.BOLD}  Failed Videos:{Colors.RESET}")
        for fv in failed_videos:
            print(f"   • {fv['title']}")
            print(f"     {Colors.DIM}{fv['error']}{Colors.RESET}")

    print(f"\n{Colors.GREEN}📂 Videos saved to: ./{channel_name}/{Colors.RESET}\n")


def main():
    print_banner()

    # ─── Get channel URL ──────────────────────────────────────────────────
    if len(sys.argv) > 1:
        channel_url = sys.argv[1]
    else:
        print(f"{Colors.BOLD}Enter YouTube Channel URL:{Colors.RESET}")
        print(f"{Colors.DIM}  Examples:{Colors.RESET}")
        print(f"{Colors.DIM}    https://www.youtube.com/@ChannelName{Colors.RESET}")
        print(f"{Colors.DIM}    https://www.youtube.com/c/ChannelName{Colors.RESET}")
        print(f"{Colors.DIM}    https://www.youtube.com/channel/UC...{Colors.RESET}")
        print()
        channel_url = input(f"{Colors.CYAN}▶ URL: {Colors.RESET}").strip()

    if not channel_url:
        print(f"{Colors.RED}✖ No URL provided. Exiting.{Colors.RESET}")
        sys.exit(1)

    # Ensure we're targeting the /videos tab for a complete list
    if "/videos" not in channel_url and "/playlists" not in channel_url:
        if channel_url.endswith("/"):
            channel_url += "videos"
        else:
            channel_url += "/videos"

    # ─── Step 1: List all videos ──────────────────────────────────────────
    channel_name, videos = get_channel_videos(channel_url)

    if not videos:
        print(f"{Colors.RED}✖ No videos found on this channel.{Colors.RESET}")
        sys.exit(1)

    print(f"\n{Colors.GREEN}{Colors.BOLD}📺 Channel: {channel_name}{Colors.RESET}")
    list_videos(videos)

    # ─── Step 2: Confirm and download ─────────────────────────────────────
    print(f"{Colors.YELLOW}Ready to download {len(videos)} videos in BEST quality (Full HD+)?{Colors.RESET}")
    confirm = input(f"{Colors.CYAN}▶ Proceed? [Y/n]: {Colors.RESET}").strip().lower()

    if confirm in ("n", "no"):
        print(f"{Colors.DIM}Cancelled.{Colors.RESET}")
        sys.exit(0)

    # ─── Step 3: Download all videos ──────────────────────────────────────
    download_videos(videos, channel_name)


if __name__ == "__main__":
    main()
