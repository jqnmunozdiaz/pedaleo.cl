#!/usr/bin/env python3
"""
Pedaleo.cl - Central Event Synchronization Script
Runs scrapers (Bicineta, GUCA, TicketSport), dedupes and merges with existing events,
validates schema, and updates data/events.json.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from scrapers import (
    BicinetaScraper, CiclismoChileScraper, GucaScraper, RidechileScraper,
    TicketSportScraper, TusdesafiosScraper,
)
from scrapers.base_scraper import strip_accents

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_DIR, "data", "events.json")
COORDS_FILE = os.path.join(PROJECT_DIR, "data", "communes_coords.json")
EXCLUDED_FILE = os.path.join(PROJECT_DIR, "data", "excluded_events.json")


def load_coords():
    if not os.path.exists(COORDS_FILE):
        return {}
    try:
        with open(COORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def assign_coordinates(events):
    coords_data = load_coords()
    if not coords_data:
        return events

    import unicodedata

    def clean_str(s):
        s = unicodedata.normalize("NFD", s or "")
        return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()

    normalized_coords = {clean_str(k): v for k, v in coords_data.items()}

    for ev in events:
        if ev.get("lat") is not None and ev.get("lng") is not None:
            continue
        if not ev.get("region"):
            continue  # location not confirmed: never invent a pin
        commune_clean = clean_str(ev.get("commune", ""))
        location_clean = clean_str(ev.get("location", ""))
        region_clean = clean_str(ev.get("region", ""))

        matched = None
        # 1. Match commune directly
        if commune_clean and commune_clean in normalized_coords:
            matched = normalized_coords[commune_clean]

        # 2. Match commune substring
        if not matched and commune_clean:
            for k, coords in normalized_coords.items():
                if len(k) > 3 and (k in commune_clean or commune_clean in k):
                    matched = coords
                    break

        # 3. Match location string
        if not matched and location_clean:
            for k, coords in normalized_coords.items():
                if len(k) > 3 and k in location_clean:
                    matched = coords
                    break

        # 4. Match region code
        if not matched and region_clean in normalized_coords:
            matched = normalized_coords[region_clean]

        # 5. Default Santiago
        if not matched:
            matched = [-33.4489, -70.6693]

        ev["lat"] = round(matched[0], 5)
        ev["lng"] = round(matched[1], 5)

    return events


def load_excluded_ids():
    """IDs that scrapers must never (re-)add: duplicates and events removed on purpose."""
    if not os.path.exists(EXCLUDED_FILE):
        return set()
    try:
        with open(EXCLUDED_FILE, "r", encoding="utf-8") as f:
            return {item["id"] for item in json.load(f) if isinstance(item, dict) and item.get("id")}
    except Exception as e:
        print(f"[sync] Error leyendo {EXCLUDED_FILE}: {e}")
        return set()


def load_existing_events():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[sync] Error leyendo {DATA_FILE}: {e}")
        return []


def save_events(events):
    events = assign_coordinates(events)
    # Sort chronologically by date
    events.sort(key=lambda x: (x.get("date", ""), x.get("name", "")))
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)
    print(f"[sync] Guardados exitosamente {len(events)} eventos en {DATA_FILE}")


def normalize_title_for_comparison(title: str) -> str:
    """Simplifies race title to compare duplicates across sources."""
    t = title.lower()
    t = re.sub(r"\b(2025|2026|2027|1°|2°|3°|4°|5°|#\d+)\b", "", t)
    t = re.sub(r"[^a-z0-9]", "", t)
    return t


# Words that say nothing about *which* race it is (series names, ordinals, generic nouns).
GENERIC_TOKENS = {
    "copa", "chile", "desafio", "serie", "series", "fecha", "gran", "fondo", "del", "los", "las",
    "oficial", "edicion", "version", "ciclismo", "carrera", "tour", "race", "challenge", "final",
    "primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "septima", "octava",
}
ORDINAL_RE = re.compile(r"\d+(to|er|ro|do|vo|mo|ra|a|o)?")

# Words shared by many unrelated races: never enough on their own to call two titles the same race
WEAK_TOKENS = {"mtb", "xco", "xcm", "dhi", "downhill", "enduro", "gravel", "ruta", "bike", "ultra", "brevet",
               "campeonato", "festival", "rally", "cro", "series", "cup", "copa"}


def title_tokens(title: str) -> set:
    clean = strip_accents(title or "")
    clean = re.sub(r"mountain\s*bike", "mtb", clean)  # same thing, written two ways
    words = re.findall(r"[a-z0-9]+", clean)
    tokens = set()
    for w in words:
        if len(w) < 3 or w in GENERIC_TOKENS or ORDINAL_RE.fullmatch(w):
            continue
        tokens.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)  # "outdoors" == "outdoor"
    return tokens


# Links that identify a whole site or profile, not one race: never used to match events
GENERIC_LINK_HOSTS = {"instagram.com", "facebook.com", "linktr.ee", "bit.ly", "wa.me"}
GENERIC_LINK_PATHS = {"", "/", "/eventos", "/nuevo-calendario"}


def url_key(url: str):
    """Normalized link that identifies one race (None when the link is generic)."""
    if not url:
        return None
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    if not host or path in GENERIC_LINK_PATHS:
        return None
    if host in GENERIC_LINK_HOSTS and not re.match(r"^/(p|reel|events)/", path):
        return None
    query = "&".join(sorted(q for q in parts.query.split("&") if q and not q.lower().startswith("utm_")))
    return f"{host}{path}?{query}" if query else f"{host}{path}"


def regions_compatible(a: dict, b: dict) -> bool:
    """An event with an unconfirmed location is compatible with any region."""
    return not (a.get("region") and b.get("region") and a["region"] != b["region"])


def _span(ev: dict) -> tuple:
    return ev.get("date", ""), ev.get("end_date") or ev.get("date", "")


def dates_compatible(a: dict, b: dict) -> bool:
    """Same start day; or, when one of them has no confirmed location, overlapping date ranges."""
    if a.get("date") == b.get("date"):
        return True
    if a.get("location_unverified") or b.get("location_unverified"):
        (a0, a1), (b0, b1) = _span(a), _span(b)
        return a0 <= b1 and b0 <= a1
    return False


def same_commune(a: dict, b: dict) -> bool:
    ca, cb = strip_accents(a.get("commune") or ""), strip_accents(b.get("commune") or "")
    return bool(ca) and ca == cb


def is_same_event(a: dict, b: dict) -> bool:
    """
    Heuristic duplicate detection across sources: same day, compatible region and
    titles that share their distinctive words (e.g. "AMT XCO #1 Temuco" and
    "AMT XCO SERIES 2026 - Temuco").
    """
    if not dates_compatible(a, b) or not regions_compatible(a, b):
        return False
    ta, tb = title_tokens(a.get("name", "")), title_tokens(b.get("name", ""))
    if not ta or not tb:
        return False
    common = ta & tb
    if not common:
        return False
    if ta == tb:
        return True
    if ta <= tb or tb <= ta:
        if len(common) >= 2:
            return True
        # a single shared word is enough only when it is distinctive ("minga") and the place matches
        return next(iter(common)) not in WEAK_TOKENS and same_commune(a, b)
    return len(common) / len(ta | tb) >= 0.6


def find_match(new_ev: dict, existing_events: list, existing_map: dict):
    norm_key = f"{normalize_title_for_comparison(new_ev['name'])}_{new_ev['date']}"
    match = existing_map.get(new_ev["id"]) or existing_map.get(norm_key)
    if match:
        return match

    # Same registration link = same race, even when the title was written differently
    # Same link on the same day = same race, even when the title is written differently.
    # (The date must match: one page or post is often shared by a whole series or by two
    # editions, e.g. AMT XCO #1..#4. Reschedules are handled by the id match above.)
    keys = {k for k in (url_key(new_ev.get("registration_url")), url_key(new_ev.get("url"))) if k}
    if keys:
        for ev in existing_events:
            shared = keys & {url_key(ev.get("registration_url")), url_key(ev.get("url"))}
            if shared and ev.get("date") == new_ev.get("date") and regions_compatible(ev, new_ev):
                return ev

    for ev in existing_events:
        if is_same_event(ev, new_ev):
            return ev
    return None


def enrich_match(match: dict, new_ev: dict) -> int:
    """Fills gaps in an existing event with better data from another source. Returns changes made."""
    changes = 0

    # A later scrape that finally knows the place upgrades an unconfirmed location
    if match.get("location_unverified") and not new_ev.get("location_unverified"):
        for field in ("region", "region_name", "commune", "location"):
            match[field] = new_ev.get(field)
        match.pop("location_unverified", None)
        match.pop("lat", None)
        match.pop("lng", None)
        changes += 1

    # Real distances replace the "Ver bases" placeholder
    placeholder = match.get("distances") in (None, [], ["Ver bases"])
    if placeholder and new_ev.get("distances") and new_ev["distances"] != ["Ver bases"]:
        for field in ("distances", "distance_min_km", "distance_max_km"):
            match[field] = new_ev.get(field)
        changes += 1

    return changes


def dedupe_existing(events: list) -> tuple:
    """
    Folds duplicates already in the catalogue (e.g. found by a smarter matcher than the one that
    first added them). The older entry is kept and enriched with whatever the newer one knows.
    """
    kept, removed = [], 0
    for ev in events:
        twin = next((k for k in kept if k["id"] != ev["id"] and is_same_event(k, ev)), None)
        if twin:
            enrich_match(twin, ev)
            for d in ev.get("disciplines", []):
                if d not in twin.get("disciplines", []):
                    twin.setdefault("disciplines", []).append(d)
            print(f"[sync] Duplicado fusionado: '{ev['name']}' -> '{twin['name']}' ({twin['date']})")
            removed += 1
        else:
            kept.append(ev)
    return kept, removed


def merge_events(existing_events, new_scraped_events):
    """
    Merges scraped events into existing events without overwriting manual edits.
    Events from the same source get their dates refreshed (races get rescheduled).
    """
    existing_map = {}
    for ev in existing_events:
        existing_map[ev["id"]] = ev
        existing_map[f"{normalize_title_for_comparison(ev['name'])}_{ev['date']}"] = ev

    added_count = 0
    updated_count = 0
    today = date.today().isoformat()

    for new_ev in new_scraped_events:
        match = find_match(new_ev, existing_events, existing_map)

        # A series reusing the same title ("Tour DH Cup #5") must not rewrite a race that already happened
        if match and match["id"] == new_ev["id"] and match.get("end_date", match["date"]) < today \
                and new_ev["date"] != match["date"] and new_ev["date"] >= today:
            new_ev = dict(new_ev, id=f"{new_ev['id']}-{new_ev['date']}")
            # The next edition may already have been added by a previous run
            match = existing_map.get(new_ev["id"])

        if match:
            if match.get("source") == new_ev.get("source"):
                for field in ("date", "end_date"):
                    if new_ev.get(field) and match.get(field) != new_ev[field]:
                        print(f"[sync] Fecha actualizada ({field}) en '{match['name']}': {match.get(field)} -> {new_ev[field]}")
                        match[field] = new_ev[field]
                        updated_count += 1

            updated_count += enrich_match(match, new_ev)

            # Update fields only if missing or richer
            if (not match.get("registration_url") or "pedaleo.cl" in match.get("registration_url", "")) and new_ev.get("registration_url"):
                match["registration_url"] = new_ev["registration_url"]
                updated_count += 1
            if not match.get("description") and new_ev.get("description"):
                match["description"] = new_ev["description"]
            # Permite múltiples formatos combinando disciplinas de distintas fuentes
            for d in new_ev.get("disciplines", []):
                if d not in match.get("disciplines", []):
                    match.setdefault("disciplines", []).append(d)
                    updated_count += 1
        else:
            existing_events.append(new_ev)
            existing_map[new_ev["id"]] = new_ev
            existing_map[f"{normalize_title_for_comparison(new_ev['name'])}_{new_ev['date']}"] = new_ev
            added_count += 1

    return existing_events, added_count, updated_count


def improve_links(events):
    """Cleans tracking parameters and replaces generic Welcu links by the race's own Welcu page when it can be found."""
    from welcu_links import clean_link, is_generic_welcu, resolve_generic_link

    fixed = 0
    for ev in events:
        for field in ("url", "registration_url"):
            link = ev.get(field) or ""
            better = clean_link(link)
            if is_generic_welcu(better):
                better = resolve_generic_link(better, ev.get("name", ""))
            if better != link:
                ev[field] = better
                fixed += 1
    if fixed:
        print(f"[sync] {fixed} enlaces limpiados o reemplazados por la página propia del evento.")
    return events


