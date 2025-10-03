# modules/network/service_librenms.py
import os
import time
import math
import requests
from typing import Any, Dict, Iterable, List, Optional
from flask import current_app

# ----------------------------
# Simple in-memory cache (TTL)
# ----------------------------
_cache: Dict[str, tuple[float, Any]] = {}

# A single Session keeps connections alive across requests
_session: Optional[requests.Session] = None


def _cfg(key: str, default=None):
    """Prefer Flask config, then env var, then default."""
    try:
        val = current_app.config.get(key)  # type: ignore[attr-defined]
        if val is not None:
            return val
    except Exception:
        pass
    return os.getenv(key, default)


def _get_base_url() -> str:
    base = _cfg("LIBRENMS_BASE_URL")
    if not base:
        raise RuntimeError("LIBRENMS_BASE_URL not configured")
    return str(base).rstrip("/")


def _get_token() -> str:
    token = _cfg("LIBRENMS_API_TOKEN")
    if not token:
        raise RuntimeError("LIBRENMS_API_TOKEN not configured")
    return str(token)


def _ttl() -> int:
    return int(_cfg("LIBRENMS_CACHE_TTL", 60))  # seconds


def _timeout() -> int:
    return int(_cfg("LIBRENMS_TIMEOUT", 8))  # seconds


def _retries() -> int:
    return int(_cfg("LIBRENMS_RETRIES", 1))  # small retry for flakiness


def _cache_key(path: str) -> str:
    # path already includes query string; good enough for local cache
    return f"librenms:{path}"


def _session_headers() -> Dict[str, str]:
    return {
        "X-Auth-Token": _get_token(),
        "Accept": "application/json",
        "User-Agent": "wtr.network/monitor (librenms-client)",
    }


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(_session_headers())
    return _session


def _get(path: str, *, nocache: bool = False) -> Any:
    """
    GET to LibreNMS with bearer token, cached by path.
    """
    key = _cache_key(path)
    now = time.time()
    if not nocache:
        hit = _cache.get(key)
        if hit and (now - hit[0]) < _ttl():
            return hit[1]

    url = f"{_get_base_url()}/api/v0{path}"
    sess = _get_session()

    last_exc = None
    for attempt in range(1, _retries() + 2):
        try:
            resp = sess.get(url, timeout=_timeout())
            # Basic rate-limit/backoff awareness (LibreNMS typically doesn't 429, but just in case)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        time.sleep(int(retry_after))
                    except Exception:
                        time.sleep(1)
                else:
                    time.sleep(1)
                continue
            resp.raise_for_status()
            data = resp.json()
            _cache[key] = (now, data)
            return data
        except Exception as e:
            last_exc = e
            # small exponential backoff
            time.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))
    # If we got here, all attempts failed
    raise last_exc if last_exc else RuntimeError("LibreNMS request failed")


# ----------------------------
# LibreNMS endpoints
# ----------------------------
def get_device(device_id: int) -> dict:
    """
    Returns LibreNMS device payload for a specific numeric device_id.
    https://docs.librenms.org/API/Devices/#get-a-single-device
    """
    return _get(f"/devices/{int(device_id)}")


def get_health(device_id: int) -> dict:
    """
    Returns health metrics payload (temps, fans, memory, storage, etc.)
    https://docs.librenms.org/API/Health/
    """
    return _get(f"/devices/{int(device_id)}/health")


# ----------------------------
# Helpers / Normalizers
# ----------------------------
def _pick_device_payload(dev: Any) -> Dict[str, Any]:
    """
    Normalize various LibreNMS API shapes into a single device dict.
    Shapes seen in the wild:
      { "device": {...} }
      { "devices": [ {...} ] }
      { ...device fields... }
    """
    if isinstance(dev, dict):
        if "device" in dev and isinstance(dev["device"], dict):
            return dev["device"]
        if "devices" in dev and isinstance(dev["devices"], list) and dev["devices"]:
            maybe = dev["devices"][0]
            return maybe if isinstance(maybe, dict) else {}
        return dev
    return {}


def _normalize_status(s_raw: Any, uptime: Any = None, last_polled: Any = None) -> Optional[str]:
    """
    Return 'up', 'down', or None.
    """
    if isinstance(s_raw, (int, bool)):
        return "up" if s_raw in (1, True) else "down"
    if isinstance(s_raw, str):
        s = s_raw.strip().lower()
        if s in ("1", "up", "true"):
            return "up"
        if s in ("0", "down", "false"):
            return "down"
    # Fallback heuristic: if recently polled and uptime present, treat as up
    if uptime and last_polled:
        return "up"
    return None


