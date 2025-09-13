# modules/home/routes.py
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

from flask import render_template, jsonify, request, url_for, current_app

from . import home_bp
from .news_provider import fetch_headlines, list_sources, DEFAULT_IDS
from .weather_provider import (
    fetch_weather, DEFAULT_LAT, DEFAULT_LON, DEFAULT_TZ, PRESETS
)

# ======================== CONFIG HELPERS ========================

def _cfg(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read from Flask config first, then env."""
    val = current_app.config.get(name)
    if val is None:
        val = os.getenv(name, default)
    return val

def _verify_tls() -> bool:
    # Accept bool or string in config/env
    raw = _cfg('IMMICH_VERIFY_TLS', 'true')
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() not in ('false', '0', 'no', 'off')

# Immich configuration names
IMMICH_ALBUM_URL_NAME = "IMMICH_ALBUM_URL"
IMMICH_BASE_URL_NAME  = "IMMICH_BASE_URL"
IMMICH_SHARE_KEY_NAME = "IMMICH_SHARE_KEY"

# ======================== STATIC potd SETTINGS ========================

potd_RELATIVE_DIR = "images/potd"  # under /static
potd_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# ======================== IMMICH CACHES ========================

# Unified cache (used for album-url or share-key sources)
_potd_CACHE: Dict[str, object] = {
    "ts": 0.0,
    "items": [],          # List[{'name','url','full'}]
    "thumb_tmpl": None,   # for share-key mode
    "full_tmpl": None,    # for share-key mode
    "source_fingerprint": None,  # (album_url or base+key) to invalidate on change
}
_potd_TTL = 600  # seconds

# ======================== STATIC LISTING ========================

def _list_potd_static(limit: int = 24) -> List[Dict[str, str]]:
    static_dir = Path(current_app.static_folder or "static")
    potd_dir = static_dir / potd_RELATIVE_DIR
    if not potd_dir.exists():
        return []

    items: List[Tuple[float, str]] = []
    for p in potd_dir.iterdir():
        if p.is_file() and p.suffix.lower() in potd_EXTS:
            try:
                mtime = p.stat().st_mtime
            except OSError:
                mtime = 0
            items.append((mtime, p.name))

    items.sort(reverse=True)
    out: List[Dict[str, str]] = []
    for _, name in items[: max(1, int(limit))]:
        url = url_for("static", filename=f"{potd_RELATIVE_DIR}/{name}")
        out.append({"name": name, "url": url, "full": url})
    return out

# ======================== IMMICH (HTTP HELPERS) ========================

def _http_get(url: str, timeout: int = 8) -> Optional[str]:
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout, verify=_verify_tls())
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def _http_get_json(url: str, timeout: int = 8):
    try:
        import requests  # type: ignore
        r = requests.get(url, timeout=timeout, verify=_verify_tls())
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def _http_head_ok(url: str, timeout: int = 5) -> bool:
    try:
        import requests  # type: ignore
        # Some servers block HEAD; try HEAD then fall back to lightweight GET
        r = requests.head(url, timeout=timeout, allow_redirects=True, verify=_verify_tls())
        if 200 <= r.status_code < 400:
            return True
        r = requests.get(url, timeout=timeout, stream=True, verify=_verify_tls())
        return 200 <= r.status_code < 400
    except Exception:
        return False

# ======================== IMMICH (ALBUM URL MODE) ========================

def _immich_album_url() -> Optional[str]:
    # Allow overriding via query param for testing: ?potd_album_url=...
    qp = request.args.get("potd_album_url")
    if qp:
        return qp.strip()
    val = _cfg(IMMICH_ALBUM_URL_NAME)
    return val.strip() if isinstance(val, str) else None

_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_SRCSET_RE  = re.compile(r'srcset=["\']([^"\']+)["\']', re.IGNORECASE)
_OG_IMAGE_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)

def _parse_img_urls_from_html(html: str, base_url: str) -> List[str]:
    """
    Permissive scrape: collect <img src>, highest-res from srcset, and og:image.
    Normalize to absolute URLs relative to album page.
    """
    urls: List[str] = []

    # src=
    for m in _IMG_SRC_RE.finditer(html):
        u = m.group(1).strip()
        if u:
            urls.append(urljoin(base_url, u))

    # srcset=
    for m in _SRCSET_RE.finditer(html):
        srcset = m.group(1)
        parts = [p.strip() for p in srcset.split(",") if p.strip()]
        if parts:
            last = parts[-1].split()[0]
            urls.append(urljoin(base_url, last))

    # og:image
    for m in _OG_IMAGE_RE.finditer(html):
        u = m.group(1).strip()
        if u:
            urls.append(urljoin(base_url, u))

    # Deduplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)

    # Heuristic: keep only images or Immich endpoints
    keepers: List[str] = []
    for u in uniq:
        low = u.lower()
        if any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
            keepers.append(u)
        elif "/thumbnail" in low or "/file" in low or "/original" in low or "/api/assets/" in low:
            keepers.append(u)

    return keepers

def _list_potd_from_album_url(limit: int = 24) -> List[Dict[str, str]]:
    album_url = _immich_album_url()
    if not album_url:
        return []

    # Cache key specific to album URL
    fingerprint = f"album::{album_url}"
    now = time.time()
    if (_potd_CACHE["source_fingerprint"] == fingerprint and
        (now - float(_potd_CACHE["ts"])) < _potd_TTL and
        _potd_CACHE["items"]):
        return _potd_CACHE["items"][: max(1, int(limit))]

    html = _http_get(album_url)
    if not html:
        return []

    img_urls = _parse_img_urls_from_html(html, base_url=album_url)
    if not img_urls:
        return []

    # Try to keep only reachable URLs; if none pass, fall back to raw list
    reachable = [u for u in img_urls if _http_head_ok(u)]
    if not reachable:
        reachable = img_urls

    items: List[Dict[str, str]] = []
    for u in reachable[: max(1, int(limit))]:
        name = os.path.basename(urlparse(u).path) or "image"
        items.append({"name": name, "url": u, "full": u})

    if items:
        _potd_CACHE["ts"] = now
        _potd_CACHE["items"] = items
        _potd_CACHE["source_fingerprint"] = fingerprint

    return items

# ======================== IMMICH (SHARE KEY MODE) ========================

def _immich_share_enabled() -> bool:
    return bool(_cfg(IMMICH_BASE_URL_NAME) and _cfg(IMMICH_SHARE_KEY_NAME))

def _immich_base() -> str:
    val = _cfg(IMMICH_BASE_URL_NAME, "") or ""
    return val.rstrip("/")

def _immich_key() -> str:
    return _cfg(IMMICH_SHARE_KEY_NAME, "") or ""

def _immich_fetch_assets_raw(take: int = 200) -> List[dict]:
    base = _immich_base()
    key = _immich_key()
    if not base or not key:
        return []

    candidates = [
        f"{base}/api/shared-link/{key}/assets?skip=0&take={max(take,1)}&order=desc",
        f"{base}/api/shared-link/{key}",
    ]
    for url in candidates:
        data = _http_get_json(url)
        if not data:
            continue
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ("assets", "items", "nodes"):
                arr = data.get(k)
                if isinstance(arr, list) and arr:
                    return arr
    return []

def _immich_select_templates(sample_id: str) -> Tuple[Optional[str], Optional[str]]:
    base = _immich_base()
    key = _immich_key()
    thumb_tmps = [
        f"{base}/api/shared-link/{key}/thumbnail/{{id}}?size=preview",
        f"{base}/api/assets/{{id}}/thumbnail?size=preview&key={key}",
        f"{base}/api/assets/{{id}}/thumbnail?size=preview",
    ]
    full_tmps = [
        f"{base}/api/shared-link/{key}/file/{{id}}",
        f"{base}/api/assets/{{id}}/file?key={key}",
        f"{base}/api/assets/{{id}}/original",
    ]
    chosen_thumb: Optional[str] = None
    chosen_full: Optional[str] = None
    for tmpl in thumb_tmps:
        if _http_head_ok(tmpl.replace("{id}", sample_id)):
            chosen_thumb = tmpl
            break
    for tmpl in full_tmps:
        if _http_head_ok(tmpl.replace("{id}", sample_id)):
            chosen_full = tmpl
            break
    return chosen_thumb, chosen_full

def _list_potd_share_key(limit: int = 24) -> List[Dict[str, str]]:
    base = _immich_base()
    key  = _immich_key()
    if not base or not key:
        return []

    fingerprint = f"share::{base}::{key}"
    now = time.time()
    if (_potd_CACHE["source_fingerprint"] == fingerprint and
        (now - float(_potd_CACHE["ts"])) < _potd_TTL and
        _potd_CACHE["items"]):
        return _potd_CACHE["items"][: max(1, int(limit))]

    assets = _immich_fetch_assets_raw(take=max(100, int(limit)))
    if not assets:
        return []

    ids: List[str] = []
    for a in assets:
        aid = a.get("id") or a.get("assetId") or a.get("assetID")
        if isinstance(aid, str):
            ids.append(aid)
    if not ids:
        return []

    if not _potd_CACHE["thumb_tmpl"] or not _potd_CACHE["full_tmpl"]:
        thumb_tmpl, full_tmpl = _immich_select_templates(ids[0])
        _potd_CACHE["thumb_tmpl"] = thumb_tmpl
        _potd_CACHE["full_tmpl"] = full_tmpl
    else:
        thumb_tmpl = _potd_CACHE["thumb_tmpl"]
        full_tmpl  = _potd_CACHE["full_tmpl"]

    out: List[Dict[str, str]] = []
    for aid in ids[: max(1, int(limit))]:
        thumb = thumb_tmpl.replace("{id}", aid) if thumb_tmpl else None
        full  = full_tmpl.replace("{id}", aid) if full_tmpl else (thumb or "")
        out.append({"name": aid, "url": thumb or full, "full": full})

    _potd_CACHE["ts"] = now
    _potd_CACHE["items"] = out
    _potd_CACHE["source_fingerprint"] = fingerprint
    return out

# ======================== UNIFIED SELECTOR ========================

def _list_potd(limit: int = 24, force_src: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Source priority:
      1) force_src=album/share/static (if provided)
      2) IMMICH_ALBUM_URL (public album page, no password)
      3) IMMICH_BASE_URL + IMMICH_SHARE_KEY (public share)
      4) /static/images/potd/
    """
    src = (force_src or "").strip().lower()
    if src == "album":
        items = _list_potd_from_album_url(limit)
        if items:
            return items
    elif src == "share" or src == "immich":
        items = _list_potd_share_key(limit)
        if items:
            return items
    elif src == "static":
        return _list_potd_static(limit)

    # Auto-select
    if _immich_album_url():
        items = _list_potd_from_album_url(limit)
        if items:
            return items

    if _immich_share_enabled():
        items = _list_potd_share_key(limit)
        if items:
            return items

    return _list_potd_static(limit)

# ======================== ROUTES ========================

@home_bp.route("/")
def index():
    # Photos-of-the-day
    try:
        potd_count = int(request.args.get("potd", 24))
    except (TypeError, ValueError):
        potd_count = 24
    force_src = request.args.get("potd_source")  # 'album' | 'share'|'immich' | 'static' | None

    potd_items = _list_potd(limit=potd_count, force_src=force_src)
    current_app.logger.info("HOME index: POTD %s -> %d items", (force_src or "auto"), len(potd_items))

    return render_template(
        "home/index.html",
        active="home",
        base_version="HomeBeta v0.4",
        potd_items=potd_items,
    )

@home_bp.get("/api/weather")
def api_weather():
    # allows ?lat= & lon= & tz= & label=
    lat = float(request.args.get("lat", DEFAULT_LAT))
    lon = float(request.args.get("lon", DEFAULT_LON))
    tz  = request.args.get("tz", DEFAULT_TZ)
    label = request.args.get("label")
    data = fetch_weather(lat, lon, tz, label=label)
    return jsonify(data)

@home_bp.get("/api/weather/presets")
def api_weather_presets():
    return jsonify(PRESETS)

# NEWS: list available source options
@home_bp.get("/api/news/sources")
def api_news_sources():
    return jsonify(list_sources())

# NEWS: fetch headlines (hard-cap TOTAL to 25)
@home_bp.get("/api/news")
def api_news():
    src_param = request.args.get("sources", ",".join(DEFAULT_IDS)).strip()
    ids = [s for s in (src_param.split(",") if src_param else []) if s]
    try:
        limit = int(request.args.get("limit", 25))  # per-source
    except Exception:
        limit = 25
    data = fetch_headlines(ids, limit_per_source=limit)
    return jsonify({"items": data[:25]})

# potd JSON (honors source + limit + optional potd_album_url)
@home_bp.get("/api/potd")
def api_potd():
    try:
        lim = int(request.args.get("limit", 24))
    except (TypeError, ValueError):
        lim = 24
    src = request.args.get("src")  # 'album' | 'share'|'immich' | 'static' | None
    items = _list_potd(limit=lim, force_src=src)
    current_app.logger.info("API /potd src=%s -> %d items", (src or "auto"), len(items))
    return jsonify({"items": items})
