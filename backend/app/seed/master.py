"""Master data for the demo project: an Assam refinery expansion (Units 2 & 3).

Everything here is *plan-side* truth: work fronts, lines/drawings, the L5/L6
activity list (written out as the XER-like CSV), reporters, permits, store issues,
equipment and seeded site weather. Field events are generated separately in
`history.py` and pushed through the real pipeline.

A few activities are *reserved for the live demo* (see DEMO_SCRIPT.md) and must not
receive any history events: see RESERVED.
"""
from datetime import date, datetime, timedelta

D = date.fromisoformat

PROJECT = {
    "id": "RFX-ASM",
    "name": "Refinery Expansion — Assam (Units 2 & 3)",
    "lat": 27.47, "lon": 95.34,
}

# ───────────────────────────── work fronts / geofences ─────────────────────────────
# Rectangles (lat0, lat1, lon0, lon1). ~0.0006° lat ≈ 65 m.
WORK_FRONTS = [
    # id,                name,               unit,     area,            box,                                   aliases (seeded, plan-side)
    ("WF-U3-RACK-B", "Rack B",            "Unit 3", "Pipe Racks",    (27.4740, 27.4746, 95.3370, 95.3380), ["rack b", "rack-b", "pipe rack b", "rackb"]),
    ("WF-U3-RACK-C", "Rack C",            "Unit 3", "Pipe Racks",    (27.4740, 27.4746, 95.3381, 95.3391), ["rack c", "rack-c", "pipe rack c", "rackc"]),
    ("WF-U3-FDN",    "Foundations F-10–F-14", "Unit 3", "Civil Area", (27.4730, 27.4737, 95.3370, 95.3382), ["foundation area", "fdn area"]),
    ("WF-U3-PUMP",   "Pump House",        "Unit 3", "Pump House",    (27.4730, 27.4736, 95.3385, 95.3395), ["pump house", "pumphouse"]),
    ("WF-U3-TANK",   "Tank Farm",         "Unit 3", "Tank Farm",     (27.4748, 27.4756, 95.3370, 95.3385), ["tank farm", "tankfarm", "tank area"]),
    ("WF-U2-SUBSTN", "Substation SS-2",   "Unit 2", "Substation",    (27.4660, 27.4666, 95.3410, 95.3420), ["substation", "ss-2", "ss2", "sub station"]),
    ("WF-U2-RACK-A", "Rack A",            "Unit 2", "Pipe Racks",    (27.4668, 27.4674, 95.3410, 95.3425), ["rack a", "rack-a", "pipe rack a"]),
    ("WF-U2-COMP",   "Compressor House",  "Unit 2", "Compressor House", (27.4660, 27.4666, 95.3423, 95.3433), ["compressor house", "comp house"]),
    ("WF-U2-STRUCT", "Structure ST-2",    "Unit 2", "Structures",    (27.4652, 27.4658, 95.3410, 95.3422), ["st-2", "structure st-2", "st2"]),
    ("WF-U2-CT",     "Cooling Tower",     "Unit 2", "Cooling Tower", (27.4652, 27.4658, 95.3425, 95.3437), ["cooling tower", "ct basin"]),
]

# Site slang that is NOT in the plan. The history generator uses these in week 1;
# planner corrections turn them into learned aliases so weeks 2-3 auto-sync.
SLANG = {
    "north rack": ("work_front", "WF-U3-RACK-B"),
    "cw line": ("line", "24-P-1203"),
    "bijli ghar": ("work_front", "WF-U2-SUBSTN"),
    "compressor shed": ("work_front", "WF-U2-COMP"),
    "steam line": ("line", "18-P-2101"),
    "tanki area": ("work_front", "WF-U3-TANK"),
}


def polygon(box):
    lat0, lat1, lon0, lon1 = box
    return [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]


# ───────────────────────────── lines / drawings / systems ──────────────────────────
LINES = [
    # line_no,     drawing,   system,              unit,     spools: {ordinal: work_front}
    ("24-P-1203", "ISO-4417", "Cooling Water",       "Unit 3", {1: "WF-U3-RACK-B", 2: "WF-U3-RACK-B", 3: "WF-U3-RACK-B", 4: "WF-U3-RACK-B", 5: "WF-U3-RACK-C", 6: "WF-U3-RACK-C"}),
    ("16-P-1207", "ISO-4421", "Process Water",       "Unit 3", {i: "WF-U3-RACK-B" for i in range(1, 6)}),
    ("12-P-1215", "ISO-4430", "Instrument Air",      "Unit 3", {i: "WF-U3-RACK-C" for i in range(1, 5)}),
    ("8-P-1220",  "ISO-4433", "Fire Water",          "Unit 3", {i: "WF-U3-RACK-C" for i in range(1, 4)}),
    ("24-P-1108", "ISO-4402", "Cooling Water Return", "Unit 3", {i: "WF-U3-TANK" for i in range(1, 6)}),
    ("10-P-1301", "ISO-4502", "Condensate",          "Unit 3", {i: "WF-U3-PUMP" for i in range(1, 4)}),
    ("18-P-2101", "ISO-5101", "Steam",               "Unit 2", {i: "WF-U2-RACK-A" for i in range(1, 6)}),
    ("14-P-2110", "ISO-5110", "Fuel Gas",            "Unit 2", {i: "WF-U2-RACK-A" for i in range(1, 5)}),
    ("12-P-2120", "ISO-5120", "Plant Air",           "Unit 2", {i: "WF-U2-COMP" for i in range(1, 4)}),
]


