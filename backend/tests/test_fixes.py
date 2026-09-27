"""Regression tests for the issues found in the post-build audit (see docs/decisions/0010-audit-fixes.md)."""
import hashlib
import sqlite3
from datetime import date

from sqlmodel import select

from app import clock, db
from app.api import analytics
from app.api.hse import HSEAction, act as hse_act
from app.db import session_scope
from app.models import Activity, Alias, Event, HSEEvent, Report
from app.pipeline import ask, extract_rules, ingest, learning

from .conftest import NOW, RACK_B, RACK_C, TANK, WEAK, send

GAUGE = ["hydrotest_line24_gauge.jpg"]


def _hse_for(event_id):
    with session_scope() as s:
        return s.exec(select(HSEEvent).where(HSEEvent.event_id == event_id)).all()


def _set_scope(hse_id, scope):
    with clock.frozen(NOW), session_scope() as s:
        hse_act(hse_id, HSEAction(action="scope", stop_work_scope=scope), s)


# ───────────── 1. stop-work enforcement ─────────────

def test_active_stop_work_blocks_schedule_write_in_zone(site):
    [near] = send("Near miss, sling slipped at crane CR-50T-02", gps=RACK_B)
    [h] = _hse_for(near.id)
    _set_scope(h.id, "zone")                                        # HSE officer stops Rack B
    [e] = send("Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder", gps=RACK_B)
    assert e.state == "hse_hold" and e.matched_activity_id is None and e.date_written is None
    assert f"HSE #{h.id}" in e.route_reason and "stop-work" in e.route_reason
    with session_scope() as s:
        assert s.get(Activity, "PIP-3-2340").actual_start is None    # nothing written inside the stopped zone
    [held] = _hse_for(e.id)
    assert held.kind == "stop_work" and held.info_match_activity == "PIP-3-2340" and held.hse_event_text == e.source_sentence


def test_stop_work_does_not_block_other_zones_and_lifts_on_close(site):
    [near] = send("Near miss, sling slipped at crane CR-50T-02", gps=RACK_B)
    [h] = _hse_for(near.id)
    _set_scope(h.id, "zone")
    [e] = send("Line 24 hydrotest completed", gps=TANK, photos=GAUGE)       # Tank Farm — outside the Rack B stop
    assert e.state == "linked" and e.date_written == "actual_finish"
    with clock.frozen(NOW), session_scope() as s:
        hse_act(h.id, HSEAction(action="close", note="cleared after toolbox talk"), s)
    [e2] = send("Rack B pe spool 3 aur 4 erect ho gaye", gps=RACK_B)        # stop closed → normal again
    assert e2.state == "linked" and e2.matched_activity_id == "PIP-3-2340"


def test_unit_and_site_scope(site):
    [near] = send("Near miss, sling slipped at crane CR-50T-02", gps=RACK_B)
    [h] = _hse_for(near.id)
    _set_scope(h.id, "unit")                                        # Unit 3 → Tank Farm (Unit 3) is covered too
    [e] = send("Line 24 hydrotest completed", gps=TANK, photos=GAUGE)
    assert e.state == "hse_hold" and e.date_written is None
    with session_scope() as s:
        assert s.get(Activity, "PIP-3-2401").actual_finish is None


def test_stop_without_scope_is_not_enforced(site):
    """A near-miss alone (no blast radius set yet) must not freeze the site."""
    send("Near miss, sling slipped at crane CR-50T-02", gps=RACK_B)
    [e] = send("Rack B pe spool 3 aur 4 erect ho gaye", gps=RACK_B)
    assert e.state == "linked"


# ───────────── 3 + 10. field_conf persistence (Hindi question, why, failing) ─────────────

