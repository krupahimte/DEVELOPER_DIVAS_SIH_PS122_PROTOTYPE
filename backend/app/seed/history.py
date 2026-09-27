"""Seed step 2: ~3 weeks of field history (5–25 Sep 2026) pushed through the REAL pipeline.

Nothing here writes states or confidences directly. We simulate:
  * ground-truth progress per activity (true start/finish with realistic slips)
  * the messages crews would send — English / Hinglish, WhatsApp / PWA / Telegram / DPR
    uploads, with week-1 *site slang* the plan doesn't know ("north rack", "bijli ghar"…)
  * reporters answering (or ignoring) clarifying questions
  * planners reviewing the queue each evening — approving or correcting with a reason,
    which teaches the KG aliases, so auto-sync % rises in weeks 2–3 by itself
  * blockers (13-Sep heavy rain, a false rain claim on dry 18-Sep, crane breakdown, drawing
    revision, manpower), HSE items, unplanned work, duplicates across channels, offline lag.
The demo-reserved activities (master.RESERVED) receive no progress events.
"""
import random
from datetime import date, datetime, time, timedelta

from sqlmodel import Session, select

from .. import clock
from ..models import Activity, Event, HSEEvent, Report, Reporter
from ..pipeline import ingest, learning
from ..pipeline.kg import get_kg, invalidate
from . import master as M

D0, D1 = date(2026, 9, 5), date(2026, 9, 25)
SEED = 20260926
rnd = random.Random(SEED)          # re-seeded at the start of every run() — see there

# Crew slang the plan doesn't know. Crews keep using it all three weeks — what changes is
# whether the KG has learned it (from planner decisions in week 1).
SLANG_FOR_WF = {"WF-U3-RACK-B": "north rack", "WF-U3-RACK-C": "naya rack", "WF-U2-SUBSTN": "bijli ghar",
                "WF-U2-COMP": "compressor shed", "WF-U3-TANK": "tanki area", "WF-U3-PUMP": "pump ghar", "WF-U2-CT": "CT side"}
SLANG_FOR_LINE = {"14-P-2110": "gas header"}
NOUN = {"install": "installation", "erect": "erection", "pour": "concreting", "coat": "waterproofing", "fill": "filling", "torque": "torquing",
        "clear": "clearance", "paint": "painting", "insulate": "insulation", "grout": "grouting", "align": "alignment", "flush": "flushing",
        "terminate": "termination", "calibrate": "calibration", "shutter": "shuttering", "excavate": "excavation", "build": "brickwork",
        "level": "levelling", "pave": "paving", "lay": "laying", "test": "testing", "fabricate": "fabrication"}
POOR_SIGNAL = {"WF-U3-TANK", "WF-U2-CT", "WF-U3-FDN"}
TRADES = {"Piping": [("fitter", 4, 12), ("welder", 2, 8), ("helper", 4, 10)], "Civil": [("mason", 3, 8), ("helper", 6, 20), ("bar bender", 2, 6)],
          "Structural": [("rigger", 3, 8), ("fitter", 2, 6)], "Electrical": [("electrician", 3, 8), ("helper", 4, 10)],
          "Instrumentation": [("technician", 2, 6)], "Mechanical": [("fitter", 2, 6), ("rigger", 2, 4)]}
WF_NAME = {w[0]: w[1] for w in M.WORK_FRONTS}
SHORT_WF = {"WF-U2-SUBSTN": "SS-2", "WF-U2-STRUCT": "ST-2", "WF-U3-FDN": None}


def reporter_for(a: Activity, reps: dict) -> Reporter | None:
    cands = [r for r in reps.values() if r.discipline == a.discipline and a.work_front in (r.work_fronts or [])]
    if not cands:
        cands = [r for r in reps.values() if r.discipline == a.discipline and r.role in ("supervisor", "foreman")]
    return rnd.choice(cands) if cands else None


