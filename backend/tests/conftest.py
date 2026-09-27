"""Test fixtures: an isolated SQLite DB with master data only (fast, deterministic)."""
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / 'data' / 'test.db'}"
os.environ["ANTHROPIC_API_KEY"] = ""          # tests exercise the rule extractor (no key, no internet)

from app import clock, db  # noqa: E402
from app.db import session_scope, save_settings  # noqa: E402
from app.pipeline import ingest  # noqa: E402
from app.pipeline.kg import invalidate  # noqa: E402
from app.seed import load  # noqa: E402

RACK_B = (27.4743, 95.3375, 8)
RACK_C = (27.4743, 95.3386, 8)
TANK = (27.4752, 95.3377, 8)
WEAK = (27.4743, 95.33805, 80)
NOW = datetime(2026, 9, 26, 14, 30)


@pytest.fixture()
def site():
    """Fresh DB with master data; the history is NOT replayed (tests control every event)."""
    db.engine.dispose()
    db.init_db(drop=True)
    load.write_plan_files()
    invalidate()
    with session_scope() as s:
        load.load_master(s)
        save_settings(s, {"weather_mode": "seeded_only", "llm_enabled": False})
        from app.models import Activity
        from datetime import date
        # the minimal history the demo assumes
        for aid, st, fi in [("PIP-3-2345", "2026-08-27", "2026-09-12"), ("PIP-3-2108", "2026-09-02", "2026-09-15"),
                            ("PIP-3-2352", "2026-09-08", "2026-09-21"), ("PIP-3-2401", "2026-09-24", None)]:
            a = s.get(Activity, aid)
            a.actual_start = date.fromisoformat(st)
            a.actual_finish = date.fromisoformat(fi) if fi else None
            s.add(a)
        s.commit()
    invalidate()
    yield
    invalidate()


def send(text, reporter="R-KALITA", gps=RACK_B, photos=None, channel="pwa", at=NOW):
    with clock.frozen(at), session_scope() as s:
        res = ingest.ingest(s, text=text, source_type="chat", channel=channel, reporter_id=reporter,
                            gps_lat=gps[0] if gps else None, gps_lon=gps[1] if gps else None, gps_accuracy=gps[2] if gps else None,
                            photo_ids=photos or [])
        for e in res["events"]:
            s.refresh(e)
        return [e.model_copy() for e in res["events"]]
