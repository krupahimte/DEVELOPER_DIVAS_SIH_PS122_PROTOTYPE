"""Controlled vocabularies shared by the rule extractor, matcher, HSE and unplanned
classifiers. English + Hindi (romanised) + common Hinglish site usage.

Every entry is a regex fragment; matching is case-insensitive on the raw text so that
spans stay valid against the verbatim input.
"""

# canonical action → surface forms
ACTIONS = {
    "erect": [r"erect(?:ed|ion|ing)?", r"lag(?:a|aya|aye|ayi|gaye|gaya)\b", r"lift(?:ed|ing)?\s+and\s+placed", r"placed"],
    "weld": [r"weld(?:ed|ing|s)?(?!\s*(?:machine|m/c|set|rod))", r"jod(?:a|ai)\b", r"joint(?:s)?\s+(?:done|complete|kiya)"],
    "fit_up": [r"fit[\s-]?up", r"fitup"],
    "fabricate": [r"fabricat(?:e|ed|ion|ing)"],
    "pour": [r"pour(?:ed|ing)?", r"concret(?:ing|ed|e\s+poured)", r"casting", r"cast(?:ed)?\b", r"dhalai", r"\bpcc\b"],
    "excavate": [r"excavat(?:e|ed|ion|ing)", r"digging", r"khudai", r"khodai"],
    "pull": [r"pull(?:ed|ing)?", r"kheench(?:a|e)?", r"cabling"],
    "lay": [r"\blaid\b", r"\blay(?:ing)?\b", r"bichaya"],
    "test": [r"hydro[\s-]?test(?:ed|ing)?", r"pneumatic\s+test", r"loop\s+check(?:ed|ing)?", r"test(?:ed|ing)?\b", r"megger(?:ed|ing)?", r"load\s+test"],
    "install": [r"install(?:ed|ation|ing)?", r"fix(?:ed|ing)\b", r"mount(?:ed|ing)?", r"fitted"],
    "paint": [r"paint(?:ed|ing)?", r"primer", r"coating"],
    "insulate": [r"insulat(?:e|ed|ion|ing)"],
    "backfill": [r"back[\s-]?fill(?:ed|ing)?"],
    "shutter": [r"shutter(?:ing|ed)?", r"formwork"],
    "rebar": [r"rebar", r"reinforcement", r"bar\s+bending", r"bar\s+tying", r"sariya"],
    "grout": [r"grout(?:ed|ing)?"],
    "align": [r"align(?:ed|ment|ing)?"],
    "terminate": [r"terminat(?:e|ed|ion|ing)", r"glanding"],
    "calibrate": [r"calibrat(?:e|ed|ion|ing)"],
    "torque": [r"torqu(?:e|ed|ing)", r"bolt\s+tightening"],
    "flush": [r"flush(?:ed|ing)?"],
    "fill": [r"sand\s+fill(?:ing|ed)?", r"compaction", r"compacted"],
    "coat": [r"waterproof(?:ing|ed)?"],
    "clear": [r"punch(?:\s+list)?\s+(?:clear|point)"],
    "level": [r"level(?:l)?(?:ed|ing)", r"grading"],
    "cut": [r"cutting", r"\bcut\b", r"gas\s+cutting"],
    "grind": [r"grinding", r"grind(?:ed)?"],
    "build": [r"brickwork", r"masonry"],
    "dismantle": [r"dismantl(?:e|ed|ing)", r"removed", r"khol\s+diya"],
    "clear": [r"punch(?:\s+list)?\s+(?:clear|point)", r"housekeeping", r"scrap\s+clear(?:ing|ed)?", r"clearing"],
}
ACTIONS["install"] = ACTIONS["install"] + [r"sheeting"]

# action → discipline prior (helps narrow candidates when the reporter is unknown)
ACTION_DISCIPLINE = {
    "erect": None, "weld": "Piping", "fit_up": "Piping", "fabricate": "Piping", "pour": "Civil", "excavate": "Civil",
    "pull": "Electrical", "lay": None, "test": None, "install": None, "paint": None, "insulate": "Piping",
    "backfill": "Civil", "shutter": "Civil", "rebar": "Civil", "grout": None, "align": "Mechanical",
    "terminate": "Electrical", "calibrate": "Instrumentation", "torque": "Structural", "flush": "Mechanical",
    "fill": "Civil", "coat": "Civil", "level": "Civil", "build": "Civil",
}

