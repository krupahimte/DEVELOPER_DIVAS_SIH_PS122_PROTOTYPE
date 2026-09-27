"""Planner Review Queue + learning."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import clock
from ..db import get_session
from ..models import Activity, Event, Report
from ..pipeline import learning
from ..pipeline.kg import get_kg

router = APIRouter(prefix="/api/review", tags=["review"])


def escalate_stale(s: Session):
    """Clarifying questions unanswered for 2 h go to the planner (the cap is one question)."""
    now = clock.now()
    for ev in s.exec(select(Event).where(Event.state == "clarifying")).all():
        if ev.clarification_asked_at and now - ev.clarification_asked_at >= timedelta(hours=2):
            ev.state = "review"
            ev.route_reason = "no answer to the clarifying question within 2 h — planner decides"
            s.add(ev)
    s.commit()


@router.get("/queue")
def queue(s: Session = Depends(get_session)):
    escalate_stale(s)
    evs = s.exec(select(Event).where(Event.state.in_(["review", "clarifying"])).order_by(Event.id.desc())).all()
    out = []
    for e in evs:
        r = s.get(Report, e.report_id)
        out.append({"id": e.id, "state": e.state, "text": e.source_sentence, "date": e.event_date, "reporter_id": e.reporter_id,
                    "channel": e.channel, "reason": e.route_reason, "top": e.top_k_candidates[0] if e.top_k_candidates else None,
                    "match_conf": e.match_conf, "margin": e.match_margin, "contradictions": e.contradictions, "blocker": e.blocker_flag,
                    "confs": {"extraction": e.extraction_conf, "match": e.match_conf, "date": e.date_conf, "verification": e.verification_conf},
                    "captured_at": r.captured_at if r else None})
    return out


class ReviewIn(BaseModel):
    action: str                      # approve | correct | reassign | reject | unplanned
    activity_id: str | None = None
    reason: str | None = None        # wrong_area | wrong_object | terminology
    reviewer: str = "R-IYER"
    seconds: float | None = None
    alias_term: str | None = None


@router.post("/{event_id}")
def act(event_id: int, body: ReviewIn, s: Session = Depends(get_session)):
    if body.action not in ("approve", "correct", "reassign", "reject", "unplanned"):
        raise HTTPException(400, "bad action")
    res = learning.review(s, event_id, body.action, body.activity_id, body.reason, body.reviewer, body.seconds, body.alias_term)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error"))
    return res


@router.get("/{event_id}/suggest-alias")
def suggest(event_id: int, activity_id: str, reason: str | None = None, s: Session = Depends(get_session)):
    ev = s.get(Event, event_id)
    act = s.get(Activity, activity_id)
    if not ev or not act:
        raise HTTPException(404)
    sug = learning.suggest_alias(s, ev, act, reason)
    return {"term": sug[0], "target_type": sug[1], "target": sug[2], "scope_zone": sug[3]} if sug else {"term": None}


@router.get("/activities/search")
def search_activities(q: str = "", s: Session = Depends(get_session)):
    kg = get_kg(s)
    ql = q.lower()
    rows = [a for a in s.exec(select(Activity)).all() if a.actual_finish is None and (not ql or ql in a.activity_id.lower() or ql in a.name.lower()
                                                                                      or (a.work_front or "").lower().find(ql) >= 0)]
    return [{"activity_id": a.activity_id, "name": a.name, "wf_name": kg.work_fronts[a.work_front].name if a.work_front else None,
             "planned_start": a.planned_start, "planned_finish": a.planned_finish, "actual_start": a.actual_start} for a in rows[:25]]