def spool_id(line_no: str, n: int) -> str:
    size, _, num = line_no.split("-")
    return f"SPL-{size}-{num}-{n:02d}"


CONTRACTORS = [
    ("C-LTH", "L&T Hydrocarbon", "Pkg-4 Piping", ["Piping"]),
    ("C-BCW", "Brahmaputra Civil Works", "Pkg-1 Civil", ["Civil"]),
    ("C-NEE", "NE Electricals & Instruments", "Pkg-6 E&I", ["Electrical", "Instrumentation"]),
    ("C-KST", "Kaziranga Structurals", "Pkg-2 Structural", ["Structural"]),
    ("C-DMX", "Delta Mech Erectors", "Pkg-5 Mechanical", ["Mechanical"]),
]
DISC_CONTRACTOR = {d: c[0] for c in CONTRACTORS for d in c[3]}

REPORTERS = [
    # id, name, name_hi, role, discipline, contractor, work_fronts, language
    ("R-KALITA", "S. Kalita", "एस. कलिता", "supervisor", "Piping", "C-LTH", ["WF-U3-RACK-B", "WF-U3-RACK-C"], "hi"),
    ("R-BORA", "M. Bora", "एम. बोरा", "foreman", "Piping", "C-LTH", ["WF-U3-TANK", "WF-U3-PUMP"], "hi"),
    ("R-KONWAR", "T. Konwar", "टी. कोंवर", "supervisor", "Piping", "C-LTH", ["WF-U2-RACK-A", "WF-U2-COMP"], "hi"),
    ("R-GOGOI", "R. Gogoi", "आर. गोगोई", "supervisor", "Civil", "C-BCW", ["WF-U3-FDN", "WF-U2-CT", "WF-U3-TANK"], "hi"),
    ("R-SHARMA", "A. Sharma", "ए. शर्मा", "supervisor", "Electrical", "C-NEE", ["WF-U2-SUBSTN", "WF-U2-RACK-A"], "en"),
    ("R-DAS", "P. Das", "पी. दास", "supervisor", "Instrumentation", "C-NEE", ["WF-U3-PUMP", "WF-U3-RACK-B", "WF-U3-RACK-C"], "en"),
    ("R-SAIKIA", "J. Saikia", "जे. सैकिया", "supervisor", "Structural", "C-KST", ["WF-U2-STRUCT", "WF-U2-COMP"], "hi"),
    ("R-BARUAH", "K. Baruah", "के. बरुआ", "supervisor", "Mechanical", "C-DMX", ["WF-U2-COMP", "WF-U3-PUMP", "WF-U3-TANK"], "en"),
    ("R-HAZARIKA", "N. Hazarika", "एन. हज़ारिका", "hse", None, None, [], "en"),
    ("R-IYER", "V. Iyer", "वी. अय्यर", "planner", "Piping", None, [], "en"),
    ("R-MENON", "S. Menon", "एस. मेनन", "planner", "Civil", None, [], "en"),
    ("R-CHOUDHURY", "D. Choudhury", "डी. चौधरी", "pm", None, None, [], "en"),
]

# ─────────────────────────────────── activities ──────────────────────────────────────
# Each tuple: (id, name, discipline, unit, work_front, action, object_class, line_no,
#              planned_start, planned_finish, predecessors, scope_objects, permit_type)
ACTIVITIES: list[tuple] = []


def A(aid, name, disc, unit, wf, action, ocls, line, ps, pf, preds=(), scope=(), permit=None):
    ACTIVITIES.append((aid, name, disc, unit, wf, action, ocls, line, D(ps), D(pf), list(preds), list(scope), permit))


def _spools(line, wf=None):
    for l in LINES:
        if l[0] == line:
            return [spool_id(line, n) for n, w in l[4].items() if wf is None or w == wf]
    return []


