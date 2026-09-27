"""Layer 4 — evidence: EXIF (GPS + timestamp) and CV plausibility.

Photos are evidence only — never a progress source.
"""
from datetime import datetime, timedelta
from pathlib import Path

from PIL import ExifTags, Image

from .. import config
from . import cv_service


def _to_deg(v):
    d, m, s = [float(x) for x in v]
    return d + m / 60 + s / 3600


def read_exif(path: Path) -> dict:
    out = {"gps": None, "timestamp": None}
    try:
        with Image.open(path) as im:
            ex = im.getexif()
            if not ex:
                return out
            tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
            sub = ex.get_ifd(0x8769) or {}
            dto = sub.get(36867) or tags.get("DateTime")
            if dto:
                try:
                    out["timestamp"] = datetime.strptime(str(dto), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    pass
            gps = ex.get_ifd(0x8825)
            if gps and 2 in gps and 4 in gps:
                lat = _to_deg(gps[2]) * (-1 if gps.get(1) == "S" else 1)
                lon = _to_deg(gps[4]) * (-1 if gps.get(3) == "W" else 1)
                out["gps"] = [round(lat, 6), round(lon, 6)]
    except Exception:
        pass
    return out


def photo_path(photo_id: str) -> Path:
    p = config.UPLOAD_DIR / photo_id
    if p.exists():
        return p
    return config.SAMPLE_DIR / "photos" / photo_id


def assess(photo_ids: list[str], claim: dict, captured_at: datetime | None) -> dict:
    """→ exif_gps, exif_timestamp, recycled flag, cv objects/score."""
    res = {"exif_gps": [], "exif_timestamp": None, "recycled": False, "cv_objects": [], "cv_score": None, "cv_model": None}
    scores = []
    for pid in photo_ids or []:
        p = photo_path(pid)
        ex = read_exif(p) if p.exists() else {"gps": None, "timestamp": None}
        if ex["gps"] and not res["exif_gps"]:
            res["exif_gps"] = ex["gps"]
        if ex["timestamp"] and res["exif_timestamp"] is None:
            res["exif_timestamp"] = ex["timestamp"]
            if captured_at and captured_at - ex["timestamp"] > timedelta(hours=24):
                res["recycled"] = True
        cv = cv_service.check(p, claim)
        res["cv_objects"] = sorted(set(res["cv_objects"]) | set(cv["objects"]))
        res["cv_model"] = cv["model_version"]
        scores.append(cv["score"])
    if scores:
        res["cv_score"] = max(scores)
    return res
