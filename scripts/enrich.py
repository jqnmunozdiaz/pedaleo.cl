"""
Pedaleo.cl - Light enrichment of races from their own Welcu page

Welcu event pages describe the race in a meta description that often lists the distances.
Only that short, structured text is read (never the whole page), and only for races that
still show "Ver bases". Anything that does not look like a list of distances is ignored.
"""

import re
from typing import List, Optional

import requests
from concurrent.futures import ThreadPoolExecutor

from scrapers.base_scraper import extract_elevation, parse_distances
from welcu_links import HEADERS, is_generic_welcu, is_welcu

MAX_DISTANCES = 6


def meta_text(html: str) -> str:
    """The page's short descriptions (og:description / meta description), whitespace-normalized."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    metas = soup.find_all("meta", attrs={"property": "og:description"}) + soup.find_all("meta", attrs={"name": "description"})
    return re.sub(r"\s+", " ", " ".join(m.get("content", "") for m in metas))


def distances_from_text(text: str) -> Optional[tuple]:
    """(labels, min_km, max_km) when the text lists a believable set of distances, otherwise None."""
    labels, low, high = parse_distances([text])
    if not labels or len(labels) > MAX_DISTANCES:
        return None
    return labels, low, high


def page_distances(html: str) -> Optional[tuple]:
    return distances_from_text(meta_text(html))


def _fetch(url: str) -> str:
    """Meta description of a page ('' when it cannot be read)."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        return meta_text(response.text) if response.status_code == 200 else ""
    except Exception:
        return ""


def enrich_from_welcu(events: List[dict], workers: int = 4) -> int:
    """Fills in distances and elevation gain from Welcu pages. Returns how many races were improved."""
    todo = [
        e for e in events
        if (e.get("distances") in (None, [], ["Ver bases"]) or not e.get("elevation_gain_m"))
        and is_welcu(e.get("registration_url", "")) and not is_generic_welcu(e["registration_url"])
    ]
    if not todo:
        return 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        texts = list(pool.map(lambda e: _fetch(e["registration_url"]), todo))

    improved = 0
    for ev, text in zip(todo, texts):
        changed = False
        if ev.get("distances") in (None, [], ["Ver bases"]):
            found = distances_from_text(text)
            if found:
                ev["distances"], ev["distance_min_km"], ev["distance_max_km"] = found
                changed = True
        if not ev.get("elevation_gain_m"):
            gain = extract_elevation(text)
            if gain:
                ev["elevation_gain_m"] = gain
                changed = True
        improved += changed
    return improved


# kept for callers that only care about distances
enrich_distances = enrich_from_welcu