def test_clarification_fields_survive_persistence(site):
    send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("spool erected near rack", gps=WEAK)
    assert e.state == "clarifying"
    with session_scope() as s:                                       # fresh session → values come from the DB
        ev = s.get(Event, e.id)
        fc = ev.field_conf
        assert fc.get("_question_hi") and fc["_question_hi"] != ev.clarification_asked
        assert fc.get("_inference_why")
        assert "_failing" in fc and isinstance(fc["_failing"], list)
        reply = ingest.compose_reply(s, s.get(Report, ev.report_id), [ev])
        assert reply["question"]["question_hi"] == fc["_question_hi"]
        assert fc["_question_hi"] in reply["hi"] and ev.clarification_asked in reply["en"]


def test_review_explanation_and_failing_dimensions_persist(site):
    [e] = send("Spool 5 erected")
    assert e.state == "review"
    with session_scope() as s:
        fc = s.get(Event, e.id).field_conf
        assert fc.get("_inference_why")
        assert "verification" in fc["_failing"]                     # material not issued + location conflict pull verification down


# ───────────── 4. weather provenance ─────────────

def test_weather_enrichment_is_stored_as_fetched(site):
    [e] = send("Heavy rain from 2 pm, Rack B work stopped", at=NOW.replace(day=13))
    with session_scope() as s:
        ev = s.get(Event, e.id)
        assert ev.weather_fetched and ev.weather_fetched["rain_mm"] == 42.0
        assert ev.provenance["weather_fetched"] == "FETCHED" and ev.provenance["weather_source"] == "FETCHED"
        assert ev.provenance["weather_corroborates"] == "DERIVED"
        assert ev.provenance.get("weather_reported") in ("EXTRACTED", None)   # the claim is not relabelled


# ───────────── 5. dedup ─────────────

def test_progress_then_finish_is_not_a_duplicate(site):
    [p] = send("Line 24 hydrotest pressure hold chal raha hai, 2 ghante", channel="whatsapp", gps=TANK)
    assert p.state in ("linked", "review", "clarifying") and p.object_event_type == "progress"
    [f] = send("Line 24 hydrotest completed", gps=TANK, photos=GAUGE, channel="pwa")
    assert p.dedup_key.split("|")[:2] == f.dedup_key.split("|")[:2]    # same object+action — the old key collided
    assert f.state == "linked" and f.duplicate_of is None and f.date_written == "actual_finish"
    with session_scope() as s:
        assert s.get(Activity, "PIP-3-2401").actual_finish == date(2026, 9, 26)


def test_exact_duplicate_on_another_channel_still_deduplicated(site):
    [a] = send("Line 24 hydrotest completed", gps=TANK, photos=GAUGE, channel="pwa")
    [b] = send("Line 24 hydrotest completed", gps=TANK, photos=GAUGE, channel="whatsapp")
    assert a.state == "linked" and b.state == "duplicate" and b.duplicate_of == a.id


# ───────────── 6. Ask filtering ─────────────

def test_ask_counts_respect_decision_state_and_unit(site):
    good = send("Heavy rain from 2 pm, Rack B work stopped", gps=RACK_B, at=NOW.replace(day=13))[0]      # Unit 3, GPS-evidenced
    rej = send("Work stopped due to rain from 2pm", gps=RACK_B)[0]                                        # planner will reject
    basin = send("Baarish 3 baje se, basin wall shuttering ruk gaya", reporter="R-GOGOI", gps=None, at=NOW.replace(day=21))[0]
    with clock.frozen(NOW), session_scope() as s:
        learning.review(s, rej.id, "reject", None, None, "R-IYER", 5)
        ev = s.get(Event, basin.id)                    # the seed's misattribution: Unit 2 basin guessed onto a Unit 3 footing
        ev.matched_activity_id, ev.geofence_result, ev.geofence_zone_id, ev.location_zone_text = "CIV-3-1132", "unknown", None, None
        s.add(ev)
        s.commit()
    with session_scope() as s:
        r = ask.answer(s, "How many rain delays in Unit 3 in September?")
        ids = [c["event_id"] for c in r["citations"]]
        assert good.id in ids                                                   # correct-unit rain event included
        assert rej.id not in ids                                                # planner-rejected excluded
        assert basin.id not in ids and basin.id in r["excluded_unplaced"]       # unit not evidenced → not counted
        assert r["answer"].startswith(f"{len(ids)} rain delay")
        assert "sql" not in r and "Python" in r["filters"]                      # no pretend SQL
        for c in r["citations"]:                                                # citations point at real events
            e = s.get(Event, c["event_id"])
            assert e is not None and c["text"] == (e.cause_text or e.source_sentence)
        hist = ask.answer(s, "How many rain delays in Unit 3 in September including rejected?")
        assert rej.id in [c["event_id"] for c in hist["citations"]]