def truth_schedule(acts: dict) -> dict:
    """activity → (true_start, true_finish|None) as the site actually ran (hidden from the pipeline)."""
    truth = {}
    order = sorted(acts.values(), key=lambda a: a.planned_start)
    for _ in range(3):
        for a in order:
            if a.activity_id in M.RESERVED:
                continue
            if a.actual_start:
                s = a.actual_start
            else:
                preds = [truth.get(p, (None, None))[1] or (acts[p].actual_finish if p in acts else None) for p in a.predecessors or []]
                if any(p is None for p in preds):
                    continue
                s = a.planned_start + timedelta(days=rnd.choice([0, 0, 1, 1, 2, 3]))
                if preds:
                    s = max(s, max(preds) + timedelta(days=1))
            if s > D1:
                continue
            f = a.actual_finish
            if f is None:
                dur = (a.planned_finish - a.planned_start).days
                f = s + timedelta(days=max(1, dur + rnd.choice([-1, 0, 0, 1, 2, 3, 4])))
                if f > D1 or a.activity_id in ("PIP-3-2401",):
                    f = None
            truth[a.activity_id] = (s, f)
    truth["PIP-3-2108"] = (date(2026, 9, 2), date(2026, 9, 15))
    truth["PIP-3-2352"] = (date(2026, 9, 8), date(2026, 9, 21))
    truth["PIP-3-2401"] = (date(2026, 9, 24), None)       # hydrotest running; demo step 4 finishes it
    truth["PIP-3-2345"] = (date(2026, 8, 27), date(2026, 9, 12))
    return truth


def loc_phrase(a: Activity, week1: bool, hinglish: bool) -> tuple[str, bool]:
    wf = a.work_front
    if wf in SLANG_FOR_WF and rnd.random() < (0.75 if week1 else 0.6):
        return SLANG_FOR_WF[wf], True
    name = SHORT_WF.get(wf, WF_NAME.get(wf, ""))
    return (name or ""), False


def manpower(a: Activity, hinglish: bool) -> str:
    if rnd.random() < 0.4:
        return ""
    parts = []
    for trade, lo, hi in TRADES.get(a.discipline, [])[: rnd.choice([1, 2, 2, 3])]:
        n = rnd.randint(lo, hi)
        parts.append(f"{n} {trade}")
    if not parts:
        return ""
    tail = " the" if hinglish and rnd.random() < 0.5 else ""
    return ", " + " ".join(parts) + tail


