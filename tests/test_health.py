"""
Tests for source health checks and stale-race removal.
Run from the project root:  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import source_health as h  # noqa: E402
from sync_events import merge_events  # noqa: E402
from test_pipeline import make_event  # noqa: E402

TODAY = "2026-10-13"


class HealthTests(unittest.TestCase):
    def test_normal_run_updates_the_baseline(self):
        stats, warnings, healthy = h.assess_sources({"bicineta": 110}, {"bicineta": {"count": 100, "date": "2026-10-01"}}, TODAY)
        self.assertEqual((warnings, healthy), ([], True))
        self.assertEqual(stats["bicineta"], {"count": 110, "date": TODAY})

    def test_collapse_is_flagged_and_does_not_lower_the_baseline(self):
        before = {"bicineta": {"count": 100, "date": "2026-10-01"}}
        stats, warnings, healthy = h.assess_sources({"bicineta": 20}, before, TODAY)
        self.assertFalse(healthy)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(stats["bicineta"]["count"], 100)

    def test_empty_source_with_history_is_flagged_but_never_seen_source_is_not(self):
        _, warnings, healthy = h.assess_sources({"guca": 0}, {"guca": {"count": 14, "date": "2026-10-01"}}, TODAY)
        self.assertFalse(healthy)
        _, warnings, healthy = h.assess_sources({"ticketsport": 0}, {}, TODAY)
        self.assertEqual((warnings, healthy), ([], True))

    def test_small_sources_are_not_judged_on_ratio(self):
        _, _, healthy = h.assess_sources({"tiny": 1}, {"tiny": {"count": 4, "date": "2026-10-01"}}, TODAY)
        self.assertTrue(healthy)


class LastSeenTests(unittest.TestCase):
    def test_mark_seen_refreshes_only_once_a_week(self):
        seen = h.mark_seen({}, ["a"], "2026-10-01")
        self.assertEqual(seen["a"], "2026-10-01")
        self.assertEqual(h.mark_seen(seen, ["a"], "2026-10-05")["a"], "2026-10-01")   # too soon: no churn
        self.assertEqual(h.mark_seen(seen, ["a"], "2026-10-09")["a"], "2026-10-09")

    def events(self):
        return [
            make_event(id="listed", source="bicineta", date="2027-01-01", end_date="2027-01-01"),
            make_event(id="gone", source="bicineta", date="2027-01-02", end_date="2027-01-02"),
            make_event(id="manual", source="organizer", date="2027-01-03", end_date="2027-01-03"),
            make_event(id="past", source="bicineta", date="2026-01-01", end_date="2026-01-01"),
        ]

    OLD = {"listed": "2026-10-13", "gone": "2026-08-01", "manual": "2026-01-01", "past": "2026-01-01"}

    def test_only_unlisted_upcoming_scraped_races_are_dropped(self):
        kept, dropped, _ = h.drop_stale(self.events(), self.OLD, {"bicineta"}, True, TODAY)
        self.assertEqual([e["id"] for e in dropped], ["gone"])
        self.assertEqual({e["id"] for e in kept}, {"listed", "manual", "past"})

    def test_nothing_is_dropped_when_a_source_looks_broken(self):
        kept, dropped, _ = h.drop_stale(self.events(), self.OLD, {"bicineta"}, False, TODAY)
        self.assertEqual((dropped, len(kept)), ([], 4))

    def test_unknown_races_start_their_clock_today(self):
        kept, dropped, seen = h.drop_stale(self.events(), {}, {"bicineta"}, True, TODAY)
        self.assertEqual(dropped, [])
        self.assertEqual(seen["gone"], TODAY)

    def test_grace_period_is_respected(self):
        recent = dict(self.OLD, gone="2026-09-25")  # 18 days ago
        _, dropped, _ = h.drop_stale(self.events(), recent, {"bicineta"}, True, TODAY)
        self.assertEqual(dropped, [])

    def test_removed_races_are_pruned_from_the_record(self):
        _, dropped, seen = h.drop_stale(self.events(), self.OLD, {"bicineta"}, True, TODAY)
        self.assertNotIn("gone", seen)


class MergeSeenTests(unittest.TestCase):
    def test_merge_reports_every_listed_race_including_matches(self):
        existing = [make_event(id="a", name="Rally Uno Temuco", region="IX", source="bicineta")]
        scraped = [make_event(id="a", name="Rally Uno Temuco", region="IX", source="bicineta"),
                   make_event(id="b", name="Otra Carrera Distinta", region="V", source="guca")]
        seen = set()
        merge_events(existing, scraped, seen=seen)
        self.assertEqual(seen, {"a", "b"})


if __name__ == "__main__":
    unittest.main()
