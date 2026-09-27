"""'Ask the Project' — the searchable memory (spec §6.7).

Structured questions ("how many rain delays in Unit 3 in September?") → filters applied in
Python over the event table (cause_category / zone / unit / date). There is no generated SQL;
the answer reports the filters it actually applied.

Decision state is respected: planner-rejected events and duplicates are left out of project-state
answers unless the question asks for rejected items / history. A unit or zone filter only counts an
event whose location is *evidenced* (text zone, GPS, a named object, a match consistent with what the
text names, or a reporter who works in one unit) — never on a bare matcher guess.  Narrative questions ("why was PIP-3-2340 late?") →
retrieve cause_text / source_sentence (TF-IDF, KG-aware) and answer with citations to
event ids. If an API key is present Claude writes the prose from the retrieved
snippets only; otherwise we return an extractive answer built from those snippets.
"""
import json
import re
from datetime import date

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlmodel import Session, select

from .. import clock, config
from ..models import Activity, Event, Reporter, ReviewAction
from .kg import get_kg

CAUSE_WORDS = {"rain": ("weather", "rain"), "weather": ("weather", None), "material": ("material", None), "permit": ("permit_hse", None),
               "manpower": ("manpower", None), "labour": ("manpower", None), "crane": ("equipment", None), "equipment": ("equipment", None),
               "breakdown": ("equipment", None), "drawing": ("drawing_rev", None), "rework": ("rework", None), "power": ("power", None),
               "access": ("access", None), "client": ("client_hold", None)}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                                      "november", "december"], 1)}


def _scope(kg, q: str):
    zones, acts = set(), set()
    for h in kg.find_aliases(q):
        if h.target_type == "work_front":
            zones.add(h.target)
        elif h.target_type == "activity":
            acts.add(h.target)
        elif h.target_type == "line":
            acts |= set(kg.activities_for_line(h.target))
    for m in re.finditer(r"\b[A-Z]{3}-\d-\d{4}\b", q.upper()):
        if m.group(0) in kg.activities:
            acts.add(m.group(0))
    units = {f"Unit {u}" for u in re.findall(r"\b(?:unit|u)\s*-?\s*([23])\b", q, re.I)}
    discs = {d for d in ("Piping", "Civil", "Structural", "Electrical", "Instrumentation", "Mechanical") if d.lower() in q.lower()}
    return zones, acts, units, discs


def _wf_of(kg, e: Event):
    wf = e.location_zone_text or e.geofence_zone_id
    if not wf and e.matched_activity_id in kg.activities:
        wf = kg.activities[e.matched_activity_id].work_front
    return wf


def _place(kg, e: Event, reporter: Reporter | None) -> tuple[str | None, str | None, str]:
    """(work_front, unit, basis) from evidence, strongest first. basis='unknown' ⇒ don't count it in a unit/zone filter."""
    wfs = kg.work_fronts
    if e.location_zone_text in wfs:
        return e.location_zone_text, wfs[e.location_zone_text].unit, "text"
    if e.geofence_result == "inside" and e.geofence_zone_id in wfs:
        return e.geofence_zone_id, wfs[e.geofence_zone_id].unit, "gps"
    obj_wfs = {kg.objects[o].work_front for o in (e.object_ids or []) if o in kg.objects and kg.objects[o].work_front}
    if len(obj_wfs) == 1:
        w = obj_wfs.pop()
        return w, wfs[w].unit if w in wfs else None, "object"
    a = kg.activities.get(e.matched_activity_id) if e.matched_activity_id else None
    if a and a.work_front in wfs:
        human = (e.route_reason or "").startswith("planner") or bool(e.clarification_response)
        # a cause-only (blocker) record is attached to the best *guess*; trust it only if it agrees with what the text names
        consistent = not e.blocker_flag or e.line_ref or not e.object_class or e.object_class == a.object_class
        if human or consistent:
            return a.work_front, wfs[a.work_front].unit, "planner" if human else "match"
    units = {wfs[w].unit for w in (reporter.work_fronts if reporter else []) or [] if w in wfs}
    if len(units) == 1:
        return None, units.pop(), "reporter"
    return None, None, "unknown"


