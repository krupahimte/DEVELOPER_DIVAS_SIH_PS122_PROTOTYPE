"""SQLModel tables — a direct transcription of extraction-schema-v2.

Conventions
-----------
* The atom is the field **Event**; a **Report** is only the envelope (0..N events).
* Provenance is stored per field in a JSON column ``provenance = {field: TAG}`` where
  TAG ∈ GIVEN | EXTRACTED | FETCHED | DERIVED | HUMAN. The UI renders it as chips.
* Every EXTRACTED field has a span in ``spans = {field: [start, end]}`` pointing into
  ``source_sentence``'s parent text (``Report.raw_text``), plus ``span_offset`` so spans
  can be rendered against the sentence too.
* Lists / dicts use JSON columns. Always *re-assign* them (not mutate) so SQLAlchemy
  notices the change.
"""
from datetime import date
from typing import Any, Optional

from sqlalchemy import JSON, Column
from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

# All timestamps are project-local (IST) wall-clock time → stored naive.
datetime = NaiveDatetime


def J(default_factory=dict):
    return Field(default_factory=default_factory, sa_column=Column(JSON))


# ───────────────────────────── master data / KG entities ──────────────────────────────

class Reporter(SQLModel, table=True):
    id: str = Field(primary_key=True)                 # e.g. R-KALITA
    name: str
    name_hi: str = ""
    role: str                                         # supervisor | foreman | planner | hse | pm
    discipline: Optional[str] = None
    contractor: Optional[str] = None
    work_fronts: list = J(list)                       # reporter → work_front edges (GIVEN)
    language: str = "en"
    phone: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class WorkFront(SQLModel, table=True):
    id: str = Field(primary_key=True)                 # WF-U3-RACK-B
    name: str                                         # "Rack B"
    unit: str                                         # "Unit 3"
    area: str                                         # "Pipe Racks"
    polygon: list = J(list)                           # [[lon, lat], ...] GeoJSON ring
    centroid_lat: float = 0
    centroid_lon: float = 0
    aliases: list = J(list)                           # seeded names ("rack b", "north rack"...)


class Line(SQLModel, table=True):
    """Piping line / system object with its drawing (object→drawing, object→system edges)."""
    line_no: str = Field(primary_key=True)            # 24-P-1203
    drawing_no: str                                   # ISO-4417
    system: str                                       # Cooling Water
    unit: str


class ObjectItem(SQLModel, table=True):
    """A countable scope object (spool, foundation, cable, loop...)."""
    object_id: str = Field(primary_key=True)          # SPL-24-1203-03
    object_class: str                                 # spool
    parent: Optional[str] = None                      # line_no / tray / structure
    ordinal: Optional[int] = None                     # 3
    work_front: Optional[str] = None
    label: str = ""