def test_ask_excludes_event_evidenced_in_other_unit(site):
    [u2] = send("Heavy rain from 2 pm, Rack B work stopped", gps=RACK_B, at=NOW.replace(day=13))
    with session_scope() as s:                                 # evidence (GPS) puts it in Unit 2, match says Unit 3
        ev = s.get(Event, u2.id)
        ev.geofence_result, ev.geofence_zone_id, ev.location_zone_text = "inside", "WF-U2-CT", None
        s.add(ev)
        s.commit()
        r = ask.answer(s, "How many rain delays in Unit 3 in September?")
        assert u2.id not in [c["event_id"] for c in r["citations"]]
        r2 = ask.answer(s, "How many rain delays in Unit 2 in September?")
        assert u2.id in [c["event_id"] for c in r2["citations"]]


# ───────────── 7. auto-sync KPI ─────────────

def test_clarification_resolved_is_not_auto_sync(site):
    [auto] = send("Rack B pe spool 3 aur 4 erect ho gaye")
    [e] = send("spool erected near rack", gps=WEAK)
    with clock.frozen(NOW), session_scope() as s:
        r = ingest.answer_clarification(s, e.id, "PIP-3-2340")
        assert r["event"].state == "linked"
    with clock.frozen(NOW), session_scope() as s:
        a, q = s.get(Event, auto.id), s.get(Event, e.id)
        assert analytics.outcome_of(a) == "AUTO_SYNC" and analytics.is_auto(a)
        assert analytics.outcome_of(q) == "QUESTION_RESOLVED" and not analytics.is_auto(q)
        k = analytics.overview(area="WF-U3-RACK-B", discipline=None, s=s)["kpis"]
        assert k["auto_sync_pct"] == 50.0                              # 1 of 2 — the answered one is human-confirmed


# ───────────── 8. seed determinism ─────────────

def _fingerprint():
    path = db.engine.url.database
    c = sqlite3.connect(path)
    rows = c.execute("select id, state, matched_activity_id, dedup_key, route_reason from event order by id").fetchall()
    acts = c.execute("select activity_id, actual_start, actual_finish from activity order by 1").fetchall()
    als = c.execute("select term, target_node, scope_zone from alias order by 1").fetchall()
    c.close()
    return len(rows), als, hashlib.sha256(repr((rows, acts)).encode()).hexdigest()


def test_seed_is_deterministic_across_resets_in_one_process():
    from app.seed import run
    run.reset(verbose=False)
    first = _fingerprint()
    run.reset(verbose=False)                                           # second reset in the same process (Settings → Reset)
    assert _fingerprint() == first
    with session_scope() as s:                                         # planted demo facts still hold
        for aid in ("PIP-3-2340", "PIP-3-2341", "PIP-3-2342", "PIP-3-2351"):
            assert s.get(Activity, aid).actual_start is None
        assert s.get(Activity, "PIP-3-2401").actual_start == date(2026, 9, 24) and s.get(Activity, "PIP-3-2401").actual_finish is None
        assert s.get(Activity, "PIP-3-2345").actual_finish == date(2026, 9, 12)
        assert s.exec(select(Alias)).first() is not None


# ───────────── 9. matching edge case: "Motor cabling" ─────────────

def test_cabling_reads_as_cable_pulling():
    [x] = extract_rules.extract("Motor cabling P-101A/B", date(2026, 9, 26))
    assert x.action == "pull" and x.object_class == "cable"