def compose(a: Activity, kind: str, day: date, progress_idx: int, hinglish: bool) -> tuple[str, bool]:
    """→ (message text, used_slang)"""
    week1 = day <= date(2026, 9, 11)
    loc, slang = loc_phrase(a, week1, hinglish)
    at = (f" {loc} pe" if hinglish else f" at {loc}") if loc else ""
    mp = manpower(a, hinglish)
    act, name = a.action, a.name
    if act == "erect" and a.object_class == "spool":
        scope = a.scope_objects or []
        if progress_idx >= len(scope) and kind != "finish":
            return (f"Spool erection{at} line {a.line_no} touch-up and bolting continued{mp}"), slang
        n = int(scope[min(progress_idx, len(scope) - 1)].split("-")[-1]) if scope else 1
        if kind == "finish" and len(scope) > 1:
            return (f"All spools erected{at} line {a.line_no}, erection complete{mp}" if not hinglish else
                    f"{loc + ' pe ' if loc else ''}line {a.line_no} ke saare spools erect ho gaye{mp}"), slang
        if hinglish:
            return f"{loc + ' pe ' if loc else ''}spool {n} erect ho gaya{mp}", slang
        return f"Spool {n} erected{at}{mp}", slang
    if act == "weld":
        k = rnd.randint(3, 9)
        line = a.line_no
        if kind == "start":
            return (f"Field welding started line {line}{at}{mp}" if not hinglish else f"line {line} ki welding shuru{at.replace(' pe', '')}{mp}"), slang
        if kind == "finish":
            return f"All field joints welded line {line}, welding fully completed{mp}", slang
        return (f"{k} joints welded on line {line}{mp}" if not hinglish else f"line {line} pe {k} joint weld kiye{mp}"), slang
    if act == "test" and a.object_class == "line":
        if kind == "start":
            return f"Hydrotest line {a.line_no} started, filling in progress", slang
        if kind == "finish":
            return f"Hydrotest line {a.line_no} completed", slang
        return f"Hydrotest line {a.line_no} pressurisation continued", slang
    if act == "test" and a.object_class == "loop":
        lp = (a.scope_objects or ["LOOP-L-301"])[0].replace("LOOP-", "")
        return (f"Loop check {lp} started" if kind == "start" else f"Loop check {lp} completed" if kind == "finish" else f"Loop check {lp} in progress"), slang
    if a.discipline == "Civil" and (a.scope_objects or [""])[0].startswith("FDN-F-"):
        f = a.scope_objects[0].replace("FDN-", "")
        step = name.split(" foundation")[0]
        if kind == "start":
            return (f"{step} {f} started{mp}" if not hinglish else f"{f} ka {step.lower()} shuru kiya{mp}"), slang
        if kind == "finish":
            qty = f", {rnd.randint(12, 30)} m3" if a.action == "pour" else ""
            return (f"{step} of {f} completed{qty}{mp}" if not hinglish else f"{f} {step.lower()} complete ho gaya{qty}{mp}"), slang
        return (f"{step} {f} continued{mp}" if not hinglish else f"{f} {step.lower()} chal raha hai{mp}"), slang
    if act == "pull":
        t = (a.scope_objects or ["TRAY-T-1"])[0].replace("TRAY-", "")
        m = rnd.randint(60, 220)
        if kind == "start":
            return f"Cable pulling started tray {t} Unit 2{mp}", slang
        if kind == "finish":
            return f"Cable pulling tray {t} completed, all cables pulled{mp}", slang
        return (f"Continued cable pulling Unit 2 tray {t}, {m} m pulled{mp}" if not hinglish else f"tray {t} cable pulling chal raha hai, aaj {m} m{mp}"), slang
    # generic: use the plan name (+ a verb if the name has none), with slang for the location if any
    base = name
    from ..pipeline.xer_parse import _derive_action
    if not _derive_action(name) and act in NOUN:
        base = f"{base} {NOUN[act]}"
    if slang and a.work_front in SLANG_FOR_WF:
        for w in (WF_NAME.get(a.work_front, "@@"), "SS-2", "Compressor house", "compressor house", "Cooling tower", "Pump house", "pump house", "Tank"):
            base = base.replace(w, "")
        base = f"{' '.join(base.split())} {SLANG_FOR_WF[a.work_front]}"
    if kind == "start":
        return (f"{base} started{mp}" if not hinglish else f"{base} ka kaam shuru{mp}"), slang
    if kind == "finish":
        return (f"{base} fully completed{mp}" if not hinglish else f"{base} poora complete ho gaya{mp}"), slang
    return (f"{base} work in progress{mp}" if not hinglish else f"{base} ka kaam chal raha hai{mp}"), slang


def gps_for(wf: str | None, good: bool):
    if not wf:
        return None, None, None
    w = next(x for x in M.WORK_FRONTS if x[0] == wf)
    lat0, lat1, lon0, lon1 = w[4]
    if good:
        return round(rnd.uniform(lat0 + 0.0001, lat1 - 0.0001), 6), round(rnd.uniform(lon0 + 0.0001, lon1 - 0.0001), 6), rnd.choice([6, 8, 12, 15])
    return round((lat0 + lat1) / 2 + rnd.uniform(-0.0006, 0.0006), 6), round((lon0 + lon1) / 2 + rnd.uniform(-0.0006, 0.0006), 6), rnd.choice([60, 90])


def send(session, day, hh, mm, text, reporter, channel, wf, photo=None, gps_mode="auto", lag_h=0.0, source_type=None):
    sync_at = datetime.combine(day, time(hh, mm))
    captured = sync_at - timedelta(hours=lag_h)
    if gps_mode == "auto":
        gps_mode = "good" if channel == "pwa" and rnd.random() < 0.85 else ("weak" if channel == "pwa" else "none")
    lat = lon = acc = None
    if gps_mode in ("good", "weak"):
        lat, lon, acc = gps_for(wf, gps_mode == "good")
    with clock.frozen(sync_at):
        return ingest.ingest(session, text=text, source_type=source_type or ("whatsapp" if channel == "whatsapp" else "telegram" if channel == "telegram" else "chat"),
                             channel=channel, reporter_id=reporter.id if reporter else None, captured_at=captured, queued_at=captured,
                             gps_lat=lat, gps_lon=lon, gps_accuracy=acc, photo_ids=[photo] if photo else [],
                             device_id=f"android-{abs(hash(reporter.id if reporter else 'x')) % 9000 + 1000}", app_version="pwa-1.4.2" if channel == "pwa" else None,
                             use_llm=False)


