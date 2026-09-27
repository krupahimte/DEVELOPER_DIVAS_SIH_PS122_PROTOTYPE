"""Rule-based extractor — the mandatory offline fallback (no key, no internet).

Pipeline: sentence split → clause split → multi-event grouping → field extraction.
Every value carries an absolute span into the input text, so the Review Queue can
highlight exactly where it came from.
"""
import re
from datetime import date, timedelta

from . import vocab
from .schema import ExtractedEvent

I = re.IGNORECASE


def _alt(patterns, b=False):
    body = "(?:" + "|".join(patterns) + ")"
    return re.compile(r"\b" + body + r"\b" if b else body, I)


ACTION_RX = {k: _alt(v, b=True) for k, v in vocab.ACTIONS.items()}
EVENT_RX = {k: _alt(v) for k, v in vocab.EVENT_WORDS.items()}
ACT_FINISH_RX = _alt(vocab.ACTIVITY_LEVEL_FINISH)
BLOCKER_RX = _alt(vocab.BLOCKER_WORDS)
CAUSE_RX = {(c, sub): re.compile(r"\b(?:" + "|".join(p) + ")", I) for c, subs in vocab.CAUSES.items() for sub, p in subs.items()}
HSE_RX = {k: _alt(v) for k, v in vocab.HSE_TYPES.items()}
STOP_WORK_RX = _alt(vocab.STOP_WORK)
MISHAP_RX = {k: _alt(v) for k, v in vocab.MISHAP.items()}
OBJ_RX = {k: _alt(v) for k, v in vocab.OBJECT_CLASSES.items()}
TRADE_RX = re.compile(r"(\d{1,3})\s*(?:nos?\.?\s*)?(" + "|".join(f"(?P<{k}>{v})" for k, v in vocab.TRADES.items()) + r")\b", I)
EQUIP_RX = {k: re.compile(v, I) for k, v in vocab.EQUIP_WORDS.items()}