# ---- Piping, Unit 3 -------------------------------------------------------------
A("PIP-3-2201", "Fabricate spools line 24-P-1203", "Piping", "Unit 3", None, "fabricate", "spool", "24-P-1203", "2026-08-03", "2026-08-28", scope=_spools("24-P-1203"))
A("PIP-3-2202", "Fabricate spools line 16-P-1207", "Piping", "Unit 3", None, "fabricate", "spool", "16-P-1207", "2026-08-10", "2026-09-04", scope=_spools("16-P-1207"))
A("PIP-3-2203", "Fabricate spools line 12-P-1215", "Piping", "Unit 3", None, "fabricate", "spool", "12-P-1215", "2026-08-01", "2026-08-20", scope=_spools("12-P-1215"))
A("PIP-3-2204", "Fabricate spools line 8-P-1220", "Piping", "Unit 3", None, "fabricate", "spool", "8-P-1220", "2026-08-12", "2026-09-02", scope=_spools("8-P-1220"))
A("PIP-3-2205", "Fabricate spools line 24-P-1108", "Piping", "Unit 3", None, "fabricate", "spool", "24-P-1108", "2026-08-01", "2026-08-25", scope=_spools("24-P-1108"))
A("PIP-3-2206", "Fabricate spools line 10-P-1301", "Piping", "Unit 3", None, "fabricate", "spool", "10-P-1301", "2026-08-18", "2026-09-08", scope=_spools("10-P-1301"))
A("PIP-3-2340", "Erect spools line 24-P-1203 Rack B", "Piping", "Unit 3", "WF-U3-RACK-B", "erect", "spool", "24-P-1203", "2026-09-10", "2026-09-30", ["PIP-3-2201"], _spools("24-P-1203", "WF-U3-RACK-B"))
A("PIP-3-2341", "Erect spools line 24-P-1203 Rack C", "Piping", "Unit 3", "WF-U3-RACK-C", "erect", "spool", "24-P-1203", "2026-09-18", "2026-10-05", ["PIP-3-2201"], _spools("24-P-1203", "WF-U3-RACK-C"))
A("PIP-3-2342", "Erect spools line 16-P-1207 Rack B", "Piping", "Unit 3", "WF-U3-RACK-B", "erect", "spool", "16-P-1207", "2026-10-12", "2026-10-26", ["PIP-3-2202"], _spools("16-P-1207"))
A("PIP-3-2345", "Erect spools line 12-P-1215 Rack C", "Piping", "Unit 3", "WF-U3-RACK-C", "erect", "spool", "12-P-1215", "2026-08-25", "2026-09-12", ["PIP-3-2203"], _spools("12-P-1215"))
A("PIP-3-2346", "Erect spools line 8-P-1220 Rack C", "Piping", "Unit 3", "WF-U3-RACK-C", "erect", "spool", "8-P-1220", "2026-10-16", "2026-10-28", ["PIP-3-2204"], _spools("8-P-1220"))
A("PIP-3-2108", "Erect spools line 24-P-1108 Tank Farm", "Piping", "Unit 3", "WF-U3-TANK", "erect", "spool", "24-P-1108", "2026-09-01", "2026-09-16", ["PIP-3-2205"], _spools("24-P-1108"))
A("PIP-3-2109", "Erect spools line 10-P-1301 Pump House", "Piping", "Unit 3", "WF-U3-PUMP", "erect", "spool", "10-P-1301", "2026-09-12", "2026-09-28", ["PIP-3-2206"], _spools("10-P-1301"))
A("PIP-3-2351", "Field weld joints line 12-P-1215 Rack C", "Piping", "Unit 3", "WF-U3-RACK-C", "weld", "joint", "12-P-1215", "2026-09-15", "2026-10-03", ["PIP-3-2345"], permit="hot_work")
A("PIP-3-2352", "Field weld joints line 24-P-1108 Tank Farm", "Piping", "Unit 3", "WF-U3-TANK", "weld", "joint", "24-P-1108", "2026-09-06", "2026-09-19", ["PIP-3-2108"], permit="hot_work")
A("PIP-3-2353", "Field weld joints line 24-P-1203 Rack B", "Piping", "Unit 3", "WF-U3-RACK-B", "weld", "joint", "24-P-1203", "2026-09-22", "2026-10-10", ["PIP-3-2340"], permit="hot_work")
A("PIP-3-2361", "Install pipe supports Rack B", "Piping", "Unit 3", "WF-U3-RACK-B", "install", "support", None, "2026-09-02", "2026-09-20", permit="hot_work")
A("PIP-3-2362", "Install pipe supports Rack C", "Piping", "Unit 3", "WF-U3-RACK-C", "install", "support", None, "2026-08-20", "2026-09-08")
A("PIP-3-2401", "Hydrotest line 24-P-1108", "Piping", "Unit 3", "WF-U3-TANK", "test", "line", "24-P-1108", "2026-09-20", "2026-09-27", ["PIP-3-2352"])
A("PIP-3-2402", "Hydrotest line 24-P-1203", "Piping", "Unit 3", "WF-U3-RACK-B", "test", "line", "24-P-1203", "2026-10-14", "2026-10-20", ["PIP-3-2340", "PIP-3-2341", "PIP-3-2353"])
A("PIP-3-2403", "Pneumatic test line 12-P-1215", "Piping", "Unit 3", "WF-U3-RACK-C", "test", "line", "12-P-1215", "2026-10-06", "2026-10-09", ["PIP-3-2351"])
A("PIP-3-2501", "Painting line 24-P-1108", "Piping", "Unit 3", "WF-U3-TANK", "paint", "line", "24-P-1108", "2026-09-28", "2026-10-08", ["PIP-3-2401"])
A("PIP-3-2502", "Insulation line 10-P-1301", "Piping", "Unit 3", "WF-U3-PUMP", "insulate", "line", "10-P-1301", "2026-10-10", "2026-10-24", ["PIP-3-2109"])

