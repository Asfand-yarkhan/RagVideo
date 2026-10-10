"""Getting a transcript: YouTube captions first, Whisper on the audio as a fallback."""

import json
import logging
from dataclasses import asdict, dataclass, field

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from . import config

log = logging.getLogger(__name__)


class TranscriptError(Exception):
    """Raised with a message that is safe to show to the user."""


@dataclass
class Segment:
    start: float  # seconds
    duration: float
    text: str


@dataclass
class Transcript:
    video_id: str
    language: str
    source: str  # "captions" or "whisper"
    segments: list[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    @property
    def duration_seconds(self) -> int:
        if not self.segments:
            return 0
        last = self.segments[-1]
        return int(last.start + last.duration)


# ── Cache (so a video is only ever fetched from YouTube once) ───────────────

def _cache_path(video_id: str):
    return config.TRANSCRIPT_CACHE_DIR / f"{video_id}.json"


def _load_cached(video_id: str) -> Transcript | None:
    path = _cache_path(video_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segments"] = [Segment(**s) for s in data["segments"]]
    return Transcript(**data)


def _save_cached(transcript: Transcript) -> None:
    config.TRANSCRIPT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(transcript.video_id).write_text(json.dumps(asdict(transcript), ensure_ascii=False), encoding="utf-8")


# ── Captions ────────────────────────────────────────────────────────────────

def _proxy_config():
    if config.WEBSHARE_PROXY_USERNAME and config.WEBSHARE_PROXY_PASSWORD:
        return WebshareProxyConfig(
            proxy_username=config.WEBSHARE_PROXY_USERNAME,
            proxy_password=config.WEBSHARE_PROXY_PASSWORD,
        )
    if config.PROXY_URL:
        return GenericProxyConfig(http_url=config.PROXY_URL, https_url=config.PROXY_URL)
    return None


def _clean(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def _fetch_captions(video_id: str) -> Transcript:
    api = YouTubeTranscriptApi(proxy_config=_proxy_config())
    available = api.list(video_id)

    # Prefer English (manual captions are tried before auto-generated ones).
    try:
        chosen = available.find_transcript(["en", "en-US", "en-GB"])
    except NoTranscriptFound:
        chosen = next(iter(available))
        if chosen.is_translatable:
            try:
                chosen = chosen.translate("en")
            except CouldNotRetrieveTranscript:
                pass  # keep the original language; the LLM can still work with it

    fetched = chosen.fetch()
    segments = [
        Segment(start=round(s.start, 2), duration=round(s.duration, 2), text=_clean(s.text))
        for s in fetched
        if _clean(s.text)
    ]
    return Transcript(video_id=video_id, language=fetched.language_code, source="captions", segments=segments)


# ── Public entry point ──────────────────────────────────────────────────────

def get_transcript(video_id: str) -> Transcript:
    cached = _load_cached(video_id)
    if cached:
        return cached

    try:
        transcript = _fetch_captions(video_id)
    except (TranscriptsDisabled, NoTranscriptFound, StopIteration):
        # No captions: yt-dlp will transcribe the audio with Whisper.
        transcript = _via_ytdlp(video_id)
    except (RequestBlocked, IpBlocked):
        # YouTube blocked the caption request. yt-dlp (with browser cookies, if set) may still get through.
        log.warning("Caption request blocked by YouTube for %s; trying yt-dlp", video_id)
        transcript = _via_ytdlp(video_id)
    except AgeRestricted:
        raise TranscriptError("This video is age-restricted, so its transcript can't be accessed.")
    except (VideoUnavailable, VideoUnplayable):
        raise TranscriptError("This video is unavailable (private, deleted, or region-locked).")
    except CouldNotRetrieveTranscript as exc:
        log.exception("Caption fetch failed for %s", video_id)
        raise TranscriptError(f"Couldn't get the transcript from YouTube: {exc.CAUSE_MESSAGE or 'unknown error'}")

    if not transcript.segments:
        raise TranscriptError("The transcript for this video is empty.")
    _save_cached(transcript)
    return transcript


def _via_ytdlp(video_id: str) -> Transcript:
    from .ytdlp_source import transcript_via_ytdlp  # imported lazily: yt-dlp is slow to import

    return transcript_via_ytdlp(video_id)
