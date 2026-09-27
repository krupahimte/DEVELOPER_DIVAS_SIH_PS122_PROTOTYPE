# SiteSync: complete guide

This file explains what SiteSync is, how it works inside, how to start it, and how each kind of user uses it, screen by screen. For the 12-step demo, see [DEMO_SCRIPT.md](DEMO_SCRIPT.md). For why each design choice was made, see [docs/decisions/](docs/decisions/README.md).

---

## 1. What is SiteSync? (the one-minute version)

On a big construction project (here, a refinery expansion in Assam), the **planning schedule** lists hundreds of small jobs called **activities**, for example *"PIP-3-2340: Erect spools line 24-P-1203, Rack B"*. Each activity has a **planned** start and finish date. Planners also need the **actual** dates: when work really started and finished.

The people who know the actual dates are the **site supervisors**, and they don't fill in schedules. They send WhatsApp messages, voice notes, photos and daily report PDFs, like:

> *"Rack B pe spool 3 aur 4 erect ho gaye, 12 fitter 8 welder"*

So the schedule never learns what actually happened.

**SiteSync closes that gap.** It reads those messy messages and works out:
1. **What happened:** started, finished, still in progress, or blocked by a problem.
2. **Which activity it was about:** matched using a *knowledge graph* of the site (work areas, pipelines, drawings, crews).
3. **How sure it is:** four separate scores plus a gap between the top two guesses.

Then it does exactly one of these:

| Situation | What SiteSync does |
|---|---|
| Very sure on all counts | **Auto-syncs**: writes the actual start/finish date into the schedule |
| Unsure about one thing | Asks the worker **one** short question (e.g. *"Rack B or Rack C?"*) |
| Unsure or contradictory | Sends it to a **planner** to approve with one tap |
| Matches nothing in the plan | Marks it **unplanned work** |
| Anything about **safety** | Always goes to the **HSE (safety) officer**, never automatic |

Every value it stores remembers **where it came from** (a "provenance" tag) and points back to the **exact words** in the original message.

---

## 2. The two apps

| App | Address | Who uses it | Device |
|---|---|---|---|
| **Field App** | http://localhost:5173/field | Site supervisors, foremen | Phone (works offline) |
| **WhatsApp simulator** | http://localhost:5173/field/whatsapp | Same people, via "WhatsApp" | Phone-frame on screen |
| **Control Room** | http://localhost:5173/control | Planners, project manager, HSE officer | Laptop / big screen |

