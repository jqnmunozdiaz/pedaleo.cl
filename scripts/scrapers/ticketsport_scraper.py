"""
Scraper for TicketSport.cl (Plataforma chilena de cronometraje e inscripciones)
Fetches upcoming cycling, MTB XCM/XCO, and gravel races from the home page
(the /eventos page only lists past events).
"""

import re
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, strip_accents

MONTHS_EN = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

CYCLING_HINTS = ["mtb", "ciclis", "bici", "gravel", "rally", "xco", "xcm", "bike", "pedal", "downhill", "enduro"]


class TicketSportScraper(BaseScraper):
    def __init__(self):
        super().__init__("ticketsport")
        self.base_url = "https://ticketsport.cl"

    def fetch_events(self):
        events = []
        try:
            res = self.session.get(self.base_url, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                events = self.parse_html(soup)
            else:
                print(f"[ticketsport_scraper] HTTP {res.status_code} en {self.base_url}")
        except Exception as e:
            print(f"[ticketsport_scraper] Error conectando a {self.base_url}: {e}")

        return events

    @staticmethod
    def _text(node, selector):
        el = node.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    @staticmethod
    def _parse_date(day_text, month_year_text):
        """('17', 'October 2026') -> '2026-10-17'"""
        m = re.match(r"([A-Za-z]+)\s+(\d{4})", month_year_text.strip())
        if not m or not re.fullmatch(r"\d{1,2}", day_text.strip()):
            return None
        month = MONTHS_EN.get(m.group(1).lower())
        if not month:
            return None
        return f"{m.group(2)}-{month}-{day_text.strip().zfill(2)}"

    def parse_html(self, soup):
        events = []
        seen = set()

        for link in soup.select('a[href^="/eventos/"]'):
            item = link.select_one(".item")
            href = link.get("href", "")
            if not item or href in seen:
                continue

            title = self._text(item, ".titulo")
            sport = self._text(item, ".deporte")
            place = self._text(item, ".lugar")
            fecha = [p.get_text(strip=True) for p in item.select(".fecha p")]
            if not title or len(fecha) < 2:
                continue

            # Never invent a date: without one the event cannot be listed
            date_str = self._parse_date(fecha[0], fecha[1])
            if not date_str:
                continue

            if self.is_non_cycling(f"{title} {sport}") or self.is_foreign(place):
                continue
            clean = strip_accents(f"{title} {sport}")
            if not any(hint in clean for hint in CYCLING_HINTS):
                continue  # sport unknown ("."), and nothing in the title says bikes

            region_code, _, keep = self.locate(place, title)
            if not keep:
                seen.add(href)
                continue

            url = f"{self.base_url}{href}"
            seen.add(href)
            events.append(self.build_event(
                title=title,
                date=date_str,
                place=place,
                region_code=region_code,
                disciplines=self.detect_disciplines(f"{title} {sport}"),
                url=url,
                organizer="TicketSport",
                description=f"Competencia de ciclismo disponible en TicketSport.cl: {title}",
                price_type="free" if "gratis" in strip_accents(item.get_text(" ")) else "paid",
            ))

        return events
