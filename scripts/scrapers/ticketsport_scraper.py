"""
Scraper for TicketSport.cl (Plataforma chilena de cronometraje e inscripciones)
Fetches cycling, MTB XCM/XCO, and gravel races.
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class TicketSportScraper(BaseScraper):
    def __init__(self):
        super().__init__("ticketsport")
        self.base_url = "https://ticketsport.cl"

    def fetch_events(self):
        events = []
        try:
            res = self.session.get(f"{self.base_url}/eventos", timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                events = self.parse_html(soup)
        except Exception as e:
            print(f"[ticketsport_scraper] Error conectando a {self.base_url}: {e}")

        return events

    def parse_html(self, soup):
        events = []
        cards = soup.select(".evento, .card-evento, .item-evento, .card, article")

        for card in cards:
            text = card.get_text(" ", strip=True)
            text_lower = text.lower()

            if not any(k in text_lower for k in ["ciclismo", "mtb", "gravel", "ruta", "xcm", "xco", "pedaleo", "ciclista"]):
                continue

            title_el = card.select_one("h2, h3, h4, h5, .title, .nombre-evento")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                continue

            link_el = card.select_one("a[href]")
            link = link_el["href"] if link_el else self.base_url
            if link.startswith("/"):
                link = f"{self.base_url}{link}"

            date_match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", text)
            if date_match:
                day, month, year = date_match.groups()
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                date_str = "2026-11-01"

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
                "commune": region_name,
                "location": region_name,
                "distances": ["Ver bases"],
                "distance_min_km": 30,
                "distance_max_km": 60,
                "elevation_gain_m": 0,
                "price_type": "paid",
                "status": "open",
                "organizer": "TicketSport",
                "url": link,
                "registration_url": link,
                "description": f"Competencia de ciclismo disponible en TicketSport.cl: {title}",
                "featured": False,
                "source": "ticketsport"
            })

        return events