def _humanize_seconds(sec: Optional[float]) -> Optional[str]:
    """
    Convert seconds into a compact human string, e.g. '3d 4h', '2h 5m', '45s'.
    """
    if sec is None:
        return None
    try:
        s = int(sec)
    except Exception:
        return None
    if s < 0:
        return None
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    if h < 48:
        return f"{h}h {m}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


def summarize_live_status(device_id: Optional[int]) -> dict:
    """
    Returns a normalized live status summary for one device.
    Keys:
      ok, error, status, status_raw, status_reason,
      live_ip, uptime_seconds, uptime_human, last_polled,
      icmp_disable, snmp_disable, device_disabled
    """
    if not device_id:
        return {
            "ok": False, "error": "No librenms_device_id set", "status": None,
            "live_ip": None, "uptime_seconds": None, "uptime_human": None, "last_polled": None
        }

    try:
        dev = get_device(int(device_id))
        payload = _pick_device_payload(dev)

        # Extract raw values safely (field names seen in the wild)
        s_raw = payload.get("status")  # 1/0/bool/str
        reason = payload.get("status_reason")  # 'icmp', 'snmp', ...
        live_ip = payload.get("ip") or payload.get("hostname")

        # Uptime: LibreNMS often exposes one or more of these
        uptime = (
            payload.get("uptime")
            or payload.get("uptime_sec")
            or payload.get("device_uptime")
        )
        # Human variants (if provided by your install)
        uptime_h = (
            payload.get("uptime_long")
            or payload.get("uptime_text")
            or payload.get("uptime_human")
        )
        if not uptime_h:
            uptime_h = _humanize_seconds(uptime if isinstance(uptime, (int, float)) else None)

        last_polled = payload.get("last_polled") or payload.get("last_polled_timetaken")
        icmp_disable = payload.get("icmp_disable")
        snmp_disable = payload.get("snmp_disable")
        device_disabled = payload.get("disabled") or payload.get("disable")

        status = _normalize_status(s_raw, uptime=uptime, last_polled=last_polled)

        return {
            "ok": True,
            "error": None,
            "status": status,             # 'up' | 'down' | None
            "status_raw": s_raw,          # for debugging
            "status_reason": reason,      # show 'icmp', 'snmp', etc.
            "live_ip": live_ip,
            "uptime_seconds": uptime if isinstance(uptime, (int, float)) else None,
            "uptime_human": uptime_h,
            "last_polled": last_polled,
            "icmp_disable": icmp_disable,
            "snmp_disable": snmp_disable,
            "device_disabled": device_disabled,
        }
    except Exception as e:
        return {
            "ok": False, "error": str(e), "status": None,
            "live_ip": None, "uptime_seconds": None, "uptime_human": None, "last_polled": None
        }


def summarize_live_status_map(device_ids: Iterable[int]) -> Dict[int, str]:
    """
    Batch helper tailored for your JS widget.
    Returns { device_id: 'up' | 'down' | 'unknown' }
    """
    result: Dict[int, str] = {}
    for raw_id in device_ids:
        try:
            did = int(raw_id)
        except Exception:
            continue
        s = summarize_live_status(did).get("status")
        result[did] = s if s in ("up", "down") else "unknown"
    return result


def get_syslog(device_id: int, limit: int = 50) -> list[dict]:
    """
    Fetch device syslog entries. Returns a list (possibly empty).
    On failure, returns a single error row so the UI explains emptiness.
    """
    if not device_id:
        return []
    try:
        data = _get(f"/logs/syslog/{int(device_id)}?limit={int(limit)}")
        # Common shapes:
        # {"status":"ok","logs":[...]} or {"syslog":[...]} or plain list
        if isinstance(data, dict):
            if isinstance(data.get("logs"), list):
                return data["logs"]
            if isinstance(data.get("syslog"), list):
                return data["syslog"]
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        return [{
            "timestamp": None,
            "priority": "error",
            "program": None,
            "msg": f"Syslog unavailable: {e}"
        }]

# ----------------------------
# Service checks (warnings + critical)
# ----------------------------
from typing import Any, Dict, List, Optional

