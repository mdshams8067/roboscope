# RoboScope

An autonomous multi-agent pipeline that reads accepted papers from top robotics conferences every 24 hours and turns them into a clean, readable research portal — structured summaries, visual flow diagrams, and conference-organised browsing for early-stage researchers.

---

## What It Does

RoboScope targets the problem of keeping up with conference-accepted research across ICRA, IROS, RSS, and CoRL. Instead of reading abstracts one by one, you get a curated daily digest: papers selected across conferences, summarised for someone starting a Master's degree, and broken down into a visual step-by-step flow.

**Five agents run in sequence every 24 hours:**

1. **SourceWatcher** — fetches accepted papers from a configurable conference registry. arXiv conferences (ICRA, IROS, RSS) are queried using the `co:` comment field so only papers that explicitly declare conference acceptance are returned. OpenReview conferences (CoRL) are queried directly via the authenticated OpenReview API for accepted submissions. Every paper is deduplicated against a SQLite database — a paper published once is never surfaced again.

2. **CuratorAgent** — selects papers via random round-robin across conferences: each conference pool is shuffled independently, then one paper is taken from each conference before any gets a second slot. This guarantees every active conference appears in every feed. Conference acceptance is the quality filter — no LLM scoring is applied. After selection, a single LLM call labels each chosen paper with a `research_theme` and a `why_this_matters` sentence written for an early researcher.

3. **SummarizerAgent** — downloads the paper PDF and extracts targeted sections (Abstract, Introduction, Conclusion, Limitations) using `core/text_extractor.py`. This richer context is passed to the LLM to produce a structured summary: headline, hook, what it does, key idea, core challenge, key assumption, key result, what it enables, open-source link (if any), and a TL;DR.

4. **ImageAgent** — downloads the same PDF (reusing cached bytes from SummarizerAgent), extracts all embedded figures using PyMuPDF, matches them to captions using pdfplumber, and asks the LLM to pick the figure that best represents the paper's core method. The chosen figure is converted to JPEG and uploaded to Supabase Storage. Falls back to a curated Unsplash robotics image if the PDF has no usable figures.