class Contractor(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    scope_package: str                                # contractor → scope_package edge
    disciplines: list = J(list)


class Activity(SQLModel, table=True):
    """Parsed from the XER-like CSV. The match target — never an event source."""
    activity_id: str = Field(primary_key=True)
    wbs: str
    name: str
    discipline: str
    unit: str
    area: str
    work_front: Optional[str] = None
    action: Optional[str] = None                      # canonical verb derived from name
    object_class: Optional[str] = None
    line_no: Optional[str] = None
    planned_start: date
    planned_finish: date
    actual_start: Optional[date] = None
    actual_finish: Optional[date] = None
    actual_start_source_event: Optional[int] = None
    actual_finish_source_event: Optional[int] = None
    actual_start_prov: Optional[str] = None
    actual_finish_prov: Optional[str] = None
    predecessors: list = J(list)
    scope_objects: list = J(list)
    permit_type_required: Optional[str] = None
    contractor: Optional[str] = None
    scope_package: Optional[str] = None


class Permit(SQLModel, table=True):
    permit_id: str = Field(primary_key=True)
    permit_type: str                                  # hot_work | confined_space | height | excavation | electrical_isolation | radiography
    work_front: str
    valid_from: datetime
    valid_to: datetime
    status: str = "valid"                             # valid | expired | pending | revoked
    gas_test_done: bool = False
    issued_to: Optional[str] = None


class MaterialIssue(SQLModel, table=True):
    item_id: str = Field(primary_key=True)            # SPL-24-1203-05
    description: str
    status: str                                       # issued | not_issued
    issued_at: Optional[datetime] = None
    work_front: Optional[str] = None


class Equipment(SQLModel, table=True):
    equipment_id: str = Field(primary_key=True)       # CR-50T-02
    type: str                                         # crane_50T
    work_front: Optional[str] = None
    status: str = "working"                           # working | idle | breakdown


class WeatherObs(SQLModel, table=True):
    """Seeded site-station weather (fallback when Open-Meteo is unreachable)."""
    day: date = Field(primary_key=True)
    rain_mm: float
    temp_max: float
    wind_kmph: float
    hourly_rain: list = J(list)                       # 24 values, mm/h
    source: str = "site_station_seed"


# ─────────────────────────────── envelope + event ───────────────────────────────────

class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_type: str                                  # chat | voice | whatsapp | telegram | dpr_pdf | dpr_text | xlsx | photo | hse_form
    source_doc_id: Optional[str] = None
    channel: str                                      # pwa | whatsapp | telegram | dpr_upload | spreadsheet
    reporting_date: date
    reporter_id: Optional[str] = None
    contractor: Optional[str] = None
    discipline: Optional[str] = None
    area_unit: Optional[str] = None
    device_id: Optional[str] = None
    app_version: Optional[str] = None
    input_language: Optional[str] = None              # en | hi | hi-en
    captured_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    sync_lag_s: Optional[float] = None                # DERIVED
    offline_flag: bool = False                        # DERIVED
    raw_text: str = ""                                # verbatim (GIVEN)
    transcript_raw: Optional[str] = None              # pre-normalisation ASR output (GIVEN)
    raw_file: Optional[str] = None                    # stored original bytes path
    audio_id: Optional[str] = None
    photo_ids: list = J(list)
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    gps_timestamp: Optional[datetime] = None
    clarification_count: int = 0
    extractor: str = "rules"                          # rules | llm | spreadsheet
    event_count: int = 0
    provenance: dict = J(dict)


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: int = Field(foreign_key="report.id", index=True)
    seq: int = 0                                      # position within the report
    created_at: Optional[datetime] = None
    reporter_id: Optional[str] = None
    channel: Optional[str] = None
    discipline: Optional[str] = None

    # Layer 2 — core
    action: Optional[str] = None
    object_event_type: Optional[str] = None           # start | finish | progress | none
    activity_inference: Optional[str] = None          # starts | completes | advances | blocked | unknown
    object_class: Optional[str] = None
    object_id: Optional[str] = None                   # primary resolved object (join key)
    object_ids: list = J(list)                        # all resolved objects
    object_qualifier: Optional[str] = None            # "spool 3 and 4"
    object_ordinals: list = J(list)
    line_ref: Optional[str] = None                    # "24-P-1203" or partial "24"
    drawing_no: Optional[str] = None
    location_text: Optional[str] = None
    location_zone_text: Optional[str] = None          # work front resolved from text
    quantity: Optional[float] = None
    uom: Optional[str] = None
    event_date: Optional[date] = None
    source_sentence: str = ""
    source_span: list = J(list)                       # [start, end] of the sentence in Report.raw_text
    spans: dict = J(dict)                             # field → [start, end] in Report.raw_text
    document_section: Optional[str] = None
    input_language: Optional[str] = None

    # Layer 3 — location
    geofence_result: Optional[str] = None             # inside | boundary | outside | unknown
    geofence_zone_id: Optional[str] = None
    location_conflict: bool = False
    exif_gps: list = J(list)
    exif_timestamp: Optional[datetime] = None
    photo_recycled_flag: bool = False

    # Layer 4 — evidence
    photo_ids: list = J(list)
    photo_count: int = 0
    cv_objects_detected: list = J(list)
    cv_plausibility: Optional[float] = None
    cv_model_version: Optional[str] = None
    evidence_completeness: Optional[str] = None       # none | partial | full
    verification_score: Optional[float] = None

    # Layer 6 — blocker
    blocker_flag: bool = False
    cause_category: Optional[str] = None
    cause_subcategory: Optional[str] = None
    cause_text: Optional[str] = None                  # verbatim
    time_lost_h: Optional[float] = None
    blocker_resolved_at: Optional[datetime] = None
    affected_activities: list = J(list)

    # Layer 7 — HSE flags on the event (details live in HSEEvent)
    hse_event_flag: bool = False
    stop_work_flag: bool = False
    mishap_flag: bool = False
    permit_status: Optional[str] = None

    # Layer 8 — resources
    manpower_total: Optional[int] = None
    manpower_by_trade: dict = J(dict)
    manhours: Optional[float] = None
    shift: Optional[str] = None
    equipment_deployed: list = J(list)
    equipment_idle_flag: bool = False
    equipment_breakdown: bool = False
    material_consumed: dict = J(dict)
    material_shortage_flag: bool = False
    material_item_id: Optional[str] = None
    material_issued_status: Optional[str] = None      # issued | not_issued | unknown

    # Layer 9 — weather
    weather_reported: Optional[str] = None
    weather_fetched: dict = J(dict)
    weather_source: Optional[str] = None
    weather_window: Optional[str] = None
    weather_corroborates: Optional[str] = None        # true | false | unavailable
    weather_severity: Optional[str] = None            # normal | adverse | extreme

    # Layer 10 — derived
    matched_activity_id: Optional[str] = None
    state: str = "unparseable"                        # linked | review | unplanned | duplicate | unparseable | clarifying | hse_hold
    route_reason: Optional[str] = None
    dedup_key: Optional[str] = None
    duplicate_of: Optional[int] = None
    prev_hash: Optional[str] = None
    candidate_set_size: int = 0
    match_path: Optional[str] = None                  # kg_narrowed | vector_only | fuzzy_fallback
    top_k_candidates: list = J(list)                  # [{activity_id, name, score, signals, kg_path, ...}]
    match_margin: Optional[float] = None
    signals_fired: list = J(list)
    match_rationale: Optional[str] = None
    contradictions: list = J(list)                    # ["material_not_issued", ...]
    proposed_write: Optional[str] = None              # "Actual Start = 13-Sep for PIP-3-2340"
    date_written: Optional[str] = None                # actual_start | actual_finish | None

    # Four confidences — stored separately, never blended
    extraction_conf: Optional[float] = None
    match_conf: Optional[float] = None
    date_conf: Optional[float] = None
    verification_conf: Optional[float] = None

    # Clarification
    clarification_asked: Optional[str] = None
    clarification_options: list = J(list)             # [{label, value}]
    clarification_dimension: Optional[str] = None
    clarification_response: Optional[str] = None
    clarification_asked_at: Optional[datetime] = None
    clarification_latency_s: Optional[float] = None
    clarification_count: int = 0

    # Unplanned
    unplanned_flag: bool = False
    unplanned_class: Optional[str] = None
    suggested_parent_wbs: Optional[str] = None
    change_order_candidate: bool = False
    unplanned_status: Optional[str] = None            # open | linked | proposed

    extractor: Optional[str] = None
    provenance: dict = J(dict)
    field_conf: dict = J(dict)


class HSEEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: Optional[int] = Field(default=None, foreign_key="event.id")
    report_id: Optional[int] = None
    created_at: Optional[datetime] = None
    kind: str = "incident"                            # incident | permit | stop_work
    work_front: Optional[str] = None
    permit_required: bool = False
    permit_type: Optional[str] = None
    permit_id: Optional[str] = None
    permit_status: Optional[str] = None
    permit_validity_window: Optional[str] = None
    gas_test_done: Optional[bool] = None
    hse_event_type: Optional[str] = None
    hse_severity: str = "observation"                 # observation | minor | major | critical
    hse_event_text: str = ""                          # verbatim — never paraphrased
    stop_work_flag: bool = False
    stop_work_scope: Optional[str] = None             # zone | activity | unit | site
    hse_reported_to: Optional[str] = None
    mishap_flag: bool = False
    mishap_category: Optional[str] = None
    rework_triggered: bool = False
    equipment_id: Optional[str] = None
    gated_activities: list = J(list)
    info_match_activity: Optional[str] = None         # what the matcher *would* have linked
    info_match_conf: Optional[float] = None
    status: str = "open"                              # open | acknowledged | closed
    assigned_to: Optional[str] = None
    closed_note: Optional[str] = None
    reporter_id: Optional[str] = None


# ─────────────────────────────── learning + audit ───────────────────────────────────

class ReviewAction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int
    planner_action: str                               # approved | corrected | rejected | reassigned | unplanned
    proposed_activity_id: Optional[str] = None
    corrected_activity_id: Optional[str] = None
    correction_reason: Optional[str] = None           # wrong_area | wrong_object | terminology
    planner_review_seconds: Optional[float] = None
    reviewer: Optional[str] = None
    at: Optional[datetime] = None
    alias_learned: Optional[str] = None


class Alias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    term: str = Field(index=True)                     # normalised lower-case
    target_node: str                                  # activity / work-front / object id
    target_type: str                                  # activity | work_front | object | line
    scope_zone: Optional[str] = None                  # only applies when the report is in/for this work front
    learned_from_event: Optional[int] = None
    at: Optional[datetime] = None
    source: str = "planner"                           # planner | seed_master


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prev_hash: str
    hash: str
    actor: str
    action: str
    entity: Optional[str] = None                      # "event:42"
    payload_json: str
    at: datetime


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: Any = Field(default=None, sa_column=Column(JSON))