# word → object_event_type
EVENT_WORDS = {
    "start": [r"start(?:ed|s)?\b", r"begun", r"began", r"commenc(?:ed|e)", r"shuru", r"chalu", r"mobili[sz]ed"],
    "finish": [r"complet(?:ed|e)", r"\bdone\b", r"finish(?:ed)?", r"ho\s+gay[aei]", r"ho\s+gaya", r"pura\b", r"poora\b", r"khatam",
               r"lagaya", r"lag\s+gay[ae]", r"kar\s+diya", r"erected", r"poured", r"\blaid\b", r"installed", r"welded", r"tested", r"pulled", r"aligned", r"grouted", r"cast\b"],
    "progress": [r"continu(?:ed|ing|e)", r"in\s+progress", r"ongoing", r"chal\s+raha", r"chal\s+rahi", r"jari", r"progress(?:ing)?"],
}
ACTIVITY_LEVEL_FINISH = [r"hydro[\s-]?test\s+(?:completed|done|passed|ok)", r"(?:completed|done|passed)\s+hydro[\s-]?test",
                         r"all\s+(?:\d+\s+)?(?:spools?|joints?|cables?)", r"saare\s+(?:spools?|joints?)", r"erection\s+complete",
                         r"fully\s+complet", r"poori\s+ho\s+gayi", r"entire", r"complete\s+line", r"loop\s+check\s+(?:completed|done|ok)",
                         r"test\s+(?:completed|done|passed|ok)", r"(?:completed|done)\b.*\bin\s+full"]

# blockers
BLOCKER_WORDS = [r"stopp?ed", r"\bstop\b", r"halt(?:ed)?", r"held\s+up", r"on\s+hold", r"\bband\b", r"ruk\s+gay[ai]", r"ruka",
                 r"could\s+not", r"couldn'?t", r"not\s+(?:able|possible)", r"nahi\s+ho\s+pay[ai]", r"delay(?:ed)?", r"waiting",
                 r"not\s+come", r"nahi\s+aaya", r"nahi\s+aya", r"idle", r"break\s*down", r"broke", r"kharab", r"short(?:age)?\b", r"\bno\s+work\b",
                 r"affected", r"suspended", r"not\s+(?:yet\s+)?started", r"nahi\s+hua", r"under\s+repair", r"\bawaited\b", r"(?:client|owner|pmc)\s+hold"]
CAUSES = {
    "weather": {"rain": [r"rain(?:ing|ed|s|y)?\b", r"baar?ish", r"barsaat", r"shower"], "heat": [r"heat", r"garmi"], "wind": [r"high\s+wind", r"toofan", r"storm"],
                "lightning": [r"lightning", r"bijli\s+chamak"], "waterlogging": [r"water[\s-]?logg(?:ed|ing)", r"pani\s+bhar"]},
    "material": {"not_received": [r"material\s+(?:not|nahi)", r"not\s+(?:received|issued|come)", r"nahi\s+aa?ya", r"shortage\s+of", r"short\s+of",
                                  r"(?:spools?|cement|cable|electrode|bolts?)\s+(?:not|nahi)"]},
    "permit_hse": {"permit": [r"no\s+permit", r"permit\s+(?:not|nahi|expired|pending)", r"ptw\s+(?:not|pending)", r"without\s+permit"]},
    "manpower": {"shortage": [r"manpower\s+short", r"labou?r\s+short", r"less\s+manpower", r"workers?\s+absent", r"shifted\s+to", r"strike", r"log\s+kam"]},
    "equipment": {"breakdown": [r"break\s*down", r"broke(?:n)?", r"machine\s+kharab", r"crane\s+(?:down|kharab|not\s+working)", r"not\s+working",
                                r"hydraulic\s+(?:leak|failure)", r"under\s+repair"], "idle": [r"\bidle\b"],
                  "unavailable": [r"waiting\s+for\s+(?:crane|hydra|machine|excavator)", r"crane\s+not\s+available"]},
    "drawing_rev": {"revision": [r"drawing", r"\brev(?:ision)?\b", r"\bifc\b", r"clash"]},
    "rework": {"rework": [r"rework", r"re-?weld", r"redo", r"rejected", r"repair", r"dobara"]},
    "client_hold": {"hold": [r"client\s+(?:hold|stopped|instruction)", r"owner\s+hold", r"pmc\s+hold"]},
    "access": {"access": [r"no\s+access", r"access\s+(?:blocked|not)", r"road\s+blocked", r"scaffold(?:ing)?\s+not"]},
    "power": {"outage": [r"power\s+(?:cut|failure|off)", r"no\s+power", r"bijli\s+nahi", r"dg\s+(?:failure|down)"]},
}

