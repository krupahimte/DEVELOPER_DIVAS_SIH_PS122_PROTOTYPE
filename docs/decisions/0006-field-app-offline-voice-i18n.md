# 0006 — Field App: simple above all, offline-first, voice-first, Hindi/English

**Phase:** 4 · **Status:** accepted · **Date:** 2026-09-26

## What we did
- **React + Vite + Tailwind PWA** (manifest + hand-written service worker for the app shell). Its own layout is a phone frame on desktop and full-screen on a phone.
- **Home:** greeting with the worker's name and today's work fronts, an online/offline pill ("Offline: 3 reports waiting, will send automatically"), **four giant tiles** (Speak · Type · Photo + note · Work stopped / Problem), a **red Safety button** and *My reports*.
- **Chat (WhatsApp look):**
  - Hold-to-talk mic using the Web Speech API (`hi-IN` / `en-IN`); the transcript is sent as `transcript_raw`.
  - Bot replies in plain words with a ✏️ *Fix* button.
  - The single clarifying question renders as big tap buttons.
  - A collapsible **quick-add** (manpower steppers, equipment chips, day/night) appears after sending.
- **Problem chips:** Rain · Material not come · No permit · Machine broke · Manpower short · Drawing issue · Accident (red). Each asks one follow-up, "since what time?", then composes the sentence (Hinglish when the UI is Hindi).
- **Safety report:** voice or text plus an optional photo. Confirmation: *"Sent to HSE officer. Someone will call you."*
- **My reports:** ✅ recorded · ⏳ checking · ❓ question for you · 📤 waiting for signal · 🛑 with safety officer.
- **Offline queue** (`lib/offlineQueue.ts`, `idb`): every submission is written to IndexedDB first (`queued_at`), photos as Blobs. It flushes on `online`, every 4 s, with **exponential backoff (2ⁿ s, capped at 60 s)**.
- **All strings live in `lib/i18n.ts`.** No "activity ID", "confidence" or other jargon on any worker screen.
- **WhatsApp simulator** (`/field/whatsapp`): a phone-frame chat posting `channel="whatsapp"` with **no GPS**, including quick-reply buttons for the question.
- **Demo-only dev panel** (🐞): simulate offline, GPS quality (at a zone / weak ±80 m / none / real device) and backdated capture. The demo needs Assam coordinates from a laptop in a hall. The panel is visibly separate from the worker UI.

## Why
- Gloves, glare and weak signal mean one primary action per screen, targets ≥ 56 px, text ≥ 18 px, high contrast, and icon + word on every button.
- **Hindi as the default** because the demo supervisor's language is `hi`, with one tap to English.
- **Queue first, send second** means nothing is lost if the network drops mid-request, and `captured_at` / `queued_at` / `synced_at` are all real, which is exactly the lag metric the PS cares about.
- **Composed sentences from chips** instead of structured forms: the same extractor path handles them, the verbatim text stays human-readable in the audit trail, and there are no forms longer than three inputs.
- **Devanagari handling** (ADR 0002): Chrome's `hi-IN` writes "रैक बी…". We normalise it for extraction but keep the original.

- **Bundle split:** the Control Room (Recharts, Leaflet) is lazy-loaded, so the Field App ships **~80 KB gzipped JS** instead of ~277 KB. That matters on a cheap phone over 2G.

## Consequences / limits
- Web Speech works in Chrome/Edge (it uses Google's cloud recogniser). A production build would swap in on-device ASR. The PS waives production ASR.
- Photos taken through the browser camera may lose GPS EXIF on some phones. Files picked from the gallery keep it, and the demo photos carry EXIF (one stripped, one two months old).

## How to verify
- Open http://localhost:5173/field at phone size and send *"Rack B pe spool 3 aur 4 erect ho gaye"*: the reply comes back in Hindi in under a second.
- 🐞 → Simulate offline → send two messages → header shows *"Offline: 2 reports waiting"* → untick → both sync.
