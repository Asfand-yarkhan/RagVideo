"""Chunking a transcript and searching it with Hugging Face embeddings."""

import threading
from dataclasses import dataclass

import numpy as np

from . import config
from .transcript import Segment

_model = None
_model_lock = threading.Lock()


def embedding_model():
    """The sentence-transformers model, downloaded from Hugging Face on first use."""
    global _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(config.EMBEDDING_MODEL)
    return _model


def _query_prefix() -> str:
    # BGE English models retrieve better when queries carry this instruction.
    name = config.EMBEDDING_MODEL.lower()
    if "bge-" in name and "-en" in name:
        return "Represent this sentence for searching relevant passages: "
    return ""


def embed(texts: list[str], is_query: bool = False) -> np.ndarray:
    if is_query:
        texts = [_query_prefix() + t for t in texts]
    return embedding_model().encode(texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32)


@dataclass
class Chunk:
    text: str
    start: float  # seconds into the video where this chunk begins


def build_chunks(segments: list[Segment], target_chars: int = 1000, overlap_segments: int = 2) -> list[Chunk]:
    """Groups caption segments into ~target_chars chunks, keeping each chunk's start time."""
    chunks: list[Chunk] = []
    i = 0
    while i < len(segments):
        j, size = i, 0
        while j < len(segments) and (size < target_chars or j == i):
            size += len(segments[j].text) + 1
            j += 1
        chunks.append(Chunk(text=" ".join(s.text for s in segments[i:j]), start=segments[i].start))
        if j >= len(segments):
            break
        i = max(j - overlap_segments, i + 1)
    return chunks


class VideoIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.vectors = embed([c.text for c in chunks]) if chunks else np.zeros((0, 1))

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        if not self.chunks:
            return []
        scores = self.vectors @ embed([query], is_query=True)[0]
        top = np.argsort(-scores)[:k]
        # Return in video order so the LLM reads the context chronologically.
        return [self.chunks[i] for i in sorted(top)]


def format_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
