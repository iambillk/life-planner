# modules/home/news_provider.py
from __future__ import annotations
import time
from typing import List, Dict
import requests
import feedparser

# ---- Source map (IDs -> human name + RSS URL) -------------------------------
NEWS_SOURCES = {
    "rt_all":      {"name": "RT: All",        "url": "https://www.rt.com/rss"},
    "rt_world":    {"name": "RT: World",      "url": "https://www.rt.com/rss/news"},
    "rt_russia":   {"name": "RT: Russia",     "url": "https://www.rt.com/rss/russia"},
    "rt_business": {"name": "RT: Business",   "url": "https://www.rt.com/rss/business"},
    "rt_opinion":  {"name": "RT: Opinion",    "url": "https://www.rt.com/rss/op-ed"},
    "rt_podcasts": {"name": "RT: Podcasts",   "url": "https://www.rt.com/rss/podcasts"},
    "rt_india":    {"name": "RT: India",      "url": "https://www.rt.com/rss/india"},
    "rt_africa":   {"name": "RT: Africa",     "url": "https://www.rt.com/rss/africa"},
    "rt_ent":      {"name": "RT: Entertainment","url": "https://www.rt.com/rss/pop-culture"},
}

# Pick your default 2–3 here
DEFAULT_IDS = ["rt_world", "rt_russia", "rt_business"]

# ---- Fetch settings ----------------------------------------------------------
TTL = 600  # 10 minutes per-feed cache
_CACHE: Dict[str, tuple[float, List[dict]]] = {}

HTTP_HEADERS = {
    # Many publishers block generic Python UAs; this avoids 403/bozo-parsing issues.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36 BillasPlanner/1.0"
}
HTTP_TIMEOUT = 10

def _cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    ts, data = hit
    if time.time() - ts > TTL:
        return None
    return data

def _cache_set(key: str, data):
    _CACHE[key] = (time.time(), data)

# ---- Core fetch --------------------------------------------------------------
def _download(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.content
    except Exception:
        return None

def fetch_feed(feed_id: str, limit: int = 50) -> List[dict]:
    """Fetch and normalize a single feed by id. Returns up to `limit` items."""
    if feed_id not in NEWS_SOURCES:
        return []

    # cache hit?
    cached = _cache_get(feed_id)
    if cached is not None:
        return cached[:limit]

    url = NEWS_SOURCES[feed_id]["url"]
    raw = _download(url)
    if raw is None:
        _cache_set(feed_id, [])
        return []

    parsed = feedparser.parse(raw)

    items: List[dict] = []
    for e in parsed.entries[:25]:  # read a few extra; we trim below
        title = getattr(e, "title", "").strip()
        link = getattr(e, "link", "")
        published = getattr(e, "published", None) or getattr(e, "updated", None) or None
        items.append({
            "title": title or "(untitled)",
            "link": link,
            "published": published,        # may be None or RFC822 string
            "source_id": feed_id,
            "source": NEWS_SOURCES[feed_id]["name"],
        })

    _cache_set(feed_id, items)
    return items[:limit]

def fetch_headlines(source_ids: List[str] | None, limit_per_source: int = 4) -> List[dict]:
    ids = source_ids or DEFAULT_IDS
    out: List[dict] = []
    for fid in ids:
        out.extend(fetch_feed(fid, limit=limit_per_source))

    # Best-effort sort by published (strings compare okay if RFC822-like; None goes last)
    def ts_key(item):
        return item.get("published") or ""
    out.sort(key=ts_key, reverse=True)
    return out

def list_sources() -> List[dict]:
    return [{"id": k, "name": v["name"]} for k, v in NEWS_SOURCES.items()]
