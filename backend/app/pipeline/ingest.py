"""Pipeline orchestrator (spec §4):

Capture → format-specific extraction (+spans, +provenance)
  → location & evidence → [match, informational] → HSE? ─yes─► hse_hold (human, always)
  → event_type (safe rule) → 4-number gate + margin
      ├ linked (auto-sync) → write actual dates + audit
      ├ clarifying (≤1 question per report) → re-run → linked | review
      ├ review (planner, one tap)
      └ unplanned
  → enrichment (weather, material) → audit chain → SSE

Nothing is silently dropped: every input ends in a visible state.
"""
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from .. import bus, clock
from ..db import get_settings
from ..models import Activity, Event, HSEEvent, Report, Reporter
from . import audit, clarify, enrich_weather, event_type, extract_llm, extract_rules, gate, hse, location, matcher, unplanned
from .evidence import assess
from .kg import get_kg
from .schema import ExtractedEvent
from .translit import has_devanagari, normalise

EXTRACTED_FIELDS = ["action", "object_event_type", "object_class", "object_qualifier", "line_ref", "drawing_no", "location_text",
                    "quantity", "uom", "event_date", "cause_category", "cause_subcategory", "cause_text", "time_lost_h",
                    "hse_event_type", "stop_work_flag", "permit_status", "manpower_by_trade", "manpower_total", "manhours", "shift",
                    "equipment_deployed", "material_consumed", "weather_reported", "object_ids"]


# ────────────────────────────────── entry point ──────────────────────────────────

def ingest(session: Session, *, text: str, source_type: str, channel: str, reporter_id: str | None,
           captured_at: datetime | None = None, queued_at: datetime | None = None,
           gps_lat=None, gps_lon=None, gps_accuracy=None, gps_timestamp=None, photo_ids=None,
           device_id=None, app_version=None, transcript_raw=None, source_doc_id=None, audio_id=None,
           reporting_date: date | None = None, extracted: list[ExtractedEvent] | None = None, raw_file=None,
           section_of=None, discipline=None, area_unit=None, actor=None, use_llm: bool | None = None) -> dict:
    settings = get_settings(session)
    now = clock.now().replace(microsecond=0)
    reporter = session.get(Reporter, reporter_id) if reporter_id else None
    original = text or ""
    norm_text = normalise(original)
    if has_devanagari(original) and not transcript_raw:
        transcript_raw = original
    captured_at = captured_at or now
    queued_at = queued_at or captured_at
    lag = max(0.0, (now - captured_at).total_seconds())
    rep = Report(
        source_type=source_type, source_doc_id=source_doc_id, channel=channel,
        reporting_date=reporting_date or captured_at.date(), reporter_id=reporter_id,
        contractor=reporter.contractor if reporter else None, discipline=discipline or (reporter.discipline if reporter else None),
        area_unit=area_unit, device_id=device_id, app_version=app_version,
        captured_at=captured_at, queued_at=queued_at, synced_at=now, sync_lag_s=lag, offline_flag=lag > 900,
        raw_text=norm_text, transcript_raw=transcript_raw, raw_file=raw_file, audio_id=audio_id, photo_ids=list(photo_ids or []),
        gps_lat=gps_lat, gps_lon=gps_lon, gps_accuracy=gps_accuracy, gps_timestamp=gps_timestamp,
    )
    rep.provenance = {k: "GIVEN" for k in ("source_type", "channel", "reporting_date", "reporter_id", "captured_at", "queued_at",
                                           "synced_at", "raw_text", "gps_lat", "gps_lon", "gps_accuracy", "device_id")}
    rep.provenance.update({"sync_lag_s": "DERIVED", "offline_flag": "DERIVED", "input_language": "EXTRACTED"})
    session.add(rep)
    session.flush()
    audit.append(session, actor or (reporter_id or "system"), "report.received", f"report:{rep.id}",
                 {"channel": channel, "source_type": source_type, "chars": len(norm_text), "photos": len(rep.photo_ids)})

    # ── format-specific extraction ──
    if extracted is None:
        llm_ok = settings.get("llm_enabled", True) if use_llm is None else use_llm
        extracted = extract_llm.extract(norm_text, rep.reporting_date) if llm_ok else None
        rep.extractor = "llm" if extracted is not None else "rules"
        if extracted is None:
            extracted = extract_rules.extract(norm_text, rep.reporting_date, section_of, gazetteer=get_kg(session).gazetteer())
    else:
        rep.extractor = "spreadsheet" if source_type == "xlsx" else rep.extractor
    rep.input_language = extracted[0].input_language if extracted else extract_rules.detect_language(norm_text)

    events = []
    if not extracted:
        ev = Event(report_id=rep.id, seq=0, created_at=now, reporter_id=reporter_id, channel=channel, state="unparseable",
                   source_sentence=norm_text[:500], source_span=[0, len(norm_text)], extractor=rep.extractor,
                   route_reason="no event could be read from the input; kept verbatim for the planner",
                   provenance={"source_sentence": "GIVEN", "state": "DERIVED"}, extraction_conf=0.0)
        session.add(ev)
        session.flush()
        audit.append(session, "pipeline", "event.unparseable", f"event:{ev.id}", {"report": rep.id})
        events.append(ev)
    for i, x in enumerate(extracted):
        ev = _event_from_extraction(rep, x, i, now, reporter)
        session.add(ev)
        session.flush()
        process_event(session, ev, rep, reporter, settings)
        events.append(ev)
    rep.event_count = len(events)
    session.add(rep)
    session.commit()
    for e in events:
        session.refresh(e)
    reply = compose_reply(session, rep, events)
    bus.publish("report", {"report_id": rep.id, "states": [e.state for e in events], "channel": channel})
    return {"report": rep, "events": events, "reply": reply}


