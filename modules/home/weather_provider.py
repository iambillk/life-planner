# modules/home/weather_provider.py
from __future__ import annotations
import os, time, requests
from typing import Any, Dict, List, Optional

# ===== Defaults ===============================================================
DEFAULT_LAT = 42.4734   # Southfield, MI
DEFAULT_LON = -83.2219
DEFAULT_TZ  = "America/Detroit"

# ===== Named presets ==========================================================
PRESETS = [
    {"id": "ortonville", "name": "Ortonville Home",           "lat": 42.8520, "lon": -83.4447, "tz": "America/Detroit"},
    {"id": "southfield", "name": "Meadview, AZ",              "lat": 36.0022, "lon": 114.0685, "tz": "America/Detroit"},
    {"id": "northern",   "name": "Saint Helen Cottage",       "lat": 44.3634, "lon": -84.4102, "tz": "America/Detroit"},
    {"id": "europe",     "name": "Lithunian Kaunas House",    "lat": 54.8968, "lon":  23.8324, "tz": "Europe/Paris"},
]

# ===== Cache (10 min) =========================================================
_CACHE: dict[str, tuple[float, dict]] = {}
TTL_SECONDS = 600

def _cache_get(key: str) -> Optional[dict]:
    hit = _CACHE.get(key)
    if not hit: return None
    ts, data = hit
    if time.time() - ts > TTL_SECONDS: return None
    return data

def _cache_set(key: str, data: dict) -> None:
    _CACHE[key] = (time.time(), data)

# ===== Helpers ================================================================
def _round_or_none(x: Any) -> Optional[int]:
    try:
        return None if x is None else round(float(x))
    except Exception:
        return None

def _safe_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def _summarize_next12_from_idx(temps_f: List[float] | None, start_idx: Optional[int]) -> dict:
    if not temps_f:
        return {"hi_f": None, "lo_f": None}
    window = temps_f[start_idx:start_idx+12] if (start_idx is not None) else temps_f[:12]
    if not window:
        window = temps_f[-12:]
    if not window:
        return {"hi_f": None, "lo_f": None}
    return {"hi_f": round(max(window)), "lo_f": round(min(window))}

# ===== Visual Crossing ========================================================
VC_API_KEY = "RKQ5HVU7GG29CAJM5YDDC6F9A"

def _vc_fetch(lat: float, lon: float, tz: str, label: Optional[str]) -> Optional[dict]:
    """
    Returns our standard payload dict OR None on failure (then caller will fallback).
    Uses Timeline API: current conditions + hourly for next ~48h.
    """
    if not VC_API_KEY:
        return None
    base = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    params = {
        "unitGroup": "us",                 # Fahrenheit, mph, inches
        "include": "current,hours",
        "iconSet": "icons2",
        "key": VC_API_KEY,
        "contentType": "json",
        "timezone": tz
    }
    try:
        r = requests.get(f"{base}/{lat:.4f},{lon:.4f}", params=params, timeout=8)
        r.raise_for_status()
        j = r.json()
    except Exception:
        return None

    # Current conditions
    cur = j.get("currentConditions") or {}
    temp_f    = _round_or_none(cur.get("temp"))
    feels_f   = _round_or_none(cur.get("feelslike"))
    cur_time  = cur.get("datetime") or cur.get("datetimeStr") or None
    cur_epoch = cur.get("datetimeEpoch")

    # Gather first ~48 hourly entries (flatten across days)
    hours: List[dict] = []
    for d in (j.get("days") or []):
        h = d.get("hours") or []
        hours.extend(h)
        if len(hours) >= 60:
            break
    temps_f = [_round_or_none(h.get("temp")) for h in hours]
    pops    = [_safe_int(h.get("precipprob")) for h in hours]  # 0..100
    epochs  = [h.get("datetimeEpoch") for h in hours]

    # Align index to current hour (by epoch if possible)
    idx = None
    if cur_epoch is not None and epochs:
        try:
            idx = epochs.index(cur_epoch)
        except ValueError:
            # nearest hour by epoch
            try:
                diffs = [abs((e or 0) - cur_epoch) for e in epochs]
                idx = diffs.index(min(diffs))
            except Exception:
                idx = None

    # If current temp missing, try aligned hourly
    if temp_f is None and idx is not None and 0 <= idx < len(temps_f):
        temp_f = temps_f[idx]
    if feels_f is None:
        feels_f = temp_f

    # POP now from aligned hour (fallback to last known)
    pop_now = None
    if idx is not None and 0 <= idx < len(pops):
        pop_now = pops[idx]
    elif pops:
        pop_now = next((p for p in pops if p is not None), pops[-1])

    out = {
        "location": label or "Location",
        "coords": {"lat": lat, "lon": lon, "tz": tz},
        "now": {
            "temp_f": temp_f,
            "feels_f": feels_f,
            "pop": pop_now,
            "code": None,             # VC 'icon' is string; your UI uses numeric code—leave None or adapt mapping.
            "time": cur_time,
        },
        "next12": _summarize_next12_from_idx(temps_f, idx),
        "updated_ts": int(time.time()),
        "source": "visual-crossing"
    }
    return out

