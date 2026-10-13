"""
Pedaleo.cl - Source health and stale-race detection

1. Health: remember how many races each scraper normally returns and warn (without touching
   the catalogue) when a run returns far fewer: the source probably changed its layout.
2. Staleness: a scraped race that no source lists any more (cancelled, removed, or moved) is
   dropped after a grace period, but only when every scraper looked healthy in that run, so an
   outage never wipes the calendar.

State lives in small files so data/events.json stays free of bookkeeping churn:
  data/source_stats.json  {source: {"count": 107, "date": "2026-10-13"}}
  data/last_seen.json     {event id: "2026-10-13"} (refreshed weekly, not nightly)
"""

import json
import os
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_FILE = os.path.join(PROJECT_DIR, "data", "source_stats.json")
LAST_SEEN_FILE = os.path.join(PROJECT_DIR, "data", "last_seen.json")

MIN_BASELINE = 10        # sources that normally return fewer races are too small to judge
HEALTHY_RATIO = 0.5      # below this share of the usual count, the run is suspicious
REFRESH_DAYS = 7         # last_seen is only rewritten when older than this (limits git churn)
STALE_DAYS = 28          # not seen for this long (so >= 21 real days) -> drop


def _load(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------------ health

def assess_sources(counts: Dict[str, int], stats: Dict[str, dict], today: Optional[str] = None) -> Tuple[Dict[str, dict], List[str], bool]:
    """
    counts: races returned per scraper in this run.
    Returns (new_stats, warnings, all_healthy). The baseline only moves on healthy runs, so one bad
    night cannot lower the bar for the next one.
    """
    today = today or date.today().isoformat()
    new_stats = dict(stats)
    warnings, healthy = [], True
    for name, count in counts.items():
        baseline = stats.get(name, {}).get("count", 0)
        if baseline >= MIN_BASELINE and count < baseline * HEALTHY_RATIO:
            healthy = False
            warnings.append(f"{name} devolvió {count} carreras (lo normal es ~{baseline}): revisar si cambió el sitio.")
        elif count == 0 and baseline:
            healthy = False
            warnings.append(f"{name} no devolvió ninguna carrera (antes ~{baseline}).")
        elif count > 0:
            new_stats[name] = {"count": count, "date": today}
    return new_stats, warnings, healthy


def load_stats(path: str = STATS_FILE) -> Dict[str, dict]:
    return _load(path)


def save_stats(stats: Dict[str, dict], path: str = STATS_FILE) -> None:
    _save(path, stats)


# ------------------------------------------------------------------ last seen

def load_last_seen(path: str = LAST_SEEN_FILE) -> Dict[str, str]:
    return _load(path)


def save_last_seen(last_seen: Dict[str, str], path: str = LAST_SEEN_FILE) -> None:
    _save(path, last_seen)


def mark_seen(last_seen: Dict[str, str], ids: Iterable[str], today: Optional[str] = None) -> Dict[str, str]:
    """Records that these races were listed today (rewriting an entry at most once a week)."""
    today = today or date.today().isoformat()
    limit = (date.fromisoformat(today) - timedelta(days=REFRESH_DAYS)).isoformat()
    updated = dict(last_seen)
    for event_id in ids:
        if event_id not in updated or updated[event_id] <= limit:
            updated[event_id] = today
    return updated


def drop_stale(
    events: List[dict],
    last_seen: Dict[str, str],
    scraper_sources: Set[str],
    all_healthy: bool,
    today: Optional[str] = None,
) -> Tuple[List[dict], List[dict], Dict[str, str]]:
    """
    Returns (kept, dropped, last_seen). Only upcoming races that came from a scraper are ever
    dropped; hand-added ones stay. Races with no record yet start their clock today.
    """
    today = today or date.today().isoformat()
    last_seen = dict(last_seen)
    limit = (date.fromisoformat(today) - timedelta(days=STALE_DAYS)).isoformat()

    kept, dropped = [], []
    for ev in events:
        seen = last_seen.setdefault(ev["id"], today)
        upcoming = (ev.get("end_date") or ev["date"]) >= today
        if all_healthy and upcoming and ev.get("source") in scraper_sources and seen < limit:
            dropped.append(ev)
        else:
            kept.append(ev)

    keep_ids = {e["id"] for e in kept}
    last_seen = {i: d for i, d in last_seen.items() if i in keep_ids}
    return kept, dropped, last_seen
