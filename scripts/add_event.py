#!/usr/bin/env python3
"""
Pedaleo.cl - CLI Wizard to Add a Bike Race
Allows fast, error-free manual addition of cycling events into data/events.json.
"""

import json
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(PROJECT_DIR, "data", "events.json")
REGIONS_FILE = os.path.join(PROJECT_DIR, "data", "regions.json")


def load_regions():
    with open(REGIONS_FILE, "r", encoding="utf-8") as f:
        return {r["id"]: r["name"] for r in json.load(f)}


def prompt_input(prompt_text, default=None, required=True):
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{prompt_text}{suffix}: ").strip()
        if not val and default:
            return default
        if not val and required:
            print("  -> Este campo es obligatorio. Por favor ingresa un valor.")
            continue
        return val


def main():
    print("==================================================")
    print("🚴 Pedaleo.cl - Asistente para Agregar Nueva Carrera")
    print("==================================================")

    regions_map = load_regions()

    name = prompt_input("Nombre de la carrera")
    date_val = prompt_input("Fecha (formato YYYY-MM-DD, ej: 2026-11-20)")
    while not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
        print("  -> Formato inválido. Debe ser YYYY-MM-DD.")
        date_val = prompt_input("Fecha (YYYY-MM-DD)")

    print("\nRegiones disponibles:")
    for rid, rname in regions_map.items():
        print(f"  [{rid}] {rname}")
    region_id = prompt_input("Código de Región (ej: RM, VI, IX, X)").upper()
    while region_id not in regions_map:
        print("  -> Código no válido.")
        region_id = prompt_input("Código de Región").upper()
    region_name = regions_map[region_id]

    commune = prompt_input("Comuna o Localidad (ej: Curicó, Farellones)")

    print("\nDisciplinas comunes: MTB, Ruta, Gravel, Ultra/Bikepacking, Enduro, Cicloturismo")
    disc_input = prompt_input("Disciplinas separadas por coma", default="MTB")
    disciplines = [d.strip() for d in disc_input.split(",") if d.strip()]

    dist_input = prompt_input("Distancias (ej: 35 km, 65 km)", default="45 km")
    distances = [d.strip() for d in dist_input.split(",") if d.strip()]

    # Extract max km numeric
    nums = [int(n) for n in re.findall(r"\d+", dist_input)]
    max_km = max(nums) if nums else 45
    min_km = min(nums) if nums else 45

    elev_input = prompt_input("Desnivel positivo en metros (+m)", default="0", required=False)
    elev_m = int(re.sub(r"[^\d]", "", elev_input) or 0)

    url = prompt_input("Link oficial o de inscripciones", default="https://pedaleo.cl")
    organizer = prompt_input("Organizador o Productora", default="Club Organizador")
    description = prompt_input("Breve descripción del evento", default=f"Competencia de {', '.join(disciplines)} en {commune}.")

    # Generate slug ID
    clean_name = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    event_id = f"{clean_name}-{date_val[:4]}"

    new_event = {
        "id": event_id,
        "name": name,
        "date": date_val,
        "end_date": date_val,
        "disciplines": disciplines,
        "region": region_id,
        "region_name": region_name,
        "commune": commune,
        "location": f"{commune}, Región {region_name}",
        "distances": distances,
        "distance_min_km": min_km,
        "distance_max_km": max_km,
        "elevation_gain_m": elev_m,
        "price_type": "paid",
        "status": "open",
        "organizer": organizer,
        "url": url,
        "registration_url": url,
        "description": description,
        "featured": False,
        "source": "manual"
    }

    # Load existing
    events = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            events = json.load(f)

    # Check duplicate ID
    if any(e["id"] == event_id for e in events):
        print(f"\n[AVISO] Ya existía un evento con ID '{event_id}'. Se actualizará.")
        events = [e for e in events if e["id"] != event_id]

    events.append(new_event)
    events.sort(key=lambda x: (x.get("date", ""), x.get("name", "")))

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

    print(f"\n[EXITO] ¡Carrera '{name}' agregada correctamente!")
    print(f"Total de carreras registradas: {len(events)}")


if __name__ == "__main__":
    main()