def _event_from_extraction(rep: Report, x: ExtractedEvent, seq: int, now, reporter) -> Event:
    ev = Event(report_id=rep.id, seq=seq, created_at=now, reporter_id=rep.reporter_id, channel=rep.channel,
               discipline=rep.discipline, extractor=x.extractor if rep.extractor != "spreadsheet" else "spreadsheet")
    for f in ("action", "object_event_type", "object_class", "object_qualifier", "object_ordinals", "line_ref", "drawing_no",
              "location_text", "quantity", "uom", "event_date", "blocker_flag", "cause_category", "cause_subcategory", "cause_text",
              "time_lost_h", "blocker_resolved_at", "hse_event_flag", "stop_work_flag", "mishap_flag", "permit_status",
              "manpower_by_trade", "manpower_total", "manhours", "shift", "equipment_deployed", "equipment_idle_flag",
              "equipment_breakdown", "material_consumed", "material_shortage_flag", "weather_reported", "input_language",
              "document_section"):
        setattr(ev, f, getattr(x, f))
    ev.object_ids = list(x.object_refs)
    ev.object_id = x.object_refs[0] if x.object_refs else None
    ev.source_sentence = x.sentence
    ev.source_span = list(x.sentence_span)
    ev.spans = {k: list(v) for k, v in x.spans.items()}
    if "object_refs" in ev.spans:
        ev.spans["object_ids"] = ev.spans.pop("object_refs")
    ev.extraction_conf = x.extraction_conf
    ev.date_conf = x.date_conf
    fc = {"_activity_level_finish": x.activity_level_finish, "_time_window": list(x.time_window) if x.time_window else None,
          "_hse": {"type": x.hse_event_type, "severity": x.hse_severity, "mishap_category": x.mishap_category,
                   "permit_type": x.permit_type, "permit_id": x.permit_id, "gas_test_done": x.gas_test_done}}
    ev.field_conf = fc
    if ev.manhours is None and ev.manpower_total:
        ev.manhours = float(ev.manpower_total * 8)
    prov = {}
    for f in EXTRACTED_FIELDS:
        v = getattr(ev, f, None)
        if v in (None, [], {}, False):
            continue
        prov[f] = "EXTRACTED" if f in ev.spans or f in ("object_ids",) else "DERIVED"
    if "event_date" not in ev.spans:
        prov["event_date"] = "DERIVED"          # defaulted to the reporting date
    prov["source_sentence"] = "GIVEN"
    if ev.cause_text:
        prov["cause_text"] = "GIVEN"            # verbatim
    if ev.manhours and "manhours" not in ev.spans:
        prov["manhours"] = "DERIVED"
    if ev.quantity is not None and "quantity" not in ev.spans:
        prov["quantity"] = "DERIVED"
    for f in ("input_language",):
        prov[f] = "EXTRACTED"
    for f in ("reporter_id", "channel"):
        prov[f] = "GIVEN"
    ev.provenance = prov
    return ev


