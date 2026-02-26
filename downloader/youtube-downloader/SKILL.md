---
name: youtube-downloader
description: Download YouTube videos with customizable quality and format options. Use this skill when the user asks to download, save, or grab YouTube videos. Supports various quality settings (best, 1080p, 720p, 480p, 360p), multiple formats (mp4, webm, mkv), and audio-only downloads as MP3.
---

# YouTube Video Downloader

Download YouTube videos with full control over quality and format settings.

# Structure:

~/.openclaw/workspace/skills/downloader/youtube-downloader/
├── scripts/
│   └── download_video.py
├── outputs/
└── SKILL.md

# All downloaded videos are saved to:

~/.openclaw/workspace/skills/youtube-downloader/outputs/


## Quick Start

From inside the skill folder:

```bash
cd ~/.openclaw/workspace/skills/downloader/youtube-downloader
python scripts/download_video.py "https://www.youtube.com/watch?v=VIDEO_ID"

By default, this downloads the video in best quality (MP4) into:

~/.openclaw/workspace/skills/downloader/youtube-downloader/outputs/

## Options

### Quality Settings

Use `-q` or `--quality` to specify video quality:

- `best` (default): Highest quality available
- `1080p`: Full HD
- `720p`: HD
- `480p`: Standard definition
- `360p`: Lower quality
- `worst`: Lowest quality available

Example:
```bash
python scripts/download_video.py "URL" -q 720p
```

### Format Options

Use `-f` or `--format` to specify output format (video downloads only):

- `mp4` (default): Most compatible
- `webm`: Modern format
- `mkv`: Matroska container

Example:
```bash
python scripts/download_video.py "URL" -f webm
```

### Audio Only

Use `-a` or `--audio-only` to download only audio as MP3:

```bash
python scripts/download_video.py "URL" -a
```

### Custom Output Directory

Use `-o` or `--output` to specify a different output directory:

```bash
python scripts/download_video.py "URL" -o /path/to/directory
```

## Complete Examples

1. Download video in 1080p as MP4:
```bash
python scripts/download_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 1080p
```

2. Download audio only as MP3:
```bash
python scripts/download_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -a
```

3. Download in 720p as WebM to custom directory:
```bash
python scripts/download_video.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" -q 720p -f webm -o /custom/path
```

# Output Folder Behavior

**Output directory is fixed to:**

~/.openclaw/workspace/skills/youtube-downloader/outputs/

The -o parameter is disabled to prevent writing outside the skill directory.

Filenames are automatically generated from the video title.

# How It Works

**This skill uses yt-dlp:**

- Automatically installs yt-dlp if missing
- Downloads video/audio streams
- Merges streams if required
- Skips playlists
- Saves files locally inside the skill folder

# Important Notes

- Internet access is required
- Only single videos are supported (no playlists)
- Large files require sufficient disk space
- Files are always saved inside the skill directory