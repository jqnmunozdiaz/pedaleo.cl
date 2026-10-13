"""
Scraper for CiclismoChile.cl, a cycling aggregator with a public JSON endpoint (/api/events).

It republishes races from several ticketing sites. Races from sources we already scrape
directly (GUCA, Tusdesafios, Bicineta) are skipped here; what it adds are the ones from
Bikerace, Welcu, Tocketicket, Timing FP and any other site it starts to include.
"""

import re
from datetime import date
from typing import Dict, List, Optional

from .base_scraper import BaseScraper, CYCLING_HINTS, MONTHS_ES, strip_accents

API_PATH = "/api/events"
DIRECT_SOURCES = {"guca", "tusdesafios", "bicineta", "ridechile"}
MONTHS_ABBR = {m[:3]: n for m, n in MONTHS_ES.items()}  # ene, feb, mar, ...
MAX_DESCRIPTION = 500

# Category label -> disciplines (parts of mixed labels such as "Mountain Bike y Gravel" are split)
CATEGORY_DISCIPLINES = {
    "mountain bike": "MTB", "mtb": "MTB", "gravel": "Gravel", "ciclismo ruta": "Ruta", "ruta": "Ruta",
    "enduro/dh": "Enduro", "enduro": "Enduro", "downhill": "Enduro", "ciclocross": "Ciclocross",
    "bikepacking": "Ultra/Bikepacking", "ultra": "Ultra/Bikepacking",
}


class CiclismoChileScraper(BaseScraper):
    def __init__(self):
        super().__init__("ciclismochile")
        self.base_url = "https://ciclismochile.cl"

    def fetch_events(self):
        try:
            res = self.session.get(
                f"{self.base_url}{API_PATH}", headers={"Accept": "application/json"}, timeout=30
            )
            if res.status_code != 200:
                print(f"[ciclismochile_scraper] HTTP {res.status_code} en {API_PATH}")
                return []
            items = res.json().get("events", [])
        except Exception as e:
            print(f"[ciclismochile_scraper] Error conectando a {self.base_url}: {e}")
            return []

        events: Dict[str, Dict] = {}
        for item in items:
            try:
                ev = self.event_from_item(item)
            except Exception as e:  # one odd item must not lose the whole run
                print(f"[ciclismochile_scraper] Item ignorado ({item.get('name')!r}): {e}")
                continue
            if ev and ev["id"] not in events:
                events[ev["id"]] = ev
        return list(events.values())

    # ------------------------------------------------------------------ dates

    @staticmethod
    def parse_dates(text: str) -> tuple:
        """
        "23 ago 2026", "17-10-2026", "24 de octubre de 2026", "21 al 22 de noviembre de 2026"
        -> (start, end) as ISO strings. Anything without a clear year, or an open-ended
        range ("10 de abril de 2023 a 31 de diciembre de 2026"), -> (None, None).
        """
        text = re.sub(r"\s+", " ", (text or "").strip().lower())

        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", text)
        if m:
            day, month, year = m.groups()
            return CiclismoChileScraper._iso(year, month, day, year, month, day)

        m = re.fullmatch(r"(\d{1,2}) ([a-z]{3}) (\d{4})", text)
        if m and m.group(2) in MONTHS_ABBR:
            day, mon, year = m.groups()
            return CiclismoChileScraper._iso(year, MONTHS_ABBR[mon], day, year, MONTHS_ABBR[mon], day)

        # "21 al 22 de noviembre de 2026"  /  "24 de octubre de 2026"
        m = re.fullmatch(r"(\d{1,2})(?: (?:al|y|-) (\d{1,2}))? de ([a-záéíóú]+) de (\d{4})", text)
        if m:
            d1, d2, month_name, year = m.groups()
            month = MONTHS_ES.get(strip_accents(month_name))
            if month:
                return CiclismoChileScraper._iso(year, month, d1, year, month, d2 or d1)
        return None, None

    @staticmethod
    def _iso(y1, m1, d1, y2, m2, d2) -> tuple:
        try:
            start = date(int(y1), int(m1), int(d1))
            end = date(int(y2), int(m2), int(d2))
        except ValueError:
            return None, None
        return (start.isoformat(), end.isoformat()) if end >= start else (None, None)

    # ------------------------------------------------------------------ one item

    def _disciplines(self, category: str, name: str) -> List[str]:
        found = []
        for part in re.split(r"\s+y\s+|,", (category or "").lower()):
            d = CATEGORY_DISCIPLINES.get(part.strip())
            if d and d not in found:
                found.append(d)
        for d in self.detect_disciplines(name, default=None):
            if d not in found:
                found.append(d)
        return found

    def event_from_item(self, item: Dict) -> Optional[Dict]:
        if (item.get("source") or "").lower() in DIRECT_SOURCES:
            return None

        name = re.sub(r"\s+", " ", item.get("name") or "").strip()
        link = (item.get("link") or "").strip()
        if not name or not re.match(r"^https?://", link, re.IGNORECASE):
            return None

        start, end = self.parse_dates(item.get("date"))
        if not start:
            return None  # no clear date: never guess one

        category = item.get("category") or ""
        place = (item.get("location") or "").strip()
        if self.is_non_cycling(name) or self.is_foreign(f"{place} {name}"):
            return None

        disciplines = self._disciplines(category, name)
        generic = strip_accents(category) in ("bike", "ciclismo")
        if not disciplines:
            clean = strip_accents(f"{name} {category}")
            if not (generic or any(h in clean for h in CYCLING_HINTS)):
                return None  # category "Deportes", "Trail Running y ...": nothing says bikes
            disciplines = self.detect_disciplines(name, default="MTB" if strip_accents(category) == "bike" else "Ruta")

        region_code, _, keep = self.locate(place, name)
        if not keep:
            return None

        return self.build_event(
            title=name,
            date=start,
            end_date=end,
            place=re.sub(r",\s*Chile$", "", place),
            region_code=region_code,
            disciplines=disciplines,
            url=link,
            price_type="free" if re.search(r"gratis|free", str(item.get("price", "")), re.IGNORECASE) else "paid",
            description=f"{name}. {category}".strip(". ") + ".",
        )
