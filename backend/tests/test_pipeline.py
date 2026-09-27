"""The tests the build prompt asks for: event_type safe rule, gate routing (incl. margin), HSE bypass,
alias learning effect, spreadsheet header mapping — plus audit chain and 'nothing dropped'."""
from datetime import date

from sqlmodel import select

from app import clock
from app.db import session_scope
from app.models import Activity, AuditLog, Event, HSEEvent
from app.pipeline import audit, extract_rules, gate, ingest, learning, spreadsheet
from app.seed import samples

from .conftest import NOW, RACK_B, RACK_C, TANK, WEAK, send

SETTINGS = {"gate": {"extraction": .85, "match": .85, "date": .80, "verification": .70, "verification_finish": .85, "margin": .10,
                     "borderline_band": .15, "clarify_top2_min": .70, "candidate_min": .50}}


# ───────────── extraction (rules, Hinglish, spans) ─────────────

def test_hinglish_single_event_with_spans():
    text = "Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder"
    [ev] = extract_rules.extract(text, date(2026, 9, 26))
    assert ev.action == "erect" and ev.object_event_type == "finish"
    assert ev.object_ordinals == [3, 4] and ev.location_text == "Rack B"
    assert ev.manpower_by_trade == {"fitter": 12, "welder": 8}
    for f, (a, b) in ev.spans.items():                   # every span points at real text
        assert 0 <= a < b <= len(text), f


def test_multi_event_split():
    evs = extract_rules.extract("Spool 3 erected and welding started on spool 4. Excavation F-12 stopped due to rain, 4 hrs lost.", date(2026, 9, 26))
    assert [e.action for e in evs] == ["erect", "weld", "excavate"]
    assert evs[2].blocker_flag and evs[2].cause_category == "weather" and evs[2].time_lost_h == 4


# ───────────── event_type safe rule ─────────────

def test_first_event_writes_actual_start_not_finish(site):
    [e] = send("Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder")
    assert e.state == "linked" and e.matched_activity_id == "PIP-3-2340"
    assert e.object_event_type == "finish" and e.activity_inference == "starts"       # object finished ≠ activity finished
    with session_scope() as s:
        a = s.get(Activity, "PIP-3-2340")
        assert a.actual_start == date(2026, 9, 26) and a.actual_finish is None and a.actual_start_source_event == e.id


