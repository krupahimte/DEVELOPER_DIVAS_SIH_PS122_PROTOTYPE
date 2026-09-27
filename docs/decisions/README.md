# Decision log

One file per important step: **what we did, why, what we rejected, and how to check it.**
Newest last.

| # | Decision | Phase |
|---|---|---|
| [0001](0001-skeleton-stack-and-data-model.md) | Stack, repo layout, event-level data model, provenance map, project clock | 1 |
| [0002](0002-extraction-rules-llm-spans.md) | Rules-first extraction, Claude optional with quote→span validation, Hinglish/Devanagari | 2 |
| [0003](0003-kg-matcher-event-type-gate.md) | KG + 3-tier matcher, compatibility scores + margin, safe event_type rule, 4-number gate, one-question clarifier | 3 |
| [0004](0004-seed-history-through-real-pipeline.md) | Seed history replayed through the real pipeline; alias-learning guardrails | 1–3 |
| [0005](0005-api-live-updates-and-idempotency.md) | API surface, SSE live updates, idempotent offline delivery, raw photo bytes | 2–6 |
| [0006](0006-field-app-offline-voice-i18n.md) | Field App: simple UI, IndexedDB queue with backoff, voice, Hindi/English, WhatsApp simulator | 4 |
| [0007](0007-control-room-review-hse-charts.md) | Review queue (keyboard, spans, learning), HSE Centre, 14 charts (no dual axes), honest match-path finding | 5, 6, 8 |
| [0008](0008-enrichment-documents-dpr-memory.md) | Weather/material enrichment, xlsx/PDF/chat ingest, cited DPR, "Ask the project" | 7, 9 |
| [0009](0009-testing-verification-and-known-limits.md) | pytest suite mapped to non-negotiables, end-to-end checks, known limits | 10 |
| [0010](0010-audit-fixes.md) | Fixes from the verification audit: stop-work enforcement, multi-tab queue, field_conf persistence, weather provenance, dedup identity, Ask filtering, KPI outcome, seed determinism | audit |
