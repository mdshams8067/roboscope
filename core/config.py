import os
from dotenv import load_dotenv

load_dotenv()

# ── Provider selection ────────────────────────────────────────────────────────
# Set LLM_PROVIDER=gemini or LLM_PROVIDER=anthropic in your .env
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")

# ── API keys ──────────────────────────────────────────────────────────────────
GOOGLE_API_KEY    = os.environ["GOOGLE_API_KEY"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # required if LLM_PROVIDER=anthropic

SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_KEY         = os.environ["SUPABASE_KEY"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# ── Model names ───────────────────────────────────────────────────────────────
# Used by core/llm.py — agents never import these directly
GEMINI_TEXT_MODEL    = os.getenv("GEMINI_TEXT_MODEL",    "gemini-2.5-flash")
ANTHROPIC_TEXT_MODEL = os.getenv("ANTHROPIC_TEXT_MODEL", "claude-sonnet-4-5")

# ── Graphical abstract (optional) ─────────────────────────────────────────────
# Requires Gemini billing enabled (Imagen is a paid API).
# Primary image source is always og:image — this only adds generated abstracts.
USE_GRAPHICAL_ABSTRACT = os.getenv("USE_GRAPHICAL_ABSTRACT", "false").lower() == "true"
GEMINI_IMAGEN_MODEL    = os.getenv("GEMINI_IMAGEN_MODEL", "imagen-3.0-fast-generate-001")

# ── Pipeline constants ────────────────────────────────────────────────────────
TOP_N_ARTICLES = 20

TOPIC_TAGS = [
    "Humanoid", "Manipulation", "SLAM", "Legged", "Surgical",
    "Aerial", "Simulation", "Foundation Models", "Safety", "Industry",
]

RSS_SOURCES = [
    {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/feeds/robotics"},
    {"name": "The Robot Report", "url": "https://www.therobotreport.com/feed/"},
    {"name": "MIT News",        "url": "https://news.mit.edu/rss/topic/robotics-mit"},
]

HN_KEYWORDS = ["robot", "robotics", "humanoid", "ROS", "SLAM", "manipulation"]

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

ARXIV_REQUIRES_INSTITUTION_MATCH = True
MINIMUM_RELEVANCE_SCORE = 7
LOW_SIGNAL_KEYWORDS = ["workshop", "survey", "extended abstract", "technical report"]

# ── Source credibility tiers ──────────────────────────────────────────────────

SOURCE_TIERS = {
    # Tier 1: peer-reviewed or primary lab output
    "arxiv_conference_accepted": 1,  # arXiv paper with ICRA/IROS/etc. acceptance in comments
    "science_robotics":          1,
    "ieee_transactions_robotics":1,
    "ieee_ral":                  1,
    "google_deepmind_blog":      1,
    # Tier 2: reputable editorial, industry, or community-curated but not peer-reviewed
    "huggingface_daily_papers":  2,  # community upvotes ≠ peer review; almost all are preprints
    "ieee_spectrum":             2,
    "mit_news":                  2,
    "the_robot_report":          2,
    "techcrunch_robotics":       2,
    "new_atlas_robotics":        2,
    "sciencedaily_robotics":     2,
    "nvidia_isaac_blog":         2,
    "boston_dynamics_blog":      2,
    "papers_with_code":          2,
    "arxiv_preprint":            2,
    # Tier 3: community aggregator, high noise
    "hacker_news":               3,
}

TIER1_CONFERENCES = [
    "ICRA", "IROS", "RSS", "CoRL", "HRI", "HUMANOIDS",
    "NeurIPS", "ICLR", "ICML", "CVPR", "ICCV", "ECCV",
    "CORL", "RA-L", "T-RO", "Science Robotics",
]

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
