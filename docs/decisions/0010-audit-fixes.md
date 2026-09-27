# 0010 — Fixes from the verification audit

**Status:** accepted · **Phase:** post-build audit

The factual audit of the running prototype (tests A–L) found bugs that the pytest suite did not catch.
Each is fixed at its root cause, has a regression test in `backend/tests/test_fixes.py`, and was re-checked end to end
(API run of all 12 demo steps, plus browser checks). Every new test was mutation-checked: it fails when its fix is reverted.

## What we changed and why

| # | Problem (root cause) | Fix |
|---|---|---|
| 1 | **Stop-work was not enforced.** The HSE Centre listed gated activities, but `process_event` never consulted open stop-work items. | `hse.active_stop_work()` finds an open (not closed) stop-work whose scope covers the new report: activity → its gated list; zone → work front; unit → all fronts of that unit; site → everything. The report zone comes from text or a GPS fix *inside* a front, and the activity must score ≥ `candidate_min` to count. A matching report becomes `hse_hold` with no date write, and gets its own HSE item `work_in_stopped_zone`. Stops raised after the reported work date don't apply. Scope-less stops (nobody has set the blast radius yet) are not enforced. Blocker (cause-only) reports are still recorded, since they write no dates. |
| 2 | **Stuck 📤 bubbles with two tabs.** `offlineQueue.ts` started its flush timer at import. The static FieldApp import in `App.tsx` meant *every* tab flushed, including the Control Room, and `onSent` only fired in the tab that delivered. | The timer starts only via `startFlusher()` from the Field App. A **Web Lock** (`navigator.locks`, `ifAvailable`) makes one tab flush at a time. Delivery moves the item `queue → sent` (IndexedDB v2, one transaction) and is announced on a **BroadcastChannel**. Every Field tab applies it only to bubbles in its own thread and reconciles 📤 bubbles against `sent` on load. Server idempotency on `client_id` stays as the last line of defence. Browser-native, no new dependency. |
| 3 / 10 | **`_question_hi`, `_inference_why`, `_failing` never saved.** `ev.field_conf = fc` was assigned before the matcher's queries autoflushed; after that the ORM's committed state *was* `fc`, so later in-place edits looked unchanged. | Always assign fresh copies (`dict(fc)`, `dict(prov)`). The Review screen shows "Why this inference" and "Held back by: … below threshold / match margin". |
| 4 | **Weather shown as DERIVED.** `enrich_weather` set `FETCHED` tags on `ev.provenance`, then `process_event` overwrote them with its local `prov`. | Merge the `weather_*` tags back into `prov` right after enrichment. The same pattern fixes the permit-table lookup (`permit_status = FETCHED`). |
| 5 | **Hydrotest finish marked "duplicate".** The dedup key `object|action|date` could not tell "pressure hold" (progress) from "completed" (finish). | Key = `object|action|event_type|date`. Exact cross-channel repeats are still deduplicated. |
| 6 | **Ask counted rejected / misattributed events.** It used every event, and took the unit from the matched activity even when that was only a guess. | `project_events()` drops duplicates and planner-rejected events (unless the question says "rejected"/"history"). Unit/zone filters count an event only on **evidence**: text zone, GPS inside, a named object, a match consistent with the object class the text names, a planner/reporter confirmation, or a single-unit reporter. The rest are reported as "not counted" with their ids. The fake `sql` string is replaced by `filters`, which lists what was actually applied in Python. |
| 7 | **Auto-sync % inflated.** A clarified event, once linked, had route reason "all four scores…" and was counted as automatic. | `analytics.outcome_of()` gives AUTO_SYNC / QUESTION_RESOLVED / PLANNER_APPROVED / HSE_HOLD / UNPLANNED / DUPLICATE / UNPARSEABLE / PENDING from the existing state fields. `is_auto` is true only for AUTO_SYNC. The learning curve now reads ≈37% → ≈64%. |
| 8 | **Seed not deterministic.** `history.rnd = random.Random(seed)` was created once at import. A second reset in the same process (Settings → Reset demo, `POST /api/admin/reset`) continued the stream and replayed a different history (257 vs 286 events). | `rnd.seed(SEED)` at the start of every `history.run()`. Verified: repeated in-process and cross-process resets give an identical fingerprint (257 events, 4 aliases). |
| 9a | **"Motor cabling P-101A/B" → unplanned.** "cabling" matched neither the `cable` class nor the `pull` action, so "P-101A" made it a *pump*. | Vocabulary: `cabling` → object class `cable`, action `pull`. The spreadsheet row now proposes **ELE-3-3400 @ 0.83** (one-tap review) instead of unplanned. |

## What we did **not** change (and why)

**9b — Unit-2 basin blocker attached to a Unit-3 footing (EV-202 in the seed).**
Root cause: the report has no text zone and no GPS, and the reporter (R. Gogoi) works three fronts in two units. The matcher then prefers F-12 shuttering: exact action `shutter`, "basin" is in the *foundation* class family, and prior-event and in-progress signals. The Cooling-Tower candidate has the exact class but only a related action.
We tried removing `basin` from the foundation family. The blocker then attached to another Unit-3 activity (PIP-3-2401), and an earlier Cooling-Tower report flipped to an HSE hold. That removed a planner correction and the learned `basin` alias from the seed, so the change cascades through the history and is **not** a small, safe fix. Proper fix later: when a blocker's top candidate is not credible *or* the candidates span several units with no location evidence, keep it unattributed (or ask one question) instead of taking `affected[0]`. That also needs weighting object-class specificity above reporter history. **Mitigation now:** Ask no longer counts such events towards a unit (fix 6).

## How to verify
```bash
cd backend && python -m pytest -q tests      # 34 tests (20 original + 14 regression)
```
Demo-order note: stop-work is now real. If the demo sets a stop-work scope (step 6), **close the item** before continuing, or later reports in that scope are held (see DEMO_SCRIPT.md).