# ---- Piping, Unit 2 -------------------------------------------------------------
A("PIP-2-2210", "Fabricate spools line 18-P-2101", "Piping", "Unit 2", None, "fabricate", "spool", "18-P-2101", "2026-08-05", "2026-08-29", scope=_spools("18-P-2101"))
A("PIP-2-2211", "Fabricate spools line 14-P-2110", "Piping", "Unit 2", None, "fabricate", "spool", "14-P-2110", "2026-08-12", "2026-09-06", scope=_spools("14-P-2110"))
A("PIP-2-2212", "Fabricate spools line 12-P-2120", "Piping", "Unit 2", None, "fabricate", "spool", "12-P-2120", "2026-08-20", "2026-09-10", scope=_spools("12-P-2120"))
A("PIP-2-2310", "Erect spools line 18-P-2101 Rack A", "Piping", "Unit 2", "WF-U2-RACK-A", "erect", "spool", "18-P-2101", "2026-09-03", "2026-09-22", ["PIP-2-2210"], _spools("18-P-2101"))
A("PIP-2-2311", "Erect spools line 14-P-2110 Rack A", "Piping", "Unit 2", "WF-U2-RACK-A", "erect", "spool", "14-P-2110", "2026-09-14", "2026-10-02", ["PIP-2-2211"], _spools("14-P-2110"))
A("PIP-2-2312", "Erect spools line 12-P-2120 Compressor House", "Piping", "Unit 2", "WF-U2-COMP", "erect", "spool", "12-P-2120", "2026-09-16", "2026-10-06", ["PIP-2-2212"], _spools("12-P-2120"))
A("PIP-2-2350", "Field weld joints line 18-P-2101 Rack A", "Piping", "Unit 2", "WF-U2-RACK-A", "weld", "joint", "18-P-2101", "2026-09-10", "2026-09-30", ["PIP-2-2310"], permit="hot_work")
A("PIP-2-2360", "Install pipe supports Rack A", "Piping", "Unit 2", "WF-U2-RACK-A", "install", "support", None, "2026-08-25", "2026-09-12")
A("PIP-2-2410", "Hydrotest line 18-P-2101", "Piping", "Unit 2", "WF-U2-RACK-A", "test", "line", "18-P-2101", "2026-10-05", "2026-10-10", ["PIP-2-2350"])

# ---- Civil, Unit 3 foundations F-10..F-14 ----------------------------------------
_fdn_start = {10: "2026-08-10", 11: "2026-08-20", 12: "2026-09-01", 13: "2026-09-10", 14: "2026-09-22"}
for f, s0 in _fdn_start.items():
    s = D(s0)
    steps = [("excavate", "Excavation", 5), ("pour", "PCC", 2), ("rebar", "Reinforcement", 5), ("shutter", "Shuttering", 3), ("pour", "Concreting", 2), ("backfill", "Backfilling", 3)]
    prev = None
    for i, (act, label, dur) in enumerate(steps):
        aid = f"CIV-3-{1100 + (f - 10) + 10 * i}"   # F-12 excavation → CIV-3-1102 (spec example)
        e = s + timedelta(days=dur)
        A(aid, f"{label} foundation F-{f}", "Civil", "Unit 3", "WF-U3-FDN", act, "foundation", None,
          s.isoformat(), e.isoformat(), [prev] if prev else [], [f"FDN-F-{f}"], "excavation" if act == "excavate" else None)
        prev, s = aid, e + timedelta(days=1)

# ---- Civil, Unit 3 tank farm + Unit 2 cooling tower ---------------------------------
A("CIV-3-1301", "Tank pad T-301 ring wall concreting", "Civil", "Unit 3", "WF-U3-TANK", "pour", "ring wall", None, "2026-08-05", "2026-08-25")
A("CIV-3-1302", "Tank pad T-301 sand filling and compaction", "Civil", "Unit 3", "WF-U3-TANK", "fill", "tank pad", None, "2026-08-26", "2026-09-08", ["CIV-3-1301"])
A("CIV-3-1310", "Pump foundation P-101A/B concreting", "Civil", "Unit 3", "WF-U3-PUMP", "pour", "foundation", None, "2026-08-04", "2026-08-18")
A("CIV-2-1401", "Cooling tower basin raft concreting", "Civil", "Unit 2", "WF-U2-CT", "pour", "basin", None, "2026-08-01", "2026-08-22")
A("CIV-2-1402", "Cooling tower basin wall shuttering", "Civil", "Unit 2", "WF-U2-CT", "shutter", "basin", None, "2026-08-23", "2026-09-10", ["CIV-2-1401"])
A("CIV-2-1403", "Cooling tower basin wall concreting", "Civil", "Unit 2", "WF-U2-CT", "pour", "basin", None, "2026-09-11", "2026-09-24", ["CIV-2-1402"], permit="confined_space")
A("CIV-2-1404", "Cooling tower basin waterproofing", "Civil", "Unit 2", "WF-U2-CT", "coat", "basin", None, "2026-09-25", "2026-10-10", ["CIV-2-1403"], permit="confined_space")
A("CIV-2-1410", "Compressor foundation K-201 concreting", "Civil", "Unit 2", "WF-U2-COMP", "pour", "foundation", None, "2026-08-01", "2026-08-16")
A("CIV-2-1420", "Substation SS-2 building brickwork", "Civil", "Unit 2", "WF-U2-SUBSTN", "build", "brickwork", None, "2026-08-01", "2026-08-24")
A("CIV-2-1421", "Substation SS-2 cable trench", "Civil", "Unit 2", "WF-U2-SUBSTN", "excavate", "trench", None, "2026-08-20", "2026-09-06", permit="excavation")
A("CIV-2-1430", "Structure ST-2 pedestal grouting", "Civil", "Unit 2", "WF-U2-STRUCT", "grout", "pedestal", None, "2026-08-18", "2026-08-30")

