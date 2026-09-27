# 0005 — API surface, live updates (SSE) and idempotent offline delivery

**Phase:** 2–6 · **Status:** accepted · **Date:** 2026-09-26

## What we did
- Six routers: `field` (report, photo, clarify, my-reports, thread), `review` (queue, decide, suggest-alias, activity search), `hse` (items, actions, permit board), `analytics` (one `/overview` payload for all 14 charts), `audit` (log, verify, **SSE `/api/stream`**) and `control` (meta, events, activities, XER export, uploads, DPR, ask, settings, unplanned, aliases, reset).
- **Server-Sent Events** via a tiny in-process bus (`bus.py`). The pipeline runs in FastAPI's threadpool and hops onto the event loop with `call_soon_threadsafe`. It publishes `report`, `event`, `schedule`, `review`, `hse` and `hse_update`.
- **Idempotent report delivery:** the Field App's IndexedDB queue sends a `client_id` with every report. The server stores it as `Report.source_doc_id` and returns the original result on a retry instead of creating a second report.
- **Photos are uploaded as raw bytes** (`/api/field/photo`) and stored untouched, so EXIF GPS and the timestamp survive to the evidence layer.
- The project clock shifts client timestamps (`clock.shift`), so a phone's real "now" lands on the demo date.
- First start **auto-seeds** if the DB is empty; `POST /api/admin/reset` reseeds for demos.

## Why
- **SSE rather than WebSockets:** traffic is one-way (server → Control Room), it auto-reconnects in the browser, it passes through the Vite proxy, and it needs no extra dependency. Live alerts (HSE red banner + sound) and a live-updating Gantt are both one-way.
- **One analytics payload** keeps the Overview to a single request (<150 ms on the seeded DB) and computes every chart from the event store, so nothing is canned.
- **Idempotency is required** by the offline design: exponential-backoff retries *will* resend a report whose response was lost on a flaky 2G link. Without `client_id` the dedup rule (object+action+date across channels) would not catch same-channel retries of reports with no object.

## Alternatives considered
- WebSockets: bidirectional, but more moving parts for no gain.
- Background task queue (Celery/RQ): unnecessary. The pipeline runs in ~20–40 ms per event.

## How to verify
- Open the Control Room and send a report from the Field App: the Gantt and KPIs refresh without a reload. An HSE item flashes the red banner.
- Tick *Simulate offline*, send twice, untick: exactly two reports arrive even if a retry happens.
