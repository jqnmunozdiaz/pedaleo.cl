"""
Scraper for Bicineta.cl (Plataforma especializada en ciclismo en Chile)
Fetches cycling races across categories: MTB, Ruta, Gravel, Ultra, Brevet.
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class BicinetaScraper(BaseScraper):
    def __init__(self):
        super().__init__("bicineta")
        self.base_url = "https://www.bicineta.cl"
        self.categories = [
            ("mtb", "MTB"),
            ("ruta", "Ruta"),
            ("gravel", "Gravel"),
            ("ultra", "Ultra/Bikepacking"),
            ("brevet", "Ruta"),
        ]

    def fetch_events(self):
        events_by_id = {}

        # 1. Main events page
        self._scrape_page(f"{self.base_url}/eventos", default_discipline="MTB", events_dict=events_by_id)

        # 2. Category pages
        for cat_slug, disc_name in self.categories:
            url = f"{self.base_url}/eventos/{cat_slug}"
            self._scrape_page(url, default_discipline=disc_name, events_dict=events_by_id)

        return list(events_by_id.values())

    def _scrape_page(self, url, default_discipline, events_dict):
        try:
            res = self.session.get(url, timeout=12)
            if res.status_code != 200:
                return
            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.select(".event-card:not(.is-hidden)")

            for card in cards:
                title_el = card.select_one(".event-title a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or title.lower() in ["event-title", "template"]:
                    continue

                place_el = card.select_one(".event-place-and-area")
                place = place_el.get_text(strip=True) if place_el else ""

                # Exclude events outside Chile (e.g. Brazil, Argentina)
                if any(x in place.lower() for x in ["brazil", "brasil", "argentina", "peru", "perú", "colombia"]):
                    continue

                date_el = card.select_one(".event-start-at")
                date_dt = date_el.get("datetime", "") if date_el else ""
                date_text = date_el.get_text(strip=True) if date_el else ""

                # Format date to YYYY-MM-DD
                date_iso = self._parse_date(date_dt, date_text)
                if not date_iso:
                    continue

                # End date
                end_el = card.select_one(".event-end-at")
                end_dt = end_el.get("datetime", "") if end_el else ""
                end_iso = self._parse_date(end_dt, "") or date_iso

                # Link & description
                link_el = card.select_one(".event-external-link a")
                link = link_el.get("href", "") if link_el else ""
                if not link or link == "event-external-url":
                    detail_link = title_el.get("href", "")
                    link = f"{self.base_url}{detail_link}" if detail_link.startswith("/") else detail_link

                desc_el = card.select_one(".event-description")
                desc = desc_el.get_text(strip=True) if desc_el else f"Competencia de ciclismo: {title} en {place}."

                org_el = card.select_one(".event-organization a")
                org = org_el.get_text(strip=True) if org_el else "Bicineta / Organización Local"

                # Region & Commune
                region_code, region_name = self.resolve_region(f"{place} {title}")
                commune = place.split("-")[0].strip() if "-" in place else place.strip() or region_name

                # Disciplines
                disciplines = self.detect_disciplines(f"{title} {default_discipline} {desc}")
                if default_discipline not in disciplines and len(disciplines) == 0:
                    disciplines.append(default_discipline)

                slug = self.generate_slug(title, date_iso)

                if slug not in events_dict:
                    events_dict[slug] = {
                        "id": slug,
                        "name": title,
                        "date": date_iso,
                        "end_date": end_iso,
                        "disciplines": disciplines,
                        "region": region_code,
                        "region_name": region_name,
                        "commune": commune,
                        "location": place or f"{commune}, Región {region_name}",
                        "distances": ["Ver bases"],
                        "distance_min_km": 30,
                        "distance_max_km": 60,
                        "elevation_gain_m": 0,
                        "price_type": "paid",
                        "status": "open",
                        "organizer": org,
                        "url": link or self.base_url,
                        "registration_url": link or self.base_url,
                        "description": desc,
                        "featured": False,
                        "source": "bicineta"
                    }

        except Exception as e:
            print(f"[bicineta_scraper] Error en {url}: {e}")

    def _parse_date(self, date_dt, date_text):
        if date_dt and re.match(r"^\d{4}-\d{2}-\d{2}", date_dt):
            return date_dt[:10]

        # Spanish month parsing fallback
        months = {
            "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
            "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
            "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12"
        }
        text_lower = date_text.lower()
        m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", text_lower)
        if m:
            day = m.group(1).zfill(2)
            mon_str = m.group(2)
            for name, num in months.items():
                if name in mon_str:
                    year = "2026"  # Current active season
                    return f"{year}-{num}-{day}"

        return None