# ---- Structural -----------------------------------------------------------------------
A("STR-3-4101", "Erect structural steel Rack B", "Structural", "Unit 3", "WF-U3-RACK-B", "erect", "steel", None, "2026-08-01", "2026-08-25", permit="height")
A("STR-3-4102", "Erect structural steel Rack C", "Structural", "Unit 3", "WF-U3-RACK-C", "erect", "steel", None, "2026-08-05", "2026-08-28", permit="height")
A("STR-3-4110", "Pump house roof sheeting", "Structural", "Unit 3", "WF-U3-PUMP", "install", "roof sheeting", None, "2026-09-01", "2026-09-18", permit="height")
for i, (lvl, s, e) in enumerate([("EL +6m", "2026-08-31", "2026-09-10"), ("EL +12m", "2026-09-11", "2026-09-24"), ("EL +18m", "2026-09-25", "2026-10-08")]):
    A(f"STR-2-420{i}", f"Erect columns and beams ST-2 {lvl}", "Structural", "Unit 2", "WF-U2-STRUCT", "erect", "steel", None, s, e,
      [f"STR-2-420{i-1}"] if i else ["CIV-2-1430"], permit="height")
    A(f"STR-2-421{i}", f"Bolt torquing ST-2 {lvl}", "Structural", "Unit 2", "WF-U2-STRUCT", "torque", "bolt", None,
      (D(s) + timedelta(days=5)).isoformat(), (D(e) + timedelta(days=4)).isoformat(), [f"STR-2-420{i}"], permit="height")
A("STR-2-4230", "Grating and handrail ST-2", "Structural", "Unit 2", "WF-U2-STRUCT", "install", "grating", None, "2026-10-09", "2026-10-25", ["STR-2-4202"], permit="height")
A("STR-2-4240", "Compressor house crane girder erection", "Structural", "Unit 2", "WF-U2-COMP", "erect", "girder", None, "2026-09-01", "2026-09-15", permit="height")

# ---- Electrical, Unit 2 substation + racks ---------------------------------------------
A("ELE-2-3001", "Transformer TR-201 installation", "Electrical", "Unit 2", "WF-U2-SUBSTN", "install", "transformer", None, "2026-08-25", "2026-09-08")
A("ELE-2-3002", "HT panel erection SS-2", "Electrical", "Unit 2", "WF-U2-SUBSTN", "erect", "panel", None, "2026-09-01", "2026-09-14")
A("ELE-2-3003", "LT panel erection SS-2", "Electrical", "Unit 2", "WF-U2-SUBSTN", "erect", "panel", None, "2026-09-08", "2026-09-22")
A("ELE-2-3010", "Earthing grid SS-2", "Electrical", "Unit 2", "WF-U2-SUBSTN", "lay", "earthing", None, "2026-08-18", "2026-09-04", permit="excavation")
for t in range(1, 7):
    ps = D("2026-08-28") + timedelta(days=5 * (t - 1))
    A(f"ELE-2-305{t}", f"Cable tray installation Unit 2 tray T-{t}", "Electrical", "Unit 2", "WF-U2-RACK-A", "install", "tray", None,
      ps.isoformat(), (ps + timedelta(days=7)).isoformat(), permit="height", scope=[f"TRAY-T-{t}"])
    pid = "ELE-2-3100" if t == 4 else f"ELE-2-31{t:02d}"     # spec example id for tray T-4
    A(pid, f"Cable pulling Unit 2 tray T-{t}", "Electrical", "Unit 2", "WF-U2-RACK-A", "pull", "cable", None,
      (ps + timedelta(days=6)).isoformat(), (ps + timedelta(days=16)).isoformat(), [f"ELE-2-305{t}"], [f"TRAY-T-{t}"])
A("ELE-2-3200", "Cable termination HT panel SS-2", "Electrical", "Unit 2", "WF-U2-SUBSTN", "terminate", "cable", None, "2026-09-20", "2026-10-06", ["ELE-2-3002"])
A("ELE-2-3201", "Cable termination LT panel SS-2", "Electrical", "Unit 2", "WF-U2-SUBSTN", "terminate", "cable", None, "2026-10-01", "2026-10-15", ["ELE-2-3003"])
A("ELE-2-3300", "Lighting fixtures compressor house", "Electrical", "Unit 2", "WF-U2-COMP", "install", "lighting", None, "2026-09-20", "2026-10-08")
A("ELE-3-3400", "Motor cabling pumps P-101A/B", "Electrical", "Unit 3", "WF-U3-PUMP", "pull", "cable", None, "2026-09-18", "2026-10-02")

# ---- Instrumentation, Unit 3 --------------------------------------------------------------
A("INS-3-5001", "Install instruments pump house", "Instrumentation", "Unit 3", "WF-U3-PUMP", "install", "instrument", None, "2026-09-05", "2026-09-20")
A("INS-3-5002", "Impulse tubing pump house", "Instrumentation", "Unit 3", "WF-U3-PUMP", "install", "tubing", None, "2026-09-12", "2026-09-28", ["INS-3-5001"])
A("INS-3-5010", "Instrument cable tray Rack B", "Instrumentation", "Unit 3", "WF-U3-RACK-B", "install", "tray", None, "2026-08-24", "2026-09-10", permit="height")
A("INS-3-5011", "Instrument cable tray Rack C", "Instrumentation", "Unit 3", "WF-U3-RACK-C", "install", "tray", None, "2026-09-01", "2026-09-16", permit="height")
for i, lp in enumerate(["L-301", "L-302", "L-303", "L-304", "L-305", "L-306"]):
    ps = D("2026-09-08") + timedelta(days=4 * i)
    A(f"INS-3-51{i:02d}", f"Loop check {lp} pump house", "Instrumentation", "Unit 3", "WF-U3-PUMP", "test", "loop", None,
      ps.isoformat(), (ps + timedelta(days=3)).isoformat(), ["INS-3-5001"], [f"LOOP-{lp}"])
