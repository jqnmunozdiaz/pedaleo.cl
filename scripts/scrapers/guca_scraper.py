"""
Scraper for GUCA.cl (Cronometraje deportivo y plataforma de tickets en Chile)
Fetches cycling, MTB, gravel, and multisport races with direct registration links.
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
            res = self.session.get(self.base_url, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                events = self.parse_html(soup)
        except Exception as e:
            print(f"[guca_scraper] Error conectando a {self.base_url}: {e}")

        return events

    def parse_html(self, soup):
        events = []
        seen_links = set()

        for a in soup.select('a[href*="/att_tickets/public/e/"]'):
            href = a.get("href", "")
            if not href or href in seen_links:
                continue

            parent = a.find_parent("div", class_=re.compile(r"col|property|item|card|owl-item"))
            if not parent:
                continue

            text = parent.get_text(" | ", strip=True)
            text_lower = text.lower()

            # Filter for cycling / bike keywords (avoid pure trail running without bikes)
            if not any(k in text_lower for k in ["ciclismo", "gravel", "mtb", "ruta", "pedaleo", "xco", "xcm", "downhill", "desafio", "desafío"]):
                continue

            # Extract date in DD-MM-YYYY format
            date_match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", text)
            if not date_match:
                continue
            day, month, year = date_match.groups()
            date_iso = f"{year}-{month}-{day}"

            parts = [p.strip() for p in text.split("|") if p.strip()]

            # Extract Title
            title = ""
            for p in parts:
                if any(c in p.lower() for c in ["ciclismo", "gravel", "mtb", "ruta", "desafio", "desafío", "fondo", "race", "tour", "series"]) and len(p) > 8:
                    title = p
                    break
            if not title:
                slug_part = href.split("/")[-1].replace("-", " ").title()
                title = slug_part

            # Clean Title
            title = re.sub(r"\s+", " ", title).strip()

            # Commune / Location
            commune = "Chile"
            for p in parts:
                if p.lower() in ["inscribete acá", "inscríbete acá", "ticket", "crono", "ver más", "gratis"]:
                    continue
                if not re.search(r"\d", p) and len(p) < 25 and p != title:
                    commune = p
                    break

            region_code, region_name = self.resolve_region(f"{commune} {title}")
            disciplines = self.detect_disciplines(f"{title} {text}")
            slug = self.generate_slug(title, date_iso)

            seen_links.add(href)
            events.append({
                "id": slug,
                "name": title,
                "date": date_iso,
                "end_date": date_iso,
                "disciplines": disciplines,
                "region": region_code,
                "region_name": region_name,
                "commune": commune,
                "location": f"{commune}, Región {region_name}",
                "distances": ["Ver bases"],
                "distance_min_km": 30,
                "distance_max_km": 60,
                "elevation_gain_m": 0,
                "price_type": "paid",
                "status": "open",
                "organizer": "GUCA / Club Organizador",
                "url": href,
                "registration_url": href,
                "description": f"Competencia de {', '.join(disciplines)} cronometrada por GUCA en {commune}.",
                "featured": False,
                "source": "guca"
            })

        return events