The **landing page** (http://localhost:5173) lets you pick who you are. These are demo users, so there's no password.

---

## 3. How to start it

### First time only
You need Python 3.11+ and Node 18+.

```bash
pip install -r backend/requirements.txt
```

```bash
npm --prefix frontend install
```

### Every time
Open **two terminals** in the project folder.

Terminal 1 (backend):
```bash
cd backend && python -m uvicorn app.main:app --port 8000
```

Terminal 2 (frontend):
```bash
npm --prefix frontend run dev
```

Then open **http://localhost:5173** in Chrome or Edge.

- On the very first start the backend builds the demo site by itself (about 10 seconds).
- If you have `make`: `make install` once, then `make dev`.
- **No internet or API key needed.** Everything works offline. (Optional: put `ANTHROPIC_API_KEY=...` in a `.env` file to let Claude read messages instead of the built-in rules.)

### Reset the demo
Control Room → **Settings → Reset demo**. This rebuilds all data exactly as it started. Do it before every presentation.

### Run the automated tests
```bash
cd backend && python -m pytest -q tests
```
Expected: `20 passed`.

---

## 4. The demo world (seed data)

The demo pretends **today is 26 September 2026**.

- **Site:** Units 2 and 3 of a refinery, split into **10 work areas** (geofences on a map): Rack B, Rack C, Tank Farm, Pump House, Foundations, Substation SS-2, Rack A, Compressor House, Structure ST-2 and Cooling Tower.
- **Plan:** **150 activities** across Piping, Civil, Structural, Electrical, Instrumentation and Mechanical, planned from August to October.
- **People:** supervisors such as **S. Kalita** (Piping, Rack B & C), **R. Gogoi** (Civil), **A. Sharma** (Electrical), planners **V. Iyer** and **S. Menon**, HSE officer **N. Hazarika**, and project manager **D. Choudhury**.
- **Three weeks of history** (5–25 Sep, about 260 reports) were sent through the real system, including:
  - Heavy rain on **13 Sep (42 mm)**, and a false "rain" claim on a dry day.
  - A crane breakdown, a drawing revision and a manpower shortage. These are why **Rack B piping is late**.
  - Crew slang like *"north rack"*, *"bijli ghar"*, *"naya rack"*, which the system **learned** from planner corrections.
  - Safety items (near miss, first aid, an expired confined-space permit) and unplanned work.
- **Planted problems for the demo:**
  - No hot-work permit exists for Rack C.
  - Spool 5 was never issued from the store.
  - 26 Sep is dry, so any rain claim today won't match the weather records.

Sample files to upload are in `sample_data/`: a messy Excel DPR, a DPR PDF, a Hinglish WhatsApp chat export, and 4 photos (normal, hydrotest, EXIF stripped, 2-month-old photo).

---

## 5. Field App: how a supervisor uses it

Open the landing page → **Field App** → pick a supervisor (e.g. **S. Kalita**). The app opens in **Hindi**; tap **EN** (top right) for English.

### Home screen
- **Greeting** plus today's work area (e.g. *Unit 3 · Rack B / Rack C*).
- **Green/amber bar:** online, or *"Offline: 3 reports waiting, will send automatically"*.
- Four big buttons:

| Button | What it does |
|---|---|
| 🎤 **Speak update** | Opens chat. **Hold** the mic button, speak, release: it's sent. |
| ⌨️ **Type update** | Opens chat with the keyboard. Type and press send. |
| 📷 **Photo + note** | Take or choose a photo, add a short note, send. The photo's GPS and time are kept as evidence. |
| ⛔ **Work stopped / Problem** | Tap a reason (Rain · Material not come · No permit · Machine broke · Manpower short · Drawing issue), then *"since what time?"*. That's the whole report. |

- 🛡️ **Safety report** (big red button): describe an accident, near miss or unsafe condition by voice or text, optionally with a photo. It goes **straight to the HSE officer**.
- ✅ **My reports**: today's reports with a simple status: ✅ recorded · ⏳ checking · ❓ question for you · 📤 waiting for signal · 🛑 with safety officer.

### The chat
- Your message appears on the right; SiteSync's reply appears on the left in plain words, e.g. *"✅ Got it: Spool 3 & 4, erected, Rack B. Marked in schedule."*
- If it misunderstood, tap **✏️ Fix** to resend a corrected version.
- If it needs help, it asks **one question with big buttons** (e.g. *Rack B / Rack C / Something else*). Tap one.
- After sending, you can optionally open **"Add people & machines"** to add fitters, welders, helpers and riggers with + / − buttons, equipment chips, and day/night shift.

### Works without signal
Every report is saved on the phone first. With no signal it waits (📤) and sends itself automatically when the signal returns, retrying with longer and longer gaps.

### 🐞 Demo controls (bottom-right bug button)
This panel is only for demos; real workers never see it:
- **Simulate offline:** pretend there's no signal.
- **GPS:** pretend you're standing at a particular work area, or have a weak signal, or no GPS. A laptop in a hall isn't in Assam, so this is needed.
- **Captured … hours ago:** pretend the report was written earlier (for the offline demo).

### WhatsApp simulator
Landing page → **WhatsApp simulator**. It's a WhatsApp-looking phone. Messages go into the same system as `channel = whatsapp` with **no GPS** (real WhatsApp doesn't send it). Use the **"Try"** list on the right for the demo messages, and pick who's sending from the dropdown.

