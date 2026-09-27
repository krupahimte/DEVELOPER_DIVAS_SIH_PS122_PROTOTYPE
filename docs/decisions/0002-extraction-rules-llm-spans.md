# 0002 — Extraction: rules first, Claude optional, spans mandatory

**Phase:** 2 (Ingest + extraction) · **Status:** accepted · **Date:** 2026-09-26

## What we did
- **`extract_rules.py`** is a deterministic extractor that is the mandatory offline path. It runs sentence split → clause split → **multi-event grouping** → field extraction. Every value carries an **absolute character span** into the normalised text.
- **`vocab.py`** holds controlled vocabularies in English, romanised Hindi and Hinglish: actions (erect / *lagaya*, pour / *dhalai*, excavate / *khudai*…), event words (*ho gaye* = finish, *chal raha* = progress, *shuru* = start), blocker causes, the HSE taxonomy, permit triggers, trades and object classes.
- **`translit.py`** handles Chrome `hi-IN` voice, which writes English site words in Devanagari ("रैक बी पे स्पूल ३ …"). It is normalised with a site-word dictionary plus a phonetic fallback. The Devanagari original is kept verbatim as `transcript_raw`, and spans point into the normalised text.
- **`extract_llm.py`** calls Claude (official `anthropic` SDK, `output_config` JSON-schema structured output, model from `LLM_MODEL`, default `claude-opus-5`). It is used only when `ANTHROPIC_API_KEY` is set and LLM is enabled in Settings. The model returns a **verbatim quote** for each field and we locate the quote in the text to get the span.
- **Gazetteer:** the rule extractor is given the KG's place names (plan names, seeded aliases, *learned* aliases). A learned slang place ("north rack") therefore becomes a recognised `location_text` with a span.
- **`extraction_conf`** is computed from which parts of a clean reading were found (action, object, event word, location), capped at 0.95, and reduced when much of the vocabulary is unexplained.

## Why
- **Rules are mandatory, not a toy:** the demo must run with no key and no internet, and field sites often have neither. With rules as the baseline the LLM is an *upgrade*, never a dependency.
- **Quotes instead of offsets from the LLM:** LLMs are unreliable at character arithmetic but good at copying text. Locating the quote gives exact spans *and* a hallucination test for free: a quote that isn't in the text means the field is nulled and `extraction_conf` drops by 0.08 per dropped field (spec §4.1).
- **Any API failure → rules:** errors, timeouts, refusals and missing keys all fall back. A slow or refused LLM call must never lose a site report.
- **Multi-event grouping rules** (a new event only when a clause brings a *different* action, or a blocker after a progress clause) keep "Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder" as **one** event with manpower attached, while splitting "Spool 3 erected and welding started on spool 4" into **two**.
- **A blocker verb beats a work verb** ("Rack B spool erection *not started*"). Treating it as progress would write a false Actual Start on the very activity that is late.

## Bugs found and fixed while testing
| Symptom | Cause | Fix |
|---|---|---|
| "12 fitter 8 **welder**" created a *weld* event | action regex had no word boundary | `\b…\b` on actions; `weld` excludes "welding machine" |
| "d**rain**age" read as a rain claim | missing `\b` on cause regexes | leading `\b`, `rain\b` |
| "Near miss" became `location_text` | `near` preposition pattern | `near(?!\s+miss)` |
| "fire water line" raised a **fire incident** | naive `\bfire\b` | negative look-ahead for water / hydrant / fighting |
| "cut on hand" demanded a hot-work permit | `\bcut\b` in hot-work triggers | hot work = welding, gas/torch cutting, grinding only |
| "roof sheeting ka kaam chal raha hai" was *unparseable* | no verb, so no event | an object class plus a state word also makes an event |

## Alternatives considered
- LLM-only extraction: fails the no-key/no-internet non-negotiable.
- spaCy/NER models: heavy, English-centric, and still need the site vocabulary.

## How to verify
- `pytest -k extract` (tests in `backend/tests/`).
- In the Review Queue, highlighted spans line up with the verbatim source sentence.
