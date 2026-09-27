# 0007 — Control Room: review queue, HSE Centre, 14 charts

**Phase:** 5, 6, 8 · **Status:** accepted · **Date:** 2026-09-26

## What we did
- **Review Queue** (the planner's main screen):
  - List on the left, detail on the right.
  - Keyboard: **A** approve, **1/2/3** pick candidate, **R** reject, **U** unplanned, **J/K** move, **Enter/Esc** confirm/cancel a correction.
  - The detail shows the **verbatim sentence with extracted spans highlighted** (colour per field, hover links span ↔ field row), provenance chips on every value, **four labelled confidence bars** with threshold ticks (failing ones red/amber), the **margin gauge**, and top-3 candidate cards with *signals* (green) / *penalties* (red) chips and the **KG path**.
  - It also shows the proposed write and object-vs-activity inference side by side, and contradiction flags.
  - Choosing another candidate opens the **reason picker** (wrong_area / wrong_object / terminology) with the **suggested alias pre-filled and editable**. A **timer** records `planner_review_seconds`, and the toast reads *"Learned: 'spool 5' → SPL-16-1207-05"*.
- **HSE Centre** (red accent):
  - Items sorted by severity with **verbatim** text.
  - The *"would have matched X @ 0.89 — HELD"* line.
  - A **stop-work scope** prompt (activity/zone/unit/site) that recomputes gated activities and draws the **blast radius** on the map.
  - Acknowledge / assign / close-with-note.
  - A **permit board** per zone: valid / expiring soon / expired / pending / *missing because an open activity needs it*.
- **Overview:** 8 KPI tiles and the 14 charts from the build prompt, all computed server-side from events, with tooltips and click-through to the filtered Event Explorer (`/control/events?ids=…`).
- **Schedule:** planned vs actual, provenance of each actual date (DERIVED / HUMAN), a link to the **source event**, variance, and **PMIS write-back** CSV (XER-like, with source event ids).
- **Event Explorer / detail:** filters on state, channel, cause, match path and dates. The detail shows **all 10 layers** (empty layers collapsed with "not present — normal"), provenance chips, and the **state history + hash chain** with *Verify integrity*.

## Chart decisions (dataviz rules applied)
- **Status colours are reserved** for routing state and identical everywhere: green = linked, amber = review/clarify, blue = unplanned, red = HSE, grey = duplicate/unparseable. Always paired with a text label.
- **Identity colours** (disciplines, channels, trades, match paths) use a **validated categorical order** (blue, orange, aqua, yellow, magenta, green, violet, red), assigned by entity and never cycled.
- **No dual axes.** The build prompt asks for "Pareto bars + cumulative % line", "stacked weather bars + rain_mm line" and "aliases vs auto-sync %":
  - The **Pareto** plots each cause's *share* and the cumulative % on **one 0–100% axis** (with an 80% guide).
  - **Weather** and **learning curve** are **two small charts sharing an x-axis** (`syncId`) instead of two y-scales.
- The **Gantt** is custom HTML (Recharts has no Gantt): grey planned bar, coloured actual bar, a **◆ at each actual date whose tooltip names the source event and provenance**, variance labels, ⚠ for reported blockers, and a dashed project-date line. Clicking a row opens its events.
- The **funnel** is a Recharts Sankey (Reports → Events → HSE / Auto / Clarify / Review / Unplanned / Duplicate → outcomes). Clicking a node filters events.

## Honest finding
The **match-path mix** is almost entirely `kg_narrowed`, because every known reporter seeds the KG through reporter → work-front edges. `vector_only` / `fuzzy_fallback` fire for **unknown reporters and uploaded documents** (e.g. the xlsx DPR in demo step 10). We did not fake a shift. What *does* shift as aliases are learned is the **clarify rate** (down) and **auto-sync %** (up), shown in the learning-curve chart.

## How to verify
- In the Review queue, press **J/K** to move, **2** to open the correction, then **Enter**. `planner_review_seconds` appears in the event's history.
- Click any Pareto bar or weather day and the Event Explorer opens pre-filtered.
