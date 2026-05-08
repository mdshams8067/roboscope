# RoboScope — Claude Code Project Guide

## What This Project Is

An autonomous multi-agent robotics news intelligence pipeline that:
1. Fetches articles from arXiv, RSS feeds, and Hacker News (SourceWatcher)
2. Scores and filters them using Claude tool use (CuratorAgent)
3. Summarises each into structured JSON using Claude (SummarizerAgent)
4. Generates photorealistic images using Gemini Imagen (ImageAgent)
5. Assembles the final `feed.json` consumed by the React frontend (DeliveryAgent)

Entry point: `python run.py` — runs all 5 agents in sequence.

## Tech Stack

- **Backend**: Python 3.11, `anthropic` SDK, `google-generativeai`, `feedparser`, `arxiv`, `supabase`
- **Database**: SQLite (file: `roboscope.db`) via stdlib `sqlite3`
- **Frontend**: React 18 + Vite, no CSS framework, dark theme
- **CI**: GitHub Actions cron (`.github/workflows/run_pipeline.yml`) — runs every 6h
- **Hosting**: Vercel (frontend only, static), Supabase Storage (images)

## Agent Contract

Every agent module in `agents/` follows this pattern:
- Has a single public function with a clear name (`fetch`, `curate`, `summarize`, `generate_images`, `assemble`)
- Accepts and returns plain Python dicts / lists — no custom classes
- Logs nothing itself — `run.py` owns all logging via `core.logger.RunLogger`
- Stays under ~150 lines

## Normalised Article Dict Schema

This is the core data structure passed between agents:

```python
{
    "url":       str,   # canonical article URL (dedup key)
    "title":     str,   # original title from source
    "source":    str,   # "arXiv" | "IEEE Spectrum" | "The Robot Report" | "MIT News" | "HN"
    "published": str,   # ISO 8601
    "snippet":   str,   # RSS description / arXiv abstract / HN title (may be short)
    "full_text": str | None,  # fetched by CuratorAgent tool use when snippet < 200 chars
}
```

## Summary Dict Schema (SummarizerAgent output)

```python
{
    "article_id":    str,   # sha256(url)[:8]
    "headline":      str,   # max 12 words, distinct from original title
    "digest":        str,   # 3 sentences, technically accurate, student audience
    "tags":          list,  # 2–3 items from TOPIC_TAGS in core/config.py
    "image_prompt":  str,   # one-sentence photorealistic scene description
}
```

## Image Result Dict Schema (ImageAgent output)

```python
{
    "article_id": str,
    "image_url":  str,   # Supabase public CDN URL, or Unsplash fallback
    "is_fallback": bool,
}
```

## Multi-LLM Design Rationale

- **Claude (`claude-sonnet-4-5`)** handles all reasoning tasks: scoring articles, filtering noise, producing structured JSON summaries. Claude's tool use capability is specifically exploited in CuratorAgent to fetch full article text when RSS snippets are too short.
- **Gemini Imagen (`imagen-3.0-fast-generate-001`)** handles image synthesis. It's the best available model for photorealistic text-to-image generation. Using a separate provider is an explicit architectural choice: choose models by capability, not by vendor loyalty.

## Environment Variables

See `.env.example` for all required vars. Never hardcode keys. All vars loaded via `python-dotenv` in `core/config.py`.

## Key Files

| File | Purpose |
|---|---|
| `run.py` | Pipeline entry point — import and call all agents |
| `core/config.py` | All env vars + pipeline constants (model names, TOP_N, tag vocab) |
| `core/database.py` | SQLite deduplication — `is_seen()`, `mark_seen()` |
| `core/logger.py` | `RunLogger` writes timestamped JSON logs to `runs/` |
| `agents/source_watcher.py` | Fetch + deduplicate raw articles |
| `agents/curator_agent.py` | Claude tool-use scoring + filtering |
| `agents/summarizer_agent.py` | Claude structured JSON summarisation |
| `agents/image_agent.py` | Gemini Imagen + Supabase upload + fallback logic |
| `agents/delivery_agent.py` | Assemble `feed.json` |
| `feed.json` | Output consumed by frontend; overwritten each pipeline run |
| `frontend/` | React + Vite app; deployed to Vercel |

## Running Locally

```bash
cp .env.example .env   # fill in your API keys
pip install -r requirements.txt
python run.py

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# Visit http://localhost:5173
```

## Adding a New Source

In `agents/source_watcher.py`, add a new function that returns a list of normalised article dicts, then append it to the `sources` list in `fetch()`. That's it — deduplication and downstream processing are automatic.

## Vercel Deployment

- Root directory: `frontend/`
- Build command: `npm run build`
- Output directory: `dist`
- `feed.json` is served from the repo root via Vercel's static file serving — no backend needed