---

## 6. Control Room: how planners, the HSE officer and the PM use it

Landing page → pick a planner, the PM, or the HSE officer.

**Top bar:** discipline filter, 🔔 HSE bell with the count of open safety items, sound on/off for alerts, and dark mode. When a new safety item arrives, a **red banner** flashes at the top with a beep.

### 6.1 Overview (the dashboard)
**KPI tiles:** reports today, events, **auto-sync %**, items in review, unplanned, **open HSE items**, average planner review time, and average sync lag. Click a tile to jump to its list.

**The 14 charts** (click bars, pins or nodes to open the matching events):

| # | Chart | What it tells you |
|---|---|---|
| 1 | Routing funnel | Reports → events → where each one went (auto, question, review, HSE, unplanned) |
| 2 | Planned vs actual (Gantt) | Grey = plan, colour = reality. ◆ marks the date SiteSync wrote (hover to see which message it came from); +Nd = days late; ⚠ = problems reported. Pick an area at the top right. |
| 3 | Variance by discipline | Which trades are slipping most |
| 4 | Delay causes (Pareto) | Top reasons for delays, by count or by hours lost |
| 5 | Weather claims vs evidence | "Rain" claims that weather data confirms (green) vs doesn't (red) |
| 6 | Productivity | Work done per man-hour by discipline; day vs night shift |
| 7 | Manpower & equipment | Crew size by trade per day; machines working / idle / broken |
| 8 | Confidence health | The four scores and the "top-2 gap", with the pass line |
| 9 | Match path mix | Which matching method found the activity |
| 10 | Learning curve | Words learned from planners ↑, auto-sync % ↑, questions asked ↓ |
| 11 | Sync lag heatmap | Which areas have bad signal (reports arrive hours late) |
| 12 | Channel adoption | WhatsApp vs app vs uploads per day |
| 13 | Site map | Work areas coloured by status; report pins (hollow red = sent from outside the area) |
| 14 | Field fill rate | How often each piece of information actually appears in reports |

### 6.2 Review queue (planner's main job)
The list on the left holds items waiting for a decision; the detail is on the right.

**What you see for each item:**
- The **original sentence with the understood parts highlighted** in colour. Hover a colour to see which field it became.
- Every extracted value with its **provenance chip**:

| Tag | Meaning |
|---|---|
| GIVEN | came with the message |
| EXTRACTED | read from the text |
| FETCHED | looked up, e.g. weather |
| DERIVED | calculated |
| HUMAN | set by a person |

- **Four confidence bars:** did we *read* it right, is it the right *activity*, the right *date*, is there *evidence*? Red or amber shows which one failed. The **margin** bar shows whether two activities were nearly tied.
- **Proposed write** (e.g. *Actual Start = 26-Sep for PIP-3-2340*) and **red contradiction flags** (material not issued, earlier job not finished, location conflict, old photo, weather not confirmed).
- **Top 3 candidate activities**, with green reasons, red penalties, and the knowledge-graph path.

**How to decide (keyboard or buttons):**

| Key | Action |
|---|---|
| **A** | Approve the top suggestion |
| **1 / 2 / 3** | Choose candidate 1, 2 or 3. For 2 or 3 you pick *why* the suggestion was wrong. |
| **R** | Reject |
| **U** | Mark as unplanned work |
| **J / K** | Next / previous item |
| **Enter / Esc** | Save / cancel a correction |

You can also search **any** activity in the box at the bottom to reassign.

**Teaching the system:** when you correct a match, choose a reason (*wrong area / wrong object / terminology*). SiteSync proposes the site word to learn (editable), e.g. *"spool 5"*. After saving, a toast says **"Learned: 'spool 5' → SPL-16-1207-05"**, and next time that phrase matches automatically. A timer records how many seconds each decision took.

