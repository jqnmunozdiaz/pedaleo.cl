"""
Pedaleo.cl - Link checker
Races whose registration website no longer works are not listed.

"Dead" means a definitive, repeated failure: the domain does not exist, the connection is
refused, or the page answers 404/410/5xx on every attempt. Anything ambiguous (bot blocking,
timeouts, TLS quirks, social networks that cannot be checked without logging in) is treated as
alive so a good race is never lost because of a flaky check.
"""

import json
import os
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Callable, Dict, Iterable, List, Optional
from urllib.parse import urlsplit

import requests

OK, DEAD, UNKNOWN = "ok", "dead", "unknown"

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(PROJECT_DIR, "data", "link_checks.json")

# Cannot be verified anonymously (login walls / bot blocking): assumed alive
UNCHECKABLE_HOSTS = (
    "instagram.com", "facebook.com", "fb.me", "fb.com", "linktr.ee", "wa.me", "whatsapp.com",
    "tiktok.com", "x.com", "twitter.com", "youtube.com", "youtu.be", "bit.ly", "goo.gl",
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 PedaleoBot/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

DNS_MARKERS = (
    "name or service not known", "getaddrinfo failed", "nodename nor servname",
    "temporary failure in name resolution", "nameresolutionerror", "no address associated",
)


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def _is_dns_failure(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in DNS_MARKERS) or isinstance(exc, socket.gaierror)


def _classify(status: int) -> str:
    if status in (404, 410):
        return DEAD
    if status >= 500 and status not in (999,):
        return DEAD  # still failing after the retry in check_url: the site is down
    return OK


def check_url(url: str, timeout: int = 12, attempts: int = 2, pause: float = 2.0) -> str:
    """Returns OK, DEAD or UNKNOWN for one link. DEAD needs every attempt to fail definitively."""
    if not re.match(r"^https?://", url or "", re.IGNORECASE):
        return UNKNOWN
    host = _host(url)
    if any(host == h or host.endswith("." + h) for h in UNCHECKABLE_HOSTS):
        return UNKNOWN

    verdict = UNKNOWN
    for attempt in range(attempts):
        verdict = _check_once(url, timeout)
        if verdict != DEAD:
            return verdict
        if attempt < attempts - 1:
            time.sleep(pause)
    return verdict


def _check_once(url: str, timeout: int) -> str:
    try:
        response = requests.head(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
        if response.status_code in (400, 403, 404, 405, 410, 501) or response.status_code >= 500:
            # many servers mishandle HEAD (405, even 404): confirm with GET (body is never downloaded)
            response = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True, stream=True)
            response.close()
        return _classify(response.status_code)
    except requests.exceptions.ConnectionError as e:
        if _is_dns_failure(e) or "connection refused" in str(e).lower() or "errno 111" in str(e).lower():
            return DEAD
        return UNKNOWN
    except Exception:
        return UNKNOWN  # timeouts, TLS problems, redirect loops, ...


# ------------------------------------------------------------------ cache and policy

def load_cache(path: str = CACHE_FILE) -> Dict[str, dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(cache: Dict[str, dict], path: str = CACHE_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(cache.items())), f, ensure_ascii=False, indent=1)


def event_link(ev: dict) -> str:
    return (ev.get("registration_url") or ev.get("url") or "").strip()


def filter_dead_links(
    events: List[dict],
    today: Optional[str] = None,
    checker: Callable[[str], str] = check_url,
    cache: Optional[Dict[str, dict]] = None,
    workers: int = 8,
    max_dead_share: float = 0.15,
) -> tuple:
    """
    Removes upcoming races whose registration link is dead. Returns (kept, removed, cache).

    A race that is dropped comes back by itself if its site recovers (scrapers add it again);
    hand-added races can be re-added with scripts/add_event.py.

    Safety net: if an unusually large share of links fails in one run, the runner's own
    network is the likelier culprit, so nothing is removed.
    """
    today = today or date.today().isoformat()
    cache = dict(cache if cache is not None else {})

    upcoming = [e for e in events if (e.get("end_date") or e.get("date", "")) >= today]
    urls = sorted({event_link(e) for e in upcoming if event_link(e)})
    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = dict(zip(urls, pool.map(checker, urls)))

    dead = {u for u, v in verdicts.items() if v == DEAD}
    if urls and len(dead) > max(5, max_dead_share * len(urls)):
        print(f"::warning title=Verificación de enlaces omitida::{len(dead)} de {len(urls)} enlaces fallaron; "
              "probablemente un problema de red, no se omite ninguna carrera.")
        dead = set()

    for url, verdict in verdicts.items():
        cache[url] = {"verdict": DEAD if url in dead else verdict, "checked": today}

    kept = [e for e in events if not (event_link(e) in dead and (e.get("end_date") or e.get("date", "")) >= today)]
    removed = [e for e in events if e not in kept]

    live_urls = {event_link(e) for e in kept if event_link(e)}
    cache = {u: v for u, v in cache.items() if u in live_urls or v.get("verdict") == DEAD}
    return kept, removed, cache
