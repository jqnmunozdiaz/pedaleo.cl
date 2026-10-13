"""
Base Scraper Class for Pedaleo.cl
Provides common request handling, cleaning, region resolution, and discipline classification.
"""

import json
import os
import re
import unicodedata
from datetime import date, datetime
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from welcu_links import clean_link
from urllib3.util.retry import Retry

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COORDS_PATH = os.path.join(BASE_DIR, "data", "communes_coords.json")
COMMUNES_REGIONS_PATH = os.path.join(BASE_DIR, "data", "communes_regions.json")


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


COORDS_DATA = _load_json(COORDS_PATH)
COMMUNES_REGIONS = _load_json(COMMUNES_REGIONS_PATH)

# Region names and a few well-known keywords (accent-free: text is normalized before matching).
# Specific communes live in data/communes_regions.json.
REGION_MAPPING = {
    "arica": "XV",
    "parinacota": "XV",
    "tarapaca": "I",
    "antofagasta": "II",
    "atacama": "III",
    "coquimbo": "IV",
    "valparaiso": "V",
    "metropolitana": "RM",
    "santiago": "RM",
    "rm": "RM",
    "o'higgins": "VI",
    "ohiggins": "VI",
    "maule": "VII",
    "nuble": "XVI",
    "biobio": "VIII",
    "araucania": "IX",
    "los rios": "XIV",
    "los lagos": "X",
    "chiloe": "X",
    "aysen": "XI",
    "patagonia": "XI",
    "magallanes": "XII",
    "libertador": "VI",
}

# Roman numerals are only trusted in the form "Region IV" (bare "III" or "V" appear in event titles).
ROMAN_REGION_RE = re.compile(r"\bregion\s+(?:de\s+)?(xvi|xv|xiv|xii|xi|x|ix|viii|vii|vi|iv|v|iii|ii|i)\b")

# Anything mentioning these places is outside Chile and must not be listed.
FOREIGN_PLACES = [
    "bolivia", "ecuador", "uruguay", "francia", "brasil", "brazil", "argentina", "peru", "colombia",
    "mexico", "espana", "spain", "italia", "portugal", "estados unidos", "usa", "paraguay",
    "venezuela", "costa rica", "panama", "alemania", "suiza", "nepal", "marruecos",
    "sudamerica", "latinoamerica", "europa", "estados unidos", "canada", "inglaterra", "australia",
]

# Not cycling: running, swimming, trekking, etc. (checked against the event title).
NON_CYCLING_WORDS = [
    "trail running", "running", "aguas abiertas", "natacion", "nado", "triatlon", "triathlon",
    "duatlon", "atletismo", "caminata", "senderismo", "trekking", "kayak", "ironman",
]

# Places that only say "we don't know yet"
PLACEHOLDER_PLACE_RE = re.compile(r"pronto|confirmar|por definir|a definir|\btbd\b|sin definir", re.IGNORECASE)

MONTHS_ES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "setiembre": "09", "octubre": "10",
    "noviembre": "11", "diciembre": "12",
}

# Words that clearly say "this is about bikes" (used when a source mixes several sports).
CYCLING_HINTS = [
    "ciclis", "bici", "mtb", "mountain", "gravel", "bike", "pedal", "xco", "xcm", "rally",
    "downhill", "enduro", "bikepacking", "brevet", "gran fondo", "granfondo", "cicloturismo",
]

REGION_NAMES = {
    "RM": "Metropolitana",
    "XV": "Arica y Parinacota",
    "I": "Tarapacá",
    "II": "Antofagasta",
    "III": "Atacama",
    "IV": "Coquimbo",
    "V": "Valparaíso",
    "VI": "O'Higgins",
    "VII": "Maule",
    "XVI": "Ñuble",
    "VIII": "Biobío",
    "IX": "La Araucanía",
    "XIV": "Los Ríos",
    "X": "Los Lagos",
    "XI": "Aysén",
    "XII": "Magallanes",
}