def _to_int(x: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(str(x).strip())
    except Exception:
        return default

def _normalize_hostname(item: dict) -> Optional[str]:
    return (
        item.get("hostname")
        or (item.get("device") or {}).get("hostname")
        or item.get("hostname_override")
        or item.get("service_ip")   # prefer real host/ip over #id
        or None
    )

def _is_service_obj(d: dict) -> bool:
    # Heuristic for a service row
    keys = set(d.keys())
    return (
        ("service_id" in keys or "id" in keys)
        and ("service_status" in keys or "status" in keys)
        and ("service_type" in keys or "type" in keys)
    ) or ("device_id" in keys and ("service_message" in keys or "service_name" in keys))

def _flatten_services(node: Any) -> List[dict]:
    """
    Robustly flatten whatever LibreNMS returns:
    - list of dicts
    - dict with 'services' or 'data'
    - dict of numeric keys -> dicts/lists
    - single dict service object
    """
    out: List[dict] = []

    def rec(x: Any):
        if x is None:
            return
        if isinstance(x, list):
            for v in x:
                rec(v)
            return
        if isinstance(x, dict):
            # direct service row?
            if _is_service_obj(x):
                out.append(x)
                return
            # traverse known containers first
            if "services" in x:
                rec(x["services"])
            if "data" in x:
                rec(x["data"])
            # now traverse remaining keys (avoid double-walking)
            for k, v in x.items():
                if k in ("services", "data"):
                    continue
                rec(v)
            return
        # scalars -> ignore

    rec(node)
    return out

def _normalize_one_service(s: dict) -> dict:
    state = _to_int(s.get("service_status") or s.get("status"), default=None)
    sev = "critical" if state == 2 else ("warning" if state == 1 else "unknown")
    return {
        "device_id": _to_int(s.get("device_id")),
        "hostname": _normalize_hostname(s),
        "service_id": _to_int(s.get("service_id") or s.get("id")),
        "type": (s.get("service_type") or s.get("type") or "unknown").lower(),
        "desc": s.get("service_desc") or s.get("desc") or "",
        "state": state,
        "sev": sev,  # 'warning' | 'critical' | 'unknown'
        "changed": _to_int(s.get("service_changed") or s.get("changed")),
        "message": s.get("service_message") or s.get("message") or None,
    }

def _dedupe(items: List[dict]) -> List[dict]:
    """Remove duplicate rows that arise from nested payloads / multi-fetch merges."""
    seen = set()
    out: List[dict] = []
    for it in items:
        key = (
            it.get("device_id"),
            it.get("service_id"),
            it.get("state"),
            it.get("changed") or it.get("message")
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

def _fetch_services_by_state(state_val: int) -> List[dict]:
    data = _get(f"/services?state={int(state_val)}", nocache=True)
    return _dedupe([_normalize_one_service(s) for s in _flatten_services(data)])

def get_failed_services(include_warning: bool = True) -> List[dict]:
    """
    Returns WARNING (state=1) + CRITICAL (state=2). If the state filter
    is ignored by your LibreNMS build, falls back to 'fetch all' + filter.
    """
    items: List[dict] = []
    # CRITICAL
    try:
        items.extend(_fetch_services_by_state(2))
    except Exception:
        pass
    # WARNING
    if include_warning:
        try:
            items.extend(_fetch_services_by_state(1))
        except Exception:
            pass

    # Fallback: fetch all, filter >0
    if not items:
        try:
            data_all = _get("/services", nocache=True)
            all_items = [_normalize_one_service(s) for s in _flatten_services(data_all)]
            items = [it for it in all_items if (it.get("state") in (1, 2))]
        except Exception:
            items = []

    return _dedupe(items)  # final dedupe

def summarize_failed_services() -> dict:
    items = get_failed_services(include_warning=True)
    uniq_devices = {(i.get("device_id"), i.get("hostname")) for i in items if i.get("device_id") or i.get("hostname")}
    affected_devices = len(uniq_devices)

    by_type: Dict[str, int] = {}
    by_sev: Dict[str, int] = {"warning": 0, "critical": 0}
    for i in items:
        t = (i.get("type") or "unknown").lower()
        by_type[t] = by_type.get(t, 0) + 1
        sev = (i.get("sev") or "unknown").lower()
        if sev in by_sev:
            by_sev[sev] += 1

    return {
        "total_failed": len(items),
        "affected_devices": affected_devices,
        "by_type": by_type,
        "by_severity": by_sev,
        "items": items,
    }

def summarize_failed_services_by_device() -> Dict[int, Dict[str, int]]:
    """
    Returns { device_id: {'warning': n, 'critical': m, 'total': n+m} }.
    Only counts state 1 (warning) and 2 (critical).
    """
    out: Dict[int, Dict[str, int]] = {}
    for it in get_failed_services(include_warning=True):
        did = it.get("device_id")
        sev = (it.get("sev") or "").lower()
        if not did or sev not in ("warning", "critical"):
            continue
        bucket = out.setdefault(did, {"warning": 0, "critical": 0, "total": 0})
        bucket[sev] += 1
        bucket["total"] += 1
    return out