A("INS-3-5200", "Calibration of transmitters pump house", "Instrumentation", "Unit 3", "WF-U3-PUMP", "calibrate", "transmitter", None, "2026-09-02", "2026-09-14")
A("INS-3-5300", "Install flow meters Rack B", "Instrumentation", "Unit 3", "WF-U3-RACK-B", "install", "flow meter", None, "2026-10-01", "2026-10-15")

# ---- Mechanical ------------------------------------------------------------------------------
A("MEC-3-6001", "Pump P-101A setting and levelling", "Mechanical", "Unit 3", "WF-U3-PUMP", "install", "pump", None, "2026-08-24", "2026-09-04", ["CIV-3-1310"], scope=["P-101A"])
A("MEC-3-6002", "Pump P-101B setting and levelling", "Mechanical", "Unit 3", "WF-U3-PUMP", "install", "pump", None, "2026-08-28", "2026-09-09", ["CIV-3-1310"], scope=["P-101B"])
A("MEC-3-6003", "Pump P-101A alignment", "Mechanical", "Unit 3", "WF-U3-PUMP", "align", "pump", None, "2026-09-10", "2026-09-18", ["MEC-3-6001"], scope=["P-101A"])
A("MEC-3-6004", "Pump P-101B alignment", "Mechanical", "Unit 3", "WF-U3-PUMP", "align", "pump", None, "2026-09-14", "2026-09-23", ["MEC-3-6002"], scope=["P-101B"])
A("MEC-3-6010", "Tank T-301 shell plate erection", "Mechanical", "Unit 3", "WF-U3-TANK", "erect", "tank shell", None, "2026-09-09", "2026-10-10", ["CIV-3-1302"], permit="hot_work")
A("MEC-3-6011", "Tank T-301 roof erection", "Mechanical", "Unit 3", "WF-U3-TANK", "erect", "tank roof", None, "2026-10-12", "2026-10-30", ["MEC-3-6010"], permit="height")
A("MEC-2-6101", "Compressor K-201 setting on foundation", "Mechanical", "Unit 2", "WF-U2-COMP", "install", "compressor", None, "2026-09-02", "2026-09-14", ["CIV-2-1410"], scope=["K-201"])
A("MEC-2-6102", "Compressor K-201 grouting", "Mechanical", "Unit 2", "WF-U2-COMP", "grout", "compressor", None, "2026-09-15", "2026-09-21", ["MEC-2-6101"], scope=["K-201"])
A("MEC-2-6103", "Compressor K-201 alignment", "Mechanical", "Unit 2", "WF-U2-COMP", "align", "compressor", None, "2026-09-22", "2026-10-06", ["MEC-2-6102"], scope=["K-201"])
A("MEC-2-6104", "Compressor K-201 lube oil flushing", "Mechanical", "Unit 2", "WF-U2-COMP", "flush", "compressor", None, "2026-10-07", "2026-10-20", ["MEC-2-6103"], scope=["K-201"])
A("MEC-2-6110", "Cooling tower fan installation", "Mechanical", "Unit 2", "WF-U2-CT", "install", "fan", None, "2026-10-12", "2026-10-28", ["CIV-2-1404"], permit="height")

# Filler L6 activities to reach realistic density (painting / touch-up / punch lists).
_fill = [
    ("CIV-3-1900", "Area grading and levelling Unit 3", "Civil", "Unit 3", "WF-U3-FDN", "level", "grade"),
    ("CIV-3-1901", "Precast cover slabs cable trench Unit 3", "Civil", "Unit 3", "WF-U3-PUMP", "install", "slab"),
    ("CIV-2-1901", "Paving around substation SS-2", "Civil", "Unit 2", "WF-U2-SUBSTN", "pave", "paving"),
    ("STR-3-4900", "Primer touch-up Rack B steel", "Structural", "Unit 3", "WF-U3-RACK-B", "paint", "steel"),
    ("STR-3-4901", "Primer touch-up Rack C steel", "Structural", "Unit 3", "WF-U3-RACK-C", "paint", "steel"),
    ("ELE-2-3900", "Street lighting poles Unit 2", "Electrical", "Unit 2", "WF-U2-RACK-A", "install", "pole"),
    ("INS-3-5900", "Junction box mounting Rack C", "Instrumentation", "Unit 3", "WF-U3-RACK-C", "install", "junction box"),
    ("MEC-3-6900", "Pump house EOT crane load test", "Mechanical", "Unit 3", "WF-U3-PUMP", "test", "crane"),
]
for i, (aid, name, disc, unit, wf, act, ocls) in enumerate(_fill):
    ps = D("2026-10-05") + timedelta(days=2 * i)
    A(aid, name, disc, unit, wf, act, ocls, None, ps.isoformat(), (ps + timedelta(days=10)).isoformat())

