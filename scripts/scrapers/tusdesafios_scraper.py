"""
Scraper for Tusdesafios.com (calendario de carreras de Chile).

The cycling sections (Ciclismo Ruta, Mountain Bike, Enduro/DH, Gravel, Ciclocross) list the
races; each race page has structured data (schema.org Event) with the exact dates, the place
and a link to the organizer's own site, which is what we use as the registration link.
"""

import json
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, extract_elevation

SECTIONS = [
    ("ciclismo-ruta", "Ruta"),
    ("mountain-bike", "MTB"),
    ("enduro", "Enduro"),
    ("gravel", "Gravel"),
    ("ciclocross", "Ciclocross"),
]
MAX_DESCRIPTION = 500


class TusdesafiosScraper(BaseScraper):
    def __init__(self):
        super().__init__("tusdesafios")
        self.base_url = "https://tusdesafios.com"

    # ------------------------------------------------------------------ main

    def fetch_events(self):
        cards: Dict[str, Dict] = {}
        for slug, discipline in SECTIONS:
            try:
                res = self.session.get(f"{self.base_url}/{slug}", timeout=20)
                if res.status_code != 200:
                    print(f"[tusdesafios_scraper] HTTP {res.status_code} en /{slug}")
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
            except Exception as e:
                print(f"[tusdesafios_scraper] Error en /{slug}: {e}")
                continue
            for card in self.parse_cards(soup, discipline):
                known = cards.setdefault(card["href"], card)
                if discipline not in known["disciplines"]:
                    known["disciplines"].append(discipline)  # same race listed in two sections

        events: Dict[str, Dict] = {}
        for ev in self.map_parallel(self.event_from_detail, cards.values()):
            if ev and ev["id"] not in events:
                events[ev["id"]] = ev
        return list(events.values())

    # ------------------------------------------------------------------ list page

    @staticmethod
    def _text(node, selector: str) -> str:
        el = node.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    def parse_cards(self, soup, discipline: str) -> List[Dict]:
        cards = []
        for a in soup.select("a.event-card"):
            href = a.get("href", "")
            name = self._text(a, ".event-name")
            if not href.startswith("/events/") or not name:
                continue
            cards.append({
                "href": href,
                "name": name,
                "sport": self._text(a, ".event-sport"),
                "location": self._text(a, ".event-location"),
                "tags": [t.get_text(" ", strip=True) for t in a.select(".event-tag")],
                "disciplines": [discipline],
            })
        return cards

    # ------------------------------------------------------------------ detail page

    def event_from_detail(self, card: Dict) -> Optional[Dict]:
        url = f"{self.base_url}{card['href']}"
        try:
            res = self.session.get(url, timeout=20)
            if res.status_code != 200:
                return None
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"[tusdesafios_scraper] Error leyendo {url}: {e}")
            return None
        return self.parse_detail(soup, card, url)

    @staticmethod
    def _event_jsonld(soup) -> Dict:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "Event":
                    return item
        return {}

    @staticmethod
    def _official_link(soup) -> str:
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True).lower()
            href = a["href"].strip()
            if label in ("inscripciones", "sitio oficial") and re.match(r"^https?://", href, re.IGNORECASE):
                if "tusdesafios.com" not in href:
                    return href
        return ""

    def parse_detail(self, soup, card: Dict, url: str) -> Optional[Dict]:
        data = self._event_jsonld(soup)
        # Dates come as "2026-10-15T09:00:00Z"; the day is what matters
        start = (data.get("startDate") or "")[:10]
        end = (data.get("endDate") or "")[:10] or start
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", start):
            return None  # never invent a date

        title = (data.get("name") or card["name"]).strip()
        if self.is_non_cycling(title):
            return None

        location = data.get("location") or {}
        address = location.get("address") or {}
        place = (location.get("name") or "").strip()
        region_text = " ".join(filter(None, [address.get("addressLocality"), address.get("addressRegion"), card["location"]]))
        if self.is_foreign(f"{place} {region_text}") or (address.get("addressCountry") not in (None, "", "CL")):
            return None
        region_code, _, keep = self.locate(place, region_text)
        if not keep:
            return None

        description = re.sub(r"\s+", " ", data.get("description") or "").strip()
        if len(description) > MAX_DESCRIPTION:
            description = description[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"

        # The page has the whole text; the structured-data description is cut short
        body = soup.select_one(".show2-description")
        full_text = body.get_text(" ", strip=True) if body else data.get("description") or ""

        official = self._official_link(soup)
        return self.build_event(
            elevation_gain_m=extract_elevation(full_text),
            title=title,
            date=start,
            end_date=end,
            place=place,
            region_code=region_code,
            disciplines=card["disciplines"],
            distances=card["tags"],
            url=url,
            registration_url=official or url,
            description=description or f"{title}. {card['sport']}.",
        )
