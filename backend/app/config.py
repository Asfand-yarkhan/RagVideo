"""Settings, read from backend/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # harmless on Windows, just noisy


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value and value.strip() else default


# ── Groq (LLMs + Whisper) ──────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
WRITER_MODEL = os.getenv("WRITER_MODEL", "openai/gpt-oss-120b")  # posts, notes, chat
FAST_MODEL = os.getenv("FAST_MODEL", "openai/gpt-oss-20b")  # summarising long videos, rewriting follow-ups
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")

# Groq's free tier allows roughly 8K tokens per minute per model, so a single
# request has to stay well below that. Longer transcripts are summarised in parts.
MAX_TRANSCRIPT_TOKENS_PER_CALL = _int("MAX_TRANSCRIPT_TOKENS_PER_CALL", 5000)

# ── Embeddings (Hugging Face, runs locally) ────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# ── YouTube ────────────────────────────────────────────────────────────────
# Optional proxy, needed once the app is deployed to a cloud server
# (YouTube blocks most data-center IPs). Either a full proxy URL ...
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None
# ... or Webshare "Residential" credentials (built into youtube-transcript-api).
WEBSHARE_PROXY_USERNAME = os.getenv("WEBSHARE_PROXY_USERNAME", "").strip() or None
WEBSHARE_PROXY_PASSWORD = os.getenv("WEBSHARE_PROXY_PASSWORD", "").strip() or None

# For local use when YouTube blocks your IP: yt-dlp reads your YouTube login straight
# from this browser ("firefox", "edge", "chrome", ...) each time. Nothing is saved
# in the project. Firefox works most reliably on Windows.
YTDLP_COOKIES_FROM_BROWSER = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip().lower() or None

# When a video has no captions, download its audio and transcribe it with Whisper.
ENABLE_WHISPER_FALLBACK = _bool("ENABLE_WHISPER_FALLBACK", True)
WHISPER_MAX_VIDEO_MINUTES = _int("WHISPER_MAX_VIDEO_MINUTES", 120)

# ── App ────────────────────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
TRANSCRIPT_CACHE_DIR = DATA_DIR / "transcripts"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