# More generated density: per work front "punch list" and "painting" L6 rows later in Oct.
_WF_UNIT = {w[0]: w[2] for w in WORK_FRONTS}
_seq = 0
for disc, pref in [("Piping", "PIP"), ("Civil", "CIV"), ("Electrical", "ELE"), ("Instrumentation", "INS"), ("Mechanical", "MEC"), ("Structural", "STR")]:
    for wf in [w[0] for w in WORK_FRONTS]:
        if len(ACTIVITIES) >= 150:
            break
        _seq += 1
        u = _WF_UNIT[wf]
        un = u[-1]
        ps = D("2026-10-14") + timedelta(days=_seq % 12)
        A(f"{pref}-{un}-8{_seq:03d}", f"Punch list clearance {disc.lower()} {dict((w[0], w[1]) for w in WORK_FRONTS)[wf]}",
          disc, u, wf, "clear", "punch", None, ps.isoformat(), (ps + timedelta(days=8)).isoformat())


def wbs_for(aid: str, disc: str, unit: str, wf: str | None) -> str:
    u = "U" + unit[-1]
    d = {"Piping": "PIP", "Civil": "CIV", "Structural": "STR", "Electrical": "ELE", "Instrumentation": "INS", "Mechanical": "MEC"}[disc]
    area = (wf or "SHOP").replace("WF-", "").replace(f"{u}-", "")
    return f"RFX.{u}.{d}.{area}"


# Activities the live demo relies on — history must not touch them.
RESERVED = {"PIP-3-2340", "PIP-3-2341", "PIP-3-2342", "PIP-3-2351", "PIP-3-2402", "PIP-3-2353"}

# Baseline actuals imported from the PMIS before our system went live (before 5 Sep).
# activity_id → (actual_start, actual_finish|None)
BASELINE_ACTUALS = {
    "PIP-3-2201": ("2026-08-04", "2026-08-30"),
    "PIP-3-2202": ("2026-08-11", "2026-09-04"),
    "PIP-3-2203": ("2026-08-01", "2026-08-19"),
    "PIP-3-2204": ("2026-08-13", "2026-09-03"),
    "PIP-3-2205": ("2026-08-01", "2026-08-26"),
    "PIP-3-2206": ("2026-08-19", None),
    "PIP-3-2345": ("2026-08-27", None),
    "PIP-3-2108": ("2026-09-02", None),
    "PIP-3-2362": ("2026-08-21", None),
    "PIP-3-2361": ("2026-09-03", None),
    "PIP-2-2210": ("2026-08-05", "2026-08-31"),
    "PIP-2-2211": ("2026-08-13", "2026-09-04"),
    "PIP-2-2212": ("2026-08-21", None),
    "PIP-2-2310": ("2026-09-04", None),
    "PIP-2-2360": ("2026-08-26", None),
    "CIV-3-1100": ("2026-08-10", "2026-08-16"),
    "CIV-3-1110": ("2026-08-17", "2026-08-19"),
    "CIV-3-1120": ("2026-08-20", "2026-08-26"),
    "CIV-3-1130": ("2026-08-27", "2026-08-30"),
    "CIV-3-1140": ("2026-08-31", "2026-09-02"),
    "CIV-3-1150": ("2026-09-03", None),
    "CIV-3-1101": ("2026-08-21", "2026-08-27"),
    "CIV-3-1111": ("2026-08-28", "2026-08-30"),
    "CIV-3-1121": ("2026-08-31", None),
    "CIV-3-1102": ("2026-09-01", None),
    "CIV-3-1301": ("2026-08-05", "2026-08-27"),
    "CIV-3-1302": ("2026-08-28", None),
    "CIV-3-1310": ("2026-08-04", "2026-08-19"),
    "CIV-2-1401": ("2026-08-01", "2026-08-21"),
    "CIV-2-1402": ("2026-08-24", None),
    "CIV-2-1410": ("2026-08-01", "2026-08-17"),
    "CIV-2-1420": ("2026-08-01", "2026-08-26"),
    "CIV-2-1421": ("2026-08-21", None),
    "CIV-2-1430": ("2026-08-18", "2026-08-31"),
    "STR-3-4101": ("2026-08-01", "2026-08-24"),
    "STR-3-4102": ("2026-08-06", "2026-08-30"),
    "STR-3-4110": ("2026-09-02", None),
    "STR-2-4200": ("2026-09-01", None),
    "STR-2-4240": ("2026-09-02", None),
    "ELE-2-3001": ("2026-08-26", None),
    "ELE-2-3002": ("2026-09-02", None),
    "ELE-2-3010": ("2026-08-18", "2026-09-03"),
    "ELE-2-3051": ("2026-08-28", "2026-09-04"),
    "ELE-2-3052": ("2026-09-02", None),
    "ELE-2-3101": ("2026-09-03", None),
    "INS-3-5010": ("2026-08-25", None),
    "INS-3-5011": ("2026-09-02", None),
    "INS-3-5200": ("2026-09-02", None),
    "MEC-3-6001": ("2026-08-25", "2026-09-04"),
    "MEC-3-6002": ("2026-08-29", None),
    "MEC-2-6101": ("2026-09-03", None),
}

# ─────────────────────────────── permits / material / equipment ────────────────────────
def _dt(s):
    return datetime.fromisoformat(s)