def strip_accents(text: str) -> str:
    """Removes accents and converts to lowercase for clean matching."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


_COMMUNE_TO_REGION = {strip_accents(name): code for name, code in COMMUNES_REGIONS.items()}
# Longest names first so "Chillan Viejo" wins over "Chillan"
_COMMUNES_BY_LENGTH = sorted(_COMMUNE_TO_REGION, key=len, reverse=True)


def _contains_word(text: str, word: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def infer_year(month: int, day: int, today: Optional[date] = None) -> int:
    """
    Picks the year for a date written without one ("10 de octubre"):
    the current year, or the next one when that date is already more than
    two months behind us (an event listed in January is for next season).
    """
    today = today or date.today()
    try:
        candidate = date(today.year, month, day)
    except ValueError:
        return today.year
    return today.year + 1 if (today - candidate).days > 60 else today.year


def parse_distances(values) -> tuple:
    """
    Normalizes distance strings ("120K y 60K", "45 km", "7.5K, 400m") into
    (["120 km", "60 km"], min_km, max_km). Metres are ignored; unknown -> (None, None, None).
    """
    found = []
    for raw in values or []:
        for num, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(km|k|mts|m)\b", str(raw), flags=re.IGNORECASE):
            if unit.lower() in ("m", "mts"):
                continue
            value = float(num.replace(",", "."))
            if 0 < value < 3000:
                found.append(value)
    if not found:
        return None, None, None
    unique = sorted(set(found), reverse=True)
    labels = [f"{int(v) if v == int(v) else v} km" for v in unique]
    return labels, min(found), max(found)


class BaseScraper:
    def __init__(self, name: str):
        self.name = name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36 PedaleoBot/1.0"
            ),
            "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        })
        # Source sites are flaky: retry transient failures with backoff instead of losing a whole night
        retry = Retry(total=3, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_events(self) -> List[Dict]:
        """Override in subclasses to return a list of event dictionaries."""
        raise NotImplementedError

    @staticmethod
    def commune_region(text: str) -> Optional[str]:
        """Region of the first known commune/locality named in the text (more reliable than organizers' own tags)."""
        clean = strip_accents(text or "")
        best = None  # (position, -length, region): the first place named wins, then the longest name
        for commune in _COMMUNES_BY_LENGTH:
            m = re.search(r"\b" + re.escape(commune) + r"\b", clean)
            if m and (best is None or (m.start(), -len(commune)) < best[:2]):
                best = (m.start(), -len(commune), _COMMUNE_TO_REGION[commune])
        return best[2] if best else None

    @staticmethod
    def _region_from_text(text: str) -> Optional[str]:
        clean = strip_accents(text or "")
        if not clean:
            return None

        # 1. Explicit "Región IV" style mentions
        m = ROMAN_REGION_RE.search(clean)
        if m and m.group(1).upper() in REGION_NAMES:
            return m.group(1).upper()

        # 2. Known communes / localities
        commune_region = BaseScraper.commune_region(clean)
        if commune_region:
            return commune_region

        # 3. Region names and well-known keywords
        for key, code in REGION_MAPPING.items():
            if _contains_word(clean, key):
                return code
        return None

    def resolve_region(self, location_text: str, fallback_text: str = "") -> tuple:
        """
        Resolves (region code, region name) from the place text, falling back to a
        secondary text (e.g. the event title). Returns (None, None) when the place
        cannot be located in Chile: callers should skip the event instead of guessing.
        """
        code = self._region_from_text(location_text) or self._region_from_text(fallback_text)
        if not code:
            return None, None
        return code, REGION_NAMES.get(code, "Chile")

    @staticmethod
    def is_foreign(text: str) -> bool:
        """True if the text names a country other than Chile."""
        clean = strip_accents(text or "")
        return any(_contains_word(clean, country) for country in FOREIGN_PLACES)

    @staticmethod
    def is_non_cycling(text: str) -> bool:
        """True if the title is clearly not a cycling event (running, swimming, ...)."""
        clean = strip_accents(text or "")
        return any(_contains_word(clean, word) for word in NON_CYCLING_WORDS)

    def locate(self, place: str, title: str = "") -> tuple:
        """
        Decides what to do with an event's location. Returns (region_code, region_name, keep):
        - located in Chile        -> (code, name, True)
        - abroad                  -> (None, None, False)  (dropped)
        - unknown                 -> (None, None, True)   (kept, flagged as location_unverified)
        """
        if self.is_foreign(place):
            return None, None, False
        code, name = self.resolve_region(place, title)
        if code:
            return code, name, True
        return None, None, not self.is_foreign(title)

    def build_event(self, *, title: str, date: str, place: str = "", region_code: Optional[str] = None,
                    end_date: Optional[str] = None, disciplines: Optional[List[str]] = None,
                    distances: Optional[List[str]] = None, url: str = "", registration_url: str = "",
                    organizer: str = "", description: str = "", price_type: str = "paid") -> Dict:
        """Builds a schema-complete event. A missing region marks it as location_unverified."""
        place = (place or "").strip()
        if PLACEHOLDER_PLACE_RE.search(place):
            place = ""  # "Pronto más info", "Por confirmar", ...
        verified = bool(region_code)
        region_name = REGION_NAMES.get(region_code) if verified else None
        commune = re.split(r"\s[–-]\s|,", place)[0].strip() if place else ""
        if verified and not commune:
            commune = region_name

        labels, dist_min, dist_max = parse_distances(distances)
        url = clean_link(url or registration_url)
        registration_url = clean_link(registration_url)
        event = {
            "id": self.generate_slug(title, date),
            "name": title.strip(),
            "date": date,
            "end_date": end_date if end_date and end_date >= date else date,
            "disciplines": disciplines or ["MTB"],
            "region": region_code if verified else None,
            "region_name": region_name,
            "commune": commune or None,
            "location": (f"{commune}, Región {region_name}" if verified else (place or "Ubicación por confirmar")),
            "distances": labels or ["Ver bases"],
            "distance_min_km": dist_min,
            "distance_max_km": dist_max,
            "elevation_gain_m": 0,
            "price_type": price_type,
            "status": "open",
            "organizer": organizer or "Organización oficial",
            "url": url,
            "registration_url": registration_url or url,
            "description": description or f"Competencia de ciclismo: {title}.",
            "featured": False,
            "source": self.name,
        }
        if not verified:
            event["location_unverified"] = True
        return event

    def resolve_coordinates(self, commune: str, region_code: str) -> tuple:
        """Resolves lat and lng coordinates based on commune or region code."""
        clean_commune = strip_accents(commune) if commune else ""
        if clean_commune:
            # Direct match
            for k, coords in COORDS_DATA.items():
                if strip_accents(k) == clean_commune:
                    return coords[0], coords[1]
            # Substring match (skip short regional keys like RM, XV, etc.)
            for k, coords in COORDS_DATA.items():
                if len(k) > 3 and (strip_accents(k) in clean_commune or clean_commune in strip_accents(k)):
                    return coords[0], coords[1]

        # Region fallback
        if region_code and region_code in COORDS_DATA:
            coords = COORDS_DATA[region_code]
            return coords[0], coords[1]

        # Default fallback (Santiago)
        return -33.4489, -70.6693

    def detect_disciplines(self, text: str, default: Optional[str] = "MTB") -> List[str]:
        """
        Infers cycling disciplines from title and description.
        When nothing matches, falls back to `default` (MTB is the most common in Chile);
        pass default=None to get an empty list instead.
        """
        clean = strip_accents(text)
        disciplines = []

        if any(w in clean for w in ["gravel"]):
            disciplines.append("Gravel")
        if any(w in clean for w in ["mtb", "mountain bike", "xcm", "xco", "maraton", "rally"]):
            disciplines.append("MTB")
        if any(w in clean for w in ["gran fondo", "ruta", "crono", "clasica", "criterium", "carretera"]):
            disciplines.append("Ruta")
        if any(w in clean for w in ["ultra", "bikepacking", "across", "autosuficiencia"]):
            disciplines.append("Ultra/Bikepacking")
        if any(w in clean for w in ["enduro", "descenso", "downhill", "dhi"]):
            disciplines.append("Enduro")
        if re.search(r"\bbmx\b", clean):
            disciplines.append("BMX")
        if any(w in clean for w in ["cicloturismo", "recreativo", "familiar"]):
            disciplines.append("Cicloturismo")

        if not disciplines and default:
            disciplines.append(default)

        return disciplines

    def generate_slug(self, name: str, date_str: str) -> str:
        """Generates a URL-friendly slug ID."""
        clean = strip_accents(name)
        clean = re.sub(r"[^a-z0-9]+", "-", clean).strip("-")
        year = date_str[:4] if len(date_str) >= 4 else str(date.today().year)
        if year not in clean:
            clean = f"{clean}-{year}"
        return clean
