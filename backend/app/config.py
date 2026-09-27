"""Static configuration (env-driven). Runtime-tunable values (gate thresholds etc.)
live in the Setting table and are read through `settings_store`."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]          # repo root
BACKEND = ROOT / "backend"
DATA_DIR = BACKEND / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_DIR = ROOT / "sample_data"

load_dotenv(ROOT / ".env")

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'sitesync.db'}")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-5")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
USE_MINILM = os.getenv("USE_MINILM", "0") == "1"      # optional sentence-transformers upgrade

# The demo tells a story that happens on a fixed project date. All incoming
# timestamps are shifted so that "today" on the server == PROJECT_TODAY.
PROJECT_TODAY = os.getenv("PROJECT_TODAY", "2026-09-26")

# Project site (Assam refinery expansion)
SITE_LAT, SITE_LON = 27.4700, 95.3400
TZ_OFFSET_H = 5.5   # IST

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Default gate thresholds (spec §4.6). Editable live in Settings.
DEFAULT_SETTINGS = {
    "gate": {
        "extraction": 0.85,
        "match": 0.85,
        "date": 0.80,
        "verification": 0.70,
        "verification_finish": 0.85,
        "margin": 0.10,
        "borderline_band": 0.15,
        "clarify_top2_min": 0.70,
        "candidate_min": 0.50,
    },
    "clarification_cap": 1,
    "channels": {"pwa": True, "whatsapp": True, "telegram": True, "dpr_upload": True, "spreadsheet": True},
    "llm_enabled": True,
    "weather_mode": "seeded_first",   # seeded_first | live_first | seeded_only
    "lookahead_days_ahead": 14,
    "lookahead_days_behind": 60,
}
