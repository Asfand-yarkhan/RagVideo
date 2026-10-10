"""Thin wrapper around the Groq client."""

import json
from collections.abc import Iterator
from functools import lru_cache

from groq import Groq

from . import config


class LLMNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def client() -> Groq:
    if not config.GROQ_API_KEY:
        raise LLMNotConfigured("GROQ_API_KEY is missing. Add it to backend/.env and restart the server.")
    # Free-tier rate limits are tight; the SDK waits for the retry-after header on 429s.
    return Groq(api_key=config.GROQ_API_KEY, max_retries=6, timeout=120)


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


# gpt-oss likes typographic characters (non-breaking hyphens and spaces) that paste
# badly into LinkedIn and X, and cites as 【4:32】; swap them for plain ones.
_TIDY = str.maketrans({"‑": "-", "‐": "-", " ": " ", " ": " ", " ": " ", "【": "[", "】": "]"})


def tidy(text: str) -> str:
    return text.translate(_TIDY)


def _extra_args(model: str) -> dict:
    # gpt-oss models "think" before answering; low effort keeps responses fast
    # and inside the free-tier token budget.
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    return {}


def complete(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 1500,
    temperature: float = 0.6,
    json_mode: bool = False,
) -> str:
    model = model or config.WRITER_MODEL
    kwargs = _extra_args(model)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client().chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens,
        temperature=temperature,
        **kwargs,
    )
    text = tidy(response.choices[0].message.content or "")
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def complete_json(messages: list[dict], model: str | None = None, max_tokens: int = 2000) -> dict:
    text = complete(messages, model=model, max_tokens=max_tokens, temperature=0.3, json_mode=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Be forgiving if the model wrapped the JSON in prose or code fences.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def stream(messages: list[dict], model: str | None = None, max_tokens: int = 1500, temperature: float = 0.4) -> Iterator[str]:
    model = model or config.WRITER_MODEL
    response = client().chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens,
        temperature=temperature,
        stream=True,
        **_extra_args(model),
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield tidy(delta)