def _prior_activities(session: Session, reporter_id: str | None, day: date) -> set:
    if not reporter_id:
        return set()
    rows = session.exec(select(Event.matched_activity_id).where(
        Event.reporter_id == reporter_id, Event.state == "linked", Event.matched_activity_id.is_not(None),
        Event.event_date >= day - timedelta(days=3), Event.event_date <= day))
    return {r for r in rows if r}


# ───────────────────────────────── process one event ─────────────────────────────────

def process_event(session: Session, ev: Event, rep: Report, reporter: Reporter | None, settings: dict,
                  confirmed: str | None = None, clarify_allowed: bool | None = None, actor: str = "pipeline"):
    kg = get_kg(session)
    today = ev.event_date or rep.reporting_date
    prov = dict(ev.provenance or {})
    fc = dict(ev.field_conf or {})
    ev.location_conflict = False

    # ── Layer 3: location (report GPS, else photo EXIF GPS) ──
    ev_photos = list(rep.photo_ids or [])
    evd = assess(ev_photos, {"action": ev.action, "object_class": ev.object_class}, rep.captured_at) if ev_photos else None
    lat, lon, acc = rep.gps_lat, rep.gps_lon, rep.gps_accuracy
    if lat is None and evd and evd["exif_gps"]:
        lat, lon, acc = evd["exif_gps"][0], evd["exif_gps"][1], 20
        prov["geofence_basis"] = "exif"
    gf = location.geofence(kg, lat, lon, acc)
    ev.geofence_result, ev.geofence_zone_id = gf["result"], gf["zone"]
    fc["_nearby_zones"] = gf["nearby"]
    fc["_distance_m"] = gf["distance_m"]
    prov.update({"geofence_result": "DERIVED", "geofence_zone_id": "DERIVED"})

    # ── Layer 4: evidence ──
    ev.photo_ids, ev.photo_count = ev_photos, len(ev_photos)
    if evd:
        ev.exif_gps = evd["exif_gps"]
        ev.exif_timestamp = evd["exif_timestamp"]
        ev.photo_recycled_flag = evd["recycled"]
        ev.cv_objects_detected = evd["cv_objects"]
        ev.cv_plausibility = evd["cv_score"]
        ev.cv_model_version = evd["cv_model"]
        prov.update({"photo_ids": "GIVEN", "exif_gps": "GIVEN", "exif_timestamp": "GIVEN", "cv_objects_detected": "DERIVED",
                     "cv_plausibility": "DERIVED"})
    has_gps = gf["result"] != "unknown"
    ev.evidence_completeness = "full" if (ev_photos and has_gps and ev.exif_timestamp) else ("partial" if (ev_photos or has_gps) else "none")
    prov["evidence_completeness"] = "DERIVED"

    ev.field_conf = dict(fc)      # a COPY: the matcher's queries autoflush, after which the ORM's committed state
    #                               would alias `fc` and later in-place edits (_question_hi, _inference_why,
    #                               _failing) would be invisible to change detection and never persisted.
    # ── match (informational for HSE, decisive otherwise) ──
    m = matcher.match(session, kg, ev, reporter, today, settings, _prior_activities(session, rep.reporter_id, today), confirmed)
    ev.match_path, ev.candidate_set_size, ev.top_k_candidates = m["path"], m["candidate_set_size"], m["top"]
    ev.match_margin, ev.match_rationale = m["margin"], m["rationale"]
    ev.signals_fired = m["top"][0]["signals"] if m["top"] else []
    ev.match_conf = m["match_conf"]
    ev.contradictions = list(m["contradictions"])
    ev.location_zone_text = m["text_zones"][0] if m["text_zones"] else None
    if m["resolved_objects"] and not ev.object_ids:
        ev.object_ids = m["resolved_objects"]
        ev.object_id = m["resolved_objects"][0]
        prov["object_ids"] = prov["object_id"] = "DERIVED"
    top_act = kg.activities.get(m["top"][0]["activity_id"]) if m["top"] else None
    if m["material"]:
        ev.material_item_id, ev.material_issued_status = m["material"]["item"], m["material"]["status"]
        prov.update({"material_item_id": "DERIVED", "material_issued_status": "FETCHED"})
    # location conflict: text says one zone, GPS (good fix) says another
    if ev.location_zone_text and ev.geofence_result == "inside" and ev.geofence_zone_id != ev.location_zone_text:
        ev.location_conflict = True
    elif top_act and top_act.work_front and ev.geofence_result == "inside" and ev.geofence_zone_id != top_act.work_front \
            and not ev.location_zone_text and m["top"][0]["score"] >= settings["gate"]["candidate_min"]:
        ev.location_conflict = True
    if ev.location_conflict:
        ev.contradictions = ev.contradictions + ["location_conflict"]
    if ev.photo_recycled_flag:
        ev.contradictions = ev.contradictions + ["old_photo_exif"]
    prov.update({k: "DERIVED" for k in ("match_path", "candidate_set_size", "top_k_candidates", "match_margin", "signals_fired",
                                         "match_rationale", "location_conflict", "match_conf", "extraction_conf", "date_conf",
                                         "verification_conf", "state", "matched_activity_id", "activity_inference", "dedup_key")})

    # ── verification_conf (Layer 4 composite) ──
    ev.verification_conf = ev.verification_score = _verification(ev, rep, gf, top_act, reporter)

    # ── Enrichment needed for routing (weather claims) ──
    enrich_weather.enrich(session, ev, lat if lat is not None else 27.47, lon if lon is not None else 95.34, settings.get("weather_mode", "seeded_first"))
    # keep the enrichment's own tags (weather_* = FETCHED) — `prov` is written back over ev.provenance below
    prov.update({k: v for k, v in (ev.provenance or {}).items() if k.startswith("weather_")})

    # ── HSE bypass — BEFORE and REGARDLESS of confidence ──
    zone = ev.location_zone_text or ev.geofence_zone_id or (top_act.work_front if top_act else None) \
        or (reporter.work_fronts[0] if reporter and reporter.work_fronts else None)
    at = datetime.combine(ev.event_date, (rep.captured_at or clock.now()).time())
    items = hse.check(session, ev, zone, top_act, at)
    if (ev.provenance or {}).get("permit_status") == "FETCHED":
        prov["permit_status"] = "FETCHED"          # looked up in the Permit table
    if items:
        ev.state = "hse_hold"
        ev.matched_activity_id = None
        ev.route_reason = "HSE bypass: " + ", ".join(
            f"{i['kind']}" + (f" ({i.get('permit_type')} permit {i.get('permit_status')})" if i["kind"] == "permit" else f" ({i.get('hse_event_type')})")
            for i in items) + " — routed to a human regardless of confidence"
        for it in items:
            gated = hse.gated_activities(session, kg, it.get("stop_work_scope") or ("zone" if it["kind"] == "permit" else None), zone,
                                         it.get("permit_type"), top_act.activity_id if top_act else None)
            h = HSEEvent(event_id=ev.id, report_id=rep.id, created_at=clock.now().replace(microsecond=0), work_front=zone,
                         hse_event_text=ev.source_sentence, reporter_id=rep.reporter_id, gated_activities=gated,
                         info_match_activity=top_act.activity_id if top_act else None, info_match_conf=m["top"][0]["score"] if m["top"] else None,
                         hse_reported_to="N. Hazarika (HSE Officer)", **it)
            session.add(h)
            session.flush()
            audit.append(session, "pipeline", "hse.raised", f"hse:{h.id}", {"event": ev.id, "kind": h.kind, "type": h.hse_event_type,
                                                                             "permit": h.permit_status, "severity": h.hse_severity})
            bus.publish("hse", {"hse_id": h.id, "event_id": ev.id, "kind": h.kind, "severity": h.hse_severity, "text": h.hse_event_text,
                                "work_front": zone, "permit_type": h.permit_type, "permit_status": h.permit_status})
        ev.hse_event_flag = True
        prov.update({"state": "DERIVED", "route_reason": "DERIVED"})
        ev.provenance, ev.field_conf = dict(prov), dict(fc)
        audit.append(session, actor, "event.state", f"event:{ev.id}", {"state": ev.state, "reason": ev.route_reason})
        session.add(ev)
        return ev

    # ── Blockers: cause only, never a date ──
    if ev.blocker_flag:
        ev.activity_inference = "blocked"
        zones = set(filter(None, [ev.location_zone_text, ev.geofence_zone_id])) or set(fc.get("_nearby_zones") or []) \
            or set(reporter.work_fronts if reporter else [])
        affected = [a.activity_id for a in kg.activities.values() if a.work_front in zones and a.actual_finish is None
                    and (a.actual_start or a.planned_start <= today) and a.planned_start <= today + timedelta(days=3)]
        if m["top"] and m["top"][0]["score"] >= 0.6 and (ev.action or ev.object_ids):
            affected = [m["top"][0]["activity_id"]] + [a for a in affected if a != m["top"][0]["activity_id"]]
        ev.affected_activities = affected[:12]
        ev.matched_activity_id = affected[0] if (ev.action or ev.object_ids) and affected else None
        prov.update({"affected_activities": "DERIVED", "activity_inference": "DERIVED"})
        contra = []
        if ev.weather_corroborates == "false":
            contra.append("weather_not_corroborated")
        ev.contradictions = [c for c in ev.contradictions if not c.startswith("material")] + contra
        if (ev.extraction_conf or 0) < settings["gate"]["extraction"] or contra or not affected:
            ev.state = "review"
            ev.route_reason = "blocker needs a planner look: " + (", ".join(contra) if contra else
                                                                   ("no affected activity found" if not affected else "low extraction confidence"))
        else:
            ev.state = "linked"
            ev.route_reason = f"blocker recorded against {len(affected)} activit{'y' if len(affected) == 1 else 'ies'} (cause only, no date)"
        ev.proposed_write = f"Cause '{ev.cause_category or 'unspecified'}' on {', '.join(affected[:3])}{'…' if len(affected) > 3 else ''} — no date"
        ev.provenance, ev.field_conf = dict(prov), dict(fc)
        audit.append(session, actor, "event.state", f"event:{ev.id}", {"state": ev.state, "reason": ev.route_reason, "affected": affected[:12]})
        session.add(ev)
        bus.publish("event", {"event_id": ev.id, "state": ev.state})
        return ev

    # ── active stop-work: nothing inside a stopped scope is auto-synced or written, whatever the confidence ──
    credible = top_act if (top_act and m["top"][0]["score"] >= settings["gate"]["candidate_min"]) else None
    here = ev.location_zone_text or (ev.geofence_zone_id if ev.geofence_result == "inside" else None)
    stop = hse.active_stop_work(session, kg, here, credible, ev.event_date)
    if stop:
        where = {"site": "the whole site", "unit": f"unit of {stop.work_front}", "zone": stop.work_front,
                 "activity": ", ".join(stop.gated_activities or [])}.get(stop.stop_work_scope, stop.work_front)
        ev.state = "hse_hold"
        ev.matched_activity_id = None
        ev.hse_event_flag = True
        ev.route_reason = (f"HSE bypass: active stop-work (HSE #{stop.id}, scope {stop.stop_work_scope}: {where}) — "
                           f"report held for the HSE officer, no schedule write")
        h = HSEEvent(event_id=ev.id, report_id=rep.id, created_at=clock.now().replace(microsecond=0), kind="stop_work",
                     work_front=here or (credible.work_front if credible else stop.work_front), hse_event_text=ev.source_sentence,
                     reporter_id=rep.reporter_id, hse_event_type="work_in_stopped_zone", hse_severity="major",
                     gated_activities=[credible.activity_id] if credible else [],
                     info_match_activity=credible.activity_id if credible else None,
                     info_match_conf=m["top"][0]["score"] if credible else None,
                     hse_reported_to="N. Hazarika (HSE Officer)")
        session.add(h)
        session.flush()
        audit.append(session, "pipeline", "hse.raised", f"hse:{h.id}", {"event": ev.id, "kind": "stop_work", "type": h.hse_event_type,
                                                                         "stop_work_of": stop.id, "scope": stop.stop_work_scope})
        bus.publish("hse", {"hse_id": h.id, "event_id": ev.id, "kind": h.kind, "severity": h.hse_severity, "text": h.hse_event_text,
                            "work_front": h.work_front, "permit_type": None, "permit_status": None})
        prov.update({"state": "DERIVED", "route_reason": "DERIVED"})
        fc["_stop_work_of"] = stop.id
        ev.provenance, ev.field_conf = dict(prov), dict(fc)
        audit.append(session, actor, "event.state", f"event:{ev.id}", {"state": ev.state, "reason": ev.route_reason})
        session.add(ev)
        bus.publish("event", {"event_id": ev.id, "state": ev.state})
        return ev

    # ── event_type safe rule on the top candidate ──
    inference, write, why = event_type.infer(session, ev, top_act)
    ev.activity_inference = inference
    finish = inference == "completes"
    if top_act:
        d = ev.event_date.strftime("%d-%b")
        ev.proposed_write = {"actual_start": f"Actual Start = {d} for {top_act.activity_id}",
                             "actual_finish": f"Actual Finish = {d} for {top_act.activity_id}",
                             "both": f"Actual Start & Finish = {d} for {top_act.activity_id}"}.get(write, f"No date change ({why})")
    fc["_inference_why"] = why

    # ── dedup (same object+action+event type+date arriving via another channel) ──
    # The event type (start/progress/finish) is part of the identity: "hydrotest pressure hold" (progress) and a later
    # "hydrotest completed" (finish) on the same line + day are two different facts; only the second may write Actual Finish.
    key_obj = ev.object_id or ev.line_ref
    if key_obj and ev.action:
        ev.dedup_key = f"{key_obj}|{ev.action}|{ev.object_event_type or 'none'}|{ev.event_date.isoformat()}"
        dup = session.exec(select(Event).where(Event.dedup_key == ev.dedup_key, Event.id != ev.id, Event.channel != ev.channel,
                                               Event.state.in_(["linked", "review", "clarifying"]))).first()
        if dup:
            ev.state, ev.duplicate_of = "duplicate", dup.id
            ev.route_reason = f"same object+action+event type+date already reported via {dup.channel} (event {dup.id})"
            ev.field_conf, ev.provenance = dict(fc), dict(prov)
            audit.append(session, actor, "event.state", f"event:{ev.id}", {"state": "duplicate", "of": dup.id})
            session.add(ev)
            return ev

    # ── four-number gate ──
    if clarify_allowed is None:
        clarify_allowed = rep.clarification_count < settings.get("clarification_cap", 1) and rep.channel in ("pwa", "whatsapp", "telegram")
    resource_only = not ev.action and not ev.object_class and not ev.object_ids and not ev.line_ref \
        and bool(ev.manpower_total or ev.equipment_deployed)
    scores = {"extraction": ev.extraction_conf, "match": ev.match_conf, "date": ev.date_conf, "verification": ev.verification_conf}
    r = gate.route(scores, ev.match_margin, m["top"], ev.contradictions, settings, finish, clarify_allowed)
    res_zone = ev.location_zone_text or ev.geofence_zone_id or (fc.get("_nearby_zones") or [None])[0] \
        or (reporter.work_fronts[0] if reporter and len(reporter.work_fronts or []) == 1 else None)
    if resource_only and res_zone and not any(c.startswith("material") for c in ev.contradictions):
        # manpower / equipment lines are productivity denominators, not progress: attach to the work front
        r = {"state": "linked", "reason": f"resource record attached to work front {res_zone} (no date written)", "dimension": None, "failing": []}
        write, top_act = None, None
        ev.activity_inference = "advances"
        ev.affected_activities = [a.activity_id for a in kg.activities.values() if a.work_front == res_zone and a.actual_start and not a.actual_finish][:8]
        ev.location_zone_text = ev.location_zone_text or res_zone
    ev.state, ev.route_reason = r["state"], r["reason"]
    fc["_failing"] = r["failing"]

    if ev.state == "linked":
        ev.matched_activity_id = top_act.activity_id if top_act else None
        if top_act:
            apply_write(session, ev, top_act, write, "DERIVED", actor)
    elif ev.state == "clarifying":
        q = clarify.build(r["dimension"], m["top"], ev, kg)
        ev.clarification_asked = q["question"]
        ev.clarification_options = q["options"]
        ev.clarification_dimension = r["dimension"]
        ev.clarification_asked_at = clock.now().replace(microsecond=0)
        ev.clarification_count = 1
        fc["_question_hi"] = q["question_hi"]
        rep.clarification_count += 1
        session.add(rep)
        prov["clarification_asked"] = "DERIVED"
    elif ev.state == "unplanned":
        ev.unplanned_flag = True
        ev.unplanned_class = unplanned.classify(ev.source_sentence)
        ev.suggested_parent_wbs = unplanned.suggest_parent_wbs(kg, ev, reporter)
        ev.change_order_candidate = unplanned.change_order(ev.unplanned_class)
        ev.unplanned_status = "open"
        prov.update({"unplanned_flag": "DERIVED", "unplanned_class": "DERIVED", "suggested_parent_wbs": "DERIVED", "change_order_candidate": "DERIVED"})
    elif ev.state == "review":
        ev.matched_activity_id = None

    ev.field_conf, ev.provenance = dict(fc), dict(prov)     # fresh objects ⇒ JSON columns are always flagged dirty
    audit.append(session, actor, "event.state", f"event:{ev.id}", {
        "state": ev.state, "reason": ev.route_reason, "top": m["top"][0]["activity_id"] if m["top"] else None,
        "scores": {k: round(v or 0, 3) for k, v in scores.items()}, "margin": ev.match_margin, "path": ev.match_path})
    session.add(ev)
    bus.publish("event", {"event_id": ev.id, "state": ev.state, "activity": ev.matched_activity_id})
    return ev


