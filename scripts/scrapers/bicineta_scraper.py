"""
Scraper for Bicineta.cl (Plataforma especializada en ciclismo en Chile)

The event pages only render the first 16 races; the rest are loaded by the
"Cargar más eventos" button from a JSON endpoint (/eventos/fetch_more). We read
that same endpoint (unfiltered, plus a few tag feeds as a safety net) so no race
is left behind, and keep the HTML cards as a fallback if the endpoint changes.
"""

import re
from datetime import date, timedelta
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from .base_scraper import BaseScraper, MONTHS_ES, REGION_NAMES, extract_elevation, infer_year, strip_accents

FEED_PATH = "/eventos/fetch_more"
FEED_PAGE_SIZE = 8
FEED_MAX_OFFSET = 600  # safety cap (~75 requests)
EXTRA_TAG_FEEDS = ["ultra", "brevet", "ruta", "ciclocross"]

# Bicineta tag -> Pedaleo discipline
TAG_DISCIPLINES = {
    "mtb": ["MTB"], "xco": ["MTB"], "xcm": ["MTB"], "rally": ["MTB"], "maraton": ["MTB"],
    "downhill": ["Enduro"], "dh": ["Enduro"], "enduro": ["Enduro"], "dhi": ["Enduro"],
    "ruta": ["Ruta"], "gran-fondo": ["Ruta"], "ciclismo-de-ruta": ["Ruta"], "criterium": ["Ruta"],
    "gravel": ["Gravel"],
    "ultra": ["Ultra/Bikepacking"], "bikepacking": ["Ultra/Bikepacking"], "autosuficiencia": ["Ultra/Bikepacking"],
    "brevet": ["Ultra/Bikepacking", "Ruta"],
    "cicloturismo": ["Cicloturismo"], "recreacional": ["Cicloturismo"],
    "ciclocross": ["Ciclocross"],
}

