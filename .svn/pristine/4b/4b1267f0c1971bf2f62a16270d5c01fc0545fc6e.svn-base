# modules/home/weather_provider.py
from __future__ import annotations
import time
import requests

# ===== Defaults (used if no query args) ======================================
DEFAULT_LAT = 42.4734   # Southfield, MI
DEFAULT_LON = -83.2219
DEFAULT_TZ  = "America/Detroit"

# ===== Named presets ==========================================================
# Edit these coords/names as you like. (All Timezone = America/Detroit except Paris.)
PRESETS = [
    {
        "id": "ortonville",
        "name": "Ortonville Home",
        "lat": 42.8520,
        "lon": -83.4447,
        "tz": "America/Detroit",
    },
    {
        "id": "southfield",
        "name": "Southfield SFJ DataCenter",
        "lat": 42.4734,
        "lon": -83.2219,
        "tz": "America/Detroit",
    },
    {
        "id": "northern",
        "name": "Saint Helen Cottage",
        "lat": 44.3642,   # St. Helen-ish
        "lon": -84.4103,
        "tz": "America/Detroit",
    },
    {
        "id": "europe",
        "name": "Lithunian Kaunas House",
        "lat": 48.8566,   # Paris (placeholder; change if you want)
        "lon": 2.3522,
        "tz": "Europe/Paris",
    },
]

# ===== Simple in-memory cache (10 min) =======================================
_CACHE: dict[str, tuple[float, dict]] = {}
TTL_SECONDS = 600

def _cache_get(key: str) -> dict | None:
    now = time.time()
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, data = hit
    if now - ts > TTL_SECONDS:
        return None
    return data

def _cache_set(key: str, data: dict) -> None:
    _CACHE[key] = (time.time(), data)

# ===== Fetcher ================================================================
def fetch_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON, tz: str = DEFAULT_TZ, label: str | None = None) -> dict:
    key = f"{lat:.4f},{lon:.4f},{tz}"
    cached = _cache_get(key)
    if cached:
        # allow dynamic label override without re-fetch
        if label:
            cached = {**cached, "location": label}
        return cached

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,precipitation,weather_code"
        f"&hourly=temperature_2m,precipitation_probability"
        f"&timezone={tz}"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    j = r.json()

    cur = j.get("current", {})
    hourly = j.get("hourly", {})

    out = {
        "location": label or "Location",
        "coords": {"lat": lat, "lon": lon, "tz": tz},
        "now": {
            "temp_f": c_to_f(cur.get("temperature_2m")),
            "feels_f": c_to_f(cur.get("apparent_temperature")),
            "pop": safe_int((hourly.get("precipitation_probability") or [None])[0]),
            "code": cur.get("weather_code"),
            "time": cur.get("time"),
        },
        "next12": summarize_next12(hourly),
        "updated_ts": int(time.time()),
    }

    _cache_set(key, out)
    return out

def c_to_f(x):
    return None if x is None else round((x * 9/5) + 32)

def safe_int(x):
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def summarize_next12(hourly: dict) -> dict:
    temps = hourly.get("temperature_2m") or []
    next12 = temps[:12] if len(temps) >= 12 else temps
    if not next12:
        return {"hi_f": None, "lo_f": None}
    hi = max(next12)
    lo = min(next12)
    return {"hi_f": c_to_f(hi), "lo_f": c_to_f(lo)}
