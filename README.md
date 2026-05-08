# RoboScope

An autonomous multi-agent pipeline that reads the robotics research world every 24 hours and turns it into a clean, readable news portal — complete with structured summaries, difficulty ratings, and visual flow diagrams explaining how each paper works.

---

## What It Does

Most robotics news is scattered across arXiv preprints, IEEE blogs, lab pages, and social aggregators. RoboScope pulls it all together, filters out noise, and presents the best 20 articles per day in a format designed for students and practitioners — not academics.

**Five agents run in sequence:**

1. **SourceWatcher** — fetches from arXiv (cs.RO), IEEE Spectrum, The Robot Report, MIT News, TechCrunch Robotics, New Atlas, ScienceDaily, NVIDIA, Boston Dynamics, HuggingFace Daily Papers, and Hacker News. Each article is deduplicated against a SQLite database so you never see the same story twice.

2. **CuratorAgent** — scores every article on four axes: research depth, industry impact, student accessibility, and novelty. Articles below the relevance threshold or not directly about robotics are dropped before any further processing.

3. **SummarizerAgent** — produces structured summaries: a plain-English headline, a 3-sentence digest, a difficulty rating (accessible / intermediate / advanced), key idea, result, and a student note for context.

4. **ImageAgent** — extracts the article's `og:image` or paper thumbnail. If `USE_GRAPHICAL_ABSTRACT=true`, it generates an image via Gemini Imagen and verifies it with a vision pass before uploading to Supabase Storage.

5. **DeliveryAgent** — assembles `frontend/public/feed.json` and calls FlowAgent to generate visual step-by-step flow diagrams for each article.

The React frontend (Vite, dark theme, no CSS framework) reads the JSON and renders it — featured article, picks, trending, and a full article page with the flow diagram.

---

## Architecture

```
arXiv / RSS / HN
       │
       ▼
 SourceWatcher   ←── SQLite dedup (roboscope.db)
       │
       ▼
  CuratorAgent   ←── LLM scoring (Gemini or Claude)
       │
       ▼
SummarizerAgent  ←── LLM structured output
       │
       ▼
   ImageAgent    ←── og:image → optional Imagen → Unsplash fallback
       │
       ▼
  DeliveryAgent + FlowAgent  →  frontend/public/feed.json
       │
       ▼
  React Frontend (Vercel)
```

---

## LLM Configuration

All models are configurable — the defaults below are what the author chose based on availability and pricing. Swap any of them in `.env` to fit your own preference and budget.

| Task | Default model | How to change |
|------|---------------|---------------|
| Article scoring, summarisation, flow diagrams (Gemini) | `gemini-2.5-flash` | Set `GEMINI_TEXT_MODEL` in `.env` |
| Article scoring, summarisation, flow diagrams (Anthropic) | `claude-sonnet-4-5` | Set `ANTHROPIC_TEXT_MODEL` in `.env` |
| Image generation (optional) | `imagen-3.0-fast-generate-001` | Set `GEMINI_IMAGEN_MODEL` in `.env` |

Set `LLM_PROVIDER=gemini` (default) or `LLM_PROVIDER=anthropic` in your `.env`.

---

## API Cost Breakdown

> **Note:** Prices change frequently. Always verify current rates on the official pricing pages before planning a budget.
> - Gemini: https://ai.google.dev/pricing
> - Anthropic: https://www.anthropic.com/pricing
> - Supabase: https://supabase.com/pricing
> - Gemini Imagen: https://cloud.google.com/vertex-ai/generative-ai/pricing

### Running on Gemini (default)

| Resource | Free tier | Paid |
|----------|-----------|------|
| `gemini-2.5-flash` | ~1,500 req/day, 1M tokens/min | ~$0.075 / 1M input tokens |
| `imagen-3.0-fast-generate-001` | Not free | ~$0.02 / image |
| Supabase Storage | 1 GB free | $0.021 / GB/month |
| GitHub Actions | 2,000 min/month free | — |

**Typical daily run cost (Gemini text, no Imagen):** ~$0 on free tier for moderate article volumes.

**With Imagen on (20 articles/day):** ~$0.40/day in image generation costs.

### Running on Anthropic

| Model | Input | Output |
|-------|-------|--------|
| `claude-sonnet-4-5` | Check official page | Check official page |
| `claude-haiku-4-5` | Cheaper option | Check official page |

Set `ANTHROPIC_TEXT_MODEL=claude-haiku-4-5-20251001` for a lower-cost Anthropic option.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Google AI Studio account (free): https://aistudio.google.com
- A Supabase project (free tier works): https://supabase.com
- Optional: Anthropic API key if you want `LLM_PROVIDER=anthropic`

