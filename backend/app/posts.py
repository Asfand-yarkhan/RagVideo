"""Video insights (summary, key points, quotes) and social post writing.

This is deliberately *not* RAG: a post has to reflect the whole video, so the full
transcript is read, in parts when it's too long for one request, then condensed into
notes. Posts are written from those notes.
"""

from . import config, llm
from .rag import format_timestamp
from .transcript import Segment, Transcript

# ── Step 1: notes from the whole transcript ─────────────────────────────────

NOTES_SYSTEM = """You analyse YouTube video transcripts.
Return a JSON object with exactly these keys:
- "topic": one sentence on what the video is about
- "summary": 3-5 sentence summary of the whole video
- "key_points": array of 5-8 specific, concrete insights (facts, numbers, steps, arguments), each one sentence
- "quotes": array of up to 4 short, punchy lines actually said in the video (verbatim or near-verbatim)
- "audience": who would benefit most from this video
- "suggested_questions": array of 3 interesting questions a viewer could ask about this video
Use only what is in the transcript. Never invent facts. Write in English."""

PART_SYSTEM = """You take notes on one part of a longer YouTube video transcript.
Write 6-10 dense bullet points capturing the concrete insights, facts, numbers, steps and
memorable lines from this part. Use only what is in the text. Write in English."""


def _timestamped_text(segments: list[Segment]) -> list[str]:
    """Transcript lines with a [m:ss] marker roughly every 30 seconds."""
    lines, current, mark_at = [], [], -1.0
    for seg in segments:
        if seg.start >= mark_at:
            if current:
                lines.append(" ".join(current))
            current = [f"[{format_timestamp(seg.start)}]"]
            mark_at = seg.start + 30
        current.append(seg.text)
    if current:
        lines.append(" ".join(current))
    return lines


def _split_by_tokens(lines: list[str], max_tokens: int) -> list[str]:
    parts, current, size = [], [], 0
    for line in lines:
        tokens = llm.estimate_tokens(line)
        if current and size + tokens > max_tokens:
            parts.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += tokens
    if current:
        parts.append("\n".join(current))
    return parts


def build_notes(transcript: Transcript, title: str) -> dict:
    lines = _timestamped_text(transcript.segments)
    parts = _split_by_tokens(lines, config.MAX_TRANSCRIPT_TOKENS_PER_CALL)

    if len(parts) == 1:
        material = parts[0]
        label = "Transcript"
    else:
        # Map: condense each part with the fast model, then reduce the notes below.
        part_notes = []
        for number, part in enumerate(parts, start=1):
            notes = llm.complete(
                [
                    {"role": "system", "content": PART_SYSTEM},
                    {"role": "user", "content": f"Video: {title}\nPart {number} of {len(parts)}:\n\n{part}"},
                ],
                model=config.FAST_MODEL,
                max_tokens=1200,
                temperature=0.2,
            )
            part_notes.append(f"Part {number}:\n{notes}")
        material = "\n\n".join(part_notes)
        label = "Notes from each part of the transcript"

    notes = llm.complete_json(
        [
            {"role": "system", "content": NOTES_SYSTEM},
            {"role": "user", "content": f"Video title: {title}\n\n{label}:\n{material}"},
        ],
        max_tokens=2000,
    )
    return {
        "topic": str(notes.get("topic", "")),
        "summary": str(notes.get("summary", "")),
        "key_points": [str(p) for p in notes.get("key_points", [])][:8],
        "quotes": [str(q) for q in notes.get("quotes", [])][:4],
        "audience": str(notes.get("audience", "")),
        "suggested_questions": [str(q) for q in notes.get("suggested_questions", [])][:3],
    }


# ── Step 2: write the post ──────────────────────────────────────────────────

PLATFORM_LIMITS = {"linkedin": 3000, "x_post": 280, "x_thread": 280}