def run(session: Session):
    # Restart the RNG stream on EVERY replay. It used to be seeded once at import, so a second reset inside the same
    # process (Settings → Reset demo / POST /api/admin/reset) continued the stream and replayed a different history.
    rnd.seed(SEED)
    acts = {a.activity_id: a for a in session.exec(select(Activity))}
    reps = {r.id: r for r in session.exec(select(Reporter))}
    truth = truth_schedule(acts)
    gt: dict[int, str] = {}                      # event id → true activity (for the planner simulation)
    progress_counter: dict[str, int] = {}
    specials = special_messages()
    day = D0
    stats = {"reports": 0}
    while day <= D1:
        todays = []
        for aid, (s, f) in truth.items():
            a = acts[aid]
            if not (s <= day and (f is None or day <= f)):
                continue
            if s < D0 and f and f < D0:
                continue
            if s == day:
                kind, p = "start", 0.92
            elif f == day:
                kind, p = "finish", 0.9
            else:
                kind, p = "progress", 0.33
            if rnd.random() < p:
                todays.append((a, kind))
        rnd.shuffle(todays)
        for i, (a, kind) in enumerate(todays):
            r = reporter_for(a, reps)
            if not r:
                continue
            hinglish = r.language == "hi" and rnd.random() < 0.7
            if a.action == "erect" and a.object_class == "spool" and kind != "finish":
                # which spool the crew is on follows the true progress through the duration
                span = max(1, ((f or D1) - s).days + 1)
                idx = min(len(a.scope_objects or [1]) - 1, int(((day - s).days / span) * len(a.scope_objects or [1])))
                idx = max(idx, progress_counter.get(a.activity_id, 0))
            else:
                idx = progress_counter.get(a.activity_id, 0)
            text, slang = compose(a, kind, day, idx, hinglish)
            progress_counter[a.activity_id] = idx + 1
            channel = rnd.choices(["whatsapp", "pwa", "telegram"], [0.5, 0.42, 0.08])[0]
            if slang:
                channel = rnd.choice(["whatsapp", "whatsapp", "pwa"])
            photo = None
            if kind == "finish" or (a.action == "erect" and a.object_class == "spool" and idx + 1 >= len(a.scope_objects or [1])):
                if rnd.random() < 0.8:
                    photo = f"hist_{a.action or 'work'}_{a.object_class or 'site'}_{day.day:02d}_{i}.jpg".replace(" ", "_")
                    channel = "pwa" if rnd.random() < 0.6 else channel
            lag = 0.0
            if a.work_front in POOR_SIGNAL and rnd.random() < 0.35:
                lag = rnd.choice([1.5, 3, 5, 9, 14, 17])
            hh, mm = rnd.randint(9, 18), rnd.choice([0, 7, 12, 25, 33, 41, 52])
            res = send(session, day, hh, mm, text, r, channel, a.work_front, photo=photo, lag_h=lag)
            stats["reports"] += 1
            for ev in res["events"]:
                gt[ev.id] = a.activity_id
                if ev.state == "clarifying":
                    answer_sim(session, ev, a.activity_id, day, hh, mm)
            # occasional duplicate of the same update via the contractor's DPR channel next morning
            if kind == "finish" and rnd.random() < 0.25 and day < D1:
                with clock.frozen(datetime.combine(day + timedelta(days=1), time(8, 30))):
                    res2 = ingest.ingest(session, text=text, source_type="dpr_text", channel="dpr_upload", reporter_id=r.id,
                                         captured_at=datetime.combine(day, time(19, 0)), reporting_date=day,
                                         source_doc_id=f"DPR-{a.discipline[:3].upper()}-{day.isoformat()}", use_llm=False)
                for ev in res2["events"]:
                    gt[ev.id] = a.activity_id
        for sp in specials.get(day, []):
            res = send(session, day, sp["hh"], sp.get("mm", 10), sp["text"], reps[sp["rep"]], sp.get("channel", "whatsapp"), sp.get("wf"),
                       photo=sp.get("photo"), gps_mode=sp.get("gps", "auto"), lag_h=sp.get("lag", 0))
            stats["reports"] += 1
            for ev in res["events"]:
                if sp.get("truth"):
                    gt[ev.id] = sp["truth"]
        # escalate unanswered clarifications, then the planner works the queue (not the last 3 days)
        escalate(session, datetime.combine(day, time(20, 0)))
        if day <= D1 - timedelta(days=2):
            planner_sim(session, day, gt)
        day += timedelta(days=1)
    hse_followup(session)
    # clarifications pending at seed end → leave 1-2 open, escalate the rest
    escalate(session, datetime.combine(D1, time(23, 0)))
    return stats