def _verification(ev: Event, rep: Report, gf: dict, act: Activity | None, reporter: Reporter | None = None) -> float:
    """Does the evidence support the claim? Composite of presence, identity/scope and photo plausibility.

    base .50 · known reporter on own assigned work front +.20 · GPS inside +.20 / boundary +.15 / outside −.10
    · GPS zone = activity zone +.10 · photo +.15 (CV-plausible) / +.05 · old photo −.20 · material not issued −.20
    · location conflict −.15.  A contractor DPR/spreadsheet (document of record) starts at .70.
    ⇒ text-only WhatsApp from the assigned supervisor clears the START bar (.70) but not the FINISH bar (.85).
    """
    doc = rep.source_type in ("dpr_pdf", "dpr_text", "xlsx")
    v = 0.70 if doc else 0.50
    r = gf["result"]
    if not doc and act and act.work_front and reporter and act.work_front in (reporter.work_fronts or []) and r != "outside":
        v += 0.20
    v += {"inside": 0.20, "boundary": 0.15, "outside": -0.10, "unknown": 0.0}[r]
    if act and act.work_front:
        if r == "inside" and gf["zone"] == act.work_front:
            v += 0.10
        elif r == "boundary" and act.work_front in (gf["nearby"] or []):
            v += 0.10
        elif r == "inside":
            v -= 0.05
    if ev.photo_count:
        cv = ev.cv_plausibility or 0.0
        v += 0.15 if cv >= 0.6 else 0.05
    if ev.photo_recycled_flag:
        v -= 0.20
    if any(c.startswith("material_not_issued") for c in ev.contradictions or []):
        v -= 0.20
    if ev.location_conflict:
        v -= 0.15
    return round(max(0.05, min(0.99, v)), 3)


