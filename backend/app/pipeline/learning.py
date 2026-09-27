"""Learning loop (spec §4.9): planner decisions grow the knowledge graph.

approve / correct / reassign / reject / mark-unplanned  →  ReviewAction (the training label)
correct / reassign (and approvals that resolved an ambiguity)  →  find the term that caused
the mismatch  →  Alias edge written into the KG immediately (cache invalidated)  →  audit.

Term extraction by correction_reason
  wrong_area    the location phrase in the text          → corrected activity's work front
  wrong_object  the object phrase ("spool 5", "line 24") → the matching scope object / line
  terminology   the phrase the plan vocabulary cannot explain — object phrases that map onto
                a scope object of the corrected activity first, else location-like slang
                ("north rack", "bijli ghar"), else a ≥2-word phrase → the activity

Guardrails (a bad alias silently mis-routes every future report, so we err on NOT learning):
  * never a generic/function word, a bare number, or an id pattern (F-12, T-4, 24-P-1203…)
  * never a term that is already a seeded alias of a *different* target (e.g. "rack c")
  * ordinal object aliases ("spool 5") only if unambiguous inside that work front, and they
    are scoped to that work front (Alias.scope_zone)
"""
import re

from sqlmodel import Session, select

from .. import bus, clock
from ..models import Activity, Alias, Event, ObjectItem, ReviewAction
from . import audit, vocab
from .event_type import infer
from .ingest import apply_write
from .kg import get_kg, invalidate, norm

LOC_HEADS = {"rack", "area", "side", "shed", "house", "bay", "yard", "gate", "farm", "ghar", "block", "road", "tower", "basin", "header"}
ID_RX = re.compile(r"^(?:f-?\d+|t-?\d+|l-?\d+|\d+-[a-z]-\d+|spl-.*|iso-?\d+|ptw-.*|[a-z]{1,3}-\d+[a-z]?|el.*|\d+.*)$")
_known_rx = re.compile("|".join(p for v in vocab.ACTIONS.values() for p in v) + "|" +
                       "|".join(p for v in vocab.EVENT_WORDS.values() for p in v), re.I)
_trades = re.compile("|".join(vocab.TRADES.values()), re.I)
_obj_words = re.compile("|".join(p for v in vocab.OBJECT_CLASSES.values() for p in v), re.I)


def _is_generic(term: str) -> bool:
    if re.fullmatch(r"(?:spool|joint|tray|loop|foundation|cable|panel|pump) \d{1,2}", term):
        return False            # "spool 5" — an object phrase; safety comes from the zone-ambiguity check
    words = term.split()
    if not words or all(w in vocab.GENERIC_TERMS or w.isdigit() or len(w) <= 2 for w in words):
        return True
    return bool(ID_RX.match(term)) and " " not in term


def _unexplained_phrases(kg, text: str) -> list[str]:
    # mask everything the KG already explains (seeded + learned aliases) and cut at punctuation
    low = text.lower()
    for h in sorted(kg.find_aliases(text), key=lambda h: -h.span[0]):
        low = low[:h.span[0]] + " | " + low[h.span[1]:]
    toks = re.findall(r"[a-z0-9\-]+|[|,;.:]", low)
    known_alias_words = {w for a in kg.aliases for w in a[0].split()}
    runs, cur = [], []
    for t in toks:
        if t in "|,;.:":
            if cur:
                runs.append(cur)
            cur = []
            continue
        explained = (t in vocab.STOPWORDS or t.isdigit() or _known_rx.fullmatch(t) or _trades.fullmatch(t)
                     or (t in known_alias_words and t not in LOC_HEADS) or ID_RX.match(t) or (_obj_words.fullmatch(t) and t not in LOC_HEADS))
        if not explained:
            cur.append(t)
        elif t in LOC_HEADS and cur:
            cur.append(t)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    phrases = []
    for r in runs:
        heads = [i for i, w in enumerate(r) if w in LOC_HEADS]
        if heads:                                   # "... north rack" → the ≤2 words ending at the place word
            k = heads[-1]
            phrases.append(" ".join(r[max(0, k - 1):k + 1]))
        elif len(r) <= 3:
            phrases.append(" ".join(r))
    phrases = [p for p in phrases if not _is_generic(p)]
    phrases.sort(key=lambda p: (not any(h in p.split() for h in LOC_HEADS), -len(p.split())))
    return phrases