5. **DeliveryAgent + FlowAgent** — assembles `frontend/public/feed.json` and generates a visual step-by-step flow diagram for each paper (cached in SQLite so it isn't regenerated on repeat runs).

The React frontend (Vite, dark theme, no CSS framework) reads the JSON and renders a featured article, an "Also Notable" sidebar, a "More Papers" sidebar, an "All Papers" grid, and a full article page with the flow diagram. A conference filter in the header lets you browse by venue.

---

## Architecture

```
ICRA / IROS / RSS        CoRL
(arXiv co: search)   (OpenReview API)
         \                  /
          ▼                ▼
        SourceWatcher  ←── SQLite dedup (roboscope.db)
               │
               ▼
         CuratorAgent  ←── random round-robin selection + LLM labelling
               │               adds: research_theme, why_this_matters
               ▼
       SummarizerAgent ←── PDF download → text_extractor → LLM structured summary
               │               caches: _pdf_bytes, _context_text on article dict
               ▼
          ImageAgent   ←── cached PDF → PyMuPDF figure extraction → LLM figure pick
               │               → JPEG → Supabase Storage (Unsplash fallback)
               ▼
  DeliveryAgent + FlowAgent  →  frontend/public/feed.json
               │
               ▼
       React Frontend (Vercel)
```

---

## LLM Configuration

All models are configurable. The defaults below are what the author chose based on availability and pricing.

| Task | Default model | How to change |
|------|---------------|---------------|
| Labelling, summarisation, flow diagrams (Gemini) | `gemini-2.5-flash` | Set `GEMINI_TEXT_MODEL` in `.env` |
| Labelling, summarisation, flow diagrams (Anthropic) | `claude-sonnet-4-5` | Set `ANTHROPIC_TEXT_MODEL` in `.env` |

Set `LLM_PROVIDER=gemini` (default) or `LLM_PROVIDER=anthropic` in your `.env`.

---

## API Cost Breakdown

> **Note:** Prices change frequently. Always verify current rates on the official pricing pages.
> - Gemini: https://ai.google.dev/pricing
> - Anthropic: https://www.anthropic.com/pricing
> - Supabase: https://supabase.com/pricing

### Running on Gemini (default)

| Resource | Free tier | Paid |
|----------|-----------|------|
| `gemini-2.5-flash` | ~1,500 req/day, 1M tokens/min | ~$0.075 / 1M input tokens |
| Supabase Storage | 1 GB free | $0.021 / GB/month |
| GitHub Actions | 2,000 min/month free | — |

**Typical daily run cost (5–10 papers, Gemini text):** ~$0 on free tier.

### Running on Anthropic

| Model | Note |
|-------|------|
| `claude-sonnet-4-5` | Check official pricing page |
| `claude-haiku-4-5` | Lower-cost option — set `ANTHROPIC_TEXT_MODEL=claude-haiku-4-5-20251001` |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Google AI Studio account (free): https://aistudio.google.com
- A Supabase project (free tier works): https://supabase.com
- An OpenReview account (free): https://openreview.net — required for CoRL paper fetching
- Optional: Anthropic API key if you want `LLM_PROVIDER=anthropic`

### 1. Clone and configure

```bash
git clone https://github.com/your-username/roboscope.git
cd roboscope
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
ANTHROPIC_API_KEY=                # leave blank if using Gemini
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_key
```

### 2. Create Supabase Storage bucket

In your Supabase dashboard → Storage → New bucket → name it `roboscope-images` → set to Public.

### 3. Run the pipeline

```bash
pip install -r requirements.txt
python run.py
```

First run takes 3–8 minutes (PDF downloads + LLM calls). Subsequent runs are faster — seen papers are skipped, flow diagrams are cached, and PDF bytes are reused across agents in the same run.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Hosting on Vercel + GitHub Actions (24-hour automation)

GitHub Actions runs the pipeline daily and commits the updated `feed.json` and `roboscope.db` back to the repo. Vercel serves the React frontend and auto-redeploys on every commit.

### Step 1: Push to GitHub

```bash
git init
git remote add origin https://github.com/your-username/roboscope.git
git add .
git commit -m "initial commit"
git push -u origin main
```

### Step 2: Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

| Secret name | Value |
|-------------|-------|
| `GOOGLE_API_KEY` | Your Google AI Studio key |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` |
| `OPENREVIEW_USERNAME` | Your OpenReview account email |
| `OPENREVIEW_PASSWORD` | Your OpenReview account password |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase anon key |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key |
| `ANTHROPIC_API_KEY` | Only needed if `LLM_PROVIDER=anthropic` |

### Step 3: Deploy frontend to Vercel

1. Go to https://vercel.com → New Project → Import your GitHub repo
2. Set in Vercel project settings:

   | Setting | Value |
   |---------|-------|
   | Root Directory | `frontend` |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |
   | Framework Preset | Vite |

3. Deploy. Vercel gives you a free `.vercel.app` URL.

`feed.json` is served from `/feed.json` automatically — Vercel serves `frontend/public/` as the static root. No backend needed.

### Step 4: Verify the loop

1. Go to your repo → **Actions** → **Run RoboScope Pipeline** → **Run workflow**
2. Watch the logs — papers fetched, selected, PDFs downloaded, figures extracted, summaries generated
3. Check `frontend/public/feed.json` in your repo — it should have today's date
4. Vercel redeploys within ~30 seconds of the commit

The pipeline now runs daily at midnight UTC without manual intervention.

---

## Configuration Reference

| Variable | Default | Effect |
|----------|---------|--------|
| `LLM_PROVIDER` | `gemini` | `gemini` or `anthropic` |
| `GEMINI_TEXT_MODEL` | `gemini-2.5-flash` | Gemini model for all text tasks |
| `ANTHROPIC_TEXT_MODEL` | `claude-sonnet-4-5` | Anthropic model for all text tasks |
| `ROBOSCOPE_CONFERENCES` | `ICRA,IROS,RSS,CoRL` | Comma-separated list from the conference registry |
| `ROBOSCOPE_PAPERS_PER_DAY` | `10` | Papers published to feed.json per run |
| `ROBOSCOPE_PAPERS_PER_CONF` | `50` | Candidates fetched per conference per run |
| `ROBOSCOPE_START_YEAR` | `2022` | Earliest paper year eligible for the pool |

**Default active conferences:** `ICRA`, `IROS`, `RSS`, `CoRL`

**Also available in the registry** (set via `ROBOSCOPE_CONFERENCES`): `ICLR`, `NeurIPS`, `ICML`, `HRI`, `HUMANOIDS`, `RoboSoft`

---

## Project Structure

```
roboscope/
├── agents/
│   ├── source_watcher.py   # fetch accepted papers from conference registry
│   ├── curator_agent.py    # random round-robin selection + LLM labelling
│   ├── summarizer_agent.py # PDF download + section extraction + LLM summary
│   ├── image_agent.py      # PDF figure extraction → JPEG → Supabase
│   ├── flow_agent.py       # step-by-step flow diagram generation
│   └── delivery_agent.py   # assemble feed.json
├── core/
│   ├── config.py           # all env vars, constants, conference registry
│   ├── database.py         # SQLite dedup (seen_papers) + flow cache
│   ├── llm.py              # provider abstraction (Gemini / Anthropic)
│   ├── text_extractor.py   # targeted PDF section extraction (Abstract, Intro, Conclusion, Limitations)
│   └── logger.py           # structured run logs → runs/
├── frontend/
│   ├── public/feed.json    # pipeline output consumed by React
│   └── src/
│       ├── App.jsx
│       └── components/     # Header, FeaturedCard, ArticlePage, AllNewsCard, etc.
├── .github/workflows/
│   └── run_pipeline.yml    # GitHub Actions — runs daily at midnight UTC
├── run.py                  # pipeline entry point
├── requirements.txt
└── .env.example
```

---

## License

MIT — see [LICENSE](LICENSE).