def apply_write(session: Session, ev: Event, act: Activity, write: str | None, prov_tag: str, actor: str):
    """Write actual dates back to the schedule (the deliverable) + audit."""
    if not write:
        ev.date_written = None
        return
    snapshot = act
    act = session.get(Activity, act.activity_id)      # write through the live session, not the KG snapshot
    d = ev.event_date
    changed = {}
    if write in ("actual_start", "both") and act.actual_start is None:
        act.actual_start, act.actual_start_source_event, act.actual_start_prov = d, ev.id, prov_tag
        changed["actual_start"] = d.isoformat()
    if write in ("actual_finish", "both") and act.actual_finish is None:
        if act.actual_start is None:
            act.actual_start, act.actual_start_source_event, act.actual_start_prov = d, ev.id, prov_tag
            changed["actual_start"] = d.isoformat()
        act.actual_finish, act.actual_finish_source_event, act.actual_finish_prov = d, ev.id, prov_tag
        changed["actual_finish"] = d.isoformat()
    if changed:
        ev.date_written = "+".join(changed)
        session.add(act)
        if snapshot is not act:
            snapshot.actual_start, snapshot.actual_finish = act.actual_start, act.actual_finish
        audit.append(session, actor, "schedule.write", f"activity:{act.activity_id}", {"event": ev.id, **changed, "prov": prov_tag})
        bus.publish("schedule", {"activity_id": act.activity_id, **changed, "event_id": ev.id})


