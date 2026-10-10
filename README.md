# Vid2Post

Paste a YouTube link and get a **LinkedIn post or X thread** written from the full transcript, plus a summary, key takeaways, and a **chat** that answers questions about the video with clickable timestamps.

- **Backend:** FastAPI (Python), Groq (`gpt-oss` models and Whisper), Hugging Face embeddings (`BAAI/bge-small-en-v1.5`, run locally)
- **Frontend:** React and Vite

## How it works

```
YouTube URL
  └─► transcript
        1. YouTube captions (youtube-transcript-api)
        2. if blocked or missing, subtitles via yt-dlp
        3. if there are no subtitles, audio download, then Groq Whisper
  ├─► Post writer (whole video, not RAG)
  │     transcript ─► notes (summary, key points, quotes) ─► LinkedIn / X post
  │     long videos are summarised part by part first (to stay under Groq's free-tier limits)
  └─► Chat (RAG)
        transcript ─► timestamped chunks ─► HF embeddings ─► top matches ─► Groq answer with [m:ss] citations
```

Transcripts are cached in `backend/data/` so each video is fetched from YouTube only once.

## Setup

After the one-time setup below, on Windows just double-click **`start.bat`**: it starts both servers and opens http://localhost:5173.

You need Python 3.12 (via [uv](https://docs.astral.sh/uv/)) and Node.js 20+.

### 1. Backend

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env        # then put your GROQ_API_KEY in .env
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000      # Windows
# .venv/bin/python -m uvicorn app.main:app --reload --port 8000        # macOS/Linux
```

The first request downloads the embedding model from Hugging Face (about 130 MB).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## "YouTube is blocking requests"

YouTube often blocks transcript and download requests, especially from cloud servers and sometimes from home IPs too.

- **Running locally:** set `YTDLP_COOKIES_FROM_BROWSER=firefox` (or `edge` / `chrome`) in `backend/.env`. yt-dlp then reads your YouTube login from that browser each time it runs, and no cookie file is ever stored in the project. Never commit cookie files: they give full access to your Google account.
- **Deployed:** use a residential proxy (`WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD`, or `PROXY_URL`).

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/videos` | `{ url }` → fetches the transcript, builds the index, returns video info |
| `GET` | `/api/videos/{id}/insights` | Summary, key points, quotes, suggested questions |
| `POST` | `/api/videos/{id}/posts` | `{ platform, tone, length, emojis, hashtags, mention_source, instructions }` |
| `POST` | `/api/videos/{id}/chat` | `{ message, history }` → streamed answer |