def drop_dead_links(events):
    """Removes upcoming races whose website no longer works (see link_check.py)."""
    if os.environ.get("PEDALEO_SKIP_LINK_CHECK") == "1":
        return events
    from link_check import filter_dead_links, load_cache, save_cache, event_link

    kept, removed, cache = filter_dead_links(events, cache=load_cache())
    for ev in removed:
        print(f"[sync] Sitio caído, carrera omitida: {ev['name']} ({ev['date']}) -> {event_link(ev)}")
    if removed:
        print(f"::notice title=Enlaces caídos::{len(removed)} carreras omitidas por tener el sitio web caído.")
    save_cache(cache)
    return kept


def run_sync():
    print("==================================================")
    print("🚴 Pedaleo.cl - Sincronizador de Carreras de Ciclismo")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==================================================")

    existing = load_existing_events()
    print(f"[sync] Base de datos actual: {len(existing)} eventos cargados.")

    scrapers = [
        BicinetaScraper(),
        GucaScraper(),
        RidechileScraper(),
        TusdesafiosScraper(),
        CiclismoChileScraper(),
        TicketSportScraper(),
    ]

    all_scraped = []
    for sc in scrapers:
        print(f"[sync] Ejecutando scraper: {sc.name}...")
        try:
            scraped = sc.fetch_events()
            print(f"[sync] -> {len(scraped)} eventos encontrados en {sc.name}.")
            if not scraped:
                # GitHub Actions shows this annotation on the run page: the site layout probably changed
                print(f"::warning title=Scraper sin resultados::{sc.name} no devolvió eventos; revisar si cambió el sitio de origen.")
            all_scraped.extend(scraped)
        except Exception as e:
            print(f"::warning title=Scraper con error::{sc.name}: {e}")
            print(f"[sync] -> Error en scraper {sc.name}: {e}")

    excluded = load_excluded_ids()
    if excluded:
        skipped = [ev for ev in all_scraped if ev["id"] in excluded]
        all_scraped = [ev for ev in all_scraped if ev["id"] not in excluded]
        print(f"[sync] {len(skipped)} eventos omitidos por estar en excluded_events.json.")

    merged, added, updated = merge_events(existing, all_scraped)
    merged, folded = dedupe_existing(merged)
    if folded:
        print(f"[sync] {folded} duplicados internos fusionados.")

    merged = improve_links(merged)
    merged = drop_dead_links(merged)
    print(f"[sync] Resumen: +{added} nuevas carreras agregadas, {updated} actualizadas.")
    print(f"[sync] Total final en catálogo: {len(merged)} carreras.")

    save_events(merged)
    print("[sync] Sincronización completada con éxito.")


if __name__ == "__main__":
    run_sync()
