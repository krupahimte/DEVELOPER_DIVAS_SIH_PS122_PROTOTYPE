"""Deterministic parse of the XER-like schedule export (CSV).

The schedule is the MATCH TARGET — it is never run through the event extractor.
Columns follow Primavera TASK naming where possible.
"""
import csv
import re
from datetime import date
from pathlib import Path

COLUMNS = ["task_code", "wbs", "task_name", "discipline", "unit", "area", "work_front", "target_start_date", "target_end_date",
           "act_start_date", "act_end_date", "pred_task_codes", "scope_objects", "permit_type", "contractor", "scope_package",
           "action", "object_class", "line_no"]


def write(path: Path, rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})


def _d(s):
    s = (s or "").strip()
    return date.fromisoformat(s[:10]) if s else None


def _derive_action(name: str) -> str | None:
    n = name.lower()
    for key, act in [("hydrotest", "test"), ("pneumatic test", "test"), ("loop check", "test"), ("load test", "test"), ("erect", "erect"),
                     ("weld", "weld"), ("fabricat", "fabricate"), ("concret", "pour"), ("pcc", "pour"), ("excavat", "excavate"),
                     ("cable pulling", "pull"), ("install", "install"), ("paint", "paint"), ("primer", "paint"), ("insulat", "insulate"),
                     ("backfill", "backfill"), ("shutter", "shutter"), ("reinforcement", "rebar"), ("grout", "grout"),
                     ("align", "align"), ("terminat", "terminate"), ("calibrat", "calibrate"), ("torqu", "torque"), ("flush", "flush")]:
        if key in n:
            return act
    return None


def parse(path: Path) -> list[dict]:
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["task_name"].strip()
            line = r.get("line_no") or (re.search(r"\b\d{1,2}-[A-Z]-\d{3,5}\b", name) or [None])[0]
            out.append({
                "activity_id": r["task_code"].strip(), "wbs": r["wbs"].strip(), "name": name, "discipline": r["discipline"].strip(),
                "unit": r["unit"].strip(), "area": r["area"].strip(), "work_front": r["work_front"].strip() or None,
                "planned_start": _d(r["target_start_date"]), "planned_finish": _d(r["target_end_date"]),
                "actual_start": _d(r.get("act_start_date")), "actual_finish": _d(r.get("act_end_date")),
                "predecessors": [p for p in (r.get("pred_task_codes") or "").split(";") if p],
                "scope_objects": [p for p in (r.get("scope_objects") or "").split(";") if p],
                "permit_type_required": r.get("permit_type") or None, "contractor": r.get("contractor") or None,
                "scope_package": r.get("scope_package") or None,
                "action": r.get("action") or _derive_action(name), "object_class": r.get("object_class") or None, "line_no": line or None,
            })
    return out


def to_csv_rows(activities) -> list[dict]:
    """Activity rows → XER-like CSV rows (PMIS write-back export)."""
    rows = []
    for a in activities:
        rows.append({
            "task_code": a.activity_id, "wbs": a.wbs, "task_name": a.name, "discipline": a.discipline, "unit": a.unit, "area": a.area,
            "work_front": a.work_front or "", "target_start_date": a.planned_start.isoformat(), "target_end_date": a.planned_finish.isoformat(),
            "act_start_date": a.actual_start.isoformat() if a.actual_start else "", "act_end_date": a.actual_finish.isoformat() if a.actual_finish else "",
            "pred_task_codes": ";".join(a.predecessors or []), "scope_objects": ";".join(a.scope_objects or []),
            "permit_type": a.permit_type_required or "", "contractor": a.contractor or "", "scope_package": a.scope_package or "",
            "action": a.action or "", "object_class": a.object_class or "", "line_no": a.line_no or "",
        })
    return rows
