# SiteSync — demo script (≈ 8 minutes)

**Setup:** `make dev` (or run the backend and frontend commands in two terminals), then open http://localhost:5173.
Before presenting, press **Control Room → Settings → Reset demo** (≈10 s). The project date is fixed at **26 Sep 2026**.
Keep two windows side by side: **Field App** (phone size, S. Kalita) and **Control Room → Overview**.

The 🐞 button on the Field App opens the demo-only controls: *simulate offline*, *GPS quality* and *captured N hours ago*.
These are demo controls; a worker never sees them.

| # | Do | What happens (and why it matters) |
|---|---|---|
| 1 | Field App (Hindi) → **बोलकर बताएं** (hold mic) or **लिखकर बताएं**: *"Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder"* | Reply: *✅ मिल गया: Spool 3 & 4, erected, Rack B. शेड्यूल में दर्ज।* **Auto-synced** to **PIP-3-2340** as **Actual Start 26-Sep** (first event, object finished ≠ activity finished). The Control Room Gantt (Rack B) updates live over SSE. Match .99, margin ≥ .10, all four scores green. |
| 2 | 🐞 → GPS **Weak signal ±80 m**. Type *"spool erected near rack"* | Rack B and Rack C both fit (.82 / .77 → margin .05). The phone shows **one** question as big buttons: **"Rack B or Rack C?"**. Tap **Rack B** and it links (no date written: already started). |
| 3 | 🐞 → GPS back to *At my work front*, tick **Simulate offline**, set *captured 5 h ago*. Send two updates (e.g. *"Rack B supports ka kaam chal raha hai, 6 fitter"* and *"Rack B pe 10 fitter 6 welder 4 helper aaj"*; don't report spools 1–2 here, because that completes PIP-3-2340 and changes step 12) and a **Photo + note** | The header shows *"Offline: 3 reports waiting, will send automatically"* and bubbles show 📤. Untick offline and they sync (exponential backoff queue in IndexedDB). *Overview → Avg sync lag* and the **sync-lag heatmap** reflect the 5 h. |
| 4 | 🐞 → GPS **At Tank Farm**. **Photo + note** → demo photo `hydrotest_line24_gauge.jpg`, note *"Line 24 hydrotest completed"* | Writes **Actual Finish** on **PIP-3-2401 (Hydrotest line 24-P-1108)**: scope = activity ("the object is the whole line"), and photo + GPS clear the **stricter finish bar (.85)**. *(Without the photo you get one question, "Can you send a photo?". Finish claims need more evidence than starts.)* |
| 5 | 🐞 → GPS **At Rack C**. *"Welding started Rack C"* | Hot work with **no valid hot-work permit for Rack C** means **HSE hold**. A red alert banner (with a sound) appears in the Control Room. The **HSE Centre** shows *"would have matched PIP-3-2351 @ 0.89, HELD, not synced"*. |
| 6 | Field App → **सेफ्टी रिपोर्ट**: *"Near miss, sling slipped at crane CR-50T-02"* | Phone: *"Sent to HSE officer. Someone will call you."* The HSE Centre shows the item with the **verbatim** text, mishap = equipment, and a **stop-work scope prompt** (activity / zone / unit / site). Choose *zone* to see the blast radius on the map and the gated activities. **Then show enforcement:** from the phone (GPS still *At Rack C*) send *"Rack C pe spool 3 erect ho gaya"* and it is **held** (🛑 reply, no schedule write, new HSE item *work_in_stopped_zone*). **Finally Close the near-miss item** (note: *"Toolbox talk held, zone cleared"*). Otherwise later Rack C matches, such as step 8, stay held. |
| 7 | 🐞 → GPS **At Rack B**. *"Work stopped due to rain from 2pm"* | Cause recorded (weather / rain, 4 h, affects Rack B activities) with **no date written**. The seeded site weather for 26-Sep is **0 mm**, so `weather_corroborates = false`, it goes to review, and it appears red in **Weather claims vs evidence**. |
| 8 | *"Spool 5 erected"* (GPS at Rack B) | Resolves to spool 5 on Rack C (PIP-3-2341). **Material not issued** + **location conflict** send it to review. Open **Review queue**: spans highlighted, contradictions in red. Search **PIP-3-2342**, reason **Terminology**, then **Save**. Toast: *"Learned: 'spool 5' → SPL-16-1207-05"* (the crew numbers spools by erection sequence on Rack B). **Send "Spool 5 erected" again: it auto-syncs** (signal `alias`). |
| 9 | Switch user to **R. Gogoi** (landing page) or use the WhatsApp simulator: *"Laid temporary drainage near U3 gate"* | No candidate ≥ .50, so **Unplanned**, class **site_prep**, suggested parent WBS **RFX.U3.CIV.…**. *Unplanned work → Propose* exports a CSV with the **activity id left blank** (we never author ids). |
| 10 | Control Room → **DPR & uploads** → Spreadsheet → **Use sample** (`dpr_25sep_messy_headers.xlsx`) | Header row found under the title rows. **"Desc of Work"→description, "Qty Done"→quantity, "Nos"→uom, "Manpwr"→manpower**, and **12 events** created. No LLM. |
| 11 | **Generate DPR** for **13 Sep** (HTML or PDF) | A clean DPR rebuilt from events: progress, manpower, blockers with **verbatim cause text**, weather **reported vs fetched (42 mm, corroborated)**, and HSE. Every line cites **EV-n**. |
| 12 | **Ask the project**: *"Why is Rack B piping late?"*. Then **Audit trail → Verify audit chain** | A cited timeline: crane breakdown 11–12 Sep, then heavy rain 13 Sep (42 mm, corroborated), then ISO-4417 rev C awaited 16–19 Sep, then manpower shifted 22 Sep, plus *"PIP-3-2340 planned 10-Sep, actual start 26-Sep (+16 d)"*. **Verify** gives **✅ intact** (every SHA-256 link recomputed). |

## Things to point at while you talk
- **Overview → Learning curve:** aliases learned from planner decisions rise, auto-sync % rises (≈37% → ≈64%; answered questions and planner approvals are *not* counted as auto-sync) and the clarify rate falls. This comes from the real pipeline replaying 3 weeks of history, not a canned series.
- **Confidence health:** four histograms (never one blended score) plus the margin histogram with the gate line.
- **Event explorer → any event:** all 10 layers, a provenance chip on every value, and the state history with hash-chain links.
- **WhatsApp simulator** (`/field/whatsapp`): the same pipeline with `channel=whatsapp` and no GPS. Verification then relies on the reporter's assigned work front, which is enough for a start but never for a finish.

## If something goes wrong
- The history tells the story only once per reset. If you repeat a step, reset first (Settings → Reset demo).
- Voice needs Chrome/Edge with microphone permission. Otherwise use *type update*: it is the same pipeline, and `transcript_raw` is kept for voice.
