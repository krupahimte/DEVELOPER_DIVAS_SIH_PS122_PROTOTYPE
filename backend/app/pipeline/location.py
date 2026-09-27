"""Layer 3 — location. GPS → geofence_zone_id (a KG node), never a hard gate.

* point-in-polygon with shapely
* gps_accuracy > 50 m ⇒ result is `boundary`, and every zone within the accuracy
  radius is kept as "nearby" (no zone signal, but no penalty either)
* missing GPS ⇒ `unknown` (lowers verification later, never rejects)
"""
import math

from shapely.geometry import Point, Polygon

from .kg import KG

_polys: dict[str, Polygon] = {}


def _poly(kg: KG, wf_id: str) -> Polygon:
    if wf_id not in _polys:
        _polys[wf_id] = Polygon(kg.work_fronts[wf_id].polygon)
    return _polys[wf_id]


def meters_between(lat1, lon1, lat2, lon2) -> float:
    dy = (lat2 - lat1) * 111_320
    dx = (lon2 - lon1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _dist_to_poly_m(kg, wf_id, lat, lon) -> float:
    p = _poly(kg, wf_id)
    pt = Point(lon, lat)
    if p.contains(pt):
        return 0.0
    near = p.exterior.interpolate(p.exterior.project(pt))
    return meters_between(lat, lon, near.y, near.x)


def geofence(kg: KG, lat, lon, accuracy) -> dict:
    """→ {result, zone, nearby: [wf...], distance_m}"""
    if lat is None or lon is None:
        return {"result": "unknown", "zone": None, "nearby": [], "distance_m": None}
    dists = sorted((_dist_to_poly_m(kg, wf, lat, lon), wf) for wf in kg.work_fronts)
    d0, wf0 = dists[0]
    acc = accuracy if accuracy is not None else 15
    nearby = [wf for d, wf in dists if d <= max(acc, 25)]
    if acc > 50:
        return {"result": "boundary", "zone": None, "nearby": nearby or [wf0], "distance_m": round(d0, 1)}
    if d0 == 0.0:
        return {"result": "inside", "zone": wf0, "nearby": [wf0], "distance_m": 0.0}
    if d0 <= acc:
        return {"result": "boundary", "zone": None, "nearby": nearby, "distance_m": round(d0, 1)}
    return {"result": "outside", "zone": None, "nearby": [], "distance_m": round(d0, 1)}


def zone_centroid(kg: KG, wf_id: str):
    w = kg.work_fronts[wf_id]
    return w.centroid_lat, w.centroid_lon
