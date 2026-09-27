"""LLM extraction with Claude (structured JSON output) — optional; rules are the fallback.

Design choice: LLMs are unreliable at character offsets, so the model returns a
*verbatim quote* for every field it fills. We locate each quote in the input to get
the span. A quote that is not found in the text is a hallucinated span: that field is
nulled and extraction_conf is lowered (spec §4.1). Output is validated with Pydantic
(ExtractedEvent). Any API error, refusal, timeout or missing key → rule extractor.
"""
import json
import re
from datetime import date

from .. import config
from .schema import ExtractedEvent

FIELDS_STR = ["action", "object_event_type", "object_class", "object_qualifier", "line_ref", "drawing_no", "location_text", "uom",
              "cause_category", "cause_subcategory", "hse_event_type", "hse_severity", "permit_status", "permit_type", "shift",
              "weather_reported", "mishap_category"]
FIELDS_NUM = ["quantity", "time_lost_h", "manpower_total"]
FIELDS_BOOL = ["blocker_flag", "hse_event_flag", "stop_work_flag", "mishap_flag", "activity_level_finish", "equipment_breakdown"]

_field = {"type": "object", "properties": {"value": {"type": ["string", "null"]}, "quote": {"type": ["string", "null"]}},
          "required": ["value", "quote"], "additionalProperties": False}
_numf = {"type": "object", "properties": {"value": {"type": ["number", "null"]}, "quote": {"type": ["string", "null"]}},
         "required": ["value", "quote"], "additionalProperties": False}
_boolf = {"type": "object", "properties": {"value": {"type": "boolean"}, "quote": {"type": ["string", "null"]}},
          "required": ["value", "quote"], "additionalProperties": False}
EVENT_SCHEMA = {
    "type": "object",
    "properties": {
        "sentence_quote": {"type": "string"},
        **{f: _field for f in FIELDS_STR}, **{f: _numf for f in FIELDS_NUM}, **{f: _boolf for f in FIELDS_BOOL},
        "object_ordinals": {"type": "array", "items": {"type": "integer"}},
        "object_refs": {"type": "array", "items": {"type": "string"}},
        "manpower_by_trade": {"type": "array", "items": {"type": "object", "properties": {"trade": {"type": "string"}, "count": {"type": "integer"}},
                                                         "required": ["trade", "count"], "additionalProperties": False}},
        "equipment_deployed": {"type": "array", "items": {"type": "string"}},
        "event_date": {"type": ["string", "null"]},
        "date_quote": {"type": ["string", "null"]},
        "extraction_conf": {"type": "number"},
    },
    "required": ["sentence_quote", *FIELDS_STR, *FIELDS_NUM, *FIELDS_BOOL, "object_ordinals", "object_refs", "manpower_by_trade",
                 "equipment_deployed", "event_date", "date_quote", "extraction_conf"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object", "properties": {"input_language": {"type": "string"}, "events": {"type": "array", "items": EVENT_SCHEMA}},
          "required": ["input_language", "events"], "additionalProperties": False}

SYSTEM = """You extract construction field events from site supervisors' messages on an EPC refinery project (Assam).
Messages may be English, Hindi (romanised) or Hinglish, e.g. "Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter the".

Return one object per distinct field EVENT (one message can hold several; resources like manpower attach to the event in the same clause).
For EVERY field you fill, `quote` must be an exact, verbatim substring of the message that supports it. If no substring supports it, value=null and quote=null. Never paraphrase quotes. `sentence_quote` is the verbatim clause the event came from.

Vocabularies:
- action: erect, weld, fit_up, fabricate, pour, excavate, pull, lay, test, install, paint, insulate, backfill, shutter, rebar, grout, align, terminate, calibrate, torque, flush, cut, grind
- object_event_type: start | finish | progress | none   (what the text literally says; "erected"/"ho gaye" = finish; blockers = none)
- activity_level_finish: true only if completion is unambiguous for the whole activity (e.g. "hydrotest completed", "all spools erected")
- object_class: spool, line, joint, foundation, cable, tray, loop, pump, compressor, steel, support, drainage, ...
- line_ref: full line number like 24-P-1203, or just the size if only "line 24" is said
- object_refs: explicit ids only (SPL-24-1203-03, F-12 → FDN-F-12, tray T-4 → TRAY-T-4, loop L-303 → LOOP-L-303, P-101B, CR-50T-02)
- cause_category: weather, material, permit_hse, manpower, equipment, drawing_rev, rework, client_hold, access, power
- hse_event_type: near_miss, first_aid, lti, property_damage, spill, fire, gas_release, unsafe_act, unsafe_condition; hse_severity: observation, minor, major, critical
- permit_status only if the text states it: valid, expired, pending, missing, revoked
- event_date: ISO date. Resolve "today/aaj", "yesterday/kal" against the reporting date given below. null if not stated.
- extraction_conf: your confidence 0..1 that this event was read correctly.
Do not invent activity ids, percentages or costs."""


def _find(text: str, quote: str | None, lo: int = 0):
    if not quote:
        return None
    i = text.find(quote, lo)
    if i < 0:
        i = text.lower().find(quote.lower(), lo)
    if i < 0:
        i = text.lower().find(quote.lower())
    return (i, i + len(quote)) if i >= 0 else None


def extract(text: str, reporting_date: date) -> list[ExtractedEvent] | None:
    """→ events, or None if the LLM is unavailable (caller falls back to rules)."""
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=25.0, max_retries=1)
        resp = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=8000,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"Reporting date: {reporting_date.isoformat()}\n\nMessage:\n{text}"}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        if resp.stop_reason == "refusal":
            return None
        raw = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(raw)
    except Exception:
        return None
    return _to_events(text, reporting_date, data)


