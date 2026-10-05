"""
Base Scraper Class for Pedaleo.cl
Provides common request handling, cleaning, region resolution, and discipline classification.
"""

import json
import os
import re
import unicodedata
from datetime import datetime
from typing import Dict, List, Optional
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COORDS_PATH = os.path.join(BASE_DIR, "data", "communes_coords.json")
COORDS_DATA = {}
if os.path.exists(COORDS_PATH):
    try:
        with open(COORDS_PATH, "r", encoding="utf-8") as _f:
            COORDS_DATA = json.load(_f)
    except Exception:
        pass

REGION_MAPPING = {
    "arica": "XV",
    "parinacota": "XV",
    "xv": "XV",
    "tarapaca": "I",
    "tarapacá": "I",
    "i": "I",
    "antofagasta": "II",
    "ii": "II",
    "atacama": "III",
    "iii": "III",
    "coquimbo": "IV",
    "la serena": "IV",
    "iv": "IV",
    "valparaiso": "V",
    "valparaíso": "V",
    "vina del mar": "V",
    "viña del mar": "V",
    "casablanca": "V",
    "v": "V",
    "metropolitana": "RM",
    "santiago": "RM",
    "rm": "RM",
    "lo barnechea": "RM",
    "chicureo": "RM",
    "colina": "RM",
    "o'higgins": "VI",
    "ohiggins": "VI",
    "rancagua": "VI",
    "machali": "VI",
    "machalí": "VI",
    "matanzas": "VI",
    "navidad": "VI",
    "pichilemu": "VI",
    "vi": "VI",
    "maule": "VII",
    "talca": "VII",
    "curico": "VII",
    "curicó": "VII",
    "colbun": "VII",
    "colbún": "VII",
    "vii": "VII",
    "nuble": "XVI",
    "ñuble": "XVI",
    "chillan": "XVI",
    "chillán": "XVI",
    "xvi": "XVI",
    "biobio": "VIII",
    "biobío": "VIII",
    "concepcion": "VIII",
    "concepción": "VIII",
    "curanilahue": "VIII",
    "viii": "VIII",
    "araucania": "IX",
    "araucanía": "IX",
    "temuco": "IX",
    "pucon": "IX",
    "pucón": "IX",
    "villarrica": "IX",
    "lonquimay": "IX",
    "melipeuco": "IX",
    "ix": "IX",
    "los rios": "XIV",
    "los ríos": "XIV",
    "valdivia": "XIV",
    "lago ranco": "XIV",
    "ranco": "XIV",
    "panguipulli": "XIV",
    "xiv": "XIV",
    "los lagos": "X",
    "puerto varas": "X",
    "puerto montt": "X",
    "osorno": "X",
    "frutillar": "X",
    "chiloe": "X",
    "chiloé": "X",
    "castro": "X",
    "ancud": "X",
    "x": "X",
    "aysen": "XI",
    "aysén": "XI",
    "coyhaique": "XI",
    "xi": "XI",
    "magallanes": "XII",
    "punta arenas": "XII",
    "puerto natales": "XII",
    "xii": "XII",
}

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

    def fetch_events(self) -> List[Dict]:
        """Override in subclasses to return a list of event dictionaries."""
        raise NotImplementedError

    def resolve_region(self, location_text: str) -> tuple[str, str]:
        """Resolves region code and region name from text."""
        clean = strip_accents(location_text)
        for key, code in REGION_MAPPING.items():
            if re.search(r"\b" + re.escape(key) + r"\b", clean):
                return code, REGION_NAMES.get(code, "Chile")
        return "RM", "Metropolitana"

    def resolve_coordinates(self, commune: str, region_code: str) -> tuple[float, float]:
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

    def detect_disciplines(self, text: str) -> List[str]:
        """Infers cycling disciplines from title and description."""
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
        if any(w in clean for w in ["cicloturismo", "recreativo", "familiar"]):
            disciplines.append("Cicloturismo")

        if not disciplines:
            disciplines.append("MTB")  # Default to MTB as it is most common in Chile

        return disciplines

    def generate_slug(self, name: str, date_str: str) -> str:
        """Generates a URL-friendly slug ID."""
        clean = strip_accents(name)
        clean = re.sub(r"[^a-z0-9]+", "-", clean).strip("-")
        year = date_str[:4] if len(date_str) >= 4 else "2026"
        if year not in clean:
            clean = f"{clean}-{year}"
        return clean
