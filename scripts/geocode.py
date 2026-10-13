"""
Pedaleo.cl - Cached geocoding for races whose commune is not in data/communes_coords.json

Uses OpenStreetMap's Nominatim (https://operations.osmfoundation.org/policies/nominatim/):
identifying User-Agent, at most one request per second, and every answer (also "not found")
is cached in data/geocode_cache.json, so a place is looked up once, ever.
"""

import json
import math
import os
import time
from typing import Dict, Optional, Tuple

import requests

from scrapers.base_scraper import REGION_NAMES, strip_accents

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(PROJECT_DIR, "data", "geocode_cache.json")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {
    "User-Agent": "PedaleoBot/1.0 (https://github.com/jqnmunozdiaz/pedaleo.cl; contacto@pedaleo.cl)",
    "Accept-Language": "es",
}
MIN_INTERVAL = 1.1          # seconds between requests (policy: max 1 per second)
MAX_LOOKUPS_PER_RUN = 60    # the rest waits for the next night
MAX_KM_FROM_REGION = 650    # a namesake town in another part of the country is not the place we want

# "Araucanía" or "O'Higgins" alone name a region, not a place: geocoding them lands on a random town
REGION_WORDS = (
    {strip_accents(n) for n in REGION_NAMES.values()}
    | {strip_accents(n).split(" ", 1)[1] for n in REGION_NAMES.values() if n.startswith(("La ", "Los "))}  # "Araucanía", "Ríos"
    | {"ohiggins", "libertador", "metropolitana", "chile", "patagonia", "region metropolitana"}
)

CHILE_BOX = {"lat": (-56.0, -17.0), "lng": (-110.0, -66.0)}


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


class Geocoder:
    def __init__(self, centroids: Dict[str, Tuple[float, float]], cache_path: str = CACHE_FILE,
                 max_lookups: int = MAX_LOOKUPS_PER_RUN, session=None, sleep=time.sleep):
        self.centroids = centroids
        self.cache_path = cache_path
        self.cache: Dict[str, Optional[list]] = self._load()
        self.max_lookups = max_lookups
        self.lookups = 0
        self.session = session or requests.Session()
        self.sleep = sleep
        self._last_request = 0.0
        self.dirty = False

    def _load(self) -> dict:
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save(self) -> None:
        if not self.dirty:
            return
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(self.cache.items())), f, ensure_ascii=False, indent=1)
        self.dirty = False

    def _valid(self, point: Tuple[float, float], region_code: str) -> bool:
        if not (CHILE_BOX["lat"][0] <= point[0] <= CHILE_BOX["lat"][1] and CHILE_BOX["lng"][0] <= point[1] <= CHILE_BOX["lng"][1]):
            return False
        centroid = self.centroids.get(region_code)
        return centroid is None or haversine_km(point, centroid) <= MAX_KM_FROM_REGION

    def _request(self, query: str) -> Optional[list]:
        wait = MIN_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            self.sleep(wait)
        self._last_request = time.monotonic()
        self.lookups += 1
        response = self.session.get(
            NOMINATIM_URL,
            params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "cl"},
            headers=HEADERS, timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        results = response.json()
        if not results:
            return None
        return [round(float(results[0]["lat"]), 5), round(float(results[0]["lon"]), 5)]

    def __call__(self, commune: str, region_name: str, region_code: str) -> Optional[Tuple[float, float]]:
        if not commune or strip_accents(commune).replace("'", "") in REGION_WORDS:
            return None
        query = f"{commune}, {region_name}, Chile"
        if query not in self.cache:
            if self.lookups >= self.max_lookups:
                return None  # over budget: try again tomorrow, nothing is cached
            try:
                self.cache[query] = self._request(query)
            except Exception as e:  # network trouble: do not cache, do not stop the sync
                print(f"[geocode] No se pudo consultar '{query}': {e}")
                return None
            self.dirty = True
        value = self.cache[query]
        point = tuple(value) if value else None
        return point if point and self._valid(point, region_code) else None