### 6.3 HSE Centre (safety officer)
- Every safety item appears here, sorted by severity, **with the worker's exact words** (never summarised). This includes near misses, injuries, unsafe acts, and work started with a **missing or expired permit**.
- It shows what the item *would* have updated (e.g. *"would have matched PIP-3-2351 @ 0.89, HELD, not synced"*), which proves safety bypasses automation.
- **Stop-work scope:** choose activity / zone / unit / site. The map shows the affected area and lists the activities that must stop.
- **Stop-work is enforced:** while the item is open, any new report inside that scope is **held** (not synced, no schedule date written) and appears here as *"work_in_stopped_zone"*. The worker is told not to start until cleared. Reports outside the scope are unaffected. **Close** the item to lift the stop.
- **Acknowledge**, **Assign to** someone, and **Close** (a note is required).
- **Permit board:** for each work area, permits are shown as valid / expiring soon / expired / pending / **missing** (an active job needs one and none exists).

### 6.4 Unplanned work
Work that matches nothing in the plan, e.g. *"Laid temporary drainage near U3 gate"*.
- SiteSync classifies it: scope creep / missing activity / rework / site prep / emergency.
- It suggests where it belongs in the plan (**parent WBS**) and flags **change-order candidates**.
- **Link** it to an existing activity, or **Propose** a new one. **Proposals CSV** exports proposals with the activity ID left blank for the planner, because SiteSync never invents activity IDs.

### 6.5 Schedule
All 150 activities with planned and actual dates.
- Each actual date shows who set it (**DERIVED** = by SiteSync, **HUMAN** = by a planner) and a link to the **message that proved it**.
- Days of variance and a status (late / in progress / done).
- **PMIS write-back (XER CSV)** downloads the updated schedule to load back into Primavera.

### 6.6 Event explorer
Search every event, filtering by state, channel, delay cause, match method and dates. Click one to see:
- **All 10 information layers** (envelope, core, location, evidence, context, blocker, safety, resources, weather, derived). Empty layers are collapsed, which is normal.
- The full **history** of what happened to it.
- **Verify integrity**, which checks nobody tampered with the records.

### 6.7 Ask the project
Type a question in plain English:
- *"Why is Rack B piping late?"*: a dated list of causes, each linked to the original message (EV-numbers).
- *"How many rain delays in Unit 3 in September?"*: a count, hours lost, and how many weather confirms. Planner-rejected and duplicate reports are left out (add *"including rejected"* to see them). A report only counts towards a unit if its location is evidenced (text, GPS, named object, or a consistent match); reports whose unit is only a guess are listed as "not counted". The grey line under the answer lists the **filters actually applied** (they run in Python; there is no generated SQL).

Every sentence in an answer is cited, so nothing is made up.

### 6.8 DPR & uploads
- **Generate DPR:** pick a date (try **13 Sep**), optionally a discipline or area, and get a clean **Daily Progress Report** (HTML or PDF) rebuilt from the day's messages. Every line cites its source message; weather shows *reported vs measured*.
- **Upload:**
  - **Excel DPR:** messy headers like "Desc of Work", "Qty Done", "Nos" are recognised automatically, one row per event. Use **Use sample** to try it.
  - **DPR PDF / text:** split by area headings, then read line by line.
  - **WhatsApp chat export (.txt):** each message becomes a report, matched to the sender by name.

### 6.9 Audit trail
- A list of every action ever taken: reports, decisions, date writes, learned words, safety actions.
- Each entry is **chained** to the previous one with a SHA-256 hash, so changing any old record breaks the chain.
- **Verify audit chain** re-checks everything and shows ✅ intact.
- The right side lists all **words the system has learned**.

### 6.10 Settings
- **Gate thresholds (sliders):** how sure SiteSync must be before auto-syncing. Changes apply immediately to new messages.
- Question cap (1), Claude on/off, weather source (built-in site station / internet / offline), look-ahead window, enabled channels.
- **Reset demo.**