def _conflicts(kg, term: str, target: str) -> bool:
    return any(t == term and tgt != target for t, _, tgt, _ in kg.aliases)


def suggest_alias(session: Session, ev: Event, corrected: Activity, reason: str | None, approving: bool = False):
    """→ (term, target_type, target_node, scope_zone) or None."""
    kg = get_kg(session)
    text = ev.source_sentence or ""
    cands = []

    def object_target():
        if ev.object_ordinals and ev.object_class:
            for so in corrected.scope_objects or []:
                o = kg.objects.get(so)
                if o and o.ordinal in ev.object_ordinals:
                    # unambiguous inside its work front?
                    same = session.exec(select(ObjectItem).where(ObjectItem.object_class == o.object_class, ObjectItem.ordinal == o.ordinal,
                                                                 ObjectItem.work_front == o.work_front)).all()
                    if len(same) == 1:
                        return ("object", so, o.work_front)
                    return None
        if corrected.line_no and ev.line_ref and "-" not in ev.line_ref:
            return ("line", corrected.line_no, None)
        return None

    obj_phrase = norm(ev.object_qualifier) if ev.object_qualifier and ev.object_ordinals and len(ev.object_ordinals) == 1 else None
    if ev.line_ref and not obj_phrase:
        m = re.search(r"line\s*(?:no\.?\s*)?" + re.escape(ev.line_ref), text, re.I)
        obj_phrase = norm(m.group(0)) if m else None

    if reason in ("wrong_object", "terminology") and obj_phrase:
        t = object_target()
        if t:
            cands.append((obj_phrase, *t))
    if corrected.work_front:
        for p in _unexplained_phrases(kg, text):
            if any(h in p.split() for h in LOC_HEADS):
                cands.append((p, "work_front", corrected.work_front, None))
        if reason == "wrong_area" and ev.location_text:
            cands.append((norm(ev.location_text), "work_front", corrected.work_front, None))
    if reason == "terminology" and not approving:
        for p in _unexplained_phrases(kg, text):
            if len(p.split()) >= 2:
                cands.append((p, "activity", corrected.activity_id, None))
    for term, ttype, target, scope in cands:
        if len(term) >= 4 and not _is_generic(term) and not _conflicts(kg, term, target):
            return (term, ttype, target, scope)
    return None


def learn_alias(session: Session, term: str, ttype: str, target: str, event_id: int | None, actor: str, scope_zone=None) -> Alias | None:
    term = norm(term)
    if len(term) < 3 or _is_generic(term):
        return None
    existing = session.exec(select(Alias).where(Alias.term == term, Alias.target_node == target)).first()
    if existing:
        return existing
    al = Alias(term=term, target_node=target, target_type=ttype, scope_zone=scope_zone, learned_from_event=event_id,
               at=clock.now().replace(microsecond=0))
    session.add(al)
    session.flush()
    audit.append(session, actor, "alias.learned", f"alias:{al.id}", {"term": term, "target": target, "type": ttype,
                                                                     "scope_zone": scope_zone, "event": event_id})
    invalidate()
    return al


