"""HSE Centre: open items, permit board, acknowledge / assign / close, stop-work blast radius."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import bus, clock
from ..db import get_session
from ..models import Activity, Event, HSEEvent, Permit, WorkFront
from ..pipeline import audit, hse as hse_rules
from ..pipeline.kg import get_kg

router = APIRouter(prefix="/api/hse", tags=["hse"])
SEV = {"critical": 0, "major": 1, "minor": 2, "observation": 3}


@router.get("")
def items(s: Session = Depends(get_session)):
    rows = s.exec(select(HSEEvent)).all()
    rows.sort(key=lambda h: (h.status == "closed", SEV.get(h.hse_severity, 9), -(h.id or 0)))
    out = []
    for h in rows:
        ev = s.get(Event, h.event_id) if h.event_id else None
        out.append({**h.model_dump(), "event_date": ev.event_date if ev else None, "channel": ev.channel if ev else None,
                    "photo_ids": ev.photo_ids if ev else []})
    return out


class HSEAction(BaseModel):
    action: str                 # acknowledge | assign | close | scope
    assigned_to: str | None = None
    note: str | None = None
    stop_work_scope: str | None = None
    actor: str = "R-HAZARIKA"


@router.post("/{hid}")
def act(hid: int, body: HSEAction, s: Session = Depends(get_session)):
    h = s.get(HSEEvent, hid)
    if not h:
        raise HTTPException(404)
    if body.action == "acknowledge":
        h.status = "acknowledged"
        h.assigned_to = h.assigned_to or body.actor
    elif body.action == "assign":
        h.assigned_to = body.assigned_to
        h.status = "acknowledged" if h.status == "open" else h.status
    elif body.action == "close":
        h.status, h.closed_note = "closed", body.note or "closed"
    elif body.action == "scope":
        h.stop_work_scope = body.stop_work_scope
        h.stop_work_flag = True
        kg = get_kg(s)
        h.gated_activities = hse_rules.gated_activities(s, kg, body.stop_work_scope, h.work_front, h.permit_type, h.info_match_activity)
    s.add(h)
    audit.append(s, body.actor, f"hse.{body.action}", f"hse:{h.id}", {"status": h.status, "assigned_to": h.assigned_to, "note": body.note,
                                                                      "scope": h.stop_work_scope})
    s.commit()
    bus.publish("hse_update", {"hse_id": h.id, "status": h.status})
    return h


@router.get("/permits")
def permit_board(s: Session = Depends(get_session)):
    """Permit status by zone: valid / expiring soon (<24 h) / expired / pending / missing (required by an open activity)."""
    now = clock.now()
    permits = s.exec(select(Permit)).all()
    wfs = {w.id: w for w in s.exec(select(WorkFront))}
    board = []
    for p in permits:
        st = p.status
        if st == "valid" and p.valid_to < now:
            st = "expired"
        elif st == "valid" and p.valid_to - now < timedelta(hours=24):
            st = "expiring_soon"
        board.append({"permit_id": p.permit_id, "type": p.permit_type, "work_front": p.work_front, "wf_name": wfs[p.work_front].name,
                      "valid_from": p.valid_from, "valid_to": p.valid_to, "status": st, "gas_test_done": p.gas_test_done})
    # missing: an open, started-or-due activity requires a permit type with no valid permit in its zone
    have = {(b["work_front"], b["type"]) for b in board if b["status"] in ("valid", "expiring_soon")}
    for a in s.exec(select(Activity)).all():
        if a.permit_type_required and a.work_front and a.actual_finish is None and a.planned_start <= clock.today() + timedelta(days=7) \
                and (a.work_front, a.permit_type_required) not in have:
            key = (a.work_front, a.permit_type_required)
            if not any(b["status"] == "missing" and (b["work_front"], b["type"]) == key for b in board):
                board.append({"permit_id": None, "type": a.permit_type_required, "work_front": a.work_front, "wf_name": wfs[a.work_front].name,
                              "valid_from": None, "valid_to": None, "status": "missing", "needed_by": a.activity_id})
    return board
