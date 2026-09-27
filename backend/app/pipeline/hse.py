"""HSE bypass — a hard rule, applied before and regardless of confidence (spec §4.3).

An event goes to `hse_hold` (human, always; never auto-synced) if
  * hse_event_flag / stop_work_flag / mishap_flag is set, or
  * a permit status stated in the text is missing / expired / revoked, or
  * the work implies a permit (hot work, confined space, height, excavation,
    radiography) and no *valid* permit exists in the Permit table for that zone
    and time window  → "permit missing" item.
"""
import re
from datetime import datetime

from sqlmodel import Session, select

from ..models import Activity, Event, HSEEvent, Permit
from . import vocab

TRIGGERS = {k: re.compile("|".join(v), re.I) for k, v in vocab.PERMIT_TRIGGERS.items()}
HOT_ACTIONS = {"weld": "hot_work", "cut": "hot_work", "grind": "hot_work", "excavate": "excavation"}


def permit_status_for(session: Session, ptype: str, zone: str, at: datetime) -> tuple[str, Permit | None]:
    rows = list(session.exec(select(Permit).where(Permit.permit_type == ptype, Permit.work_front == zone)))
    for p in rows:
        if p.status == "valid" and p.valid_from <= at <= p.valid_to:
            return "valid", p
    for p in rows:
        if p.status == "revoked":
            return "revoked", p
    for p in rows:
        if p.status == "pending":
            return "pending", p
    for p in rows:
        if p.status == "expired" or p.valid_to < at:
            return "expired", p
    return "missing", None


def implied_permit(ev: Event, act: Activity | None) -> str | None:
    if ev.blocker_flag or not ev.action:
        return None
    if ev.action in HOT_ACTIONS:
        return HOT_ACTIONS[ev.action]
    for ptype, rx in TRIGGERS.items():
        if rx.search(ev.source_sentence or ""):
            return ptype
    if act and act.permit_type_required and ev.object_event_type in ("start", "progress", "finish"):
        return act.permit_type_required
    return None


def stop_scope_from_text(text: str) -> str | None:
    t = text.lower()
    if re.search(r"whole\s+site|entire\s+site|all\s+work|poora\s+site", t):
        return "site"
    if re.search(r"\bunit\b", t):
        return "unit"
    if re.search(r"rack|zone|area|house|farm", t):
        return "zone"
    return None


def check(session: Session, ev: Event, zone: str | None, act: Activity | None, at: datetime) -> list[dict]:
    """→ list of HSE items (kwargs for HSEEvent). Empty list ⇒ not HSE."""
    items = []
    text = ev.source_sentence or ""
    hx = (ev.field_conf or {}).get("_hse") or {}
    htype = hx.get("type")
    if ev.hse_event_flag or ev.stop_work_flag or ev.mishap_flag:
        items.append(dict(kind="stop_work" if ev.stop_work_flag and not htype else "incident",
                          hse_event_type=htype or ("unsafe_condition" if ev.stop_work_flag else "near_miss"),
                          hse_severity=hx.get("severity") or vocab.HSE_SEVERITY.get(htype or "", "major" if ev.stop_work_flag else "minor"),
                          mishap_category=hx.get("mishap_category"),
                          stop_work_flag=ev.stop_work_flag, stop_work_scope=stop_scope_from_text(text) if ev.stop_work_flag else None,
                          mishap_flag=ev.mishap_flag, rework_triggered=bool(re.search(r"rework|redo|dobara", text, re.I)),
                          equipment_id=next((e for e in ev.equipment_deployed or [] if "-" in e), None)))
    if ev.permit_status in ("missing", "expired", "revoked"):
        items.append(dict(kind="permit", permit_required=True, permit_status=ev.permit_status, permit_id=hx.get("permit_id"),
                          permit_type=hx.get("permit_type") or implied_permit(ev, act), hse_event_type="unsafe_act", hse_severity="major",
                          gas_test_done=hx.get("gas_test_done")))
    ptype = implied_permit(ev, act)
    if ptype and zone and not any(i["kind"] == "permit" for i in items):
        status, permit = permit_status_for(session, ptype, zone, at)
        if status in ("missing", "expired", "revoked"):
            items.append(dict(kind="permit", permit_required=True, permit_type=ptype, permit_status=status,
                              permit_id=permit.permit_id if permit else None,
                              permit_validity_window=f"{permit.valid_from:%d-%b %H:%M} → {permit.valid_to:%d-%b %H:%M}" if permit else None,
                              gas_test_done=permit.gas_test_done if permit else None,
                              hse_event_type="unsafe_act", hse_severity="major"))
        else:
            ev.permit_status = status
            ev.provenance = {**(ev.provenance or {}), "permit_status": "FETCHED"}
    return items


def gated_activities(session: Session, kg, scope: str | None, zone: str | None, ptype: str | None, matched: str | None) -> list[str]:
    open_acts = [a for a in kg.activities.values() if a.actual_finish is None]
    if scope == "site":
        return sorted(a.activity_id for a in open_acts if a.actual_start)[:40]
    if scope == "unit" and zone and zone in kg.work_fronts:
        unit = kg.work_fronts[zone].unit
        return sorted(a.activity_id for a in open_acts if a.unit == unit and (a.actual_start or a.activity_id == matched))
    if zone:
        acts = [a for a in open_acts if a.work_front == zone]
        if ptype:
            acts = [a for a in acts if a.permit_type_required == ptype or a.activity_id == matched] or acts
        return sorted(a.activity_id for a in acts)
    return [matched] if matched else []


def active_stop_work(session: Session, kg, zone: str | None, act: Activity | None, day) -> HSEEvent | None:
    """The open (not closed) stop-work whose blast radius covers this report, if any.

    A stop-work is *active* once the HSE officer (or the report text) has set a scope, until the item is closed.
    Scope semantics — same as the HSE Centre map:
      activity → the gated activities of that item          zone → the item's work front
      unit     → every work front of that unit              site → everything
    `zone` is where the new report says/GPS puts it; `act` is the activity it would have matched (if credible).
    Stops raised after the reported work date do not apply (a back-dated report of earlier work is not a breach).
    """
    rows = session.exec(select(HSEEvent).where(HSEEvent.stop_work_flag == True, HSEEvent.stop_work_scope.is_not(None),  # noqa: E712
                                               HSEEvent.status != "closed")).all()
    zones = {z for z in (zone, act.work_front if act else None) if z}
    units = {kg.work_fronts[z].unit for z in zones if z in kg.work_fronts} | ({act.unit} if act and act.unit else set())
    for h in sorted(rows, key=lambda r: r.id or 0):
        if h.created_at and day and day < h.created_at.date():
            continue
        sc = h.stop_work_scope
        if sc == "site":
            return h
        if sc == "unit" and h.work_front in kg.work_fronts and kg.work_fronts[h.work_front].unit in units:
            return h
        if sc == "zone" and h.work_front in zones:
            return h
        if sc == "activity" and act and act.activity_id in (h.gated_activities or []):
            return h
    return None
