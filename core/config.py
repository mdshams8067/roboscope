import os
import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Provider selection ────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# ── API keys ──────────────────────────────────────────────────────────────────
GOOGLE_API_KEY    = os.environ["GOOGLE_API_KEY"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

OPENREVIEW_USERNAME = os.environ.get("OPENREVIEW_USERNAME", "")
OPENREVIEW_PASSWORD = os.environ.get("OPENREVIEW_PASSWORD", "")

SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_KEY         = os.environ["SUPABASE_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# ── Model names ───────────────────────────────────────────────────────────────
GEMINI_TEXT_MODEL    = os.getenv("GEMINI_TEXT_MODEL",    "gemini-2.5-flash")
ANTHROPIC_TEXT_MODEL = os.getenv("ANTHROPIC_TEXT_MODEL", "claude-sonnet-4-5")

# ── Graphical abstract (optional) ─────────────────────────────────────────────
USE_GRAPHICAL_ABSTRACT = os.getenv("USE_GRAPHICAL_ABSTRACT", "false").lower() == "true"
GEMINI_IMAGEN_MODEL    = os.getenv("GEMINI_IMAGEN_MODEL", "imagen-3.0-fast-generate-001")

# ── Conference registry ───────────────────────────────────────────────────────
# Each entry defines a conference, its access method, and its source tier.

CONFERENCE_REGISTRY = {
    # arXiv comment-detection group — acceptance noted by authors in comment field
    "ICRA": {
        "access": "arxiv",
        "arxiv_keywords": ["ICRA", "International Conference on Robotics and Automation"],
        "tier": 1,
        "field": "robotics",
    },
    "IROS": {
        "access": "arxiv",
        "arxiv_keywords": ["IROS", "Intelligent Robots and Systems"],
        "tier": 1,
        "field": "robotics",
    },
    "RSS": {
        "access": "arxiv",
        "arxiv_keywords": ["Robotics: Science and Systems"],
        "tier": 1,
        "field": "robotics",
    },
    "HRI": {
        "access": "arxiv",
        "arxiv_keywords": ["HRI", "Human-Robot Interaction"],
        "tier": 1,
        "field": "robotics",
    },
    "HUMANOIDS": {
        "access": "arxiv",
        "arxiv_keywords": ["Humanoids", "IEEE-RAS International Conference on Humanoid"],
        "tier": 1,
        "field": "robotics",
    },
    "RoboSoft": {
        "access": "arxiv",
        "arxiv_keywords": ["RoboSoft"],
        "tier": 2,
        "field": "robotics",
    },
    # OpenReview API group
    "CoRL": {
        "access": "openreview",
        "venue_id": "robot-learning.org/CoRL/{year}/Conference",
        "tier": 1,
        "field": "robotics",
    },
    "ICLR": {
        "access": "openreview",
        "venue_id": "ICLR.cc/{year}/Conference",
        "tier": 1,
        "field": "ml",
    },
    "NeurIPS": {
        "access": "openreview",
        "venue_id": "NeurIPS.cc/{year}/Conference",
        "tier": 1,
        "field": "ml",
    },
    "ICML": {
        "access": "openreview",
        "venue_id": "ICML.cc/{year}/Conference",
        "tier": 1,
        "field": "ml",
    },
}

# Active conferences — overridable via ROBOSCOPE_CONFERENCES env var
# Comma-separated list from CONFERENCE_REGISTRY keys
_env_conferences = os.environ.get("ROBOSCOPE_CONFERENCES", "")
ACTIVE_CONFERENCES = (
    [c.strip() for c in _env_conferences.split(",") if c.strip()]
    if _env_conferences
    else ["ICRA", "IROS", "RSS", "CoRL"]
)

# Papers published to feed.json per day — hard ceiling enforced by DeliveryAgent
PAPERS_PER_DAY = int(os.environ.get("ROBOSCOPE_PAPERS_PER_DAY", "10"))

# Candidates fetched per conference per run — fetch wide, dedup narrows it down
PAPERS_PER_CONFERENCE = int(os.environ.get("ROBOSCOPE_PAPERS_PER_CONF", "50"))

# Minimum new papers guaranteed per conference per run — triggers deeper re-fetch
MIN_NEW_PER_CONFERENCE = int(os.environ.get("ROBOSCOPE_MIN_NEW_PER_CONF", "5"))

# Backward-compat alias used by CuratorAgent — fetch 3× the daily target as candidates
TOP_N_ARTICLES = PAPERS_PER_DAY * 3

# Historical pool start year — papers from this year onwards are eligible
ARXIV_START_YEAR = int(os.environ.get("ROBOSCOPE_START_YEAR", "2022"))

# OpenReview years to query (start year → current year inclusive)
CURRENT_YEAR = datetime.datetime.now().year
OPENREVIEW_YEARS = list(range(ARXIV_START_YEAR, CURRENT_YEAR + 1))

# ── Tag vocabulary ───────────────────────────────────────────────────────────

TOPIC_TAGS = [
    "Humanoid", "Manipulation", "SLAM", "Legged", "Surgical",
    "Aerial", "Simulation", "Foundation Models", "Safety", "Industry",
]

# ── Fallback images ───────────────────────────────────────────────────────────

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=800",
    "https://images.unsplash.com/photo-1561557944-6e7860d1a7eb?w=800",
    "https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=800",
    "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800",
    "https://images.unsplash.com/photo-1531746790731-6c087fecd65a?w=800",
    "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=800",
    "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800",
    "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=800",
    "https://images.unsplash.com/photo-1714846461908-97f72ff6c42e?w=800",
    "https://images.unsplash.com/photo-1682687221073-53ad74c2cad7?w=800",
]

# ── Credibility filter ────────────────────────────────────────────────────────

CREDIBLE_INSTITUTIONS = [
    "MIT", "Carnegie Mellon", "CMU", "Stanford", "ETH Zurich",
    "UC Berkeley", "Berkeley", "Oxford", "Georgia Tech",
    "DeepMind", "Google Research", "Meta AI", "FAIR",
    "NVIDIA Research", "Toyota Research", "Boston Dynamics",
    "Agility Robotics", "Figure", "Unitree", "Sanctuary",
    "KAIST", "TU Delft", "Imperial College", "Toronto",
]

ARXIV_REQUIRES_INSTITUTION_MATCH = False
MINIMUM_RELEVANCE_SCORE = 7
LOW_SIGNAL_KEYWORDS = ["workshop", "survey", "extended abstract", "technical report"]

# ── Breakthrough detection ────────────────────────────────────────────────────

BREAKTHROUGH_SIGNALS = [
    "state-of-the-art", "state of the art", "outperforms",
    "first", "novel", "surpasses", "real-world deployment",
    "zero-shot", "generaliz", "dexterous", "autonomous",
    "end-to-end", "foundation model", "vision-language-action",
    "VLA", "humanoid", "legged", "manipulation",
]

BREAKTHROUGH_MIN_TIER  = 2
BREAKTHROUGH_MIN_SCORE = 8.5

# ── Graphical abstract verification ──────────────────────────────────────────

GRAPHICAL_ABSTRACT_MAX_ATTEMPTS = 3
GRAPHICAL_ABSTRACT_MIN_SCORE    = 8

# ── Flow agent ────────────────────────────────────────────────────────────────

BLOCK_TYPES = [
    "problem", "limitation", "idea", "method", "data",
    "experiment", "result", "insight", "deployment",
    "impact", "context", "announcement", "next",
]
FLOW_AGENT_MAX_BLOCKS = 12
