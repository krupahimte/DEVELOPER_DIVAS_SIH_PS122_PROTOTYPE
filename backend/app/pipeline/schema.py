"""The contract every extractor (rules, LLM, spreadsheet) must return.

Spans are absolute character offsets into the *normalised* report text
(`Report.raw_text`). A value without a span is only allowed for DERIVED fields
(e.g. an implicit event_date that defaults to the reporting date).
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExtractedEvent(BaseModel):
    sentence: str
    sentence_span: tuple[int, int]
    input_language: str = "en"

    # core
    action: Optional[str] = None
    object_event_type: Optional[str] = None           # start | finish | progress | none
    activity_level_finish: bool = False               # completion language is unambiguous at activity level
    object_class: Optional[str] = None
    object_qualifier: Optional[str] = None
    object_ordinals: list[int] = Field(default_factory=list)
    object_refs: list[str] = Field(default_factory=list)   # ids seen in text: SPL-..., FDN-F-12, P-101B, TRAY-T-4, LOOP-L-303
    line_ref: Optional[str] = None                     # "24-P-1203" or partial "24"
    drawing_no: Optional[str] = None
    location_text: Optional[str] = None
    quantity: Optional[float] = None
    uom: Optional[str] = None
    event_date: Optional[date] = None
    date_conf: float = 0.85
    date_explicit: bool = False

    # blocker
    blocker_flag: bool = False
    cause_category: Optional[str] = None
    cause_subcategory: Optional[str] = None
    cause_text: Optional[str] = None
    time_lost_h: Optional[float] = None
    time_window: Optional[tuple[int, int]] = None      # hours, e.g. (14, 18)
    blocker_resolved_at: Optional[datetime] = None

    # HSE
    hse_event_flag: bool = False
    hse_event_type: Optional[str] = None
    hse_severity: Optional[str] = None
    stop_work_flag: bool = False
    mishap_flag: bool = False
    mishap_category: Optional[str] = None
    rework_triggered: bool = False
    permit_status: Optional[str] = None               # only when stated in text
    permit_type: Optional[str] = None
    permit_id: Optional[str] = None
    gas_test_done: Optional[bool] = None

    # resources
    manpower_by_trade: dict[str, int] = Field(default_factory=dict)
    manpower_total: Optional[int] = None
    manhours: Optional[float] = None
    shift: Optional[str] = None
    equipment_deployed: list[str] = Field(default_factory=list)
    equipment_idle_flag: bool = False
    equipment_breakdown: bool = False
    material_consumed: dict[str, float] = Field(default_factory=dict)
    material_shortage_flag: bool = False

    weather_reported: Optional[str] = None

    spans: dict[str, tuple[int, int]] = Field(default_factory=dict)
    extraction_conf: float = 0.5
    extractor: str = "rules"
    document_section: Optional[str] = None
