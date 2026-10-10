"""Fallback transcript source using yt-dlp.

Used when youtube-transcript-api can't get captions (no captions, or YouTube blocked
the request). It tries YouTube's subtitles through yt-dlp first, and if there are
none, downloads the audio and transcribes it with Whisper on Groq.
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from groq import APIStatusError
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from . import config, llm
from .transcript import Segment, Transcript, TranscriptError

log = logging.getLogger(__name__)

# Audio is re-encoded to 16 kHz mono at 32 kbps (what Whisper uses internally anyway)
# and cut into 10-minute pieces, each about 2.4 MB, far below Groq's upload limit.
PIECE_SECONDS = 600

BLOCKED_MESSAGE = (
    "YouTube is blocking requests from this computer's IP address. "
    "Set YTDLP_COOKIES_FROM_BROWSER or a proxy in backend/.env (see README)."
)


def transcript_via_ytdlp(video_id: str) -> Transcript:
    with tempfile.TemporaryDirectory(prefix="vid2post_") as tmp:
        tmp_dir = Path(tmp)
        with YoutubeDL(_options(tmp_dir)) as ydl:
            info = _extract_info(ydl, video_id)

            subtitles = _subtitles(ydl, info)
            if subtitles:
                return Transcript(video_id=video_id, language=subtitles[0], source="captions", segments=subtitles[1])

            if not config.ENABLE_WHISPER_FALLBACK:
                raise TranscriptError("This video has no captions, and the Whisper fallback is turned off.")
            audio_file = _download_audio(ydl, info)

        return _transcribe(video_id, audio_file, tmp_dir)


def _options(tmp_dir: Path) -> dict:
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "source.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # YouTube requires solving a JavaScript challenge; Node.js is used for that.
        "js_runtimes": {"node": {}},
    }
    if config.PROXY_URL:
        options["proxy"] = config.PROXY_URL
    if config.YTDLP_COOKIES_FROM_BROWSER:
        options["cookiesfrombrowser"] = (config.YTDLP_COOKIES_FROM_BROWSER, None, None, None)
    return options


def _extract_info(ydl: YoutubeDL, video_id: str) -> dict:
    try:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except DownloadError as exc:
        message = str(exc)
        log.warning("yt-dlp failed for %s: %s", video_id, message)
        if "Sign in to confirm" in message or "not a bot" in message:
            raise TranscriptError(BLOCKED_MESSAGE)
        if "age" in message.lower() and "sign in" in message.lower():
            raise TranscriptError("This video is age-restricted, so its transcript can't be accessed.")
        if "cookies" in message.lower() and config.YTDLP_COOKIES_FROM_BROWSER:
            raise TranscriptError(
                f"Couldn't read cookies from {config.YTDLP_COOKIES_FROM_BROWSER}. "
                "Close the browser completely and try again, or use Firefox."
            )
        raise TranscriptError("Couldn't load this video from YouTube.")


# ── Subtitles ───────────────────────────────────────────────────────────────

def _pick_track(info: dict) -> tuple[str, list[dict]] | None:
    """Prefers English, and manual subtitles over auto-generated ones."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    original = info.get("language")

    candidates = []
    candidates += [(lang, tracks) for lang, tracks in manual.items() if lang.startswith("en")]
    candidates += [(lang, auto[lang]) for lang in ("en-orig", "en") if lang in auto]
    candidates += [(lang, tracks) for lang, tracks in manual.items() if lang != "live_chat"]
    if original and f"{original}-orig" in auto:
        candidates.append((original, auto[f"{original}-orig"]))

    for lang, tracks in candidates:
        if any(t.get("ext") == "json3" for t in tracks):
            return lang.removesuffix("-orig"), tracks
    return None


def _subtitles(ydl: YoutubeDL, info: dict) -> tuple[str, list[Segment]] | None:
    picked = _pick_track(info)
    if not picked:
        return None
    language, tracks = picked
    url = next(t["url"] for t in tracks if t.get("ext") == "json3")
    try:
        data = json.loads(ydl.urlopen(url).read().decode("utf-8"))
    except Exception:
        log.exception("Downloading subtitles failed")
        return None

    segments = []
    for event in data.get("events", []):
        text = " ".join("".join(seg.get("utf8", "") for seg in event.get("segs") or []).split())
        if text:
            segments.append(
                Segment(
                    start=round(event.get("tStartMs", 0) / 1000, 2),
                    duration=round(event.get("dDurationMs", 0) / 1000, 2),
                    text=text,
                )
            )
    return (language, segments) if segments else None


# ── Audio + Whisper ─────────────────────────────────────────────────────────

def _download_audio(ydl: YoutubeDL, info: dict) -> Path:
    if info.get("is_live"):
        raise TranscriptError("This is a live stream. Try again once the stream has ended.")
    minutes = (info.get("duration") or 0) / 60
    if minutes > config.WHISPER_MAX_VIDEO_MINUTES:
        raise TranscriptError(
            f"This video has no captions and is {minutes:.0f} minutes long. "
            f"Audio transcription is limited to {config.WHISPER_MAX_VIDEO_MINUTES} minutes."
        )
    try:
        info = ydl.process_ie_result(info, download=True)
    except DownloadError as exc:
        log.warning("Audio download failed: %s", exc)
        raise TranscriptError("Couldn't download this video's audio for transcription.")
    return Path(info["requested_downloads"][0]["filepath"])


def _transcribe(video_id: str, audio_file: Path, tmp_dir: Path) -> Transcript:
    segments: list[Segment] = []
    language = "en"
    for index, piece in enumerate(_split_audio(audio_file, tmp_dir)):
        offset = index * PIECE_SECONDS
        result = _transcribe_piece(piece)
        language = result.get("language") or language
        for seg in result.get("segments") or []:
            text = " ".join(str(seg.get("text", "")).split())
            if text:
                start = float(seg.get("start", 0))
                end = float(seg.get("end", start))
                segments.append(Segment(start=round(offset + start, 2), duration=round(end - start, 2), text=text))
        if not result.get("segments") and result.get("text"):
            segments.append(Segment(start=offset, duration=PIECE_SECONDS, text=result["text"].strip()))
    return Transcript(video_id=video_id, language=_language_code(language), source="whisper", segments=segments)


def _split_audio(source: Path, tmp_dir: Path) -> list[Path]:
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
        "-f", "segment", "-segment_time", str(PIECE_SECONDS), "-reset_timestamps", "1",
        str(tmp_dir / "piece_%03d.mp3"),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("ffmpeg failed: %s", result.stderr)
        raise TranscriptError("Couldn't process this video's audio.")
    return sorted(tmp_dir.glob("piece_*.mp3"))


def _transcribe_piece(path: Path) -> dict:
    try:
        with path.open("rb") as audio:
            response = llm.client().audio.transcriptions.create(
                file=(path.name, audio.read()),
                model=config.WHISPER_MODEL,
                response_format="verbose_json",
                temperature=0,
            )
    except APIStatusError as exc:
        log.error("Groq Whisper failed: %s", exc)
        if exc.status_code == 429:
            raise TranscriptError("Groq's audio transcription limit was reached. Try again in a while.")
        raise TranscriptError("Audio transcription failed.")
    return response.model_dump()


LANGUAGE_NAMES = {"english": "en", "urdu": "ur", "hindi": "hi", "arabic": "ar", "spanish": "es", "french": "fr", "german": "de"}


def _language_code(language: str) -> str:
    # Whisper reports full names ("English"); captions use codes ("en").
    return LANGUAGE_NAMES.get(language.lower(), language.lower())
