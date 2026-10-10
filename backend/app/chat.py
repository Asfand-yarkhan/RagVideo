"""RAG chat over a video transcript."""

from collections.abc import Iterator

from . import config, llm
from .rag import format_timestamp
from .sessions import VideoSession

CHAT_SYSTEM = """You are Vid2Post, an assistant that answers questions about one YouTube video.
Video: "{title}"{author}

{overview}Below are the transcript excerpts most relevant to the user's question, each starting with its timestamp.

{context}

Rules:
- Answer using the overview and the excerpts above. If they don't cover the question, say the video doesn't seem to cover it; don't guess.
- After each claim, cite where it is said using exactly this format: [4:32] (square brackets, no other words like "around" or "mark").
- Be concise and clear. Use short paragraphs or bullet lists when helpful."""

CONDENSE_SYSTEM = """Rewrite the user's latest message as a standalone search query about the video,
resolving words like "it", "that", "he" using the conversation. Output only the rewritten question."""

HISTORY_TURNS = 6


def _standalone_question(message: str, history: list[dict]) -> str:
    """Follow-ups like "explain that more" need the conversation to find the right excerpts."""
    if not history:
        return message
    convo = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in history[-4:])
    try:
        rewritten = llm.complete(
            [
                {"role": "system", "content": CONDENSE_SYSTEM},
                {"role": "user", "content": f"Conversation:\n{convo}\n\nLatest message: {message}"},
            ],
            model=config.FAST_MODEL,
            max_tokens=400,
            temperature=0,
        )
        return rewritten or message
    except Exception:
        return message


def answer(session: VideoSession, message: str, history: list[dict]) -> Iterator[str]:
    query = _standalone_question(message, history)
    excerpts = session.index.search(query, k=6)
    context = "\n\n".join(f"[{format_timestamp(c.start)}] {c.text}" for c in excerpts)

    overview = ""
    if session.notes:
        overview = (
            f"Overview of the whole video:\n{session.notes['summary']}\n"
            + "\n".join(f"- {p}" for p in session.notes["key_points"])
            + "\n\n"
        )

    system = CHAT_SYSTEM.format(
        title=session.title,
        author=f" by {session.author}" if session.author else "",
        overview=overview,
        context=context or "(no excerpts found)",
    )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-HISTORY_TURNS:]]
    messages.append({"role": "user", "content": message})
    return llm.stream(messages)