LINE_FULL = re.compile(r"\b(\d{1,2})\s*[\"”]?\s*-\s*([A-Z]{1,3})\s*-\s*(\d{3,5})\b", I)
LINE_PART = re.compile(r"\bline\s*(?:no\.?\s*)?(\d{1,2})\b(?!\s*[\"”]?\s*-\s*[A-Z])", I)
SPOOL_ID = re.compile(r"\bSPL-\d{1,2}-\d{3,5}-\d{2}\b", I)
SPOOL_ORD = re.compile(r"\bspools?\s*(?:no\.?\s*|number\s*|#\s*)?(\d{1,2}(?:\s*(?:,|&|and|aur|\+|/|to)\s*\d{1,2})*)", I)
FDN = re.compile(r"\b(?:foundation\s+|footing\s+)?F\s*-\s*(\d{1,2})\b", I)
TAG = re.compile(r"\b((?:P|K|TR|T)-\d{3}[A-Z]?|CR-\d{2}T-\d{2}|HY-\d{2}T-\d{2}|EX-\d{2}T-\d{2})\b", I)
TRAY = re.compile(r"\btray\s*(?:no\.?\s*)?T\s*-?\s*(\d)\b", I)
LOOP = re.compile(r"\bloop\s*(?:no\.?\s*)?(?:check\s+)?L\s*-?\s*(\d{3})\b|\bL-(\d{3})\b", I)
DRAWING = re.compile(r"\bISO[\s-]?(\d{4})\b", I)
PERMIT_ID = re.compile(r"\bPTW-[A-Z0-9-]+\b", I)
WORD_RACK = re.compile(r"\b(?!pipe\b|the\b|on\b|at\b|near\b)([a-z]{3,})\s+rack\b(?!\s*-?\s*[A-D]\b)", I)
RACK = re.compile(r"\b(?:pipe\s*)?rack\s*-?\s*([A-D])\b", I)
UNIT = re.compile(r"\b(?:unit|U)\s*-?\s*([23])\b", I)
ELEV = re.compile(r"\bEL\s*[+-]?\s*\d+(?:\.\d+)?\s*m?\b", I)
NEAR = re.compile(r"\b(?:near(?!\s+miss)|at|inside|beside|behind|opposite)\s+(?:the\s+)?([A-Za-z0-9][\w\-]*(?:\s+[A-Za-z0-9][\w\-]*){0,3}?)(?=\s*(?:[,.;!]|$|\bpe\b|\bmein\b|\bfor\b|\bdue\b|\bfrom\b|\bsince\b|\bwith\b|\btoday\b|\bby\b))", I)
QTY = re.compile(r"\b(\d+(?:\.\d+)?)\s*(" + vocab.UOM + r")(?![\w])", I)
MANPOWER_TOTAL = re.compile(r"\b(?:manpower|man\s*power|log)\s*[:\-]?\s*(\d{1,3})\b|\b(\d{1,3})\s+(?:manpower|people|persons|log)\b", I)
MANHOURS = re.compile(r"\b(\d{1,4})\s*(?:man[\s-]?hours|manhours|mh)\b", I)
NIGHT = re.compile(r"\b(?:night(?:\s+shift)?|raat)\b", I)
DAY_SHIFT = re.compile(r"\bday\s+shift\b|\bdin\s+(?:ki\s+)?shift\b", I)
CEMENT = re.compile(r"\b(\d+)\s*bags?\s*(?:of\s+)?cement\b", I)
ELECTRODE = re.compile(r"\b(\d+(?:\.\d+)?)\s*kg\s*(?:of\s+)?electrodes?\b", I)
CONCRETE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:m3|cum|cu\.?\s?m)\s*(?:of\s+)?(?:concrete|rmc)?", I)
HOURS_LOST = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:hrs?|hours?|ghante|ghanta)\b", I)
FROM_TIME = re.compile(r"\b(?:from|since|se)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje)?(?:\s*(?:to|till|until|tak|-)\s*(\d{1,2})(?::\d{2})?\s*(am|pm|baje)?)?", I)
DATE_EXPL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-/.]*(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?(?:[\s\-/.,]*(\d{2,4}))?\b", I)
DATE_NUM = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b")
REL_DATES = [(re.compile(r"\bday\s+before\s+yesterday\b|\bparso\b", I), -2, 0.8),
             (re.compile(r"\byesterday\b|\bkal\s+raat\b", I), -1, 0.9),
             (re.compile(r"\bkal\b", I), -1, 0.7),
             (re.compile(r"\btoday\b|\baaj\b|\btonight\b", I), 0, 0.92)]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
GAS_TEST = re.compile(r"gas\s+test\s+(done|ok|completed|not\s+done|pending|nahi)", I)

DOC_HEADER = re.compile(r"\s*(?:project|date|reporter|contractor|client|report\s+no|dpr\s+no|prepared\s+by)\s*:", I)
SENT_SPLIT = re.compile(r"(?<!\bno)(?<!\bNo)[.!?।](?!\d)|\n+")
CLAUSE_SPLIT = re.compile(r",|;|\s+(?:and\s+then|then|also|and|aur|tatha|phir|but|lekin)\s+", I)
HINGLISH = re.compile(r"\b(?:pe|mein|ho\s+gay[aei]|kiya|aur|nahi|hai|tha|the|wala|raha|baje|kal|aaj|ka|ki)\b", I)


def _first(rx, text, s, e):
    return rx.search(text, s, e)


def detect_language(text: str) -> str:
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    hits = len(HINGLISH.findall(text))
    return "hi-en" if hits >= 1 else "en"


def split_sentences(text: str):
    """Yield (start, end) spans of sentences, trimmed."""
    pos = 0
    for m in SENT_SPLIT.finditer(text):
        yield from _trim(text, pos, m.start())
        pos = m.end()
    yield from _trim(text, pos, len(text))


def _trim(text, s, e):
    while s < e and text[s] in " \t\r\n-•*":
        s += 1
    while e > s and text[e - 1] in " \t\r\n":
        e -= 1
    if e - s >= 2:
        yield (s, e)


def _heads(text, s, e):
    """Which kinds of 'head' cue a clause contains."""
    has_action = any(rx.search(text, s, e) for rx in ACTION_RX.values())
    has_block = bool(BLOCKER_RX.search(text, s, e))
    has_hse = any(rx.search(text, s, e) for rx in HSE_RX.values()) or bool(STOP_WORK_RX.search(text, s, e))
    return has_action, has_block, has_hse


def group_events(text, s, e):
    """Split one sentence into event-sized clause groups (multi-event split)."""
    cuts = [s]
    for m in CLAUSE_SPLIT.finditer(text, s, e):
        cuts.append(m.start())
        cuts.append(m.end())
    cuts.append(e)
    chunks = [(cuts[i], cuts[i + 1]) for i in range(0, len(cuts), 2) if cuts[i + 1] - cuts[i] > 1]
    groups = []   # [start, end, kind]
    for cs, ce in chunks:
        a, b, h = _heads(text, cs, ce)
        kind = "hse" if h else ("block" if b else ("act" if a else None))
        if not groups:
            groups.append([cs, ce, kind])
            continue
        g = groups[-1]
        new = False
        if kind == "act" and g[2] == "act":
            # "spool 3 erected, welding started on spool 4" → two events when the action differs
            act_prev = {k for k, rx in ACTION_RX.items() if rx.search(text, g[0], g[1])}
            act_now = {k for k, rx in ACTION_RX.items() if rx.search(text, cs, ce)}
            new = not (act_now & act_prev)
        elif kind == "block" and g[2] == "act":
            new = not bool(re.search(r"^\s*(?:due|because|kyunki|as)\b", text[cs:ce], I))
        elif kind == "act" and g[2] == "block":
            new = True
        elif kind == "hse" and g[2] in ("act",):
            new = True
        if new:
            groups.append([cs, ce, kind])
        else:
            g[1] = ce
            if g[2] is None or (kind == "hse"):
                g[2] = kind or g[2]
    return [(g[0], g[1]) for g in groups]


def _ordinals(raw: str):
    nums = []
    for m in re.finditer(r"(\d{1,2})\s*to\s*(\d{1,2})", raw):
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < b - a < 20:
            nums += list(range(a, b + 1))
    nums += [int(n) for n in re.findall(r"\d{1,2}", re.sub(r"\d{1,2}\s*to\s*\d{1,2}", "", raw))]
    return sorted(set(nums))


def _hour(h, ampm):
    h = int(h)
    if ampm and ampm.lower() == "pm" and h < 12:
        h += 12
    if (not ampm or ampm.lower() == "baje") and 1 <= h <= 6:
        h += 12      # "2 baje" on site means 2 pm
    return h


def extract(text: str, reporting_date: date, section_of=None, gazetteer: list[str] | None = None) -> list[ExtractedEvent]:
    """Extract events from normalised text.

    `section_of(pos)` optionally returns a DPR section heading.
    `gazetteer` = known place names from the KG (work-front names + aliases, incl. learned ones), so a
    location like "pump house" or a learned "north rack" is recognised with a span.
    """
    lang = detect_language(text)
    events: list[ExtractedEvent] = []
    gaz = None
    if gazetteer:
        gaz = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(g) for g in sorted(set(gazetteer), key=len, reverse=True)) + r")(?![a-z0-9])", I)
    for ss, se in split_sentences(text):
        if DOC_HEADER.match(text, ss):
            continue                    # "Project: … Date: … Reporter: …" — document metadata, not a field event
        for s, e in group_events(text, ss, se):
            ev = _extract_one(text, s, e, reporting_date, lang)
            if ev is None:
                continue
            if gaz and not ev.location_text:
                m = gaz.search(text, s, e)
                if m:
                    ev.location_text = m.group(0)
                    ev.spans["location_text"] = m.span()
                    ev.extraction_conf = round(min(0.95, ev.extraction_conf + 0.05), 3)
            ev.sentence = text[ss:se]
            ev.sentence_span = (ss, se)
            if section_of:
                ev.document_section = section_of(ss)
            events.append(ev)
    return events