# ─────────────────────────────────── replies ───────────────────────────────────

def compose_reply(session: Session, rep: Report, events: list[Event]) -> dict:
    """Plain-words bot reply for the worker (no jargon). Returned in en + hi."""
    kg = get_kg(session)
    lines_en, lines_hi, question = [], [], None
    for e in events:
        wf = None
        if e.matched_activity_id and e.matched_activity_id in kg.activities:
            a = kg.activities[e.matched_activity_id]
            wf = kg.work_fronts[a.work_front].name if a.work_front else None
        echo = clarify.plain_echo(e, wf)
        if e.state == "linked":
            if e.blocker_flag:
                lines_en.append(f"✅ Noted: {e.cause_category or 'problem'} — {e.cause_text}. Planner informed.")
                lines_hi.append(f"✅ दर्ज: {e.cause_text}. प्लानर को बता दिया।")
            else:
                lines_en.append(f"✅ Got it: {echo}. Marked in schedule.")
                lines_hi.append(f"✅ मिल गया: {echo}. शेड्यूल में दर्ज।")
        elif e.state == "clarifying":
            question = {"event_id": e.id, "question": e.clarification_asked, "question_hi": (e.field_conf or {}).get("_question_hi"),
                        "options": e.clarification_options}
            lines_en.append(f"❓ {e.clarification_asked}")
            lines_hi.append(f"❓ {(e.field_conf or {}).get('_question_hi') or e.clarification_asked}")
        elif e.state == "hse_hold":
            lines_en.append("🛑 Safety item sent to the HSE officer. Someone will call you. Do not start until cleared.")
            lines_hi.append("🛑 सेफ्टी अधिकारी को भेजा गया। कोई आपको कॉल करेगा। मंज़ूरी तक काम शुरू न करें।")
        elif e.state == "review":
            if e.blocker_flag:
                lines_en.append(f"📝 Noted: {e.cause_text}. The planner will check it.")
                lines_hi.append(f"📝 दर्ज: {e.cause_text}. प्लानर जाँच करेंगे।")
            else:
                lines_en.append(f"⏳ Got it: {echo}. The planner will confirm.")
                lines_hi.append(f"⏳ मिल गया: {echo}. प्लानर पुष्टि करेंगे।")
        elif e.state == "unplanned":
            lines_en.append(f"📌 Noted as extra work: {echo}. The planner will review.")
            lines_hi.append(f"📌 अतिरिक्त काम के रूप में दर्ज: {echo}.")
        elif e.state == "duplicate":
            lines_en.append("🔁 Already received this update — thank you.")
            lines_hi.append("🔁 यह अपडेट पहले ही मिल चुका है — धन्यवाद।")
        else:
            lines_en.append("📝 Saved. The planner will read it.")
            lines_hi.append("📝 सेव हो गया। प्लानर पढ़ेंगे।")
    return {"en": "\n".join(lines_en), "hi": "\n".join(lines_hi), "question": question}


