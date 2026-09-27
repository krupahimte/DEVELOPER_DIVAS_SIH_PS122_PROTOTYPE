"""Database engine, sessions and the runtime settings store."""
import copy
from contextlib import contextmanager

from sqlalchemy import event as sa_event
from sqlmodel import Session, SQLModel, create_engine, select

from . import config
from .models import Setting

engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False})


@sa_event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


def init_db(drop: bool = False):
    if drop:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency."""
    with Session(engine) as s:
        yield s


@contextmanager
def session_scope():
    with Session(engine) as s:
        yield s


# ─────────────── settings store (gate thresholds etc., editable live) ───────────────

def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_settings(session: Session) -> dict:
    row = session.get(Setting, "app")
    return _deep_merge(config.DEFAULT_SETTINGS, row.value if row else {})


def save_settings(session: Session, patch: dict) -> dict:
    row = session.get(Setting, "app")
    current = row.value if row else {}
    merged = _deep_merge(current or {}, patch)
    if row:
        row.value = merged
    else:
        session.add(Setting(key="app", value=merged))
    session.commit()
    return get_settings(session)
