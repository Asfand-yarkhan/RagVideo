"""YouTube URL parsing and lightweight video metadata."""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}


def extract_video_id(url_or_id: str) -> str | None:
    """Accepts watch, youtu.be, shorts, embed and live links, or a bare 11-character ID."""
    value = url_or_id.strip()
    if VIDEO_ID_RE.match(value):
        return value
    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    candidate = None

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in YOUTUBE_HOSTS:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live", "v", "e"}:
                candidate = parts[1]

    if candidate and VIDEO_ID_RE.match(candidate):
        return candidate
    return None


@dataclass
class VideoMeta:
    title: str
    author: str
    thumbnail: str


def fetch_metadata(video_id: str) -> VideoMeta | None:
    """Title and channel via YouTube's public oEmbed endpoint (no API key needed).

    Returns None when the video is private, deleted or doesn't exist.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        response = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=10,
        )
    except httpx.HTTPError:
        # Network hiccup: don't block processing over a title.
        return VideoMeta(title="YouTube video", author="", thumbnail=thumbnail_url(video_id))

    if response.status_code != 200:
        return None
    data = response.json()
    return VideoMeta(
        title=data.get("title") or "YouTube video",
        author=data.get("author_name") or "",
        thumbnail=thumbnail_url(video_id),
    )


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
