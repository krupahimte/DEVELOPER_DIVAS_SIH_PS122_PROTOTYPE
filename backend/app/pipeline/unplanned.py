"""Unplanned-work detector (spec §4.8): classify, suggest a parent WBS, flag change orders.

We never author activity ids — we only *suggest where a planner would slot it*.
"""
import re
from collections import Counter

from . import vocab
from .kg import KG

RULES = {k: re.compile("|".join(v), re.I) for k, v in vocab.UNPLANNED_CLASS_RULES.items()}
CLASS_DISCIPLINE = {"drainage": "Civil", "road": "Civil", "fence": "Civil", "slab": "Civil", "trench": "Civil", "scaffold": "Structural",
                    "cable": "Electrical", "tray": "Electrical", "earthing": "Electrical", "lighting": "Electrical",
                    "spool": "Piping", "line": "Piping", "joint": "Piping", "support": "Piping", "loop": "Instrumentation",
                    "instrument": "Instrumentation", "pump": "Mechanical", "compressor": "Mechanical", "steel": "Structural"}


def classify(text: str, llm_class: str | None = None) -> str:
    if llm_class in ("scope_creep", "missing_activity", "rework", "site_prep", "emergency"):
        return llm_class
    for cls in ("emergency", "rework", "site_prep", "scope_creep"):
        if RULES[cls].search(text or ""):
            return cls
    return "missing_activity"


def suggest_parent_wbs(kg: KG, ev, reporter) -> str:
    disc = CLASS_DISCIPLINE.get(ev.object_class or "") or (reporter.discipline if reporter and reporter.discipline else None)
    unit = None
    m = re.search(r"\b(?:unit|u)\s*-?\s*([23])\b", ev.source_sentence or "", re.I)
    if m:
        unit = f"Unit {m.group(1)}"
    zone = ev.geofence_zone_id or ev.location_zone_text
    if not unit and zone and zone in kg.work_fronts:
        unit = kg.work_fronts[zone].unit
    if not unit and reporter and reporter.work_fronts:
        unit = kg.work_fronts[reporter.work_fronts[0]].unit
    pool = [a for a in kg.activities.values() if (not disc or a.discipline == disc) and (not unit or a.unit == unit)]
    if zone:
        same = [a for a in pool if a.work_front == zone]
        if same:
            return Counter(a.wbs for a in same).most_common(1)[0][0]
    if pool:
        # nearest by work front of the reporter, else the most common parent in that unit/discipline
        if reporter:
            same = [a for a in pool if a.work_front in (reporter.work_fronts or [])]
            if same:
                return Counter(a.wbs for a in same).most_common(1)[0][0]
        return Counter(a.wbs for a in pool).most_common(1)[0][0]
    u = "U" + (unit or "Unit 3")[-1]
    d = {"Piping": "PIP", "Civil": "CIV", "Structural": "STR", "Electrical": "ELE", "Instrumentation": "INS", "Mechanical": "MEC"}.get(disc or "", "GEN")
    return f"RFX.{u}.{d}"


def change_order(cls: str) -> bool:
    return cls in ("scope_creep", "missing_activity")