def answer_sim(session, ev, true_aid, day, hh, mm):
    if rnd.random() > 0.72:
        return                                          # reporter didn't answer → escalates later
    t = datetime.combine(day, time(hh, mm)) + timedelta(minutes=rnd.choice([2, 4, 6, 11, 18, 35]))
    vals = [o["value"] for o in ev.clarification_options]
    if true_aid in vals:
        v = true_aid
    elif "__photo" in vals:
        if rnd.random() < 0.55:
            with clock.frozen(t):
                ingest.answer_clarification(session, ev.id, "__photo", f"hist_{ev.action or 'work'}_{(ev.object_class or 'site').replace(' ', '_')}_answer.jpg")
            return
        v = "__nophoto"
    elif "__yes" in vals:
        v = "__yes"
    elif any(x.startswith("date:") for x in vals):
        v = vals[0]
    else:
        v = "__other"
    with clock.frozen(t):
        ingest.answer_clarification(session, ev.id, v)


def escalate(session, at: datetime):
    """Clarifications unanswered for 2h go to the planner (spec: second ambiguity → planner)."""
    rows = session.exec(select(Event).where(Event.state == "clarifying")).all()
    for ev in rows:
        if ev.clarification_asked_at and at - ev.clarification_asked_at >= timedelta(hours=2):
            ev.state = "review"
            ev.route_reason = "no answer to the clarifying question within 2 h — planner decides"
            session.add(ev)
    session.commit()


def planner_sim(session, day, gt):
    kg = get_kg(session)
    rows = session.exec(select(Event).where(Event.state == "review", Event.event_date <= day)).all()
    for ev in rows:
        if rnd.random() > 0.9:
            continue
        truth = gt.get(ev.id)
        planner = "R-IYER" if (ev.discipline in ("Piping", "Mechanical", "Structural") or not ev.discipline) else "R-MENON"
        secs = round(rnd.uniform(8, 45) if day < date(2026, 9, 14) else rnd.uniform(6, 25), 1)
        top = ev.top_k_candidates[0]["activity_id"] if ev.top_k_candidates else None
        with clock.frozen(datetime.combine(day, time(19, rnd.randint(0, 50)))):
            if ev.blocker_flag:
                learning.review(session, ev.id, "approve", ev.affected_activities[0] if ev.affected_activities else top, None, planner, secs) \
                    if (ev.affected_activities or top) else learning.review(session, ev.id, "reject", None, None, planner, secs)
                continue
            if not truth:
                if ev.unplanned_flag or not top:
                    continue
                learning.review(session, ev.id, "unplanned", None, None, planner, secs)
                continue
            if top == truth:
                learning.review(session, ev.id, "approve", truth, None, planner, secs)
            else:
                ta, pa = kg.activities.get(truth), kg.activities.get(top) if top else None
                if pa and ta and pa.work_front != ta.work_front:
                    reason = "wrong_area"
                elif any(s in (ev.source_sentence or "").lower() for s in list(SLANG_FOR_WF.values()) + list(SLANG_FOR_LINE.values())):
                    reason = "terminology"
                else:
                    reason = "wrong_object"
                if any(s in (ev.source_sentence or "").lower() for s in list(SLANG_FOR_WF.values()) + list(SLANG_FOR_LINE.values())):
                    reason = "terminology" if reason != "wrong_area" else "wrong_area"
                learning.review(session, ev.id, "correct" if top else "reassign", truth, reason, planner, secs)


