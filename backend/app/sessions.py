"""Processed videos kept in memory (transcripts are also cached on disk)."""

import threading
from dataclasses import dataclass, field

from . import youtube
from .rag import VideoIndex, build_chunks
from .transcript import Transcript, TranscriptError, get_transcript


@dataclass
class VideoSession:
    video_id: str
    title: str
    author: str
    thumbnail: str
    transcript: Transcript
    index: VideoIndex
    notes: dict | None = None
    notes_lock: threading.Lock = field(default_factory=threading.Lock)

    def info(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "author": self.author,
            "thumbnail": self.thumbnail,
            "source": self.transcript.source,
            "language": self.transcript.language,
            "duration_seconds": self.transcript.duration_seconds,
            "word_count": len(self.transcript.text.split()),
        }


_sessions: dict[str, VideoSession] = {}
_locks: dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def get_session(video_id: str) -> VideoSession:
    """Returns the processed video, fetching and indexing it the first time."""
    if video_id in _sessions:
        return _sessions[video_id]

    with _registry_lock:
        lock = _locks.setdefault(video_id, threading.Lock())

    # Only one request processes a given video; others wait for it.
    with lock:
        if video_id in _sessions:
            return _sessions[video_id]

        meta = youtube.fetch_metadata(video_id)
        if meta is None:
            raise TranscriptError("This video doesn't exist or is private.")
        transcript = get_transcript(video_id)
        session = VideoSession(
            video_id=video_id,
            title=meta.title,
            author=meta.author,
            thumbnail=meta.thumbnail,
            transcript=transcript,
            index=VideoIndex(build_chunks(transcript.segments)),
        )
        _sessions[video_id] = session
        return session
