#!/usr/bin/env python3
"""
Pedaleo.cl - Events Database Validator
Performs integrity, date, region, URL and geography checks on data/events.json.
Errors fail the run (exit code 1); warnings are informational.
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

VALID_REGIONS = {
    "XV", "I", "II", "III", "IV", "V", "RM", "VI",
    "VII", "XVI", "VIII", "IX", "XIV", "X", "XI", "XII"
}

VALID_STATUSES = {"open", "upcoming", "closed", "sold_out", "cancelled"}

REQUIRED_FIELDS = ["id", "name", "date", "disciplines"]

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Rough bounding box of Chilean territory (continental + Juan Fernández + Rapa Nui + Antarctic tip excluded)
LAT_RANGE = (-56.0, -17.0)
LNG_RANGE = (-110.0, -66.0)


def parse_date(value):
    """Returns a datetime for a valid YYYY-MM-DD string, otherwise None."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def validate_event(idx, ev, region_names):
    """Returns (errors, warnings) for one event."""
    errors, warnings = [], []
    name = ev.get("name")
    label = f"Evento #{idx} ({name or 'sin nombre'})"

    for field in REQUIRED_FIELDS:
        if not ev.get(field):
            errors.append(f"{label}: falta el campo obligatorio '{field}'")

    # Events whose place could not be confirmed are allowed to have no region (hidden by default in the UI)
    unverified = ev.get("location_unverified") is True
    if "location_unverified" in ev and not isinstance(ev["location_unverified"], bool):
        errors.append(f"{label}: 'location_unverified' debe ser true o false")
    if not unverified and not ev.get("region"):
        errors.append(f"{label}: falta el campo obligatorio 'region' (o marcar location_unverified: true)")
    if unverified and ev.get("region"):
        warnings.append(f"{label}: tiene región pero sigue marcado como location_unverified")

    eid = ev.get("id")
    if eid and not ID_RE.match(eid):
        errors.append(f"{label}: id '{eid}' no es un slug válido (minúsculas, números y guiones)")

    # Dates
    start = parse_date(ev.get("date"))
    if ev.get("date") and not start:
        errors.append(f"{label}: fecha inválida '{ev.get('date')}' (debe ser una fecha real YYYY-MM-DD)")
    if ev.get("end_date"):
        end = parse_date(ev["end_date"])
        if not end:
            errors.append(f"{label}: end_date inválida '{ev['end_date']}'")
        elif start and end < start:
            errors.append(f"{label}: end_date ({ev['end_date']}) es anterior a date ({ev['date']})")

    # Region
    reg = ev.get("region", "")
    if reg and reg not in VALID_REGIONS:
        errors.append(f"{label}: región '{reg}' no reconocida. Válidas: {sorted(VALID_REGIONS)}")
    elif reg and ev.get("region_name") and region_names.get(reg) and ev["region_name"] != region_names[reg]:
        errors.append(f"{label}: region_name '{ev['region_name']}' no coincide con la región {reg} ('{region_names[reg]}')")

    # Disciplines
    disciplines = ev.get("disciplines")
    if disciplines is not None and (
        not isinstance(disciplines, list) or not all(isinstance(d, str) and d.strip() for d in disciplines)
    ):
        errors.append(f"{label}: 'disciplines' debe ser una lista de textos no vacíos")

    # URLs (rendered as links, so only http/https is acceptable)
    for field in ("url", "registration_url"):
        value = ev.get(field)
        if value and not re.match(r"^https?://", value, re.IGNORECASE):
            errors.append(f"{label}: '{field}' debe empezar con http:// o https:// (valor: '{str(value)[:60]}')")
    if not ev.get("url") and not ev.get("registration_url"):
        warnings.append(f"{label}: sin 'url' ni 'registration_url'")

    # Distances: numbers, or null when unknown (never a made-up placeholder)
    lo, hi = ev.get("distance_min_km"), ev.get("distance_max_km")
    for field, value in (("distance_min_km", lo), ("distance_max_km", hi)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
            errors.append(f"{label}: '{field}' debe ser un número positivo o null")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
        errors.append(f"{label}: distance_min_km ({lo}) es mayor que distance_max_km ({hi})")

    # Status
    if ev.get("status") and ev["status"] not in VALID_STATUSES:
        warnings.append(f"{label}: status '{ev['status']}' no es uno de {sorted(VALID_STATUSES)}")

    # Coordinates
    lat, lng = ev.get("lat"), ev.get("lng")
    if (lat is None) != (lng is None):
        errors.append(f"{label}: 'lat' y 'lng' deben venir juntas")
    elif lat is not None:
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            errors.append(f"{label}: 'lat'/'lng' deben ser numéricas")
        elif not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
            errors.append(f"{label}: coordenadas ({lat}, {lng}) fuera de Chile")

    return errors, warnings


def find_duplicate_warnings(events):
    """Same-day, same-region events with overlapping titles (likely the same race from two sources)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from sync_events import is_same_event
    except Exception:  # scrapers' dependencies (requests/bs4) may be missing
        return []
    warnings = []
    for i, a in enumerate(events):
        for b in events[i + 1:]:
            if a.get("id") != b.get("id") and is_same_event(a, b):
                warnings.append(f"Posible duplicado: '{a.get('name')}' y '{b.get('name')}' ({a.get('date')})")
    return warnings


def validate(project_dir=None):
    project_dir = project_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(project_dir, "data", "events.json")
    regions_path = os.path.join(project_dir, "data", "regions.json")

    if not os.path.exists(file_path):
        print(f"[FAIL] El archivo {file_path} no existe.")
        return 1

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            events = json.load(f)
        except Exception as e:
            print(f"[FAIL] Error parseando JSON: {e}")
            return 1

    region_names = {}
    if os.path.exists(regions_path):
        with open(regions_path, "r", encoding="utf-8") as f:
            region_names = {r["id"]: r.get("short") or r["name"] for r in json.load(f)}

    print(f"[INFO] Validando {len(events)} eventos en {file_path}...")
    errors, warnings = [], []
    seen_ids = set()

    for idx, ev in enumerate(events):
        ev_errors, ev_warnings = validate_event(idx, ev, region_names)
        errors.extend(ev_errors)
        warnings.extend(ev_warnings)

        eid = ev.get("id")
        if eid:
            if eid in seen_ids:
                errors.append(f"ID duplicado detectado: '{eid}'")
            seen_ids.add(eid)

    warnings.extend(find_duplicate_warnings(events))

    if warnings:
        print(f"\n[WARN] {len(warnings)} advertencias:")
        for w in warnings:
            print(f"  - {w}")

    if errors:
        print(f"\n[FAIL] Se encontraron {len(errors)} errores:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"[OK] ¡Todos los {len(events)} eventos pasaron la validación con éxito!")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
