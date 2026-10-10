"""Vid2Post API: turn YouTube videos into social posts and chat with them."""

import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from groq import APIStatusError, AuthenticationError, RateLimitError
from pydantic import BaseModel, Field

from . import chat, config, posts
from .llm import LLMNotConfigured
from .sessions import get_session
from .transcript import TranscriptError
from .youtube import extract_video_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vid2post")

app = FastAPI(title="Vid2Post API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Errors → friendly JSON ──────────────────────────────────────────────────

@app.exception_handler(TranscriptError)
async def transcript_error(_: Request, exc: TranscriptError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(LLMNotConfigured)
async def llm_not_configured(_: Request, exc: LLMNotConfigured):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(AuthenticationError)
async def groq_auth_error(_: Request, exc: AuthenticationError):
    return JSONResponse(status_code=500, content={"detail": "Your Groq API key was rejected. Check GROQ_API_KEY in backend/.env."})


@app.exception_handler(RateLimitError)
async def groq_rate_limit(_: Request, exc: RateLimitError):
    return JSONResponse(status_code=429, content={"detail": "Groq's rate limit was reached. Wait a minute and try again."})


@app.exception_handler(APIStatusError)
async def groq_error(_: Request, exc: APIStatusError):
    log.error("Groq API error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": "The AI service returned an error. Please try again."})


# ── Schemas ─────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)


class PostRequest(BaseModel):
    platform: Literal["linkedin", "x_thread", "x_post"] = "linkedin"
    tone: Literal["professional", "casual", "storytelling", "educational", "bold"] = "professional"
    length: Literal["short", "medium", "long"] = "medium"
    emojis: bool = False
    hashtags: bool = True
    mention_source: bool = True
    instructions: str = Field(default="", max_length=500)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=40)


# ── Routes ──────────────────────────────────────────────────────────────────

def _video_id(raw: str) -> str:
    video_id = extract_video_id(raw)
    if not video_id:
        raise HTTPException(status_code=400, detail="That doesn't look like a YouTube video link.")
    return video_id


@app.get("/api/health")
def health():
    return {"ok": True, "groq_configured": bool(config.GROQ_API_KEY)}


@app.post("/api/videos")
def process_video(body: ProcessRequest):
    return get_session(_video_id(body.url)).info()


@app.get("/api/videos/{video_id}/insights")
def insights(video_id: str):
    session = get_session(_video_id(video_id))
    with session.notes_lock:
        if session.notes is None:
            session.notes = posts.build_notes(session.transcript, session.title)
    return session.notes


@app.post("/api/videos/{video_id}/posts")
def create_post(video_id: str, body: PostRequest):
    session = get_session(_video_id(video_id))
    with session.notes_lock:
        if session.notes is None:
            session.notes = posts.build_notes(session.transcript, session.title)
    return posts.write_post(session.notes, session.title, session.author, body.model_dump())


@app.post("/api/videos/{video_id}/chat")
def chat_with_video(video_id: str, body: ChatRequest):
    session = get_session(_video_id(video_id))
    history = [m.model_dump() for m in body.history]
    tokens = chat.answer(session, body.message, history)

    # Pull the first piece before streaming so setup errors (bad key, rate limit)
    # become a proper JSON error response instead of a broken stream.
    first = next(tokens, "")

    def generate():
        yield first
        try:
            yield from tokens
        except Exception:
            log.exception("Chat stream failed")
            yield "\n\n_(The answer was cut off by an error. Please try again.)_"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
