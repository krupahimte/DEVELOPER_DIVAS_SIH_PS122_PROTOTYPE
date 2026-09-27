# 0003 — KG + matcher, the event_type safe rule, and the four-number gate

**Phase:** 3 · **Status:** accepted · **Date:** 2026-09-26

## What we did
### Knowledge graph (`kg.py`)
Typed `networkx` nodes (activity, work front, area, unit, object, line, drawing, system, reporter, contractor, scope package, alias). The edges are exactly the schema's "KG context edges": object→line (part_of), line→drawing, line→system, wf→area→unit, reporter→wf, activity→predecessor, contractor→package, and alias→target. The KG holds **transient snapshots** of rows, and activity actual dates are refreshed on every match.

### Matcher (`matcher.py`) — three tiers, recorded in `match_path`
1. **kg_narrowed:** candidates are open activities reachable from the event's seeds (GPS zone, text zone/aliases, reporter fronts, objects, lines, drawings), filtered by the look-ahead window and predecessor eligibility.
2. **vector_only:** TF-IDF (char n-grams) over open activities in the discipline. It becomes MiniLM with `USE_MINILM=1`.
3. **fuzzy_fallback:** rapidfuzz token-set ratio.

Each candidate gets a **compatibility score**: additive *signals* (object_id .35, line .30, drawing .25, action .25, text location .20, geofence .15, reporter scope .12, …) and *penalties* for stated mismatches, capped at .99. We store `top_k_candidates`, `match_margin = top1 − top2`, `signals_fired`, `candidate_set_size`, a KG path ("Reporter S. Kalita → WF-U3-RACK-B → PIP-3-2340") and a readable rationale.

**Cross-checks never reject:** *material not issued* lowers verification by .20, a *predecessor open* lowers match by .15, and *location conflict* and *old photo EXIF* both add a contradiction. Any contradiction means review.

### event_type safe rule (`event_type.py`)
`object_event_type` (what the text says) and `activity_inference` (what it means at L6) are stored separately:
- The first event on an activity writes Actual Start.
- Actual Finish is written only when the claimed objects cover the full scope (accumulated across the activity's linked events), when the object *is* the activity (a whole-line hydrotest), or when the completion language is unambiguous ("all 4 spools erected, erection complete").
- Anything else advances nothing, and blockers write the cause only.

### Gate (`gate.py`)
AUTO requires **all four** scores ≥ threshold (verification .85 instead of .70 for finish claims), margin ≥ .10, and no contradiction. CLARIFY applies when exactly one dimension is borderline, **or** the margin is thin with the top two both ≥ .70. REVIEW covers everything else with a candidate ≥ .50, and UNPLANNED applies when there is none. Thresholds are live-editable.

### Clarifier (`clarify.py`)
One multiple-choice question, built from what distinguishes the top two candidates ("Rack B or Rack C?"), or from the single borderline dimension (photo / date / "did you mean"). The cap is enforced per report. An unanswered question escalates to the planner after 2 h.

## Why (the non-obvious calls)
- **Per-candidate compatibility, not normalised probabilities.** A report that fits Rack B and Rack C equally well *should* score both high, and the margin is what exposes the coin flip. Normalising would hide exactly the case the schema doc warns about (".91 vs .87").
- **A thin margin tolerates a borderline match score in the CLARIFY rule.** "spool erected near rack" scores .82 for both racks. That is one problem (ambiguity), not two, so the worker gets the one question instead of the planner getting a review item.
- **GPS is a preference, text location is a restriction.** "Spool 5 erected" sent from Rack B must still resolve to spool 5 on Rack C (and then flag *location conflict* + *material not issued*). Restricting ordinal resolution to the GPS zone missed the contradiction entirely.
- **Ordinals resolve only against eligible candidates.** Otherwise an out-of-look-ahead line on the same rack "claims" the spool.
- **The plan may lag the site.** When no eligible candidate reaches .50, predecessor-open activities may compete, with a contradiction flag. Before this fix, real work was routed to *unplanned* (spec: never reject).
- **Reporter scope mismatch penalty (−.15)** applies only when there is *no* location evidence at all (no GPS, no text zone). This stopped a slang-only WhatsApp message from auto-linking to another crew's rack at .99.
- **Verification rebalanced for WhatsApp** (0.50 base, +.20 for a registered reporter on their own assigned front). WhatsApp strips GPS and EXIF, so text-only reports from the assigned supervisor clear the **start** bar (.70) but never the **finish** bar (.85) without a photo or GPS. The schema doc's own reasoning supports this: a false start self-corrects, a false finish propagates into the critical path.
- **HSE bypass runs after an informational match** so the HSE Centre can say what the event *would* have updated ("matched PIP-3-2351 at 0.89 — held"). The routing decision is still made before and regardless of confidence.

## Consequences
- Resource-only lines ("night shift 10 welders") are attached to the work front as productivity denominators and never become "unplanned".
- Thresholds and weights are the tuning surface. The Settings page exposes the thresholds, and the weights are constants in `matcher.py`.

## How to verify (all nine demo steps pass on the seeded DB)
| Step | Result |
|---|---|
| 1 Hinglish Rack B | linked, Actual Start PIP-3-2340 (match .99, margin .16) |
| 2 "spool erected near rack" (weak GPS) | clarifying "Rack B or Rack C?" → answer → linked |
| 4 hydrotest without photo | clarifying (photo); with photo → Actual Finish |
| 5 welding Rack C | **hse_hold** (hot-work permit missing) despite match .89 |
| 7 rain on dry 26-Sep | review, `weather_corroborates=false` |
| 8 "Spool 5 erected" | review: material_not_issued + location_conflict → planner reassigns (terminology) → alias `'spool 5' → SPL-16-1207-05` → resend **auto-syncs** |
| 9 temporary drainage | unplanned / site_prep |
