#!/usr/bin/env python3
"""
YouTube Video Downloader
Downloads videos from YouTube with customizable quality and format options.
"""
import argparse
import subprocess
import sys
from pathlib import Path
import shutil


# ======== FIXED PATH CONFIG ========

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/youtube-downloader"
OUTPUT_DIR = SKILL_DIR / "outputs"

# Создаём папку outputs если её нет
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ======== Ensure yt-dlp is installed ========

def ensure_ytdlp():
    if shutil.which("yt-dlp") is None:
        print("yt-dlp not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    else:
        print("yt-dlp is available.")


# ======== Quality mapping ========

def build_format_string(quality: str, fmt: str, audio_only: bool):
    if audio_only:
        return "bestaudio"

    if quality == "best":
        return f"bestvideo+bestaudio/best"

    if quality == "worst":
        return "worst"

    # For specific resolutions
    resolution = quality.replace("p", "")
    return f"bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]"


# ======== Main download function ========

def download_video(url: str, quality: str, fmt: str, audio_only: bool):
    ensure_ytdlp()

    format_string = build_format_string(quality, fmt, audio_only)

    output_template = str(OUTPUT_DIR / "%(title)s.%(ext)s")

    command = [
        "yt-dlp",
        "-f", format_string,
        "-o", output_template,
        "--no-playlist",
        url,
    ]

    if audio_only:
        command.extend([
            "--extract-audio",
            "--audio-format", "mp3"
        ])
    else:
        command.extend([
            "--merge-output-format", fmt
        ])

    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

    print(f"\n✅ Download complete. Files saved to:\n{OUTPUT_DIR}")


# ======== CLI ========

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Secure YouTube downloader")

    parser.add_argument("url", help="YouTube video URL")

    parser.add_argument(
        "-q", "--quality",
        default="best",
        choices=["best", "1080p", "720p", "480p", "360p", "worst"],
        help="Video quality"
    )

    parser.add_argument(
        "-f", "--format",
        default="mp4",
        choices=["mp4", "webm", "mkv"],
        help="Output format (video only)"
    )

    parser.add_argument(
        "-a", "--audio-only",
        action="store_true",
        help="Download audio only as MP3"
    )

    args = parser.parse_args()

    try:
        download_video(
            url=args.url,
            quality=args.quality,
            fmt=args.format,
            audio_only=args.audio_only
        )
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)