def _to_events(text: str, rdate: date, data: dict) -> list[ExtractedEvent]:
    out, cursor = [], 0
    lang = data.get("input_language") or "en"
    for e in data.get("events", []):
        sspan = _find(text, e.get("sentence_quote"), cursor) or (0, len(text))
        cursor = sspan[0]
        ev = ExtractedEvent(sentence=text[sspan[0]:sspan[1]], sentence_span=sspan, input_language=lang, extractor="llm")
        penalty = 0.0
        for f in FIELDS_STR + FIELDS_NUM + FIELDS_BOOL:
            item = e.get(f) or {}
            val = item.get("value")
            if val in (None, False, ""):
                continue
            span = _find(text, item.get("quote"))
            if span is None:                  # hallucinated span → drop the field
                penalty += 0.08
                continue
            try:
                setattr(ev, f, val)
            except Exception:
                continue
            ev.spans[f] = span
        ev.object_ordinals = [int(x) for x in e.get("object_ordinals") or []]
        ev.object_refs = [r.upper() for r in e.get("object_refs") or [] if _find(text, r.split("-")[-1])]
        mp = {m["trade"].lower().rstrip("s"): int(m["count"]) for m in e.get("manpower_by_trade") or []}
        ev.manpower_by_trade = mp
        if mp and not ev.manpower_total:
            ev.manpower_total = sum(mp.values())
        ev.equipment_deployed = e.get("equipment_deployed") or []
        ev.event_date, ev.date_conf = rdate, 0.85
        if e.get("event_date"):
            try:
                d = date.fromisoformat(e["event_date"])
                span = _find(text, e.get("date_quote"))
                if span:
                    ev.event_date, ev.date_conf, ev.date_explicit = d, 0.92, True
                    ev.spans["event_date"] = span
            except ValueError:
                pass
        if ev.blocker_flag:
            ev.cause_text = ev.sentence
            ev.spans["cause_text"] = sspan
            ev.object_event_type = "none"
        ev.extraction_conf = round(max(0.3, min(0.97, float(e.get("extraction_conf") or 0.8)) - penalty), 3)
        out.append(ev)
    return out
