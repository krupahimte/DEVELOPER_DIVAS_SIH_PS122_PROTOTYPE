"""Overview dashboard data — every chart is computed from the event store (nothing canned)."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .. import clock
from ..db import get_session, get_settings
from ..models import Activity, Alias, Event, HSEEvent, Report, ReviewAction, WeatherObs, WorkFront
from ..pipeline.kg import get_kg

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

FILL_FIELDS = ["action", "object_event_type", "object_class", "object_id", "object_qualifier", "line_ref", "location_text", "quantity", "uom",
               "event_date", "geofence_zone_id", "photo_ids", "cv_plausibility", "cause_category", "cause_text", "time_lost_h", "hse_event_flag",
               "manpower_total", "manpower_by_trade", "shift", "equipment_deployed", "material_consumed", "material_item_id", "weather_reported",
               "weather_fetched", "matched_activity_id", "clarification_asked"]


def route_of(e: Event) -> str:
    """How the pipeline first routed this event (for the funnel)."""
    if e.state == "hse_hold":
        return "HSE hold"
    if e.state == "duplicate":
        return "Duplicate"
    if e.state == "unparseable":
        return "Unparseable"
    if e.clarification_asked:
        return "Clarify"
    if e.state == "unplanned" and not (e.route_reason or "").startswith("planner"):
        return "Unplanned"
    if e.state == "linked" and not (e.route_reason or "").startswith("planner"):
        return "Auto-sync"
    return "Review"


def outcome_of(e: Event) -> str:
    """Final processing outcome, from the existing state model:
    AUTO_SYNC · QUESTION_RESOLVED (reporter answered the one question) · PLANNER_APPROVED (planner approve/correct)
    · HSE_HOLD · UNPLANNED · DUPLICATE · UNPARSEABLE · PENDING (clarifying / review)."""
    planner = (e.route_reason or "").startswith("planner")
    if e.state == "hse_hold":
        return "HSE_HOLD"
    if e.state == "duplicate":
        return "DUPLICATE"
    if e.state == "unparseable":
        return "UNPARSEABLE"
    if e.state == "unplanned":
        return "UNPLANNED"
    if e.state == "linked":
        if planner:
            return "PLANNER_APPROVED"
        if e.clarification_asked:
            return "QUESTION_RESOLVED"      # a human answer was needed — not an automatic sync
        return "AUTO_SYNC"
    return "PENDING"


def is_auto(e: Event) -> bool:
    return outcome_of(e) == "AUTO_SYNC" and bool(e.route_reason) and (
        e.route_reason.startswith("all four") or e.route_reason.startswith("blocker recorded") or e.route_reason.startswith("resource record"))


def _days(d0: date, d1: date):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)


def _wf(kg, e):
    wf = e.location_zone_text or e.geofence_zone_id
    if not wf and e.matched_activity_id in kg.activities:
        wf = kg.activities[e.matched_activity_id].work_front
    return wf


@router.get("/overview")
def overview(area: str = "WF-U3-RACK-B", discipline: str | None = None, s: Session = Depends(get_session)):
    kg = get_kg(s)
    kg.refresh_dynamic(s)
    settings = get_settings(s)
    today = clock.today()
    evs = s.exec(select(Event)).all()
    if discipline:
        evs = [e for e in evs if e.discipline == discipline]
    reps = s.exec(select(Report)).all()
    acts = s.exec(select(Activity)).all()
    hse = s.exec(select(HSEEvent)).all()
    ras = s.exec(select(ReviewAction)).all()
    aliases = s.exec(select(Alias)).all()
    d0 = min([e.event_date for e in evs if e.event_date] or [today])
    days = list(_days(max(d0, date(2026, 9, 5)), today))

    # ── KPIs ──
    ev_today = [e for e in evs if e.event_date == today]
    decided = [e for e in evs if e.state not in ("hse_hold", "duplicate", "unparseable")]
    lags = [r.sync_lag_s for r in reps if r.sync_lag_s is not None]
    kpis = {
        "reports_today": sum(1 for r in reps if r.reporting_date == today),
        "events_today": len(ev_today),
        "events_total": len(evs),
        "auto_sync_pct": round(100 * sum(1 for e in decided if is_auto(e)) / max(1, len(decided)), 1),
        "auto_sync_pct_today": round(100 * sum(1 for e in ev_today if is_auto(e)) / max(1, sum(1 for e in ev_today if e.state not in ("hse_hold", "duplicate"))), 1),
        "in_review": sum(1 for e in evs if e.state in ("review", "clarifying")),
        "unplanned_open": sum(1 for e in evs if e.state == "unplanned" and e.unplanned_status in (None, "open")),
        "hse_open": sum(1 for h in hse if h.status != "closed"),
        "avg_review_s": round(mean([r.planner_review_seconds for r in ras if r.planner_review_seconds] or [0]), 1),
        "avg_sync_lag_h": round(mean(lags or [0]) / 3600, 2),
        "aliases_learned": sum(1 for a in aliases if a.source == "planner"),
        "activities_started": sum(1 for a in acts if a.actual_start),
        "activities_finished": sum(1 for a in acts if a.actual_finish),
    }

    # ── 1. funnel / sankey ──
    route_counts = Counter(route_of(e) for e in evs)
    clar_out = Counter(("Linked" if e.state == "linked" else "Planner review") for e in evs if e.clarification_asked)
    rev_out = Counter(("Approved/corrected" if e.state == "linked" else ("Pending" if e.state in ("review", "clarifying") else e.state.title()))
                      for e in evs if route_of(e) == "Review")
    nodes = ["Reports", "Events", "HSE hold", "Auto-sync", "Clarify", "Review", "Unplanned", "Duplicate", "Unparseable",
             "Linked after answer", "Planner review", "Approved/corrected", "Pending"]
    idx = {n: i for i, n in enumerate(nodes)}
    links = [{"source": 0, "target": 1, "value": len(evs)}]
    for k in ("HSE hold", "Auto-sync", "Clarify", "Review", "Unplanned", "Duplicate", "Unparseable"):
        if route_counts.get(k):
            links.append({"source": 1, "target": idx[k], "value": route_counts[k]})
    if clar_out.get("Linked"):
        links.append({"source": idx["Clarify"], "target": idx["Linked after answer"], "value": clar_out["Linked"]})
    if clar_out.get("Planner review"):
        links.append({"source": idx["Clarify"], "target": idx["Planner review"], "value": clar_out["Planner review"]})
    for k in ("Approved/corrected", "Pending"):
        if rev_out.get(k):
            links.append({"source": idx["Review"], "target": idx[k], "value": rev_out[k]})
    funnel = {"nodes": [{"name": n} for n in nodes], "links": links, "reports": len(reps), "routes": dict(route_counts)}

    # ── 2. Gantt for an area ──
    area_acts = [a for a in acts if a.work_front == area or a.unit == area or a.area == area]
    area_acts.sort(key=lambda a: a.planned_start)
    gantt = []
    for a in area_acts[:30]:
        src = [e.id for e in evs if e.matched_activity_id == a.activity_id and e.state == "linked"]
        blk = [e.id for e in evs if e.blocker_flag and a.activity_id in (e.affected_activities or [])]
        var_s = (a.actual_start - a.planned_start).days if a.actual_start else ((today - a.planned_start).days if a.planned_start < today else None)
        var_f = (a.actual_finish - a.planned_finish).days if a.actual_finish else None
        gantt.append({"id": a.activity_id, "name": a.name, "ps": a.planned_start.isoformat(), "pf": a.planned_finish.isoformat(),
                      "as": a.actual_start.isoformat() if a.actual_start else None, "af": a.actual_finish.isoformat() if a.actual_finish else None,
                      "as_event": a.actual_start_source_event, "af_event": a.actual_finish_source_event, "as_prov": a.actual_start_prov,
                      "af_prov": a.actual_finish_prov, "var_start": var_s, "var_finish": var_f, "events": src[-12:], "blockers": blk[-8:]})

    # ── 3. variance by discipline ──
    vd = defaultdict(lambda: {"start": [], "finish": []})
    for a in acts:
        if a.actual_start:
            vd[a.discipline]["start"].append((a.actual_start - a.planned_start).days)
        elif a.planned_start < today:
            vd[a.discipline]["start"].append((today - a.planned_start).days)
        if a.actual_finish:
            vd[a.discipline]["finish"].append((a.actual_finish - a.planned_finish).days)
    variance = [{"discipline": k, "start_slip": round(mean(v["start"]), 1) if v["start"] else 0,
                 "finish_slip": round(mean(v["finish"]), 1) if v["finish"] else 0, "n": len(v["start"])} for k, v in sorted(vd.items())]

    # ── 4. Pareto of delay causes ──
    blk = [e for e in evs if e.blocker_flag and e.cause_category]
    cc = Counter(e.cause_category for e in blk)
    hrs = defaultdict(float)
    for e in blk:
        hrs[e.cause_category] += e.time_lost_h or 0
    pareto = []
    for mode, src in (("count", cc), ("hours", hrs)):
        tot = sum(src.values()) or 1
        run = 0
        rows = []
        for k, v in sorted(src.items(), key=lambda kv: -kv[1]):
            run += v
            rows.append({"cause": k, "value": round(v, 1), "cum_pct": round(100 * run / tot, 1),
                         "events": [e.id for e in blk if e.cause_category == k][:20]})
        pareto.append({"mode": mode, "rows": rows})

    # ── 5. weather claims vs evidence ──
    wx = {w.day: w.rain_mm for w in s.exec(select(WeatherObs))}
    weather = []
    for d in days:
        claims = [e for e in evs if e.event_date == d and (e.weather_reported or e.cause_category == "weather")]
        weather.append({"day": d.isoformat(), "corroborated": sum(1 for e in claims if e.weather_corroborates == "true"),
                        "not_corroborated": sum(1 for e in claims if e.weather_corroborates == "false"),
                        "unavailable": sum(1 for e in claims if e.weather_corroborates in (None, "unavailable")),
                        "rain_mm": wx.get(d, 0), "events": [e.id for e in claims]})

    # ── 6. productivity (qty per manhour) by discipline & shift ──
    prod = defaultdict(lambda: defaultdict(list))
    shift_cmp = defaultdict(lambda: {"day": [], "night": []})
    for e in evs:
        if e.quantity and e.manhours and e.discipline and not e.blocker_flag:
            r = e.quantity / e.manhours
            prod[e.event_date.isoformat()][e.discipline].append(r)
            shift_cmp[e.discipline][e.shift or "day"].append(r)
    discs = sorted({dd for v in prod.values() for dd in v})
    productivity = [{"day": d, **{k: round(mean(v), 3) for k, v in prod[d].items()}} for d in sorted(prod)]
    shift = [{"discipline": k, "day": round(mean(v["day"]), 3) if v["day"] else 0, "night": round(mean(v["night"]), 3) if v["night"] else 0}
             for k, v in sorted(shift_cmp.items())]

    # ── 7. manpower by trade & equipment utilisation ──
    mp = defaultdict(lambda: defaultdict(int))
    trades = set()
    for e in evs:
        for t, n in (e.manpower_by_trade or {}).items():
            mp[e.event_date.isoformat()][t] += n
            trades.add(t)
    manpower = [{"day": d.isoformat(), **mp.get(d.isoformat(), {})} for d in days]
    eq = defaultdict(lambda: {"working": 0, "idle": 0, "breakdown": 0})
    for e in evs:
        for x in e.equipment_deployed or []:
            if x.startswith(("CR-", "HY-", "EX-", "WM-", "TM-", "BP-", "DG-")) or x in ("crane", "hydra", "excavator", "welding_machine", "transit_mixer"):
                k = "breakdown" if e.equipment_breakdown else ("idle" if e.equipment_idle_flag else "working")
                eq[x][k] += 1
    equipment = [{"equipment": k, **v} for k, v in sorted(eq.items(), key=lambda kv: -sum(kv[1].values()))][:10]

    # ── 8. confidence health ──
    def hist(vals, bins=10):
        out = [0] * bins
        for v in vals:
            if v is None:
                continue
            out[min(bins - 1, int(v * bins))] += 1
        return [{"bin": f"{i / bins:.1f}", "count": c} for i, c in enumerate(out)]
    scored = [e for e in evs if e.state not in ("unparseable",)]
    confidence = {k: hist([getattr(e, f"{k}_conf") for e in scored]) for k in ("extraction", "match", "date", "verification")}
    margins = [e.match_margin for e in scored if e.match_margin is not None and not e.blocker_flag and e.state != "hse_hold"]
    confidence["margin"] = [{"bin": f"{i * 0.05:.2f}", "count": sum(1 for m in margins if i * 0.05 <= m < (i + 1) * 0.05 or (i == 19 and m >= 0.95))}
                            for i in range(20)]
    confidence["thresholds"] = settings["gate"]

    # ── 9. match path mix over time + 10. learning curve ──
    path_by_day, learning = [], []
    for d in days:
        de = [e for e in evs if e.event_date == d and e.match_path and not e.blocker_flag and e.state != "hse_hold"]
        c = Counter(e.match_path for e in de)
        path_by_day.append({"day": d.isoformat(), **{k: c.get(k, 0) for k in ("kg_narrowed", "vector_only", "fuzzy_fallback")}})
    path_total = Counter(e.match_path for e in evs if e.match_path and not e.blocker_flag and e.state != "hse_hold")
    for i, d in enumerate(days):
        window = [e for e in evs if e.event_date and d - timedelta(days=6) <= e.event_date <= d and e.state not in ("hse_hold", "duplicate", "unparseable")]
        learning.append({"day": d.isoformat(), "aliases": sum(1 for a in aliases if a.at and a.at.date() <= d),
                         "auto_pct": round(100 * sum(1 for e in window if is_auto(e)) / max(1, len(window)), 1),
                         "clarify_rate": round(100 * sum(1 for e in window if e.clarification_asked) / max(1, len(window)), 1)})

    # ── 11. sync lag heatmap ──
    rep_by_id = {r.id: r for r in reps}
    lag = defaultdict(list)
    for e in evs:
        r = rep_by_id.get(e.report_id)
        wf = _wf(kg, e)
        if r and wf and r.sync_lag_s is not None:
            lag[(wf, e.event_date.isoformat())].append(r.sync_lag_s / 3600)
    heat = [{"wf": wf, "name": kg.work_fronts[wf].name, "day": d, "lag_h": round(mean(v), 2)} for (wf, d), v in lag.items() if wf in kg.work_fronts]

    # ── 12. channel adoption ──
    ch = defaultdict(Counter)
    for r in reps:
        ch[r.reporting_date.isoformat()][r.channel] += 1
    channels = [{"day": d.isoformat(), **ch.get(d.isoformat(), {})} for d in days]

    # ── 13. map ──
    wfs = s.exec(select(WorkFront)).all()
    wf_status = {}
    for w in wfs:
        aa = [a for a in acts if a.work_front == w.id]
        late = sum(1 for a in aa if not a.actual_start and a.planned_start < today)
        prog = sum(1 for a in aa if a.actual_start and not a.actual_finish)
        hse_open = sum(1 for h in hse if h.work_front == w.id and h.status != "closed")
        wf_status[w.id] = {"late": late, "in_progress": prog, "done": sum(1 for a in aa if a.actual_finish), "hse_open": hse_open,
                           "status": "hse" if hse_open else ("late" if late else ("active" if prog else "idle"))}
    pins = []
    for e in evs:
        r = rep_by_id.get(e.report_id)
        if r and r.gps_lat is not None and e.event_date and e.event_date >= today - timedelta(days=6):
            pins.append({"event_id": e.id, "lat": r.gps_lat, "lon": r.gps_lon, "state": e.state, "outside": e.geofence_result == "outside",
                         "text": e.source_sentence[:90], "day": e.event_date.isoformat()})
    geo = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"id": w.id, "name": w.name, "unit": w.unit, **wf_status[w.id]},
         "geometry": {"type": "Polygon", "coordinates": [w.polygon]}} for w in wfs]}

    # ── 14. fill-rate ──
    fill = []
    n = max(1, len(evs))
    for f in FILL_FIELDS:
        c = sum(1 for e in evs if getattr(e, f) not in (None, [], {}, False, ""))
        fill.append({"field": f, "pct": round(100 * c / n, 1), "count": c})
    obj_share = round(100 * sum(1 for e in evs if e.object_ids or e.line_ref) / n, 1)

    return {"today": today.isoformat(), "kpis": kpis, "funnel": funnel, "gantt": {"area": area, "rows": gantt}, "variance": variance,
            "pareto": pareto, "weather": weather, "productivity": {"rows": productivity, "disciplines": discs, "shift": shift},
            "manpower": {"rows": manpower, "trades": sorted(trades)}, "equipment": equipment, "confidence": confidence,
            "match_path": {"by_day": path_by_day, "total": [{"name": k, "value": v} for k, v in path_total.items()]},
            "learning": learning, "sync_lag": heat, "channels": {"rows": channels, "names": sorted({r.channel for r in reps})},
            "map": {"geo": geo, "pins": pins}, "fill_rate": {"rows": fill, "object_id_share": obj_share}}