# HSE incident taxonomy
HSE_TYPES = {
    "near_miss": [r"near[\s-]?miss", r"bal\s+bal\s+bach", r"sling\s+slipp?ed", r"almost\s+(?:fell|hit)", r"dropped\s+object", r"slipp?ed\s+from"],
    "first_aid": [r"first[\s-]?aid", r"minor\s+injur", r"cut\s+on", r"chot"],
    "lti": [r"lost\s+time", r"hospital", r"fracture", r"serious\s+injur", r"admitted"],
    "property_damage": [r"damag(?:ed|e)", r"toot\s+gay"],
    "spill": [r"spill", r"oil\s+leak"],
    "fire": [r"\bfire\b(?!\s*(?:water|fighting|hydrant|line|pump|extinguisher|alarm|proofing))", r"\baag\b\s+(?:lag|lagi)", r"\bsmoke\b"],
    "gas_release": [r"gas\s+(?:leak|release)", r"h2s"],
    "unsafe_act": [r"without\s+(?:harness|helmet|ppe)", r"no\s+(?:harness|helmet|ppe)", r"unsafe\s+act", r"harness\s+nahi"],
    "unsafe_condition": [r"unsafe", r"open\s+excavation", r"no\s+barricad", r"loose\s+scaffold", r"barricad(?:e|ing)\s+(?:missing|nahi)"],
}
HSE_SEVERITY = {"lti": "critical", "fire": "critical", "gas_release": "critical", "near_miss": "major", "first_aid": "minor",
                "property_damage": "minor", "spill": "minor", "unsafe_act": "minor", "unsafe_condition": "observation"}
STOP_WORK = [r"stop[\s-]?work", r"stopped\s+by\s+(?:hse|safety)", r"hse\s+stopped", r"safety\s+(?:ne\s+)?(?:stopped|band)"]
MISHAP = {"equipment": [r"sling", r"crane", r"hydra", r"machine"], "procedural": [r"wrong\s+(?:procedure|sequence)", r"without\s+permit"],
          "material": [r"wrong\s+material", r"defective"], "human_error": [r"mistake", r"galti", r"wrong\s+(?:spool|line)"],
          "design": [r"design\s+error", r"clash"]}

# activity type → permit type (spec §4.3)
PERMIT_TRIGGERS = {
    "hot_work": [r"\bweld(?:ing|ed)?\b(?!\s*(?:machine|m/c|set))", r"gas\s+cutting", r"torch\s+cutting", r"grinding"],
    "confined_space": [r"confined\s+space", r"inside\s+(?:the\s+)?(?:[a-z]+\s+){0,2}(?:tank|basin|vessel|pit)", r"basin\s+(?:inside|andar)", r"manhole"],
    "height": [r"at\s+height", r"el\s*\+\s*(?:1[2-9]|[2-9]\d)", r"top\s+of\s+rack", r"scaffold"],
    "excavation": [r"excavat", r"digging", r"khudai", r"trench"],
    "radiography": [r"radiograph", r"\brt\b", r"x-?ray"],
}

