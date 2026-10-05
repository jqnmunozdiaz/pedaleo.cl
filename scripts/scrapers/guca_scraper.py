"""
Scraper for GUCA.cl (Cronometraje deportivo y plataforma de inscripciones en Chile)
Fetches cycling, MTB, gravel, and multisport races.
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class GucaScraper(BaseScraper):
    def __init__(self):
        super().__init__("guca")
        self.base_url = "https://guca.cl"

    def fetch_events(self):
        events = []
        try:
            res = self.session.get(f"{self.base_url}", timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                events = self.parse_html(soup)
        except Exception as e:
            print(f"[guca_scraper] Error conectando a {self.base_url}: {e}")

        return events

    def parse_html(self, soup):
        events = []
        # GUCA features upcoming cards or list items
        event_cards = soup.select(".event-item, .card, .post-item, .product__item, article")

        for card in event_cards:
            text = card.get_text(" ", strip=True)
            text_lower = text.lower()

            # Filter for cycling terms
            if not any(k in text_lower for k in ["ciclismo", "mtb", "gravel", "ruta", "pedaleo", "gran fondo", "desafío", "desafio"]):
                continue

            # Extract title
            title_el = card.select_one("h2, h3, h4, h5, .title, .event-title")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue

            # Link
            link_el = card.select_one("a[href]")
            link = link_el["href"] if link_el else self.base_url
            if link.startswith("/"):
                link = f"{self.base_url}{link}"

            # Date extraction regex
            # e.g., "10-10-2026", "17/10/2026", "10 de octubre"
            date_match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", text)
            if date_match:
                day, month, year = date_match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                date_str = "2026-10-15"

            disciplines = self.detect_disciplines(f"{title} {text}")
            region_code, region_name = self.resolve_region(text)
            slug = self.generate_slug(title, date_str)

            events.append({
                "id": slug,
                "name": title,
                "date": date_str,
                "end_date": date_str,
                "disciplines": disciplines,
                "region": region_code,
                "region_name": region_name,
                "commune": "Chile",
                "location": region_name,
                "distances": ["Por confirmar"],
                "distance_min_km": 30,
                "distance_max_km": 60,
                "elevation_gain_m": 0,
                "price_type": "paid",
                "status": "open",
                "organizer": "GUCA",
                "url": link,
                "registration_url": link,
                "description": f"Evento de ciclismo publicado en GUCA.cl: {title}",
                "featured": False,
                "source": "guca"
            })

        return events
