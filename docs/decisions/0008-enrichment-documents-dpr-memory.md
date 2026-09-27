# 0008 — Enrichment, document ingest, DPR reconstruction and "Ask the project"

**Phase:** 7 + 9 · **Status:** accepted · **Date:** 2026-09-26

## What we did
- **Weather** (`enrich_weather.py`): `weather_reported` (the claim, EXTRACTED) and `weather_fetched` (the evidence, FETCHED) are kept separately.
  - Sources: a **seeded site-station table first**, then **Open-Meteo archive** (free, no key, 3 s timeout), per `settings.weather_mode`.
  - A rain claim is corroborated if **≥ 2.5 mm fell in the claimed window** ("from 2pm" means 14:00 to 18:00 shift end).
  - Severity: normal / adverse / **extreme (≥ 35 mm/day)**.
  - Weather enrichment runs *before* the gate for blockers, because a non-corroborated claim is a contradiction that must reach a planner.
- **Material:** the matcher looks up `MaterialIssue` for the resolved scope object. `not_issued` means a contradiction and lower verification, never a rejection.
- **Location / evidence:** shapely point-in-polygon; accuracy > 50 m means `boundary` with nearby zones kept; EXIF GPS is used when the report has none; EXIF older than 24 h means `old_photo_exif`. The CV stub has a `check(photo, claim) → {objects, score, model_version}` interface so a YOLO model can drop in.
- **Spreadsheet DPR:** header-row detection plus **rapidfuzz header mapping** against synonyms. One row is one candidate event, and spans point at the cell inside the reconstructed row line. **No LLM.**
- **DPR PDF / text:** pdfplumber → **section headings** (ALL-CAPS lines) → the heading becomes location context for every line under it → sentence/event extraction. Document metadata lines ("Project: … Date: … Reporter: …") are skipped.
- **WhatsApp chat export:** `[dd/mm/yy, h:mm AM] Name: message`, giving one report per message with the reporter matched by name.
- **End-of-day DPR** (`dpr.py`): HTML (print-ready) and PDF (reportlab), built only from events. Sections: progress, manpower & equipment, blockers with verbatim cause text + **weather reported vs fetched**, HSE (verbatim), unplanned. **Every line cites EV-n.**
- **Ask the project** (`ask.py`):
  - "How many …" questions become a **structured query** over cause_category / subcategory / month / unit / zone, and we show the filters that were applied. *(Superseded by 0010: this used to display an illustrative SQL string, but filtering happens in Python, so it now lists the real filters.)*
  - Narrative questions use **KG-aware TF-IDF retrieval** over cause_text/source_sentence, boosted for events on the asked activities/zones and for blockers when the question says *late/why/delay*, plus schedule facts (planned vs actual).
  - With a key, Claude writes the prose **from the retrieved snippets only, with [EV-n] citations**. Without one we return an extractive, cited answer.

## Why
- **Weather as evidence, not anecdote:** the schema doc's point is that "the supervisor said it rained" and "the station says it rained" carry different evidentiary weight in an extension-of-time claim. The demo shows both cases: 13-Sep, 42 mm, corroborated; 18-Sep and 26-Sep dry, not corroborated.
- **Seeded-first weather** keeps the demo deterministic. Real Assam weather on those dates is unknown to us, and the story needs the 13-Sep storm. Open-Meteo stays wired in for live use (`live_first`).
- **Extractive answers without a key** keep "Ask" honest: every sentence is a quoted field record with a citation, so nothing is invented.
- **Documents of record** (DPR / xlsx) start verification at 0.70 instead of 0.50. A contractor's signed report is evidence, so it clears start claims but still needs a planner for finish claims.

## How to verify
- *DPR & uploads → Spreadsheet → Use sample*: the mapping chips show "Desc of Work → description" etc. and 12 events are created.
- *Generate DPR* for 13 Sep shows 42 mm fetched vs "Heavy rain from 2 pm", with every line cited.
- *Ask*: "Why is Rack B piping late?" gives the cited timeline (crane → rain → ISO-4417 rev → manpower). "How many rain delays in Unit 3 in September?" gives the count, hours and corroboration split.