PERMITS = [
    # id, type, work_front, from, to, status, gas_test
    ("PTW-U3-4471", "hot_work", "WF-U3-RACK-B", _dt("2026-09-01T08:00"), _dt("2026-09-30T18:00"), "valid", True),
    ("PTW-U3-4480", "hot_work", "WF-U3-TANK", _dt("2026-09-01T08:00"), _dt("2026-09-30T18:00"), "valid", True),
    ("PTW-U3-4490", "hot_work", "WF-U3-PUMP", _dt("2026-09-01T08:00"), _dt("2026-09-27T18:00"), "valid", True),
    ("PTW-U2-3301", "hot_work", "WF-U2-RACK-A", _dt("2026-09-01T08:00"), _dt("2026-09-30T18:00"), "valid", True),
    ("PTW-U2-3302", "confined_space", "WF-U2-CT", _dt("2026-09-01T08:00"), _dt("2026-09-20T18:00"), "expired", True),
    ("PTW-U3-4500", "excavation", "WF-U3-FDN", _dt("2026-08-01T07:00"), _dt("2026-10-31T19:00"), "valid", False),
    ("PTW-U2-3310", "excavation", "WF-U2-SUBSTN", _dt("2026-08-15T07:00"), _dt("2026-09-10T19:00"), "valid", False),
    ("PTW-U2-3320", "height", "WF-U2-STRUCT", _dt("2026-08-25T07:00"), _dt("2026-09-27T19:00"), "valid", False),
    ("PTW-U3-4510", "height", "WF-U3-PUMP", _dt("2026-08-25T07:00"), _dt("2026-09-30T19:00"), "valid", False),
    ("PTW-U2-3330", "height", "WF-U2-RACK-A", _dt("2026-08-25T07:00"), _dt("2026-10-15T19:00"), "valid", False),
    ("PTW-U2-3339", "height", "WF-U2-COMP", _dt("2026-08-25T07:00"), _dt("2026-09-25T19:00"), "valid", False),
    ("PTW-U2-3340", "height", "WF-U2-COMP", _dt("2026-09-26T07:00"), _dt("2026-10-10T19:00"), "pending", False),
    ("PTW-U3-4520", "height", "WF-U3-RACK-B", _dt("2026-08-01T07:00"), _dt("2026-10-31T19:00"), "valid", False),
    ("PTW-U3-4521", "height", "WF-U3-RACK-C", _dt("2026-08-01T07:00"), _dt("2026-10-31T19:00"), "valid", False),
    ("PTW-U3-4530", "radiography", "WF-U3-TANK", _dt("2026-09-10T19:00"), _dt("2026-09-10T23:00"), "expired", False),
    # NOTE: deliberately no hot_work permit for WF-U3-RACK-C (demo step 5).
]


def material_issues():
    rows = []
    for line_no, _, _, _, spools in LINES:
        for n, wf in spools.items():
            sid = spool_id(line_no, n)
            status = "not_issued" if sid == "SPL-24-1203-05" else "issued"
            rows.append((sid, f"Spool {n} of line {line_no}", status, wf))
    rows += [
        ("TR-201", "Transformer 2 MVA", "issued", "WF-U2-SUBSTN"),
        ("CBL-DRUM-3C240-07", "HT cable drum 3C x 240", "issued", "WF-U2-RACK-A"),
        ("CBL-DRUM-3C240-08", "HT cable drum 3C x 240", "not_issued", "WF-U2-RACK-A"),
        ("TX-PT-301", "Pressure transmitter PT-301", "issued", "WF-U3-PUMP"),
    ]
    return rows


EQUIPMENT = [
    ("CR-50T-02", "crane_50T", "WF-U3-RACK-B", "working"),
    ("CR-50T-01", "crane_50T", "WF-U3-TANK", "working"),
    ("HY-14T-03", "hydra_14T", "WF-U2-RACK-A", "working"),
    ("EX-20T-01", "excavator", "WF-U3-FDN", "working"),
    ("TM-06", "transit_mixer", "WF-U3-FDN", "working"),
    ("BP-01", "boom_placer", "WF-U2-CT", "idle"),
    ("DG-250-01", "dg_set", "WF-U2-SUBSTN", "working"),
    ("WM-01", "welding_machine", "WF-U3-RACK-B", "working"),
    ("WM-02", "welding_machine", "WF-U3-TANK", "working"),
    ("WM-03", "welding_machine", "WF-U2-RACK-A", "working"),
]

# ─────────────────────────────────────── weather ─────────────────────────────────────────
# Seeded site-station weather. 13 Sep: heavy afternoon rain (42 mm, 14:00-18:00).
# 18 Sep and 26 Sep (demo day) are dry — rain claims on those days are "not corroborated".
def weather_days():
    import random
    rnd = random.Random(7)
    out = []
    d = D("2026-08-25")
    while d <= D("2026-10-05"):
        hourly = [0.0] * 24
        if d == D("2026-09-13"):
            for h, mm in zip(range(14, 18), [9.0, 14.0, 12.0, 7.0]):
                hourly[h] = mm
        elif d in (D("2026-09-18"), D("2026-09-26"), D("2026-09-19")):
            pass
        elif d in (D("2026-09-07"), D("2026-09-21"), D("2026-09-09")):
            for h in range(15, 18):
                hourly[h] = round(rnd.uniform(1.5, 4.0), 1)
        elif rnd.random() < 0.35:
            h0 = rnd.randint(12, 19)
            for h in range(h0, min(24, h0 + rnd.randint(1, 3))):
                hourly[h] = round(rnd.uniform(0.2, 1.2), 1)
        out.append((d, round(sum(hourly), 1), round(rnd.uniform(29, 34), 1), round(rnd.uniform(6, 18), 1), hourly))
        d += timedelta(days=1)
    return out
