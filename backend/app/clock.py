"""Project clock.

The demo story is anchored on PROJECT_TODAY. Real wall-clock time is shifted by a
whole number of days so the time-of-day stays real but the date is the project date.
The seed script overrides the clock per simulated day via `set_override`.
"""
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from . import config

_override: datetime | None = None


def _offset() -> timedelta:
    target = date.fromisoformat(config.PROJECT_TODAY)
    return timedelta(days=(target - datetime.now().date()).days)


def now() -> datetime:
    if _override is not None:
        return _override
    return datetime.now() + _offset()


def today() -> date:
    return now().date()


def shift(ts: datetime | None) -> datetime | None:
    """Map a real client timestamp onto the project calendar."""
    if ts is None or _override is not None:
        return ts
    if ts.tzinfo is not None:
        ts = ts.astimezone().replace(tzinfo=None)
    return ts + _offset()


@contextmanager
def frozen(at: datetime):
    global _override
    prev = _override
    _override = at
    try:
        yield
    finally:
        _override = prev
