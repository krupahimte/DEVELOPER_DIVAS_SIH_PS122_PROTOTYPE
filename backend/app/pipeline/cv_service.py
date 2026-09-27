"""CV plausibility — MOCK for the prototype.

Interface is what a real detector (e.g. YOLOv8 fine-tuned on construction classes)
would implement:  check(photo_path, claim) -> {objects, score, model_version}

Scope discipline: this says the photo is *consistent with* the claim. It does not
say the work happened, and it never measures progress.
"""
import json
from pathlib import Path

from .. import config

MODEL_VERSION = "cv-stub-0.3 (keyword+lookup; YOLO drop-in)"

KEYWORDS = {
    "spool": ["pipe_section", "flange"], "pipe": ["pipe_section"], "rack": ["steel_structure", "pipe_section"],
    "hydro": ["pressure_gauge", "pipe_section", "hose"], "gauge": ["pressure_gauge"], "test": ["pressure_gauge"],
    "excav": ["excavator", "soil_pit"], "pit": ["soil_pit"], "concrete": ["concrete_surface", "transit_mixer"],
    "rebar": ["rebar_mesh"], "cable": ["cable_drum", "cable_tray"], "tray": ["cable_tray"], "crane": ["crane", "sling"],
    "weld": ["welding_arc", "welder_ppe"], "panel": ["electrical_panel"], "pump": ["pump", "baseplate"],
    "drain": ["trench", "water"], "sling": ["sling", "crane"], "tank": ["tank_shell"], "steel": ["steel_structure"],
}
# what a plausible photo for a given claimed action/object should contain
EXPECT = {
    "erect": {"pipe_section", "steel_structure", "flange", "crane"}, "weld": {"welding_arc", "pipe_section", "welder_ppe"},
    "test": {"pressure_gauge", "pipe_section", "hose"}, "excavate": {"excavator", "soil_pit"}, "pour": {"concrete_surface", "transit_mixer"},
    "rebar": {"rebar_mesh"}, "pull": {"cable_drum", "cable_tray"}, "install": {"cable_tray", "electrical_panel", "pump", "baseplate", "pipe_section"},
    "lay": {"trench", "cable_drum", "water"}, "align": {"pump", "baseplate"},
}

_lookup_path = config.SAMPLE_DIR / "photos" / "cv_lookup.json"


def _lookup() -> dict:
    try:
        return json.loads(_lookup_path.read_text())
    except Exception:
        return {}


def check(photo_path: str | Path, claim: dict) -> dict:
    name = Path(photo_path).name.lower()
    objs = _lookup().get(name)
    if objs is None:
        objs = sorted({o for k, v in KEYWORDS.items() if k in name for o in v})
    if not objs:
        objs = ["worker", "site_background"]
    expected = EXPECT.get(claim.get("action") or "", set())
    if not expected:
        score = 0.55 if len(objs) > 2 else 0.4
    else:
        hit = len(expected & set(objs))
        score = 0.35 + 0.6 * min(1.0, hit / 2)
    # stub stand-in for a detector that knows the claimed object class
    ocls = (claim.get("object_class") or "").split(" ")[0]
    if ocls and ocls in name:
        objs = sorted(set(objs) | {ocls})
        score = max(score, 0.85)
    return {"objects": objs, "score": round(score, 2), "model_version": MODEL_VERSION}
