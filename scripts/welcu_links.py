"""
Pedaleo.cl - Welcu link helpers
A link to the Welcu home page or to an organizer's profile is not a registration page.
Welcu event pages look like https://welcu.com/<organizer>/<event>. When a race only has a
generic Welcu link, look for the matching event on the organizer's profile page.
"""

import re
import unicodedata
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

WELCU_HOSTS = ("welcu.com",)
LOCALES = {"es", "en", "pt"}
RESERVED_SEGMENTS = {"directory", "events", "compete", "account", "past", "ratings"}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 PedaleoBot/1.0"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
}


def _segments(url: str) -> List[str]:
    return [s for s in urlsplit(url).path.split("/") if s]


def is_welcu(url: str) -> bool:
    host = urlsplit(url or "").netloc.lower().removeprefix("www.")
    return host in WELCU_HOSTS


def is_generic_welcu(url: str) -> bool:
    """True for welcu.com itself, its directory pages and bare organizer profiles."""
    if not is_welcu(url):
        return False
    segs = [s for s in _segments(url) if s not in LOCALES]
    return len(segs) < 2 or segs[0] in RESERVED_SEGMENTS


def organizer_slug(url: str) -> Optional[str]:
    if not is_welcu(url):
        return None
    segs = [s for s in _segments(url) if s not in LOCALES]
    return segs[0] if len(segs) == 1 and segs[0] not in RESERVED_SEGMENTS else None


def strip_tracking(url: str) -> str:
    """Removes utm_* / fbclid parameters (they only add noise to a link)."""
    parts = urlsplit(url or "")
    if not parts.query:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "igshid")]
    return urlunsplit(parts._replace(query=urlencode(query)))


def clean_link(url: str) -> str:
    """Link without tracking parameters; Welcu links are always https."""
    url = strip_tracking((url or "").strip())
    if is_welcu(url) and url.lower().startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


GENERIC_WORDS = {
    "tour", "fecha", "desafio", "copa", "serie", "series", "gran", "fondo", "race", "challenge",
    "evento", "edicion", "version", "campeonato", "carrera", "ciclismo", "los", "las", "del", "con",
}


def _words(text: str) -> list:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn").lower()
    text = re.sub(r"mountain\s*bike", "mtb", text)
    return re.findall(r"[a-z0-9]+", text)


def _tokens(text: str) -> set:
    """Distinctive words of a title (no generic words, no years, no edition numbers)."""
    return {w for w in _words(text)
            if len(w) >= 3 and w not in GENERIC_WORDS and not re.fullmatch(r"20\d\d|\d+", w)}


def _numbers(text: str) -> set:
    """Edition numbers ("fecha 6", "#3"); years are not editions."""
    return {w for w in _words(text) if re.fullmatch(r"\d{1,2}", w)}


def best_event_link(profile_html: str, slug: str, title: str) -> Optional[str]:
    """Picks the organizer's event whose title best matches the race (needs all of its distinctive words, or at least two)."""
    from bs4 import BeautifulSoup

    wanted = _tokens(title)
    if not wanted:
        return None
    soup = BeautifulSoup(profile_html, "html.parser")
    best, best_score = None, 0
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = a["href"].split("?")[0]
        if not text or not re.match(rf"^(https?://(www\.)?welcu\.com)?/{re.escape(slug)}/[^/#]+$", href):
            continue
        if href.rsplit("/", 1)[-1] in RESERVED_SEGMENTS or href.endswith("contact_modal.js"):
            continue
        # "Fecha 5" and "Fecha 6" of the same series are different races
        nums_a, nums_b = _numbers(title), _numbers(text)
        if nums_a and nums_b and nums_a != nums_b:
            continue
        candidate = _tokens(text)
        common = len(wanted & candidate)
        # every distinctive word of the race must appear in the Welcu title (or at least two of them do)
        if (common >= 2 or (common >= 1 and wanted <= candidate)) and common > best_score:
            best, best_score = href, common
    if best and best.startswith("/"):
        best = f"https://welcu.com{best}"
    return best


def resolve_generic_link(url: str, title: str, timeout: int = 15) -> str:
    """Returns the specific event page when one can be found; otherwise the original link."""
    slug = organizer_slug(url)
    if not slug:
        return url  # the bare home page: nothing to look up
    try:
        response = requests.get(f"https://welcu.com/{slug}", headers=HEADERS, timeout=timeout)
        if response.status_code != 200:
            return url
        return best_event_link(response.text, slug, title) or url
    except Exception:
        return url