LENGTHS = {
    "linkedin": {"short": "about 500-700 characters", "medium": "about 1,000-1,400 characters", "long": "about 1,800-2,400 characters"},
    "x_thread": {"short": "4 tweets", "medium": "6-7 tweets", "long": "9-10 tweets"},
    "x_post": {"short": "under 180 characters", "medium": "under 240 characters", "long": "under 280 characters"},
}

TONES = {
    "professional": "professional and credible, like an industry expert sharing a lesson",
    "casual": "casual and conversational, like talking to a friend",
    "storytelling": "story-driven: open with a moment or tension, then reveal the lessons",
    "educational": "educational and clear, like a teacher breaking down a topic step by step",
    "bold": "bold and opinionated, with a strong contrarian hook",
}

PLATFORM_RULES = {
    "linkedin": """Write a LinkedIn post.
- First line is a scroll-stopping hook (under 15 words) that stands alone.
- Then a blank line. Short paragraphs of 1-2 lines with blank lines between them.
- Include the most valuable takeaways (a short list is fine).
- End with a question that invites comments.
- Plain text only: no markdown, no **bold**, no headings.""",
    "x_thread": """Write an X (Twitter) thread.
- Tweet 1 is the hook: make people want to read the rest. Do not number tweet 1 with "1/".
- Number the other tweets like "2/", "3/" at the start.
- Each tweet MUST be under 270 characters.
- The last tweet wraps up with the single most important takeaway.
- Separate tweets with a line containing only: ---
- Plain text only, no markdown.""",
    "x_post": """Write a single X (Twitter) post.
- It MUST be under 280 characters in total, including hashtags.
- Lead with the most surprising or useful insight.
- Plain text only, no markdown.""",
}


def write_post(notes: dict, title: str, author: str, options: dict) -> dict:
    platform = options["platform"]
    extras = []
    extras.append("Use a few relevant emojis, sparingly." if options.get("emojis") else "Do not use emojis.")
    if options.get("hashtags"):
        extras.append("End with 2-4 relevant hashtags." if platform != "x_post" else "Add 1-2 relevant hashtags.")
    else:
        extras.append("Do not use hashtags.")
    if options.get("mention_source", True):
        extras.append(f'Credit the source naturally (the video "{title}"{" by " + author if author else ""}).')
    if options.get("instructions"):
        extras.append(f"Extra instructions from the user: {options['instructions']}")

    notes_text = (
        f"Topic: {notes['topic']}\nSummary: {notes['summary']}\nKey points:\n"
        + "\n".join(f"- {p}" for p in notes["key_points"])
        + ("\nQuotes from the video:\n" + "\n".join(f'- "{q}"' for q in notes["quotes"]) if notes["quotes"] else "")
        + f"\nAudience: {notes['audience']}"
    )

    system = (
        "You are a top ghostwriter who turns YouTube videos into high-performing social posts. "
        "Write in first person as someone who watched the video and is sharing what they learned. "
        "Use ONLY facts from the notes; never invent numbers, names or claims. "
        "Avoid clichés like 'game-changer', 'dive in', 'in today's fast-paced world'. "
        "Output only the post itself, with no preamble."
    )
    user = (
        f"{PLATFORM_RULES[platform]}\n"
        f"Tone: {TONES[options['tone']]}.\n"
        f"Length: {LENGTHS[platform][options['length']]}.\n"
        + "\n".join(f"- {e}" for e in extras)
        + f"\n\nNotes about the video:\n{notes_text}"
    )

    text = llm.complete([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=2500, temperature=0.8)

    if platform == "x_post" and len(text) > 280:
        text = llm.complete(
            [
                {"role": "system", "content": "Shorten the post to under 270 characters. Keep the hook and the main insight. Output only the post."},
                {"role": "user", "content": text},
            ],
            model=config.FAST_MODEL,
            max_tokens=800,
            temperature=0.3,
        )

    result = {"platform": platform, "text": text, "tweets": None}
    if platform == "x_thread":
        tweets = [t.strip() for t in text.split("\n---") if t.strip().strip("-").strip()]
        result["tweets"] = [t.lstrip("-").strip() for t in tweets]
    return result