def test_second_event_advances_nothing(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("Rack B pe spool 2 erect ho gaya")
    assert e.state == "linked" and e.activity_inference == "advances" and e.date_written is None


def test_scope_coverage_writes_finish_with_photo(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("Rack B pe spool 1 aur 2 erect ho gaye", photos=["spool_erection_rackB.jpg"])
    assert e.activity_inference == "completes" and e.state == "linked"
    with session_scope() as s:
        assert s.get(Activity, "PIP-3-2340").actual_finish == date(2026, 9, 26)


def test_blocker_writes_cause_only(site):
    [e] = send("Crane CR-50T-02 breakdown, Rack B spool erection could not start")
    assert e.blocker_flag and e.activity_inference == "blocked" and e.cause_category == "equipment"
    with session_scope() as s:
        assert s.get(Activity, "PIP-3-2340").actual_start is None


def test_finish_needs_stricter_evidence(site):
    [e] = send("Line 24 hydrotest completed", gps=TANK)                    # no photo
    assert e.activity_inference == "completes" and e.state == "clarifying" and e.clarification_dimension == "verification"
    [e2] = send("Line 24 hydrotest completed", gps=TANK, photos=["hydrotest_line24_gauge.jpg"])
    assert e2.state == "linked" and e2.date_written == "actual_finish"


# ───────────── gate routing ─────────────

def test_gate_never_averages():
    top = [{"score": .99}, {"score": .5}]
    r = gate.route({"extraction": .99, "match": .99, "date": .99, "verification": .40}, .49, top, [], SETTINGS, False, True)
    assert r["state"] == "review"                    # mean would be .84 — but one low dimension blocks auto-sync


def test_gate_margin_case_asks_one_question(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("spool erected near rack", gps=WEAK)
    assert e.state == "clarifying" and e.match_margin < .10
    assert e.clarification_asked == "Rack B or Rack C?"
    with clock.frozen(NOW), session_scope() as s:
        r = ingest.answer_clarification(s, e.id, "PIP-3-2340")
        assert r["event"].state == "linked" and r["event"].matched_activity_id == "PIP-3-2340"


def test_gate_unplanned(site):
    [e] = send("Laid temporary drainage near U3 gate", reporter="R-GOGOI", gps=None)
    assert e.state == "unplanned" and e.unplanned_class == "site_prep" and e.suggested_parent_wbs.startswith("RFX.U3")


def test_clarification_cap_is_one(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("spool erected near rack", gps=WEAK)
    with session_scope() as s:
        from app.models import Report
        rep = s.get(Report, e.report_id)
        assert rep.clarification_count == 1
        from app.db import get_settings
        from app.models import Reporter
        ev = s.get(Event, e.id)
        ingest.process_event(s, ev, rep, s.get(Reporter, "R-KALITA"), get_settings(s))   # re-run: cap reached → review, no 2nd question
        assert ev.state == "review" and "cap" in ev.route_reason and rep.clarification_count == 1


# ───────────── HSE bypass ─────────────

def test_hse_permit_missing_holds_even_with_high_match(site):
    [e] = send("Welding started Rack C", gps=RACK_C)
    assert e.state == "hse_hold" and e.matched_activity_id is None
    with session_scope() as s:
        [h] = s.exec(select(HSEEvent).where(HSEEvent.event_id == e.id)).all()
        assert h.kind == "permit" and h.permit_type == "hot_work" and h.permit_status == "missing"
        assert h.info_match_activity == "PIP-3-2351" and h.info_match_conf > 0.85          # would have matched — still held
        assert s.get(Activity, "PIP-3-2351").actual_start is None


def test_hse_incident_is_verbatim_and_never_synced(site):
    text = "Near miss, sling slipped at crane CR-50T-02"
    [e] = send(text)
    assert e.state == "hse_hold"
    with session_scope() as s:
        [h] = s.exec(select(HSEEvent).where(HSEEvent.event_id == e.id)).all()
        assert h.hse_event_type == "near_miss" and h.hse_event_text == text


# ───────────── contradictions + learning loop ─────────────

def test_alias_learning_makes_same_phrase_autosync(site):
    [e] = send("Spool 5 erected")
    assert e.state == "review"
    assert any(c.startswith("material_not_issued") for c in e.contradictions) and "location_conflict" in e.contradictions
    with clock.frozen(NOW), session_scope() as s:
        r = learning.review(s, e.id, "reassign", "PIP-3-2342", "terminology", "R-IYER", 18)
        assert r["alias_learned"] == "'spool 5' → SPL-16-1207-05"
    [e2] = send("Spool 5 erected")
    assert e2.state == "linked" and e2.matched_activity_id == "PIP-3-2342" and "alias" in e2.signals_fired


def test_generic_words_are_never_learned(site):
    assert learning._is_generic("kaam chal") and learning._is_generic("unit 2") and learning._is_generic("f-12")
    assert not learning._is_generic("spool 5") and not learning._is_generic("north rack")


def test_weather_claim_on_dry_day_not_corroborated(site):
    [e] = send("Work stopped due to rain from 2pm")
    assert e.blocker_flag and e.weather_corroborates == "false" and e.state == "review"
    [e2] = send("Heavy rain from 2 pm, Rack B work stopped", at=NOW.replace(day=13))
    assert e2.weather_corroborates == "true" and e2.weather_severity == "extreme"


def test_missing_gps_never_rejects(site):
    [e] = send("Rack B pe spool 3 aur 4 erect ho gaye", gps=None)
    assert e.state in ("linked", "review", "clarifying") and e.geofence_result == "unknown"


def test_nothing_silently_dropped(site):
    [e] = send("ok sir 👍")
    assert e.state == "unparseable" and e.source_sentence


# ───────────── spreadsheet header mapping ─────────────

def test_spreadsheet_fuzzy_header_mapping(tmp_path):
    samples._xlsx()
    from app import config
    parsed = spreadsheet.read(config.SAMPLE_DIR / "dpr_25sep_messy_headers.xlsx", date(2026, 9, 26))
    fields = {m["header"]: m["field"] for m in parsed["mapping"].values()}
    assert fields["Desc of Work"] == "description" and fields["Qty Done"] == "quantity" and fields["Nos"] == "uom"
    assert fields["Manpwr"] == "manpower" and parsed["header_row"] == 4
    assert len(parsed["events"]) == 12 and parsed["reporting_date"] == date(2026, 9, 25)
    ev = parsed["events"][0]
    a, b = ev.spans["quantity"]
    assert parsed["raw_text"][a:b] == "180"


# ───────────── audit chain ─────────────

def test_audit_chain_verifies_and_detects_tampering(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    with session_scope() as s:
        assert audit.verify_chain(s)["ok"]
        row = s.exec(select(AuditLog).order_by(AuditLog.id)).first()
        row.payload_json = '{"tampered": true}'
        s.add(row)
        s.commit()
        v = audit.verify_chain(s)
        assert not v["ok"] and v["broken_at"] == row.id
