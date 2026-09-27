# 0001 — Skeleton: stack, repo layout and the event-level data model

**Phase:** 1 (Skeleton) · **Status:** accepted · **Date:** 2026-09-26

## What we did
- Backend: **FastAPI + SQLite (SQLModel)**, `networkx`, `rapidfuzz`, `scikit-learn`, `shapely`, `pdfplumber`, `openpyxl`, `Pillow`, `reportlab`. Runs on Python 3.14 without Docker (`make dev`).
- Repo layout as in the build prompt: `backend/app/{models,db,config,clock,bus}.py`, `backend/app/pipeline/*`, `backend/app/api/*`, `backend/app/seed/*`, `frontend/`, `sample_data/`, `docs/decisions/`.
- `models.py` is a direct transcription of **extraction-schema-v2**. The atom is `Event`, not `Report`. `Report` is the envelope (0..N events). `HSEEvent`, `Activity`, `ReviewAction`, `Alias`, `AuditLog`, `WorkFront`, `Line`, `ObjectItem`, `Permit`, `MaterialIssue`, `Equipment`, `WeatherObs` and `Setting` are all tables.
- **Provenance** is a JSON column per row, `provenance = {field: GIVEN|EXTRACTED|FETCHED|DERIVED|HUMAN}`. **Spans** are a JSON column, `spans = {field: [start, end]}`, into `Report.raw_text`. The verbatim input, `transcript_raw` and the original file path are always stored.
- **Four confidences** are four separate columns (`extraction_conf`, `match_conf`, `date_conf`, `verification_conf`). There is no blended score anywhere.
- A **project clock** (`clock.py`) pins "today" to `PROJECT_TODAY=2026-09-26` and shifts client timestamps by whole days. The seed freezes the clock per simulated moment.
- Gate thresholds and other runtime knobs live in a `Setting` row (deep-merged over defaults in `config.py`). The Settings page can therefore change them live.

## Why
- **Event-level atom:** one WhatsApp line ("spool 3 erected, welding started on spool 4") is two facts about two activities. A report-level model would force us to pick one and silently drop the other, which the PS forbids.
- **Provenance as a JSON map instead of wrapping every value:** it keeps the ~60 columns queryable with plain SQL (Pareto charts, fill-rates, RAG filters) while still letting the UI put a chip next to every value. Wrapped values (`{value, prov, span}`) would make every aggregate query unpack JSON.
- **SQLite + SQLModel:** zero setup, one file, easy to reset (`make seed`). Enough for a single-site demo. SQLModel gives Pydantic validation for free on the API edge.
- **A fixed project date:** the demo story (13-Sep rain, 26-Sep dry day, planned Aug–Oct dates) has to replay identically on any day it is presented.
- **NaiveDatetime** (`models.py` aliases `datetime = NaiveDatetime`): every timestamp on site is IST wall-clock. The installed SQLModel refuses naive datetimes unless annotated, and timezone-aware storage would only add conversion bugs for a single-timezone project.

## Alternatives considered
- Postgres + PostGIS: better geo, but adds a service to install. `shapely` does point-in-polygon for 10 fences in microseconds.
- One wide JSON blob per event: flexible, but kills the analytics queries and the fill-rate table.
- Docker compose: specified as optional. Docker is not installed on the build machine, so `make dev` is the primary path and a compose file is still provided.

## Consequences
- JSON columns must be **re-assigned, not mutated**, or SQLAlchemy won't persist the change. The pipeline always builds `prov = dict(...)` and assigns it back.
- Sparse is normal: most events fill only envelope, core, context and derived. The UI shows empty layers collapsed, and the analytics page reports a **fill rate per field**.

## How to verify
- `python -m app.seed.run` builds a fresh DB in ~7 s.
- `GET /api/events/{id}` returns the event with `provenance`, `spans` and the four confidences as separate fields.
