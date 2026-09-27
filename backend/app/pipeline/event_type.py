"""The event_type safe rule (spec §4.4, schema "The event_type Problem").

Two fields, not one:
  object_event_type   what the text literally says   (start | finish | progress | none)
  activity_inference  what it means at L6 level       (starts | completes | advances | blocked | unknown)

Rules
  * first event ever on an activity  → Actual Start
  * Actual Finish only if (a) the objects claimed finished cover the activity's full
    scope (accumulated across this activity's linked events), or (b) the object *is*
    the activity (a whole line for a line-level test), or (c) completion language is
    unambiguous at activity level ("hydrotest completed", "all spools erected")
  * anything else advances nothing; blocked events write the cause only
Finish claims face the stricter verification threshold in the gate.
"""
from sqlmodel import Session, select

from ..models import Activity, Event


def covered_objects(session: Session, activity_id: str, exclude_event: int | None = None) -> set:
    rows = session.exec(select(Event).where(Event.matched_activity_id == activity_id, Event.state == "linked",
                                            Event.object_event_type == "finish"))
    out = set()
    for r in rows:
        if r.id != exclude_event:
            out |= set(r.object_ids or [])
    return out


def infer(session: Session, ev: Event, act: Activity | None) -> tuple[str, str | None, str]:
    """→ (activity_inference, date_to_write, explanation). date_to_write ∈ actual_start | actual_finish | both | None"""
    if ev.blocker_flag:
        return "blocked", None, "Blocker: cause is recorded, no date is written."
    if act is None:
        return "unknown", None, "No activity matched."
    first = act.actual_start is None
    alf = bool((ev.field_conf or {}).get("_activity_level_finish"))
    completes, why = False, ""
    if ev.object_event_type == "finish":
        scope = set(act.scope_objects or [])
        claimed = set(ev.object_ids or [])
        if scope and claimed and scope <= (covered_objects(session, act.activity_id, ev.id) | claimed):
            completes, why = True, f"objects cover full activity scope ({len(scope)}/{len(scope)})"
        elif act.object_class == "line" and act.line_no and (ev.object_class == "line" or alf) \
                and ev.line_ref and (ev.line_ref == act.line_no or ("-" not in ev.line_ref and act.line_no.split("-")[0] == ev.line_ref)) \
                and ev.action == act.action:
            completes, why = True, "the object (whole line) is the activity"
        elif alf and (not scope or scope <= (claimed | covered_objects(session, act.activity_id, ev.id))):
            completes, why = True, "completion language is unambiguous at activity level"
        elif alf and scope and not claimed:
            completes, why = True, "activity-level completion statement"
    if completes:
        return "completes", ("both" if first else "actual_finish"), f"Finish: {why}."
    if first:
        tail = "" if ev.object_event_type != "finish" else " (object finished, activity only started)"
        return "starts", "actual_start", f"First event on {act.activity_id} → Actual Start{tail}."
    return "advances", None, "Activity already started; this event advances nothing (safe rule)."
