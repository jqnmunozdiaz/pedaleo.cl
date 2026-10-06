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
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from scrapers import BicinetaScraper, GucaScraper, TicketSportScraper

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_DIR, "data", "events.json")
COORDS_FILE = os.path.join(PROJECT_DIR, "data", "communes_coords.json")


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


def merge_events(existing_events, new_scraped_events):
    """
    Merges scraped events into existing events without overwriting manual edits.
    """
    existing_map = {}
    for ev in existing_events:
        existing_map[ev["id"]] = ev
        norm_key = f"{normalize_title_for_comparison(ev['name'])}_{ev['date']}"
        existing_map[norm_key] = ev

    added_count = 0
    updated_count = 0

    for new_ev in new_scraped_events:
        new_id = new_ev["id"]
        norm_key = f"{normalize_title_for_comparison(new_ev['name'])}_{new_ev['date']}"

        match = existing_map.get(new_id) or existing_map.get(norm_key)

        if match:
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
            existing_map[new_id] = new_ev
            existing_map[norm_key] = new_ev
            added_count += 1

    return existing_events, added_count, updated_count


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
        TicketSportScraper(),
    ]

    all_scraped = []
    for sc in scrapers:
        print(f"[sync] Ejecutando scraper: {sc.name}...")
        try:
            scraped = sc.fetch_events()
            print(f"[sync] -> {len(scraped)} eventos encontrados en {sc.name}.")
            all_scraped.extend(scraped)
        except Exception as e:
            print(f"[sync] -> Error en scraper {sc.name}: {e}")

    merged, added, updated = merge_events(existing, all_scraped)
    print(f"[sync] Resumen: +{added} nuevas carreras agregadas, {updated} actualizadas.")
    print(f"[sync] Total final en catálogo: {len(merged)} carreras.")

    save_events(merged)
    print("[sync] Sincronización completada con éxito.")


if __name__ == "__main__":
    run_sync()
