---
name: image-downloader
description: Download images and galleries from 100+ image hosting sites
---

# Gallery-DL Skill

Download images and galleries from 100+ image hosting sites using `gallery-dl`.

## Supported Sites

- **Social**: Twitter/X, Instagram, Reddit, Tumblr, Bluesky
- **Art Platforms**: DeviantArt, ArtStation, Pixiv, Newgrounds
- **Image Boards**: Danbooru, Gelbooru, e621, Rule34
- **Manga**: MangaDex, Webtoon, Tapas
- **Photo**: Flickr, 500px, Imgur
- And [many more...](https://github.com/mikf/gallery-dl/blob/master/docs/supportedsites.md)

## Capabilities

| Action | Description |
|--------|-------------|
| `download_gallery` | Download images from URL |
| `download_user` | Download all images from a user/artist |
| `get_urls` | Extract direct image URLs without downloading |
| `download_with_filter` | Download with content filtering |

## Requirements

```bash
pip install gallery-dl
```

## Authentication

For sites requiring login, set credentials in config or env:

```bash
export GALLERY_DL_USER="username"
export GALLERY_DL_PASS="password"
```

Or use browser cookies:
```python
skill.download_gallery(url, cookies_from="firefox")
```

## Usage Examples

### Download Gallery
```python
from rhea_noir.skills.gallerydl.actions import skill as gallery

result = gallery.download_gallery(
    url="https://www.deviantart.com/artist/gallery",
    output_dir="./images"
)
```

### Download User's Images
```python
result = gallery.download_user(
    url="https://twitter.com/username",
    output_dir="./images",
    limit=100
)
```

### Get Image URLs Only
```python
result = gallery.get_urls("https://imgur.com/a/albumid")
# Returns list of direct image URLs
```

### Download with Filter
```python
result = gallery.download_with_filter(
    url="https://danbooru.donmai.us/posts?tags=landscape",
    min_width=1920,
    file_types=["jpg", "png"]
)
```

## Output Templates

Default: `{category}/{subcategory}/{filename}.{extension}`

Custom templates available via `output_template` parameter.