"""
Scraper for GUCA.cl (Cronometraje deportivo y plataforma de tickets en Chile)

The home page lists every race with a sport label ("Ciclismo", "Trail Running", ...).
For each cycling candidate we open the race's detail page, which has the real
title, date range and venue; the home card is only used as a fallback.
"""

import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, CYCLING_HINTS, MONTHS_ES, strip_accents

EVENT_LINK_SELECTOR = 'a[href*="/att_tickets/public/e/"]'
DATE_RE = re.compile(r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})", re.IGNORECASE)
PLACE_RE = re.compile(r"@\s*(.+?)\s*(?:TICKETS|DETALLES|UBICACI[ÓO]N|$)", re.IGNORECASE)
MAX_DESCRIPTION = 500


class GucaScraper(BaseScraper):
    def __init__(self):
        super().__init__("guca")
        self.base_url = "https://guca.cl"

    # ------------------------------------------------------------------ main

    def fetch_events(self):
        events = []
        try:
            res = self.session.get(self.base_url, timeout=20)
            if res.status_code != 200:
                print(f"[guca_scraper] HTTP {res.status_code} en {self.base_url}")
                return events
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"[guca_scraper] Error conectando a {self.base_url}: {e}")
            return events

        seen_ids = set()
        for href, card_text in self.list_candidates(soup):
            ev = self.event_from_detail(href, card_text) or self.event_from_card(href, card_text)
            if ev and ev["id"] not in seen_ids:
                seen_ids.add(ev["id"])
                events.append(ev)
        return events

    # ------------------------------------------------------------------ list page

    def list_candidates(self, soup) -> List[tuple]:
        """Unique (event url, card text) pairs for races that are not obviously other sports."""
        found, seen = [], set()
        for a in soup.select(EVENT_LINK_SELECTOR):
            href = a.get("href", "")
            if not href or href in seen:
                continue
            seen.add(href)

            parent = a.find_parent("div", class_=re.compile(r"col|property|item|card|owl-item"))
            card_text = parent.get_text(" | ", strip=True) if parent else ""
            slug = href.rstrip("/").split("/")[-1].replace("-", " ")
            labelled_cycling = "ciclismo" in strip_accents(card_text)

            if not labelled_cycling and self.is_non_cycling(f"{slug} {card_text}"):
                continue
            found.append((href, card_text))
        return found

    @staticmethod
    def _looks_like_cycling(*texts: str) -> bool:
        clean = strip_accents(" ".join(texts))
        return any(hint in clean for hint in CYCLING_HINTS)

    # ------------------------------------------------------------------ detail page

    def event_from_detail(self, href: str, card_text: str) -> Optional[Dict]:
        try:
            res = self.session.get(href, timeout=20)
            if res.status_code != 200:
                return None
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception as e:
            print(f"[guca_scraper] Error leyendo {href}: {e}")
            return None
        return self.parse_detail(soup, href, card_text)

    def parse_detail(self, soup, href: str, card_text: str = "") -> Optional[Dict]:
        heading = soup.find(["h1", "h2"])
        title = heading.get_text(" ", strip=True) if heading else ""
        if not title and soup.title:
            title = re.sub(r"\s*-\s*GUCA\s*$", "", soup.title.get_text(strip=True))
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return None

        venue_el = soup.select_one(".event_venue")
        venue = venue_el.get_text(" ", strip=True) if venue_el else soup.get_text(" ", strip=True)[:800]

        dates = []
        for day, month_name, year in DATE_RE.findall(venue):
            month = MONTHS_ES.get(strip_accents(month_name))
            if month:
                dates.append(f"{year}-{month}-{day.zfill(2)}")
        if not dates:
            return None

        place_match = PLACE_RE.search(venue)
        place = place_match.group(1).strip() if place_match else ""

        desc_el = soup.select_one(".event_details")
        description = re.sub(r"\s+", " ", desc_el.get_text(" ", strip=True)).strip() if desc_el else ""

        if self.is_non_cycling(title):
            return None
        labelled = "ciclismo" in strip_accents(card_text)
        if not labelled and not self._looks_like_cycling(title, description[:300]):
            return None

        region_code, _, keep = self.locate(place, title)
        if not keep:
            return None

        organizer_el = soup.select_one(".event_organizer")
        organizer = ""
        if organizer_el:
            organizer = re.split(r"\s+Presenta\b", organizer_el.get_text(" ", strip=True))[0]
            organizer = re.sub(r"^GUCA\s+(?=\S)", "", organizer).strip()

        short = description if len(description) <= MAX_DESCRIPTION else description[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"
        return self.build_event(
            title=title,
            date=dates[0],
            end_date=dates[-1],
            place=place,
            region_code=region_code,
            disciplines=self.detect_disciplines(title, default=None) or self.detect_disciplines(f"{title} {description[:300]}"),
            url=href,
            organizer=organizer or "GUCA / Club Organizador",
            description=short or f"Competencia cronometrada por GUCA en {place}.",
        )

    # ------------------------------------------------------------------ card fallback

    def event_from_card(self, href: str, text: str) -> Optional[Dict]:
        """Fallback when the detail page is unavailable: use whatever the home card shows."""
        date_match = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", text)
        if not date_match:
            return None
        day, month, year = date_match.groups()
        date_iso = f"{year}-{month}-{day}"

        parts = [p.strip() for p in text.split("|") if p.strip()]
        title = ""
        for p in parts:
            if (len(p) > 8 and self._looks_like_cycling(p)) or any(w in p.lower() for w in ["desafio", "desafío", "fondo", "race", "tour", "series"]):
                title = p
                break
        if not title:
            title = href.rstrip("/").split("/")[-1].replace("-", " ").title()
        title = re.sub(r"\s+", " ", title).strip()

        if self.is_non_cycling(title) or (
            "ciclismo" not in strip_accents(text) and not self._looks_like_cycling(title, text)
        ):
            return None

        place = ""
        for p in parts:
            if p.lower() in ["inscribete acá", "inscríbete acá", "ticket", "crono", "ver más", "gratis"]:
                continue
            if re.search(r"\d", p) or len(p) >= 25 or p == title:
                continue
            if self.resolve_region(p)[0]:
                place = p
                break

        region_code, _, keep = self.locate(place, title)
        if not keep:
            return None

        return self.build_event(
            title=title,
            date=date_iso,
            place=place,
            region_code=region_code,
            disciplines=self.detect_disciplines(title, default=None) or self.detect_disciplines(text),
            url=href,
            organizer="GUCA / Club Organizador",
            description=f"Competencia cronometrada por GUCA{' en ' + place if place else ''}.",
        )

    # Kept for the unit tests and for callers that already have the home page parsed
    def parse_html(self, soup) -> List[Dict]:
        events = []
        for href, card_text in self.list_candidates(soup):
            ev = self.event_from_card(href, card_text)
            if ev:
                events.append(ev)
        return events