def hse_followup(session):
    """Close / acknowledge older HSE items like a real HSE officer would."""
    for h in session.exec(select(HSEEvent)).all():
        age = (datetime(2026, 9, 25, 20, 0) - h.created_at).days if h.created_at else 0
        if age >= 4:
            h.status, h.assigned_to, h.closed_note = "closed", "N. Hazarika", "Toolbox talk held; corrective action verified on site."
            if h.stop_work_flag and not h.stop_work_scope:
                h.stop_work_scope = "zone"
        elif age >= 1:
            h.status, h.assigned_to = "acknowledged", "N. Hazarika"
        session.add(h)
    session.commit()


def special_messages() -> dict:
    """Hand-written blockers, HSE, unplanned and weather claims that make the charts tell the story."""
    d = lambda s: date.fromisoformat(s)  # noqa: E731
    S = {}

    def add(day, **kw):
        S.setdefault(d(day), []).append(kw)

    # ── Rack B: why PIP-3-2340 is late ──
    add("2026-09-10", hh=10, text="Rack B spool erection not started, spools for line 24-P-1203 waiting for crane", rep="R-KALITA", wf="WF-U3-RACK-B", channel="pwa")
    add("2026-09-11", hh=9, text="Crane CR-50T-02 breakdown, Rack B spool erection could not start, hydraulic leak", rep="R-KALITA", wf="WF-U3-RACK-B")
    add("2026-09-12", hh=16, text="CR-50T-02 still under repair, Rack B erection on hold whole day", rep="R-KALITA", wf="WF-U3-RACK-B")
    add("2026-09-13", hh=15, mm=5, text="Heavy rain from 2 pm, Rack B work stopped", rep="R-KALITA", wf="WF-U3-RACK-B", channel="pwa")
    add("2026-09-13", hh=15, mm=20, text="Baarish 2 baje se, F-12 concreting band, pani bhar gaya", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-13", hh=16, text="Rain from 2pm to 6pm, cable pulling tray T-3 stopped", rep="R-SHARMA", wf="WF-U2-RACK-A")
    add("2026-09-13", hh=17, text="Heavy rain from 14:00, ST-2 steel erection stopped at EL +12m", rep="R-SAIKIA", wf="WF-U2-STRUCT")
    add("2026-09-16", hh=11, text="Rack B spool erection held up, drawing ISO-4417 rev C awaited from engineering", rep="R-KALITA", wf="WF-U3-RACK-B")
    add("2026-09-19", hh=10, text="ISO-4417 revised drawing still not received, Rack B spools on hold", rep="R-KALITA", wf="WF-U3-RACK-B", channel="pwa")
    add("2026-09-22", hh=12, text="Rack B spool erection not started, manpower short as fitters shifted to tank farm", rep="R-KALITA", wf="WF-U3-RACK-B")
    add("2026-09-24", hh=11, text="Spool 5 for Rack C not received from fab yard, material nahi aaya", rep="R-KALITA", wf="WF-U3-RACK-C")
    add("2026-09-12", hh=17, text="All 4 spools of line 12-P-1215 erected at Rack C, erection complete, 8 fitter", rep="R-KALITA",
        wf="WF-U3-RACK-C", channel="pwa", gps="good", photo="hist_erect_spool_rackC_complete.jpg", truth="PIP-3-2345")
    # ── weather claims: corroborated (7, 21 Sep) and NOT corroborated (18 Sep dry) ──
    add("2026-09-07", hh=17, text="Rain from 3 pm, excavation F-12 stopped", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-18", hh=15, text="Work stopped due to rain from 1 pm, pouring could not continue at F-13", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-18", hh=16, text="Rain, cable tray work stopped from 2pm", rep="R-SHARMA", wf="WF-U2-RACK-A")
    add("2026-09-21", hh=17, text="Baarish 3 baje se, basin wall shuttering ruk gaya", rep="R-GOGOI", wf="WF-U2-CT")
    add("2026-09-09", hh=18, text="Light rain from 3pm to 6pm, ST-2 bolt torquing stopped", rep="R-SAIKIA", wf="WF-U2-STRUCT")
    # ── other blockers ──
    add("2026-09-08", hh=11, text="Power cut from 11 am, DG failure at SS-2, panel work stopped 3 hrs", rep="R-SHARMA", wf="WF-U2-SUBSTN")
    add("2026-09-15", hh=10, text="Cement not received, F-13 PCC delayed, 5 hrs lost", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-17", hh=9, text="Client hold on compressor K-201 grouting, PMC instruction awaited", rep="R-BARUAH", wf="WF-U2-COMP")
    add("2026-09-20", hh=14, text="Scaffolding not ready, no access to tray T-5, work stopped 4 hrs", rep="R-SHARMA", wf="WF-U2-RACK-A")
    add("2026-09-23", hh=10, text="Welding machine WM-02 breakdown at tank farm, joints held up 3 hrs", rep="R-BORA", wf="WF-U3-TANK")
    add("2026-09-14", hh=15, text="Rework: 2 joints on line 24-P-1108 rejected in RT, re-weld required", rep="R-BORA", wf="WF-U3-TANK")
    # ── HSE ──
    add("2026-09-06", hh=11, text="Near miss, spanner dropped from EL +12m at ST-2, no one hurt", rep="R-SAIKIA", wf="WF-U2-STRUCT", channel="pwa")
    add("2026-09-12", hh=14, text="Worker found without harness at Rack A top, unsafe act, stopped and briefed", rep="R-SHARMA", wf="WF-U2-RACK-A", channel="pwa")
    add("2026-09-16", hh=10, text="First aid case, helper cut on hand while cutting tie wire at F-13", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-22", hh=9, text="Basin wall concreting inside cooling tower basin started, 12 mason", rep="R-GOGOI", wf="WF-U2-CT", truth="CIV-2-1403")
    add("2026-09-24", hh=16, text="Open excavation near F-14 without barricade, unsafe condition", rep="R-GOGOI", wf="WF-U3-FDN", channel="pwa")
    add("2026-09-25", hh=11, text="Small oil spill from hydra HY-14T-03 at Rack A, cleaned with sand", rep="R-KONWAR", wf="WF-U2-RACK-A")
    # ── unplanned work ──
    add("2026-09-06", hh=12, text="Temporary approach road made for crane near tank farm", rep="R-GOGOI", wf="WF-U3-TANK")
    add("2026-09-09", hh=15, text="Dewatering done at F-12 pit with 2 pumps after overnight seepage", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-12", hh=12, text="Client asked extra platform at compressor house, additional steel fabricated", rep="R-SAIKIA", wf="WF-U2-COMP")
    add("2026-09-15", hh=17, text="Temporary store shed erected near substation for cable drums", rep="R-SHARMA", wf="WF-U2-SUBSTN")
    add("2026-09-17", hh=11, text="Dismantled 3 supports at Rack A, wrong elevation, rework", rep="R-KONWAR", wf="WF-U2-RACK-A")
    add("2026-09-19", hh=10, text="Additional sleeve for fire water crossing, not in drawing", rep="R-GOGOI", wf="WF-U3-FDN")
    add("2026-09-21", hh=13, text="Emergency: cooling water leak at existing header near Unit 3, clamp fitted", rep="R-BORA", wf="WF-U3-TANK")
    add("2026-09-23", hh=15, text="Housekeeping and scrap clearing at Unit 2 compressor area", rep="R-KONWAR", wf="WF-U2-COMP")
    add("2026-09-24", hh=12, text="Temporary barricading fence installed around F-14 excavation", rep="R-GOGOI", wf="WF-U3-FDN")
    # ── pure resource reports ──
    add("2026-09-10", hh=8, text="Night shift at tank farm: 10 welder 6 fitter, 2 welding machine", rep="R-BORA", wf="WF-U3-TANK")
    add("2026-09-19", hh=8, text="Raat ki shift tank farm pe 8 welder aur 4 fitter the", rep="R-BORA", wf="WF-U3-TANK")
    add("2026-09-23", hh=8, text="Night shift Rack A: 6 welder, 4 fitter, hydra HY-14T-03 idle", rep="R-KONWAR", wf="WF-U2-RACK-A")
    return S