def _extract_one(text, s, e, rdate, lang):
    ev = ExtractedEvent(sentence=text[s:e], sentence_span=(s, e), input_language=lang)
    sp = ev.spans
    clause = text[s:e]

    # ── action (first match by position) ──
    best = None
    for k, rx in ACTION_RX.items():
        m = rx.search(text, s, e)
        if m and (best is None or m.start() < best[1].start()):
            best = (k, m)
    if best:
        ev.action = best[0]
        sp["action"] = best[1].span()
        # "loop check" / "hydrotest" imply test; "cable pulling" → pull
        if ev.action == "test":
            ev.object_class = "loop" if re.search(r"loop", clause, I) else ev.object_class

    # ── event type words ──
    for et in ("start", "progress", "finish"):
        m = EVENT_RX[et].search(text, s, e)
        if m:
            ev.object_event_type = et
            sp["object_event_type"] = m.span()
            break
    if ACT_FINISH_RX.search(text, s, e):
        ev.activity_level_finish = True
        if ev.object_event_type in (None, "progress"):
            ev.object_event_type = "finish"

    # ── objects ──
    m = LINE_FULL.search(text, s, e)
    if m:
        ev.line_ref = f"{m.group(1)}-{m.group(2).upper()}-{m.group(3)}"
        sp["line_ref"] = m.span()
    else:
        m = LINE_PART.search(text, s, e)
        if m:
            ev.line_ref = m.group(1)
            sp["line_ref"] = m.span()
    for m in SPOOL_ID.finditer(text, s, e):
        ev.object_refs.append(m.group(0).upper())
        sp.setdefault("object_refs", m.span())
    m = SPOOL_ORD.search(text, s, e)
    if m:
        ev.object_ordinals = _ordinals(m.group(1))
        ev.object_qualifier = m.group(0).strip()
        ev.object_class = "spool"
        sp["object_qualifier"] = m.span()
    m = FDN.search(text, s, e)
    if m:
        ev.object_refs.append(f"FDN-F-{int(m.group(1))}")
        ev.object_class = ev.object_class or "foundation"
        ev.object_qualifier = ev.object_qualifier or m.group(0)
        sp.setdefault("object_refs", m.span())
        sp.setdefault("object_qualifier", m.span())
    for m in TAG.finditer(text, s, e):
        ev.object_refs.append(m.group(1).upper())
        sp.setdefault("object_refs", m.span())
    m = TRAY.search(text, s, e)
    if m:
        ev.object_refs.append(f"TRAY-T-{m.group(1)}")
        ev.object_qualifier = ev.object_qualifier or m.group(0)
        sp.setdefault("object_refs", m.span())
        sp.setdefault("object_qualifier", m.span())
    m = LOOP.search(text, s, e)
    if m:
        ev.object_refs.append(f"LOOP-L-{m.group(1) or m.group(2)}")
        ev.object_class = "loop"
        sp.setdefault("object_refs", m.span())
    m = DRAWING.search(text, s, e)
    if m:
        ev.drawing_no = f"ISO-{m.group(1)}"
        sp["drawing_no"] = m.span()
    if not ev.object_class or ev.object_class == "line":
        best = None
        for k, rx in OBJ_RX.items():
            mm = rx.search(text, s, e)
            if mm and (best is None or mm.start() < best[1].start()):
                best = (k, mm)
        if best:
            ev.object_class = best[0]
            sp["object_class"] = best[1].span()
    elif "object_class" not in sp and "object_qualifier" in sp:
        sp["object_class"] = sp["object_qualifier"]
    if ev.line_ref and not ev.object_class:
        ev.object_class = "line"

    # ── location ──
    locs = []
    for rx in (RACK, WORD_RACK, UNIT, ELEV):
        for m in rx.finditer(text, s, e):
            locs.append(m)
    m = NEAR.search(text, s, e)
    if m:
        locs.append(m)
    if locs:
        locs.sort(key=lambda m: m.start())
        # prefer the most specific (rack / near-phrase) over "Unit 3"
        pick = next((m for m in locs if not UNIT.fullmatch(m.group(0))), locs[0])
        g = pick.group(0)
        if RACK.fullmatch(g):
            ev.location_text = f"Rack {pick.group(1).upper()}"
            sp["location_text"] = pick.span()
        elif pick.re is NEAR:
            ev.location_text = pick.group(1).strip()          # drop the preposition: "at F-12" → "F-12"
            sp["location_text"] = pick.span(1)
        else:
            ev.location_text = g.strip()
            sp["location_text"] = pick.span()
        units = [m for m in locs if UNIT.fullmatch(m.group(0))]
        if units and pick is not units[0]:
            ev.location_text += f", Unit {units[0].group(1)}"

    # ── quantity (skip manpower numbers and spool ordinals) ──
    for m in QTY.finditer(text, s, e):
        tail = text[m.end():m.end() + 14].lower()
        if TRADE_RX.match(text, m.start()) or re.match(r"\s*(fitter|welder|helper|rigger|mason|labou?r|worker)", tail):
            continue
        if "object_qualifier" in sp and sp["object_qualifier"][0] <= m.start() < sp["object_qualifier"][1]:
            continue
        ev.quantity = float(m.group(1))
        ev.uom = re.sub(r"\s+", "", m.group(2).lower()).replace("cum", "m3").replace("cu.m", "m3").replace("cum", "m3")
        sp["quantity"] = m.span(1)
        sp["uom"] = m.span(2)
        break
    if ev.quantity is None and ev.object_ordinals:
        ev.quantity, ev.uom = float(len(ev.object_ordinals)), "nos"

    # ── resources ──
    mp = {}
    first_mp = None
    for m in TRADE_RX.finditer(text, s, e):
        trade = next(k for k in vocab.TRADES if m.group(k))
        mp[trade] = mp.get(trade, 0) + int(m.group(1))
        first_mp = first_mp or m.start()
        sp["manpower_by_trade"] = (first_mp, m.end())
    if mp:
        ev.manpower_by_trade = mp
        ev.manpower_total = sum(mp.values())
    m = MANPOWER_TOTAL.search(text, s, e)
    if m and not mp:
        ev.manpower_total = int(m.group(1) or m.group(2))
        sp["manpower_total"] = m.span()
    m = MANHOURS.search(text, s, e)
    if m:
        ev.manhours = float(m.group(1))
        sp["manhours"] = m.span()
    if NIGHT.search(text, s, e):
        ev.shift = "night"
        sp["shift"] = NIGHT.search(text, s, e).span()
    elif DAY_SHIFT.search(text, s, e):
        ev.shift = "day"
        sp["shift"] = DAY_SHIFT.search(text, s, e).span()
    eq = []
    for k, rx in EQUIP_RX.items():
        m = rx.search(text, s, e)
        if m:
            eq.append(k)
            sp.setdefault("equipment_deployed", m.span())
    for ref in list(ev.object_refs):
        if re.match(r"(CR|HY|EX)-", ref):
            eq.append(ref)
            ev.object_refs.remove(ref)
    ev.equipment_deployed = sorted(set(eq))
    if re.search(r"\bidle\b", clause, I) and eq:
        ev.equipment_idle_flag = True
    if eq and re.search(r"break\s*down|broke|kharab|not\s+working|hydraulic", clause, I):
        ev.equipment_breakdown = True
    mc = {}
    for rx, key in ((CEMENT, "cement_bags"), (ELECTRODE, "electrode_kg")):
        m = rx.search(text, s, e)
        if m:
            mc[key] = float(m.group(1))
            sp.setdefault("material_consumed", m.span())
    if ev.action == "pour" and ev.uom == "m3":
        mc["concrete_m3"] = ev.quantity
    ev.material_consumed = mc

    # ── blocker ──
    bm = BLOCKER_RX.search(text, s, e)
    cause = None
    for (cat, sub), rx in CAUSE_RX.items():
        m = rx.search(text, s, e)
        if m and (cause is None or m.start() < cause[2].start()):
            cause = (cat, sub, m)
    if bm and cause or (cause and cause[0] in ("weather", "material", "manpower", "power", "access", "client_hold") and not ev.action):
        ev.blocker_flag = True
        ev.cause_category, ev.cause_subcategory = cause[0], cause[1]
        sp["cause_category"] = cause[2].span()
        ev.cause_text = clause.strip()
        sp["cause_text"] = (s, e)
        ev.object_event_type = "none"
        sp.pop("object_event_type", None)
        if cause[0] == "material":
            ev.material_shortage_flag = True
        if cause[0] == "equipment":
            ev.equipment_breakdown = ev.equipment_breakdown or cause[1] == "breakdown"
            ev.equipment_idle_flag = ev.equipment_idle_flag or cause[1] == "idle"
    elif bm:
        # "Rack B spool erection not started / on hold" — a blocker even when a work verb is present
        ev.blocker_flag = True
        ev.cause_text = clause.strip()
        sp["cause_text"] = (s, e)
        ev.object_event_type = "none"
    if ev.blocker_flag:
        m = HOURS_LOST.search(text, s, e)
        if m:
            ev.time_lost_h = float(m.group(1))
            sp["time_lost_h"] = m.span()
        m = FROM_TIME.search(text, s, e)
        if m:
            h0 = _hour(m.group(1), m.group(3))
            h1 = _hour(m.group(4), m.group(5)) if m.group(4) else 18
            if 5 <= h0 < h1 <= 24:
                ev.time_window = (h0, h1)
                if ev.time_lost_h is None:
                    ev.time_lost_h = float(h1 - h0)
                    sp["time_lost_h"] = m.span()
        if ev.time_lost_h is None and re.search(r"whole\s+day|full\s+day|pura\s+din", clause, I):
            ev.time_lost_h = 8.0
    # weather claim (can appear without being a blocker, e.g. "light rain, work continued")
    m = CAUSE_RX[("weather", "rain")].search(text, s, e) or CAUSE_RX[("weather", "heat")].search(text, s, e) \
        or CAUSE_RX[("weather", "wind")].search(text, s, e)
    if m:
        w_end = e
        tm = FROM_TIME.search(text, m.start(), e)
        if tm:
            w_end = tm.end()
        else:
            w_end = min(e, m.end() + 12)
        ev.weather_reported = text[m.start():w_end].strip(" ,.")
        sp["weather_reported"] = (m.start(), m.start() + len(ev.weather_reported))

    # ── HSE ──
    for k, rx in HSE_RX.items():
        m = rx.search(text, s, e)
        if m:
            if k == "property_damage" and not re.search(r"crane|sling|equipment|structure|pipe|drop", clause, I):
                continue
            ev.hse_event_flag = True
            ev.hse_event_type = ev.hse_event_type or k
            ev.hse_severity = vocab.HSE_SEVERITY.get(ev.hse_event_type, "observation")
            sp.setdefault("hse_event_type", m.span())
    m = STOP_WORK_RX.search(text, s, e)
    if m:
        ev.stop_work_flag = True
        ev.hse_event_flag = True
        sp["stop_work_flag"] = m.span()
    if ev.hse_event_type in ("near_miss", "first_aid", "lti", "property_damage", "fire", "spill", "gas_release"):
        for k, rx in MISHAP_RX.items():
            if rx.search(text, s, e):
                ev.mishap_flag = True
                ev.mishap_category = k
                break
    if re.search(r"rework|re-?weld|redo|dobara", clause, I):
        ev.rework_triggered = True
    m = re.search(r"(?:no|without)\s+(?:valid\s+)?permit|permit\s+(?:not|nahi)", clause, I)
    if m:
        ev.permit_status = "missing"
        sp["permit_status"] = (s + m.start(), s + m.end())
    m = re.search(r"permit\s+(?:has\s+)?expired|expired\s+permit", clause, I)
    if m:
        ev.permit_status = "expired"
        sp["permit_status"] = (s + m.start(), s + m.end())
    m = PERMIT_ID.search(text, s, e)
    if m:
        ev.permit_id = m.group(0).upper()
        sp["permit_id"] = m.span()
    m = GAS_TEST.search(text, s, e)
    if m:
        ev.gas_test_done = not re.search(r"not|pending|nahi", m.group(1), I)
        sp["gas_test_done"] = m.span()

    # ── date ──
    ev.event_date, ev.date_conf = rdate, 0.85
    m = DATE_EXPL.search(text, s, e)
    if m:
        try:
            y = int(m.group(3)) if m.group(3) else rdate.year
            y = y + 2000 if y < 100 else y
            ev.event_date = date(y, MONTHS[m.group(2).lower()[:3]], int(m.group(1)))
            ev.date_conf, ev.date_explicit = 0.95, True
            sp["event_date"] = m.span()
        except ValueError:
            pass
    if not ev.date_explicit:
        for rx, delta, conf in REL_DATES:
            m = rx.search(text, s, e)
            if m:
                ev.event_date = rdate + timedelta(days=delta)
                ev.date_conf, ev.date_explicit = conf, True
                sp["event_date"] = m.span()
                break

    # ── is there an event at all? ──
    has_resource = bool(ev.manpower_total or ev.equipment_deployed or ev.material_consumed)
    has_state_word = "object_event_type" in sp or bool(re.search(r"\bwork\s+in\s+progress\b|\bkaam\b", clause, I))
    if not (ev.action or ev.blocker_flag or ev.hse_event_flag or has_resource or ev.object_refs or ev.line_ref
            or (ev.object_class and has_state_word)):
        return None
    if ev.object_event_type is None:
        ev.object_event_type = "progress" if ev.action else "none"

    # ── extraction confidence ──
    conf = 0.55
    if ev.action:
        conf += 0.15
    if ev.object_refs or ev.object_ordinals or ev.line_ref or ev.drawing_no:
        conf += 0.12
    elif ev.object_class:
        conf += 0.06
    if "object_event_type" in sp or ev.activity_level_finish:
        conf += 0.06
    if ev.location_text:
        conf += 0.05
    if ev.blocker_flag and ev.cause_category:
        conf = max(conf, 0.88)
    if ev.hse_event_flag:
        conf = max(conf, 0.9)
    if not ev.action and not ev.blocker_flag and not ev.hse_event_flag:
        conf = min(conf, 0.6)
    # unexplained vocabulary lowers confidence
    toks = re.findall(r"[A-Za-z]+", clause.lower())
    known = sum(1 for t in toks if t in vocab.STOPWORDS or any(rx.search(t) for rx in ACTION_RX.values()) or len(t) <= 2)
    if toks and known / len(toks) < 0.25 and len(toks) > 5:
        conf -= 0.08
    ev.extraction_conf = round(min(conf, 0.95), 3)
    return ev
