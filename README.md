# SiteSync: field progress → schedule actuals (SIH PS 122 prototype)

Site supervisors report progress the way they already do (WhatsApp, voice notes, photos, DPR PDFs, spreadsheets). SiteSync turns each input into **field events**, works out what each one means (start / finish / progress / blocked), matches it to the right **L5/L6 activity** with a **knowledge graph + fuzzy/semantic matcher**, and gates it with **four separate confidences plus a match margin**. The outcome is one of:
- **auto-sync** the actual date,
- ask the reporter **at most one question**,
- send it to a planner for **one-tap review**,
- mark it as **unplanned work**.

**Safety events never auto-sync.** Every value carries a provenance tag and a span back to the verbatim sentence.

- **Field App** (`/field`, PWA): Hindi/English, voice-first, big buttons, offline queue (IndexedDB), under 30 s per report.
- **WhatsApp simulator** (`/field/whatsapp`): the same pipeline via `channel=whatsapp`. An optional real Telegram bot is available (`TELEGRAM_TOKEN`).
- **Control Room** (`/control`): 14 charts, review queue (keyboard-driven), HSE Centre, unplanned work, schedule write-back, event explorer, audit chain, Ask-the-project, DPR generator and settings.

## Run

```bash
make install
```

```bash
make dev
```

Then open http://localhost:5173. On Windows without `make`, run `cd backend && python -m uvicorn app.main:app --port 8000` and `npm --prefix frontend run dev` in two terminals. `docker compose up` also works.

- On first start the backend **builds the demo site automatically**: master data plus 3 weeks of history replayed through the pipeline (~10 s).
- `make seed` or **Settings → Reset demo** rebuilds it.
- `make test` runs the pytest suite (20 tests).
- It works with **no API key and no internet**: rule extractor, seeded site weather, CV stub, offline map fallback.
- Put `ANTHROPIC_API_KEY` in `.env` to enable Claude extraction and Claude answers in *Ask* (see `.env.example`).

## Where things are

```
backend/app/
  models.py            the ~60-field schema v2 as SQLModel tables (Event is the atom)
  pipeline/
    ingest.py          orchestrator: capture → extract → location/evidence → [HSE bypass] → event_type → match → gate → write-back
    extract_rules.py   offline extractor (Hinglish, multi-event, spans)   extract_llm.py  Claude, quotes → spans, rules fallback
    translit.py        Devanagari voice → Hinglish                         spreadsheet.py  fuzzy header mapping, PDF sections, chat export
    kg.py              networkx KG (schema edges + aliases)                matcher.py      3-tier matcher, signals, margin, cross-checks
    event_type.py      the safe rule                                       gate.py         four-number gate + margin
    clarify.py         one question                                        hse.py          HSE bypass + permits
    location.py        geofence (shapely)   evidence.py / cv_service.py    EXIF + CV plausibility stub (YOLO drop-in interface)
    enrich_weather.py  seeded site station / Open-Meteo                    unplanned.py    class + parent WBS
    learning.py        planner decisions → aliases (with guardrails)       audit.py        SHA-256 hash chain
    dpr.py             end-of-day DPR (HTML/PDF, cited)                    ask.py          filters + retrieval memory with citations
  api/                 field · review · hse · analytics · audit(+SSE) · control
  seed/                master data, sample files, 3-week history generator
frontend/src/field     Field App (PWA) + WhatsApp simulator
frontend/src/control   Control Room pages
sample_data/           schedule_xer.csv, geofences.geojson, DPR PDF, messy xlsx, Hinglish chat export, photos (EXIF / stripped / 2-month-old)
docs/decisions/        decision log: what we did and why, one file per important step
```

## Non-negotiables — where they are enforced
| Rule | Where |
|---|---|
| Nothing silently dropped | `ingest.py` gives an `unparseable` event if nothing is read; every path sets a state + audit entry |
| HSE never auto-syncs | `ingest.process_event` runs the HSE check before routing and returns `hse_hold`; tested in `test_hse_*` |
| Four confidences, never blended; margin in the gate | `gate.route`; tested in `test_gate_never_averages` |
| Max one clarifying question | `Report.clarification_count` + `clarify_allowed`; tested in `test_clarification_cap_is_one` |
| Span for every extracted value; raw kept verbatim | `ExtractedEvent.spans`; `Report.raw_text` / `transcript_raw` / `raw_file` |
| Provenance on every field | `Event.provenance`, `Report.provenance`, `<ProvChip>` in the UI |
| Missing GPS lowers confidence, never rejects | `ingest._verification`; `test_missing_gps_never_rejects` |
| We never author activity ids, % complete or cost | Unplanned proposals CSV leaves the id blank |
| Works with no key / no internet | rules extractor, `weather_mode`, CV stub |
| Correction → alias → same phrase auto-syncs | `test_alias_learning_makes_same_phrase_autosync` |
| Audit chain verifies | `test_audit_chain_verifies_and_detects_tampering`, *Verify* buttons |

See **DEMO_SCRIPT.md** for the 12-step demo and **docs/decisions/** for the reasoning behind each design choice.
