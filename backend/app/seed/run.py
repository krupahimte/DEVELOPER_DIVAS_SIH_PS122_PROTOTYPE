"""`python -m app.seed.run` — reset the demo: drop DB, write sample files, load master data,
replay 3 weeks of history through the pipeline. Deterministic (fixed RNG seeds)."""
import time

from .. import bus, db
from ..db import session_scope
from ..pipeline import audit
from ..pipeline.kg import invalidate
from . import history, load, samples


def reset(verbose=True):
    t0 = time.time()
    bus.muted = True
    try:
        db.engine.dispose()
        db.init_db(drop=True)
        load.write_plan_files()
        samples.write_samples()
        invalidate()
        with session_scope() as s:
            load.load_master(s)
            audit.append(s, "system", "seed.master_loaded", None, {"activities": 150})
            s.commit()
        invalidate()
        with session_scope() as s:
            stats = history.run(s)
            audit.append(s, "system", "seed.history_replayed", None, stats)
            s.commit()
        invalidate()
    finally:
        bus.muted = False
    if verbose:
        print(f"seeded in {time.time() - t0:.1f}s: {stats}")
    return stats


if __name__ == "__main__":
    reset()