def _rejected_ids(session: Session) -> set:
    """Events whose latest planner decision is a rejection."""
    last = {}
    for ra in session.exec(select(ReviewAction).order_by(ReviewAction.id)):
        last[ra.event_id] = ra.planner_action
    return {eid for eid, act in last.items() if act == "rejected"}


def project_events(session: Session, q: str) -> list[Event]:
    """The events a project-state answer may use: no duplicates; no planner-rejected events unless asked for."""
    evs = [e for e in session.exec(select(Event)).all() if e.state != "duplicate"]
    if re.search(r"\breject\w*|\bhistory\b|\bincluding\s+rejected\b", q, re.I):
        return evs
    rej = _rejected_ids(session)
    return [e for e in evs if e.id not in rej]


def answer(session: Session, q: str) -> dict:
    kg = get_kg(session)
    kg.refresh_dynamic(session)
    zones, acts, units, discs = _scope(kg, q)
    ql = q.lower()
    evs = project_events(session, q)
    reporters = {r.id: r for r in session.exec(select(Reporter))}

    # ── structured: counts ──
    if re.search(r"\bhow\s+many\b|\bcount\b|\bnumber\s+of\b|\bkitne\b", ql):
        cat = sub = None
        for w, (c, s) in CAUSE_WORDS.items():
            if w in ql:
                cat, sub = c, s
                break
        month = next((i for m, i in MONTHS.items() if m in ql or m[:3] + " " in ql + " "), None)
        rows, unplaced = [], []
        for e in evs:
            if not e.blocker_flag and cat:
                continue
            if cat and e.cause_category != cat:
                continue
            if sub and e.cause_subcategory != sub:
                continue
            if month and (not e.event_date or e.event_date.month != month):
                continue
            if zones or units:
                wf, unit, basis = _place(kg, e, reporters.get(e.reporter_id))
                if basis == "unknown":
                    unplaced.append(e)          # location not evidenced — reported separately, never counted
                    continue
                if zones and wf not in zones:
                    continue
                if units and unit not in units:
                    continue
            if discs and e.discipline not in discs:
                continue
            rows.append(e)
        hours = sum(e.time_lost_h or 0 for e in rows)
        corr = sum(1 for e in rows if e.weather_corroborates == "true")
        notc = sum(1 for e in rows if e.weather_corroborates == "false")
        what = f"{sub or cat or 'blocker'} delay" if cat else "matching events"
        scope = ", ".join(sorted(units | {kg.work_fronts[z].name for z in zones} | discs)) or "the whole project"
        text = f"{len(rows)} {what}{'s' if len(rows) != 1 else ''} in {scope}" + (f" during {date(2026, month, 1):%B}" if month else "") + \
               (f", {hours:g} h lost" if hours else "") + "."
        if cat == "weather":
            text += f" Weather records corroborate {corr}; {notc} not corroborated by fetched weather."
        if unplaced:
            text += (f" {len(unplaced)} more matching report{'s' if len(unplaced) != 1 else ''} had no evidenced location "
                     f"({', '.join(f'EV-{e.id}' for e in unplaced[:5])}) and {'were' if len(unplaced) != 1 else 'was'} not counted.")
        filters = ["state ≠ duplicate", "planner-rejected excluded" if not re.search(r"reject|history", ql) else "rejected included (asked)"]
        filters += (["blocker_flag"] if cat else []) + ([f"cause_category = {cat}"] if cat else []) + ([f"cause_subcategory = {sub}"] if sub else [])
        filters += ([f"month(event_date) = {month}"] if month else []) + ([f"unit ∈ {sorted(units)} (evidenced location)"] if units else [])
        filters += ([f"work front ∈ {sorted(zones)} (evidenced location)"] if zones else []) + ([f"discipline ∈ {sorted(discs)}"] if discs else [])
        return {"kind": "structured", "answer": text, "filters": "Filters applied (Python, over the event table): " + " · ".join(filters),
                "citations": [_cite(e) for e in rows[:25]], "excluded_unplaced": [e.id for e in unplaced]}

    # ── narrative: retrieve ──
    if not acts and zones:
        acts = {a.activity_id for a in kg.activities.values() if a.work_front in zones and (discs == set() or a.discipline in discs)
                and a.actual_finish is None and a.planned_start <= clock.today()}
    pool = [e for e in evs if (e.cause_text or e.source_sentence) and e.state != "duplicate"]
    docs = [(e.cause_text or e.source_sentence) + " " + " ".join(e.affected_activities or []) + " " + (e.matched_activity_id or "") for e in pool]
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    mat = vec.fit_transform(docs)
    sims = cosine_similarity(vec.transform([q]), mat)[0]
    scored = []
    for e, s in zip(pool, sims):
        boost = 0.0
        if acts and (e.matched_activity_id in acts or set(e.affected_activities or []) & acts):
            boost += 0.5
        if zones and _wf_of(kg, e) in zones:
            boost += 0.2
        if re.search(r"\b(late|delay|why|slip|behind)\b", ql) and e.blocker_flag:
            boost += 0.3
        scored.append((s + boost, e))
    scored.sort(key=lambda x: -x[0])
    top = [e for s, e in scored[:10] if s > 0.15]
    facts = []
    for aid in sorted(acts)[:4]:
        a = session.get(Activity, aid)
        if not a:
            continue
        if a.actual_start:
            slip = (a.actual_start - a.planned_start).days
            facts.append(f"{aid} ({a.name}): planned start {a.planned_start:%d-%b}, actual start {a.actual_start:%d-%b} ({slip:+d} d).")
        else:
            late = (clock.today() - a.planned_start).days
            facts.append(f"{aid} ({a.name}): planned start {a.planned_start:%d-%b}, not started yet" + (f" — {late} days late." if late > 0 else "."))
    llm = _llm_answer(q, facts, top)
    if llm:
        return {"kind": "narrative", "answer": llm, "facts": facts, "citations": [_cite(e) for e in top], "generator": "claude"}
    blockers = [e for e in top if e.blocker_flag]
    lines = facts[:]
    if blockers:
        lines.append("Reported causes, in date order:")
        for e in sorted(blockers, key=lambda e: (e.event_date, e.id)):
            w = ""
            if e.weather_corroborates in ("true", "false"):
                w = f" (fetched weather: {(e.weather_fetched or {}).get('rain_mm_window', '?')} mm → {'corroborated' if e.weather_corroborates == 'true' else 'NOT corroborated'})"
            lines.append(f"• {e.event_date:%d-%b} — {e.cause_category or 'blocker'}: “{e.cause_text}”{w} [EV-{e.id}]")
    others = [e for e in top if not e.blocker_flag][:4]
    if others:
        lines.append("Related field events:")
        lines += [f"• {e.event_date:%d-%b} “{e.source_sentence}” [EV-{e.id}]" for e in others]
    if not lines:
        lines = ["No matching field events found."]
    return {"kind": "narrative", "answer": "\n".join(lines), "facts": facts, "citations": [_cite(e) for e in top], "generator": "extractive"}


def _cite(e: Event) -> dict:
    return {"event_id": e.id, "date": e.event_date.isoformat() if e.event_date else None, "text": e.cause_text or e.source_sentence,
            "state": e.state, "activity": e.matched_activity_id, "cause": e.cause_category}


def _llm_answer(q: str, facts: list, evs: list) -> str | None:
    if not config.ANTHROPIC_API_KEY or not evs:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=20.0, max_retries=1)
        snippets = "\n".join(f"[EV-{e.id}] {e.event_date} {e.cause_category or ''}: {e.cause_text or e.source_sentence}" for e in evs)
        resp = client.messages.create(
            model=config.LLM_MODEL, max_tokens=1200,
            system="You answer questions about an EPC construction project using ONLY the schedule facts and field-event snippets given. "
                   "Cite every claim with its [EV-n] id. Quote field text verbatim when you use it. If the snippets don't answer, say so.",
            messages=[{"role": "user", "content": f"Question: {q}\n\nSchedule facts:\n" + "\n".join(facts) + f"\n\nField events:\n{snippets}"}],
        )
        if resp.stop_reason == "refusal":
            return None
        return next((b.text for b in resp.content if b.type == "text"), None)
    except Exception:
        return None