### 1. Clone and configure

```bash
git clone https://github.com/your-username/roboscope.git
cd roboscope
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
LLM_PROVIDER=gemini               # or anthropic
GOOGLE_API_KEY=your_key_here
ANTHROPIC_API_KEY=                # leave blank if using Gemini
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
USE_GRAPHICAL_ABSTRACT=false      # set true to enable Imagen (costs money)
```

### 2. Create Supabase Storage bucket

In your Supabase dashboard → Storage → New bucket → name it `roboscope-images` → set to Public.

### 3. Run the pipeline

```bash
pip install -r requirements.txt
python run.py
```

First run takes 2–5 minutes. Subsequent runs are faster due to SQLite deduplication — articles already seen are skipped.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Hosting on Vercel + GitHub Actions (24-hour automation)

This is the zero-cost deployment setup. GitHub Actions runs the Python pipeline every 24 hours and commits the updated `feed.json` back to the repo. Vercel serves the React frontend and automatically redeploys when `feed.json` changes.

### Step 1: Push your repo to GitHub

```bash
git init
git remote add origin https://github.com/your-username/roboscope.git
git add .
git commit -m "initial commit"
git push -u origin main
```

### Step 2: Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add each of these:

| Secret name | Value |
|-------------|-------|
| `GOOGLE_API_KEY` | Your Google AI Studio key |
| `LLM_PROVIDER` | `gemini` |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase anon key |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key |
| `ANTHROPIC_API_KEY` | Only needed if `LLM_PROVIDER=anthropic` |

The workflow at `.github/workflows/run_pipeline.yml` is already configured. It runs **every 24 hours at midnight UTC** and can also be triggered manually from the Actions tab.

### Step 3: Deploy frontend to Vercel

1. Go to https://vercel.com → New Project → Import your GitHub repo
2. Set these in the Vercel project settings:

   | Setting | Value |
   |---------|-------|
   | Root Directory | `frontend` |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |
   | Framework Preset | Vite |

3. Deploy. Vercel gives you a free `.vercel.app` URL.

### Step 4: Point Vite at the right feed

In production, `feed.json` is served from `/feed.json` — this works automatically because Vercel serves `frontend/public/` as the root. No backend, no server.

### Step 5: Verify the automation loop

1. Go to your repo → **Actions** tab → **Run RoboScope Pipeline** → **Run workflow**
2. Watch the logs — you should see articles fetched, scored, and summarised
3. After it finishes, check `frontend/public/feed.json` in your repo — it should be updated with today's date
4. Vercel auto-redeploys within ~30 seconds of the commit

The pipeline now runs every 24 hours without any manual intervention.

---

## Configuration Reference

All constants live in `core/config.py` and are controlled via `.env`:

| Variable | Default | Effect |
|----------|---------|--------|
| `LLM_PROVIDER` | `gemini` | `gemini` or `anthropic` |
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` | Gemini model for all text tasks |
| `ANTHROPIC_TEXT_MODEL` | `claude-sonnet-4-5` | Anthropic model for all text tasks |
| `USE_GRAPHICAL_ABSTRACT` | `false` | Enable Imagen generation (requires billing) |
| `GEMINI_IMAGEN_MODEL` | `imagen-3.0-fast-generate-001` | Imagen model |
| `TOP_N_ARTICLES` | `20` | Articles per pipeline run |

---

## Project Structure

```
roboscope/
├── agents/
│   ├── source_watcher.py   # fetch + deduplicate from all sources
│   ├── curator_agent.py    # LLM scoring and filtering
│   ├── summarizer_agent.py # LLM structured summarisation
│   ├── image_agent.py      # og:image + optional Imagen + fallback
│   ├── flow_agent.py       # visual flow diagram generation
│   └── delivery_agent.py   # assemble feed.json
├── core/
│   ├── config.py           # all env vars and constants
│   ├── database.py         # SQLite deduplication + flow cache
│   ├── llm.py              # provider abstraction (Gemini / Anthropic)
│   └── logger.py           # structured run logs → runs/
├── frontend/
│   ├── public/feed.json    # pipeline output, read by the React app
│   └── src/
│       ├── App.jsx
│       └── components/     # Header, FeaturedCard, ArticlePage, etc.
├── .github/workflows/
│   └── run_pipeline.yml    # GitHub Actions — runs daily at midnight UTC
├── run.py                  # entry point
├── requirements.txt
└── .env.example
```

---

## License

MIT — see [LICENSE](LICENSE).