MAX_DESCRIPTION = 500


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

    # ------------------------------------------------------------------ main

    def fetch_events(self):
        events_by_id: Dict[str, Dict] = {}

        # The main feed and the tag feeds are independent: read them side by side
        feeds = self.map_parallel(self._fetch_feed, [None] + EXTRA_TAG_FEEDS, workers=len(EXTRA_TAG_FEEDS) + 1)
        items = []
        for feed in feeds:
            self._assign_dates(feed)  # each feed is chronological on its own
            items.extend(feed)

        for item in items:
            try:
                ev = self._feed_item_to_event(item)
            except Exception as e:  # one malformed item must not lose the whole run
                print(f"[bicineta_scraper] Item ignorado ({item.get('title')!r}): {e}")
                continue
            if ev:
                self._add(events_by_id, ev)

        if not events_by_id:
            print("[bicineta_scraper] El feed JSON no devolvió eventos; usando las tarjetas HTML.")
            self._fetch_html_fallback(events_by_id)

        return list(events_by_id.values())

    @staticmethod
    def _add(events_by_id, ev):
        existing = events_by_id.get(ev["id"])
        if not existing:
            events_by_id[ev["id"]] = ev
            return
        for d in ev["disciplines"]:
            if d not in existing["disciplines"]:
                existing["disciplines"].append(d)

    # ------------------------------------------------------------------ JSON feed

    def _fetch_feed(self, tag: Optional[str] = None) -> List[Dict]:
        items, seen_ids = [], set()
        offset = 0
        while offset <= FEED_MAX_OFFSET:
            params = {"offset": offset}
            if tag:
                params["tag"] = tag
            try:
                res = self.session.get(
                    f"{self.base_url}{FEED_PATH}", params=params,
                    headers={"Accept": "application/json"}, timeout=40,
                )
                if res.status_code != 200:
                    break
                page = res.json()
            except Exception as e:
                print(f"[bicineta_scraper] Error leyendo feed (tag={tag}, offset={offset}): {e}")
                break
            if not isinstance(page, list) or not page:
                break
            fresh = [it for it in page if it.get("id") not in seen_ids]
            if not fresh:
                break  # the endpoint is repeating itself
            seen_ids.update(it.get("id") for it in fresh)
            items.extend(fresh)
            offset += FEED_PAGE_SIZE
        return items

    @staticmethod
    def _parse_created(created_at: str) -> Optional[date]:
        m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{2,4})$", (created_at or "").strip())
        if not m:
            return None
        year = int(m.group(3))
        year += 2000 if year < 100 else 0
        try:
            return date(year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    @staticmethod
    def _month_days(start_at: str, end_at: Optional[str]) -> List[tuple]:
        """[(month, day), ...] mentioned in "24 de octubre", "24 de octubre - 25 de octubre 09:00", ..."""
        mentions = []
        for text in (start_at, end_at):
            for day, month_name in re.findall(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", (text or "").lower()):
                month = MONTHS_ES.get(strip_accents(month_name))
                if month:
                    mentions.append((int(month), int(day)))
        return mentions

    @classmethod
    def _assign_dates(cls, items: List[Dict], today: Optional[date] = None) -> None:
        """
        The feed has no year but lists races in chronological order from today onwards, so the year
        is the current one and rolls over each time the calendar wraps past December -> January.
        Sets item["_start"] / item["_end"] (ISO strings), or leaves them unset when unparseable.
        """
        today = today or date.today()
        year = today.year
        previous: Optional[date] = None
        for item in items:
            days = cls._month_days(item.get("start_at"), item.get("end_at"))
            if not days:
                continue
            month, day = days[0]
            try:
                start = date(year, month, day)
            except ValueError:
                continue
            if previous is None:
                # The first entries may be a few days old; anything much older is next year's edition
                if start < today - timedelta(days=45):
                    year += 1
                    start = date(year, month, day)
            elif start < previous - timedelta(days=60):
                year += 1  # calendar wrapped into the next year
                start = date(year, month, day)
            previous = max(previous, start) if previous else start

            end = start
            if len(days) > 1:
                end_month, end_day = days[-1]
                try:
                    end = date(start.year + (1 if (end_month, end_day) < (month, day) else 0), end_month, end_day)
                except ValueError:
                    end = start
            item["_start"], item["_end"] = start.isoformat(), end.isoformat()

    @staticmethod
    def _disciplines_from_tags(tags: str) -> List[str]:
        found = []
        for tag in (tags or "").lower().split(","):
            for d in TAG_DISCIPLINES.get(tag.strip(), []):
                if d not in found:
                    found.append(d)
        return found

    @staticmethod
    def _short(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip()
        if len(text) <= MAX_DESCRIPTION:
            return text
        return text[:MAX_DESCRIPTION].rsplit(" ", 1)[0] + "…"

    def _feed_item_to_event(self, item: Dict) -> Optional[Dict]:
        title = re.sub(r"\s+", " ", item.get("title") or "").strip()
        if not title:
            return None

        place = (item.get("place") or "").strip()
        if self.is_non_cycling(title) or self.is_foreign(place) or self.is_foreign(title):
            return None

        start, end = item.get("_start"), item.get("_end")
        if not start:
            print(f"[bicineta_scraper] Omitido (sin fecha válida): {title!r} / {item.get('start_at')!r}")
            return None

        # A known commune is more reliable than the organizer's own region pick; otherwise trust
        # Bicineta's area. No area means abroad or not yet placed.
        area = (item.get("area") or "").strip().upper()
        region_code = self.commune_region(place) or (area if area in REGION_NAMES else None)
        if not region_code:
            region_code, _, keep = self.locate(place, title)
            if not keep:
                return None

        disciplines = self._disciplines_from_tags(item.get("tags"))
        for d in self.detect_disciplines(title, default=None):
            if d not in disciplines:
                disciplines.append(d)

        organizer = item.get("organization")
        if isinstance(organizer, dict):
            organizer = organizer.get("name")
        link = self._clean_url(item.get("external_url") or "")
        if not re.match(r"^https?://", link, re.IGNORECASE):
            link = f"{self.base_url}/eventos"  # some organizers saved an image or nothing as the link

        return self.build_event(
            title=title,
            date=start,
            end_date=end,
            place=place,
            region_code=region_code,
            disciplines=disciplines or ["MTB"],
            elevation_gain_m=extract_elevation(item.get("description")),
            url=link,
            organizer=(organizer or "").strip() or "Bicineta / Organización Local",
            description=self._short(item.get("description")) or f"Competencia de ciclismo: {title} en {place}.",
        )

    # ------------------------------------------------------------------ HTML fallback

    def _fetch_html_fallback(self, events_by_id):
        self._scrape_page(f"{self.base_url}/eventos", default_discipline=None, events_dict=events_by_id)
        for cat_slug, disc_name in self.categories:
            self._scrape_page(f"{self.base_url}/eventos/{cat_slug}", default_discipline=disc_name, events_dict=events_by_id)
        for ev in events_by_id.values():
            if not ev["disciplines"]:
                ev["disciplines"] = ["MTB"]

    def _scrape_page(self, url, default_discipline, events_dict):
        try:
            res = self.session.get(url, timeout=20)
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
                if self.is_foreign(place) or self.is_non_cycling(title):
                    continue

                date_el = card.select_one(".event-start-at")
                date_iso = self._parse_date(
                    date_el.get("datetime", "") if date_el else "",
                    date_el.get_text(strip=True) if date_el else "",
                )
                if not date_iso:
                    continue
                end_el = card.select_one(".event-end-at")
                end_iso = self._parse_date(end_el.get("datetime", "") if end_el else "", "") or date_iso

                link_el = card.select_one(".event-external-link a")
                link = self._clean_url(link_el.get("href", "") if link_el else "")
                if not link or link == "event-external-url":
                    detail_link = title_el.get("href", "")
                    link = f"{self.base_url}{detail_link}" if detail_link.startswith("/") else detail_link

                desc_el = card.select_one(".event-description")
                desc = desc_el.get_text(strip=True) if desc_el else ""
                org_el = card.select_one(".event-organization a")
                org = org_el.get_text(strip=True) if org_el else "Bicineta / Organización Local"

                # "Temuco - IX. Araucanía": the roman numeral after the dash is the region
                area_match = re.search(r"-\s*(XVI|XV|XIV|XII|XI|X|IX|VIII|VII|VI|IV|V|III|II|I|RM)\.", place)
                region_code = area_match.group(1) if area_match else None
                if not region_code:
                    region_code, _, keep = self.locate(place, title)
                    if not keep:
                        continue

                disciplines = self.detect_disciplines(f"{title} {default_discipline or ''} {desc}", default=None)
                ev = self.build_event(
                    title=title, date=date_iso, end_date=end_iso, place=place, region_code=region_code,
                    disciplines=disciplines, url=link, organizer=org, description=desc,
                )
                self._add(events_dict, ev)

        except Exception as e:
            print(f"[bicineta_scraper] Error en {url}: {e}")

    @staticmethod
    def _clean_url(url):
        """Organizers sometimes paste links twice or with a stray prefix ("httphttps://...")."""
        return re.sub(r"^(?:https?)+(?=https?://)", "", (url or "").strip(), flags=re.IGNORECASE)

    def _parse_date(self, date_dt, date_text):
        if date_dt and re.match(r"^\d{4}-\d{2}-\d{2}", date_dt):
            return date_dt[:10]

        # Spanish month parsing fallback ("10 de octubre", no year)
        m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", date_text.lower())
        if m:
            month = MONTHS_ES.get(strip_accents(m.group(2)))
            if month:
                day = int(m.group(1))
                return f"{infer_year(int(month), day)}-{month}-{str(day).zfill(2)}"

        return None