# ===== Open-Meteo Fallback ====================================================
def _om_fetch(lat: float, lon: float, tz: str, label: Optional[str]) -> dict:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&timezone={tz}"
        f"&timeformat=iso8601"
        f"&temperature_unit=fahrenheit"
        f"&current=temperature_2m,apparent_temperature,precipitation,weather_code,time"
        f"&hourly=time,temperature_2m,precipitation_probability"
    )
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        j = r.json()
    except Exception as e:
        return {
            "location": label or "Location",
            "coords": {"lat": lat, "lon": lon, "tz": tz},
            "now": {"temp_f": None, "feels_f": None, "pop": None, "code": None, "time": None},
            "next12": {"hi_f": None, "lo_f": None},
            "updated_ts": int(time.time()),
            "error": str(e),
            "source": "open-meteo"
        }

    cur = j.get("current", {}) or {}
    hourly = j.get("hourly", {}) or {}
    hh_times = hourly.get("time") or []
    hh_temps = hourly.get("temperature_2m") or []
    hh_pop   = hourly.get("precipitation_probability") or []

    # align by exact match if possible
    idx = None
    cur_time_iso = cur.get("time")
    if cur_time_iso and cur_time_iso in hh_times:
        idx = hh_times.index(cur_time_iso)

    temp_f = None
    if idx is not None and 0 <= idx < len(hh_temps):
        temp_f = _round_or_none(hh_temps[idx])
    if temp_f is None:
        temp_f = _round_or_none(cur.get("temperature_2m"))

    pop_now = None
    if idx is not None and 0 <= idx < len(hh_pop):
        pop_now = _safe_int(hh_pop[idx])
    elif hh_pop:
        pop_now = _safe_int(hh_pop[-1])

    return {
        "location": label or "Location",
        "coords": {"lat": lat, "lon": lon, "tz": tz},
        "now": {
            "temp_f": temp_f,
            "feels_f": _round_or_none(cur.get("apparent_temperature")) or temp_f,
            "pop": pop_now,
            "code": cur.get("weather_code"),
            "time": cur_time_iso,
        },
        "next12": _summarize_next12_from_idx([_round_or_none(x) for x in hh_temps], idx),
        "updated_ts": int(time.time()),
        "source": "open-meteo"
    }

# ===== Public API =============================================================
def fetch_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, tz: str = DEFAULT_TZ, label: str | None = None) -> dict:
    key = f"{lat:.4f},{lon:.4f},{tz}"
    cached = _cache_get(key)
    if cached:
        if label:
            cached = {**cached, "location": label}
        return cached

    # Try Visual Crossing first; fallback to Open-Meteo
    out = _vc_fetch(lat, lon, tz, label)
    if out is None:
        out = _om_fetch(lat, lon, tz, label)

    _cache_set(key, out)
    return out