---

## 7. How it works inside (plain words)

When a message arrives:

1. **Save the original** exactly as sent (text, voice transcript, photo, file). It is never changed.
2. **Read it.** Rules that understand English, Hindi and Hinglish site talk (or Claude, if a key is set) find the work done (erect, weld, pour…), what it was done to (spool 5, line 24, foundation F-12), where, how much, who worked, and any problem or safety issue. One message can contain several **events**.
3. **Check where and what proof exists.** GPS is compared with the work-area map; a photo's GPS and date are read; old photos are flagged.
4. **Find the activity.** The knowledge graph links areas, pipelines, drawings, crews and learned words, and narrows 150 activities to a few candidates. Each candidate is scored with visible reasons, and the gap between the top two is measured.
5. **Safety check first.** Any safety issue or missing permit goes to the HSE officer, whatever the scores say.
6. **Decide what it means for the schedule** (the "safe rule"):
   - The first report on an activity sets **Actual Start**.
   - **Actual Finish** is set only when the whole activity is clearly done (all its spools, the whole line tested…) and there's strong proof, such as a photo or GPS.
   - Problems record the **cause only**, never a date.
7. **The gate.** Four scores must *all* pass (reading, matching, date, evidence) and the top-2 gap must be wide. Otherwise SiteSync asks one question, or sends the item to the planner, or marks it unplanned.
8. **Enrich:** compare rain claims with weather records, and check the store issued the material.
9. **Record everything** in the tamper-proof audit chain and update the Control Room live.
10. **Learn.** Planner corrections become new "words" in the knowledge graph, so the system improves every week.

---

## 8. Glossary

| Term | Meaning |
|---|---|
| **Activity** | One job in the plan (L5/L6), e.g. PIP-3-2340 |
| **Event** | One fact from a message; one message can hold several |
| **Actual start / finish** | The real dates SiteSync writes back to the schedule |
| **Work front / geofence** | A work area drawn on the map (e.g. Rack B) |
| **Knowledge graph (KG)** | The web of links between areas, lines, drawings, crews, activities and learned words |
| **Alias** | A site word learned from planners (e.g. "north rack" = Rack B) |
| **Four confidences** | Extraction (read right?), match (right activity?), date (right day?), verification (evidence?) |
| **Margin** | Score gap between the best and second-best activity; small means a coin flip |
| **Provenance** | Where a value came from: GIVEN / EXTRACTED / FETCHED / DERIVED / HUMAN |
| **HSE** | Health, Safety & Environment |
| **Permit (PTW)** | Permission for risky work: hot work (welding), confined space, height, excavation… |
| **DPR** | Daily Progress Report |
| **WBS** | Work Breakdown Structure: where an activity sits in the plan hierarchy |
| **XER** | Primavera schedule export format; SiteSync reads and writes a CSV version |

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| Page is blank or "Loading…" forever | Check the backend terminal is running on port 8000 |
| Mic does nothing | Use Chrome or Edge and allow microphone access, or just type; it's the same system |
| Demo steps behave differently than the script | Something was already sent. **Settings → Reset demo**, then clear old chat with a hard refresh |
| Map tiles are grey | No internet. Work areas and pins still show; only the background map needs internet |
| Want the real AI reader | Add `ANTHROPIC_API_KEY` to `.env` and restart the backend |

---

## 10. Where things are in the code

```
backend/app/pipeline/   the brain: reading, matching, gate, safety, learning, audit, DPR, Ask
backend/app/api/        the web endpoints the two apps call
backend/app/seed/       the demo site and its 3-week history
backend/tests/          20 automated tests
frontend/src/field/     Field App + WhatsApp simulator
frontend/src/control/   Control Room pages
sample_data/            files to upload in the demo
docs/decisions/         why every design choice was made
DEMO_SCRIPT.md          the 12-step presentation
```
