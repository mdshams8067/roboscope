import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

CLAUDE_MODEL = "claude-sonnet-4-5"
IMAGEN_MODEL = "imagen-3.0-fast-generate-001"
TOP_N_ARTICLES = 8

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

# --- Credibility Filter Config ---

CREDIBLE_INSTITUTIONS = [
    "MIT", "Carnegie Mellon", "CMU", "Stanford", "ETH Zurich",
    "UC Berkeley", "Berkeley", "Oxford", "Georgia Tech",
    "DeepMind", "Google Research", "Meta AI", "FAIR",
    "NVIDIA Research", "Toyota Research", "Boston Dynamics",
    "Agility Robotics", "Figure", "Unitree", "Sanctuary",
    "KAIST", "TU Delft", "Imperial College", "Toronto",
]

# Applies to arXiv only — RSS sources are trusted at the source level
ARXIV_REQUIRES_INSTITUTION_MATCH = True

# Claude relevance score threshold — articles below this are dropped before summarization
MINIMUM_RELEVANCE_SCORE = 7

# arXiv content types to deprioritize in CuratorAgent novelty scoring
LOW_SIGNAL_KEYWORDS = ["workshop", "survey", "extended abstract", "technical report"]

# --- Source Credibility Tiers ---
# Tier 1: Peer-reviewed, conference-accepted, or highest-signal curated sources
# Tier 2: Reputable editorial and industry sources
# Tier 3: Community/aggregator — supplementary signal

SOURCE_TIERS = {
    "arxiv_conference_accepted": 1,
    "science_robotics":          1,
    "ieee_transactions_robotics":1,
    "ieee_ral":                  1,
    "google_deepmind_blog":      1,
    "huggingface_daily_papers":  1,
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
    "hacker_news":               3,
}

# Conference names whose appearance in arXiv comments elevates a paper to Tier 1
TIER1_CONFERENCES = [
    "ICRA", "IROS", "RSS", "CoRL", "HRI", "HUMANOIDS",
    "NeurIPS", "ICLR", "ICML", "CVPR", "ICCV", "ECCV",
    "CORL", "RA-L", "T-RO", "Science Robotics",
]

# --- Breakthrough Detection Config ---

BREAKTHROUGH_SIGNALS = [
    "state-of-the-art", "state of the art", "outperforms",
    "first", "novel", "surpasses", "real-world deployment",
    "zero-shot", "generaliz", "dexterous", "autonomous",
    "end-to-end", "foundation model", "vision-language-action",
    "VLA", "humanoid", "legged", "manipulation",
]

# Tier 3 sources are never eligible for breakthrough labeling
BREAKTHROUGH_MIN_TIER = 2

# Claude composite score required for breakthrough eligibility
BREAKTHROUGH_MIN_SCORE = 8.5

# --- Graphical Abstract Config ---

# Maximum regeneration attempts before accepting best result
GRAPHICAL_ABSTRACT_MAX_ATTEMPTS = 3

# Minimum accuracy score (out of 10) Claude must give before accepting
GRAPHICAL_ABSTRACT_MIN_SCORE = 8
