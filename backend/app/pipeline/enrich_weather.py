"""Layer 9 — weather enrichment (FETCHED). Two fields, not one:
weather_reported (the claim, EXTRACTED) vs weather_fetched (the evidence, FETCHED).

Sources, per settings.weather_mode:
  seeded_first  site-station seed table, then Open-Meteo (default: deterministic demo)
  live_first    Open-Meteo archive/forecast (free, no key), then the seed table
  seeded_only   never touch the network
"""
from datetime import date

import httpx
from sqlmodel import Session

from ..models import WeatherObs

_live_cache: dict = {}


def _live(lat, lon, day: date):
    key = (round(lat, 2), round(lon, 2), day)
    if key in _live_cache:
        return _live_cache[key]
    res = None
    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {"latitude": lat, "longitude": lon, "start_date": day.isoformat(), "end_date": day.isoformat(),
                  "hourly": "precipitation", "daily": "precipitation_sum,temperature_2m_max,wind_speed_10m_max", "timezone": "Asia/Kolkata"}
        r = httpx.get(url, params=params, timeout=3.0)
        if r.status_code == 200:
            j = r.json()
            hourly = [x or 0.0 for x in j["hourly"]["precipitation"]]
            if any(v is not None for v in j["daily"]["precipitation_sum"]):
                res = {"rain_mm": j["daily"]["precipitation_sum"][0] or 0.0, "temp_max": j["daily"]["temperature_2m_max"][0],
                       "wind_kmph": j["daily"]["wind_speed_10m_max"][0], "hourly": hourly, "source": "open-meteo archive"}
    except Exception:
        res = None
    _live_cache[key] = res
    return res


def _seeded(session: Session, day: date):
    w = session.get(WeatherObs, day)
    if not w:
        return None
    return {"rain_mm": w.rain_mm, "temp_max": w.temp_max, "wind_kmph": w.wind_kmph, "hourly": w.hourly_rain, "source": w.source}


def fetch(session: Session, lat, lon, day: date, mode: str):
    order = {"seeded_first": ("seed", "live"), "live_first": ("live", "seed"), "seeded_only": ("seed",)}.get(mode, ("seed", "live"))
    for src in order:
        if src == "seed":
            r = _seeded(session, day)
        else:
            r = _live(lat, lon, day) if lat is not None else None
        if r:
            return r
    return None


def enrich(session: Session, ev, lat, lon, mode: str):
    """Sets weather_fetched/source/window/corroborates/severity on the event."""
    if not (ev.weather_reported or ev.cause_category == "weather"):
        return
    w = fetch(session, lat, lon, ev.event_date, mode)
    if not w:
        ev.weather_corroborates = "unavailable"
        ev.weather_source = None
        return
    win = (ev.field_conf or {}).get("_time_window")
    hourly = w.get("hourly") or []
    if win and len(hourly) >= 24:
        rain_win = round(sum(hourly[win[0]:win[1]]), 1)
        ev.weather_window = f"{ev.event_date:%d-%b} {win[0]:02d}:00–{win[1]:02d}:00"
    else:
        rain_win = w["rain_mm"]
        ev.weather_window = f"{ev.event_date:%d-%b} (whole day)"
    ev.weather_fetched = {"rain_mm": w["rain_mm"], "rain_mm_window": rain_win, "temp_max": w["temp_max"], "wind_kmph": w["wind_kmph"]}
    ev.weather_source = w["source"]
    claim = (ev.weather_reported or ev.cause_subcategory or "rain").lower()
    if "heat" in claim or "garmi" in claim:
        ok = (w["temp_max"] or 0) >= 38
    elif "wind" in claim or "storm" in claim or "toofan" in claim:
        ok = (w["wind_kmph"] or 0) >= 40
    else:
        ok = rain_win >= 2.5
    ev.weather_corroborates = "true" if ok else "false"
    ev.weather_severity = "extreme" if w["rain_mm"] >= 35 else ("adverse" if w["rain_mm"] >= 2.5 or (w["temp_max"] or 0) >= 38 else "normal")
    prov = dict(ev.provenance or {})
    prov.update({"weather_fetched": "FETCHED", "weather_source": "FETCHED", "weather_corroborates": "DERIVED", "weather_severity": "DERIVED",
                 "weather_window": "FETCHED"})
    ev.provenance = prov