OBJECT_CLASSES = {
    "spool": [r"spools?", r"\bspl\b"], "line": [r"\bline\b"], "joint": [r"joints?"], "foundation": [r"foundation", r"footing", r"\bfdn\b", r"\bF-?\d{1,2}\b"],
    "cable": [r"cables?", r"cabling"], "tray": [r"tray"], "loop": [r"\bloop"], "pump": [r"\bpump\b", r"\bP-\d{3}[A-Z]?\b"],
    "compressor": [r"compressor", r"\bK-\d{3}\b"], "transformer": [r"transformer", r"\bTR-\d+"], "panel": [r"panel"],
    "steel": [r"steel", r"columns?", r"beams?"], "support": [r"supports?"], "transmitter": [r"transmitter"],
    "instrument": [r"instruments?"], "tank shell": [r"shell\s+plate", r"tank\s+shell"], "basin": [r"basin"],
    "drainage": [r"drain(?:age)?", r"nali"], "road": [r"\broad\b"], "fence": [r"fenc(?:e|ing)"], "earthing": [r"earthing"],
    "pedestal": [r"pedestal"], "trench": [r"trench"], "slab": [r"\bslab"], "brickwork": [r"brickwork"], "tubing": [r"tubing"],
    "bolt": [r"\bbolts?\b"], "grating": [r"grating"], "girder": [r"girder"], "lighting": [r"lighting", r"light\s+fixtures?"],
    "scaffold": [r"scaffold"], "tank pad": [r"tank\s+pad"], "ring wall": [r"ring\s+wall"],
}

TRADES = {"fitter": r"fitters?", "welder": r"welders?", "helper": r"helpers?|khalasi", "rigger": r"riggers?", "mason": r"masons?|mistri",
          "electrician": r"electricians?", "carpenter": r"carpenters?", "bar_bender": r"bar\s*benders?", "operator": r"operators?",
          "painter": r"painters?", "technician": r"technicians?", "labour": r"labou?rs?|workers?|mazdoor|log\b"}

EQUIP_WORDS = {"crane": r"crane", "hydra": r"hydra", "excavator": r"excavator|jcb|poclain", "transit_mixer": r"transit\s+mixer|tm\b",
               "welding_machine": r"welding\s+(?:m/c|machine)", "dg_set": r"\bdg\b", "boom_placer": r"boom\s+placer"}

UOM = r"(?:m3|cum|cu\.?\s?m|rmt|mtrs?|meters?|metres?|\bm\b|nos?\.?|numbers?|dia[\s-]?inch(?:es)?|inch[\s-]?dia|\bid\b|kg|mt\b|tons?|bags?|joints?|sqm|m2)"

STOPWORDS = set("""a an the at in on of for to and or with near by from is was were be been are has have had it this that these those
pe par mein me ka ki ke ko se aur hai hain tha the thi ho hua hui gaya gaye gayi kiya kiye kar karo raha rahi rahe abhi aaj kal
today yesterday tomorrow done completed complete started start finished finish erected erect ok okay also all some please sir team work
kaam chal shuru poora pura progress fully night day shift raat din unit site area line nos no number total approx about
""".split())
# words that must never become a learned alias on their own
GENERIC_TERMS = STOPWORDS | {"rack", "ghar", "house", "side", "shed", "yard", "gate", "spool", "spools", "joint", "joints", "cable",
                             "tray", "panel", "steel", "pipe", "piping", "civil", "electrical", "work", "crane", "machine"}

UNPLANNED_CLASS_RULES = {
    "emergency": [r"emergency", r"urgent", r"leak", r"burst", r"collapse", r"flood"],
    "rework": [r"rework", r"re-?weld", r"redo", r"dismantl", r"rejected", r"repair", r"dobara"],
    "site_prep": [r"temporar", r"\btemp\b", r"drain(?:age)?", r"level(?:l)?ing", r"access\s+road", r"approach\s+road", r"fenc", r"barricad",
                  r"clearing", r"dewater", r"site\s+prep", r"housekeeping", r"store\s+shed", r"nali"],
    "scope_creep": [r"extra", r"additional", r"client\s+(?:asked|instruction|request)", r"new\s+requirement", r"not\s+in\s+(?:drawing|scope)"],
}
