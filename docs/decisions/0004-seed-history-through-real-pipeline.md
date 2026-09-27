# 0004 — Seed data: replay three weeks of history through the real pipeline

**Phase:** 1–3 support · **Status:** accepted · **Date:** 2026-09-26

## What we did
- `seed/master.py` holds the plan-side truth: 10 work fronts (GeoJSON), 9 lines with drawings and systems, spools as objects, **150 L5/L6 activities** with WBS and predecessors (written to `sample_data/schedule_xer.csv` and **parsed back** through `xer_parse.py`), 12 reporters, contractors and scope packages, permits (valid / expired / pending, **no hot-work permit on Rack C**), store issues (**spool SPL-24-1203-05 not issued**), equipment, and seeded site weather (**13-Sep 42 mm, 14–18 h**; 18-Sep and 26-Sep dry).
- `seed/history.py` simulates 5–25 Sep:
  - Hidden **ground-truth progress** per activity (slips, predecessors).
  - The messages crews would send: English and Hinglish, WhatsApp / PWA / Telegram / DPR uploads, some offline lag on poor-signal fronts, photos on completions, and duplicate DPR lines the next morning.
  - **Crew slang** the plan doesn't know ("north rack", "naya rack", "bijli ghar", "compressor shed", "pump ghar", "CT side").
  - Reporters answering (≈72%) or ignoring clarifying questions. Unanswered questions escalate after 2 h.
  - The **planner working the queue each evening**, approving or correcting with a reason, from the generator's ground truth.
  - Hand-written blockers, HSE items and unplanned work that tell the story (why Rack B is late: crane breakdown, 13-Sep rain, ISO-4417 revision, manpower).
- **Nothing writes states or confidences directly.** Every event is produced by `ingest()`.
- `master.RESERVED` holds the demo activities (PIP-3-2340/2341/2342/2351/2353/2402), which receive no progress history. The seed asserts this (`reserved touched []`).

## Why
- **Honest charts.** The "learning curve" and "match path mix" charts are only worth showing if they come from the mechanism they claim to show. Replaying through the pipeline means the rising auto-sync % comes from aliases actually learned from planner decisions, not from a hard-coded ramp.
- **It is also the best integration test we have.** Running 250 realistic messages exposed ~10 real bugs (see ADR 0002/0003 tables), plus two alias-learning hazards (below).
- **Deterministic** (fixed RNG seeds, frozen clock), so every demo reset gives the same site.

## Findings that changed the design
1. **Naive alias learning is dangerous.** Early runs learned `'kaam chal' → STR-2-4210` and `'unit 2' → WF-U3-PUMP`. Guardrails added (`learning.py`):
   - Never learn generic or function words, bare numbers or id patterns.
   - Never learn a term that is already a seeded alias of a *different* target ("rack c").
   - Mask everything the KG already explains before looking for the unexplained phrase.
   - Take at most two words ending in a place word ("north **rack**", "bijli **ghar**").
   - Ordinal object aliases ("spool 5") are learned **only if unambiguous inside that work front**, and are **scoped** to it (`Alias.scope_zone`).
2. **Approvals can teach too.** When a planner *approves* an ambiguous item (margin < .10 or a question was asked) and the text holds an unexplained place phrase, we learn it. Most slang first appears in exactly those ambiguous items.
3. Crews keep their slang for all three weeks. What changes is whether the KG knows it, and that is what bends the auto-sync curve.

## Result (current seed)
- ~250 reports → ~260 events: linked ≈205, review ≈20–28, unplanned 12, duplicate 7, hse_hold 7.
- Auto-sync per week ≈ **40% → 49% → rising** (the last days include the open review queue).
- Learned aliases: `north rack → WF-U3-RACK-B`, `naya rack → WF-U3-RACK-C`, `bijli ghar → WF-U2-SUBSTN`, `compressor shed → WF-U2-COMP`, `spool 2 → SPL-12-2120-02 (scoped)`.

## How to verify
`make seed` prints the stats. Run `python -m app.seed.run` and then open *Overview → Learning curve*.
