# 0009 — Testing, verification against the non-negotiables, and known limits

**Phase:** 10 (Polish) · **Status:** accepted · **Date:** 2026-09-26

## What we did
- **pytest suite (20 tests, ~3 s)** on an isolated DB with master data only:
  - Hinglish extraction with valid spans, and the multi-event split.
  - The **event_type safe rule**: first event → start; object finished ≠ activity finished; scope coverage → finish; blocker → cause only; finish needs the stricter evidence bar.
  - **Gate routing**: never averages; the margin case asks one question and the answer links; unplanned; **the cap of one question**.
  - **HSE bypass**: permit missing is held even at match .89; the incident text is verbatim.
  - **Alias learning effect**: correction → alias → the same phrase auto-syncs; generic words are never learned.
  - Weather corroboration (dry day vs 13-Sep storm), missing GPS never rejects, nothing silently dropped.
  - **Spreadsheet header mapping** (12 rows, header row 4, exact cell spans).
  - **Audit chain** verifies and detects tampering.
- **End-to-end checks** of every demo step against the seeded DB (API) and through the real UI (Field App step 1 in Hindi; Overview and Review Queue rendering).
- Run tooling: `Makefile`, `docker-compose.yml`, `.env.example`, `README.md`, `DEMO_SCRIPT.md`, and *Reset demo* in Settings.

## Why this test set
Each test pins one of the build prompt's non-negotiables to an executable fact. They are the regression net for the tuning surface (vocabulary, signal weights, thresholds). Replaying the seed history (ADR 0004) acts as a broader integration test, and it surfaced most of the bugs listed in ADRs 0002–0004.

## Known limits (stated, not hidden)
| Limit | Why it's acceptable for the prototype | Production path |
|---|---|---|
| CV is a stub (filename keywords + lookup) | The PS waives progress recognition; the interface is fixed | YOLOv8 fine-tuned on construction classes behind `cv_service.check` |
| Web Speech needs Chrome/Edge + network | The PS waives production ASR | On-device Whisper/IndicASR |
| Matcher weights are hand-tuned on this site | Transparent, explainable, auditable | Learn weights from `ReviewAction` labels once there are enough |
| Match-path mix stays mostly `kg_narrowed` | Known reporters always seed the KG | Measure on real multi-contractor data (see ADR 0007) |
| Aliases are global unless ordinal-scoped | Guardrails block generic/conflicting/ambiguous terms | Scope every alias to contractor/zone and expire unused ones |
| SQLite, single process | One site, one demo | Postgres + a worker for the Telegram poller |
| Claude path untested live here (no key on the build machine) | Rules path is the non-negotiable; any LLM failure falls back to rules | Enable with `ANTHROPIC_API_KEY`; validated by Pydantic + quote-span check |

## How to verify
`make test` → `20 passed`. Then run DEMO_SCRIPT.md steps 1–12 after *Reset demo*.
