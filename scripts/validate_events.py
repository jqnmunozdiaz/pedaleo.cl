#!/usr/bin/env python3
"""
Pedaleo.cl - Events Database Validator
Performs integrity, date format, and region validation checks on data/events.json.
"""

import json
import os
import re
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

VALID_REGIONS = {
    "XV", "I", "II", "III", "IV", "V", "RM", "VI",
    "VII", "XVI", "VIII", "IX", "XIV", "X", "XI", "XII"
}

REQUIRED_FIELDS = ["id", "name", "date", "region", "disciplines"]


def validate():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(project_dir, "data", "events.json")

    if not os.path.exists(file_path):
        print(f"[FAIL] El archivo {file_path} no existe.")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            events = json.load(f)
        except Exception as e:
            print(f"[FAIL] Error parseando JSON: {e}")
            sys.exit(1)

    print(f"[INFO] Validando {len(events)} eventos en {file_path}...")
    errors = []
    seen_ids = set()

    for idx, ev in enumerate(events):
        eid = ev.get("id")
        name = ev.get("name")

        # Required fields
        for field in REQUIRED_FIELDS:
            if not ev.get(field):
                errors.append(f"Evento #{idx} ({name or 'sin nombre'}): falta el campo obligatorio '{field}'")

        # Duplicate ID check
        if eid:
            if eid in seen_ids:
                errors.append(f"ID duplicado detectado: '{eid}'")
            seen_ids.add(eid)

        # Date format check (YYYY-MM-DD)
        date_val = ev.get("date", "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
            errors.append(f"Evento '{name}': formato de fecha inválido '{date_val}' (debe ser YYYY-MM-DD)")

        # Region check
        reg = ev.get("region", "")
        if reg not in VALID_REGIONS:
            errors.append(f"Evento '{name}': región '{reg}' no reconocida. Válidas: {sorted(list(VALID_REGIONS))}")

    if errors:
        print(f"\n[FAIL] Se encontraron {len(errors)} errores:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print(f"[OK] ¡Todos los {len(events)} eventos pasaron la validación con éxito!")


if __name__ == "__main__":
    validate()