def review(session: Session, event_id: int, action: str, activity_id: str | None, reason: str | None, reviewer: str,
           seconds: float | None, alias_term: str | None = None) -> dict:
    """action ∈ approve | correct | reassign | reject | unplanned"""
    ev = session.get(Event, event_id)
    if not ev:
        return {"ok": False, "error": "event not found"}
    kg = get_kg(session)
    proposed = ev.top_k_candidates[0]["activity_id"] if ev.top_k_candidates else None
    now = clock.now().replace(microsecond=0)
    ra = ReviewAction(event_id=ev.id, planner_action={"approve": "approved", "correct": "corrected", "reassign": "reassigned",
                                                      "reject": "rejected", "unplanned": "unplanned"}[action],
                      proposed_activity_id=proposed, corrected_activity_id=activity_id if action in ("correct", "reassign") else None,
                      correction_reason=reason, planner_review_seconds=seconds, reviewer=reviewer, at=now)
    learned = None
    prov = dict(ev.provenance or {})
    if action in ("approve", "correct", "reassign"):
        target = activity_id or proposed
        act = session.get(Activity, target)
        if not act:
            return {"ok": False, "error": "activity not found"}
        changed = action in ("correct", "reassign") and target != proposed
        ambiguous_approval = action == "approve" and ((ev.match_margin is not None and ev.match_margin < 0.10) or ev.clarification_asked)
        if changed or ambiguous_approval:
            if alias_term:
                sug = (norm(alias_term), *_target_for_term(kg, norm(alias_term), act))
            else:
                sug = suggest_alias(session, ev, act, reason, approving=not changed)
            if sug:
                learned = learn_alias(session, sug[0], sug[1], sug[2], ev.id, reviewer, scope_zone=sug[3])
                ra.alias_learned = f"'{learned.term}' → {learned.target_node}" if learned else None
        ev.matched_activity_id = act.activity_id
        ev.state = "linked"
        if not ev.blocker_flag:
            if learned and learned.target_type == "object":
                ev.object_ids = [learned.target_node]
                ev.object_id = learned.target_node
                prov["object_ids"] = "HUMAN"
            inference, write, why = infer(session, ev, act)
            ev.activity_inference = inference
            apply_write(session, ev, act, write, "HUMAN", reviewer)
        ev.route_reason = f"planner {ra.planner_action}" + (f" ({reason})" if reason else "")
        prov.update({"matched_activity_id": "HUMAN", "state": "HUMAN"})
    elif action == "reject":
        ev.state = "unparseable"
        ev.route_reason = "planner rejected (kept for audit)"
        prov["state"] = "HUMAN"
    elif action == "unplanned":
        from ..models import Reporter
        from . import unplanned
        rep = session.get(Reporter, ev.reporter_id) if ev.reporter_id else None
        ev.state, ev.unplanned_flag = "unplanned", True
        ev.unplanned_class = ev.unplanned_class or unplanned.classify(ev.source_sentence)
        ev.suggested_parent_wbs = ev.suggested_parent_wbs or unplanned.suggest_parent_wbs(kg, ev, rep)
        ev.change_order_candidate = unplanned.change_order(ev.unplanned_class)
        ev.unplanned_status = "open"
        ev.matched_activity_id = None
        prov["state"] = "HUMAN"
    ev.provenance = prov
    session.add(ra)
    session.add(ev)
    audit.append(session, reviewer, f"review.{ra.planner_action}", f"event:{ev.id}",
                 {"activity": ev.matched_activity_id, "reason": reason, "seconds": seconds, "alias": ra.alias_learned})
    session.commit()
    bus.publish("review", {"event_id": ev.id, "state": ev.state, "alias": ra.alias_learned})
    return {"ok": True, "event_id": ev.id, "state": ev.state, "alias_learned": ra.alias_learned, "date_written": ev.date_written}


def _target_for_term(kg, term: str, act: Activity):
    """Planner typed the term themselves: guess what kind of node it names."""
    m = re.match(r"^([a-z]+)\s*(\d{1,2})$", term)
    if m:
        for so in act.scope_objects or []:
            o = kg.objects.get(so)
            if o and o.ordinal == int(m.group(2)):
                return ("object", so, o.work_front)
    if act.work_front and any(h in term.split() for h in LOC_HEADS):
        return ("work_front", act.work_front, None)
    if act.line_no and "line" in term.split():
        return ("line", act.line_no, None)
    return ("activity", act.activity_id, None)