# ────────────────────────────── clarification answer ──────────────────────────────

def answer_clarification(session: Session, event_id: int, value: str, extra_photo: str | None = None) -> dict:
    ev = session.get(Event, event_id)
    if not ev or ev.state != "clarifying":
        return {"ok": False, "error": "no open question"}
    rep = session.get(Report, ev.report_id)
    reporter = session.get(Reporter, rep.reporter_id) if rep.reporter_id else None
    settings = get_settings(session)
    now = clock.now().replace(microsecond=0)
    ev.clarification_response = value
    ev.clarification_latency_s = (now - ev.clarification_asked_at).total_seconds() if ev.clarification_asked_at else None
    prov = dict(ev.provenance or {})
    prov["clarification_response"] = "HUMAN"
    ev.provenance = prov
    audit.append(session, rep.reporter_id or "reporter", "clarification.answered", f"event:{ev.id}",
                 {"answer": value, "latency_s": ev.clarification_latency_s})
    confirmed = None
    if value.startswith("date:"):
        ev.event_date = date.fromisoformat(value[5:])
        ev.date_conf = 0.95
        prov["event_date"] = "HUMAN"
    elif value == "__yes":
        ev.extraction_conf = max(ev.extraction_conf or 0, 0.9)
    elif value == "__photo" and extra_photo:
        rep.photo_ids = list(rep.photo_ids or []) + [extra_photo]
        session.add(rep)
    elif value in ("__no", "__nophoto", "__other"):
        ev.state = "review"
        ev.route_reason = f"reporter answered '{value.strip('_')}' to the clarifying question — planner decides"
        session.add(ev)
        audit.append(session, "pipeline", "event.state", f"event:{ev.id}", {"state": "review", "reason": ev.route_reason})
        session.commit()
        return {"ok": True, "event": ev, "reply": compose_reply(session, rep, [ev])}
    else:
        confirmed = value
    process_event(session, ev, rep, reporter, settings, confirmed=confirmed, clarify_allowed=False, actor=rep.reporter_id or "reporter")
    session.commit()
    session.refresh(ev)
    return {"ok": True, "event": ev, "reply": compose_reply(session, rep, [ev])}
