"""Append-only, hash-chained audit log.

hash_n = sha256(prev_hash | actor | action | entity | payload_json | at_iso)
Tampering with any row breaks every hash after it; `verify_chain` recomputes all.
"""
import hashlib
import json
from datetime import datetime

from sqlmodel import Session, select

from .. import clock
from ..models import AuditLog

GENESIS = "0" * 64


def _digest(prev_hash, actor, action, entity, payload_json, at: datetime) -> str:
    raw = "|".join([prev_hash, actor, action, entity or "", payload_json, at.isoformat()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _last_hash(session: Session) -> str:
    row = session.exec(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).first()
    return row.hash if row else GENESIS


def append(session: Session, actor: str, action: str, entity: str | None = None, payload: dict | None = None) -> AuditLog:
    prev = _last_hash(session)
    at = clock.now().replace(microsecond=0)
    pj = json.dumps(payload or {}, sort_keys=True, default=str)
    row = AuditLog(prev_hash=prev, hash=_digest(prev, actor, action, entity, pj, at), actor=actor, action=action,
                   entity=entity, payload_json=pj, at=at)
    session.add(row)
    session.flush()
    return row


def verify_chain(session: Session) -> dict:
    prev = GENESIS
    n = 0
    for row in session.exec(select(AuditLog).order_by(AuditLog.id)):
        n += 1
        if row.prev_hash != prev:
            return {"ok": False, "checked": n, "broken_at": row.id, "reason": "prev_hash mismatch"}
        h = _digest(row.prev_hash, row.actor, row.action, row.entity, row.payload_json, row.at)
        if h != row.hash:
            return {"ok": False, "checked": n, "broken_at": row.id, "reason": "hash mismatch (row altered)"}
        prev = row.hash
    return {"ok": True, "checked": n, "head": prev}
