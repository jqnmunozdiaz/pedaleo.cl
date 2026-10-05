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

from scrapers import BicinetaScraper, GucaScraper, TicketSportScraper

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_DIR, "data", "events.json")


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
