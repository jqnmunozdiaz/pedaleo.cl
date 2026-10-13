"""
Scraper for Ridechile.cl "Nuevo Calendario" (curated calendar of Chilean cycling races).

One table with date, event, place, modality, distances, organizer and links.
Rows without a concrete date (REPROGRAMADO, only a year) are skipped; rows whose
place is "Por confirmar" are kept and flagged as location_unverified.
"""

import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

DAY_LIST_RE = re.compile(r"^\d{1,2}(?:\s*(?:,|y|al)\s*\d{1,2})*$", re.IGNORECASE)
DATE_CELL_RE = re.compile(r"^(?P<days>.+?)\s*/\s*(?P<month>\d{1,2})\s*/\s*(?P<year>\d{4})$")

# Columns of the table (0-based)
COL_DATE, COL_NAME, COL_PLACE, COL_MODE, COL_DIST, COL_ORG, COL_REG, COL_BASES = range(8)


class RidechileScraper(BaseScraper):
    def __init__(self):
        super().__init__("ridechile")
        self.base_url = "https://www.ridechile.cl"
        self.calendar_url = f"{self.base_url}/nuevo-calendario/"

    def fetch_events(self):
        try:
            res = self.session.get(self.calendar_url, timeout=25)
            if res.status_code != 200:
                print(f"[ridechile_scraper] HTTP {res.status_code} en {self.calendar_url}")
                return []
            return self.parse_html(BeautifulSoup(res.text, "html.parser"))
        except Exception as e:
            print(f"[ridechile_scraper] Error conectando a {self.calendar_url}: {e}")
            return []

    @staticmethod
    def parse_date_cell(text: str) -> tuple:
        """
        '24 y 25/10/2026' -> ('2026-10-24', '2026-10-25');  '22 al 27/11/2026' -> (..22, ..27);
        '06, 07 y 08/11/2026' -> (..06, ..08);  'REPROGRAMADO' / '2027' -> (None, None).
        """
        m = DATE_CELL_RE.match(re.sub(r"\s+", " ", text or "").strip())
        if not m or not DAY_LIST_RE.match(m.group("days").strip()):
            return None, None
        days = [int(d) for d in re.findall(r"\d+", m.group("days"))]
        month, year = int(m.group("month")), int(m.group("year"))
        if not 1 <= month <= 12 or not all(1 <= d <= 31 for d in days):
            return None, None
        return f"{year}-{month:02d}-{days[0]:02d}", f"{year}-{month:02d}-{days[-1]:02d}"

    @staticmethod
    def _cell_link(cell) -> str:
        a = cell.find("a", href=True) if cell else None
        href = a["href"].strip() if a else ""
        return href if re.match(r"^https?://", href, re.IGNORECASE) else ""

    def _disciplines(self, modality: str, title: str) -> List[str]:
        found = []
        for chunk in re.split(r"\s+y\s+|,|/", modality or ""):
            for d in self.detect_disciplines(chunk, default=None):
                if d not in found:
                    found.append(d)
        for d in self.detect_disciplines(title, default=None):
            if d not in found:
                found.append(d)
        return found or ["MTB"]

    def parse_html(self, soup) -> List[Dict]:
        table = None
        for candidate in soup.find_all("table"):
            if table is None or len(candidate.find_all("tr")) > len(table.find_all("tr")):
                table = candidate
        if table is None:
            return []

        events: Dict[str, Dict] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) <= COL_DIST:
                continue  # header row or malformed
            text = [c.get_text(" ", strip=True) for c in cells]

            start, end = self.parse_date_cell(text[COL_DATE])
            title = re.sub(r"\s+", " ", text[COL_NAME]).strip()
            if not start or not title:
                continue

            place = text[COL_PLACE]
            if re.search(r"confirmar|por definir|^$", place, re.IGNORECASE):
                place = ""
            if self.is_non_cycling(title) or self.is_foreign(place):
                continue
            region_code, _, keep = self.locate(place, title)
            if not keep:
                continue

            reg_link = self._cell_link(cells[COL_REG]) if len(cells) > COL_REG else ""
            bases_link = self._cell_link(cells[COL_BASES]) if len(cells) > COL_BASES else ""
            url = reg_link or bases_link or self.calendar_url
            organizer = text[COL_ORG] if len(text) > COL_ORG else ""

            ev = self.build_event(
                title=title,
                date=start,
                end_date=end,
                place=place,
                region_code=region_code,
                disciplines=self._disciplines(text[COL_MODE], title),
                distances=[text[COL_DIST]] if text[COL_DIST] else None,
                url=url,
                registration_url=url,
                organizer=organizer or "Ridechile",
                description=f"{title}: {text[COL_MODE]}{' · ' + text[COL_DIST] if text[COL_DIST] else ''}. Fuente: calendario de Ridechile.cl.",
            )
            events.setdefault(ev["id"], ev)

        return list(events.values())
