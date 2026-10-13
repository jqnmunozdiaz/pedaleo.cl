"""
Tests for map positions: commune table, cached geocoding, approximate fallbacks.
Run from the project root:  python -m unittest discover -s tests -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from geocode import Geocoder  # noqa: E402
from sync_events import assign_coordinates, region_centroids  # noqa: E402
from test_pipeline import make_event  # noqa: E402

CENTROIDS = region_centroids()


def fake_session(payloads):
    """Session whose get() answers from a queue of Nominatim-style payloads."""
    session = mock.Mock()
    queue = list(payloads)

    def get(url, params=None, headers=None, timeout=None):
        response = mock.Mock(status_code=200)
        response.json.return_value = queue.pop(0)
        return response

    session.get.side_effect = get
    return session


def make_geocoder(payloads, **kw):
    path = tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
    os.unlink(path)
    return Geocoder(CENTROIDS, cache_path=path, session=fake_session(payloads), sleep=lambda s: None, **kw), path


def unplaced(**kw):
    ev = make_event(region="VI", region_name="O'Higgins", commune="Lugar Desconocido")
    ev.pop("lat"), ev.pop("lng")
    ev.update(kw)
    return ev


class AssignCoordinatesTests(unittest.TestCase):
    def test_known_commune_uses_the_table(self):
        ev = unplaced(commune="Rancagua")
        assign_coordinates([ev])
        self.assertEqual(ev["geo"], "commune")
        self.assertAlmostEqual(ev["lat"], -34.17, places=1)

    def test_unknown_place_falls_back_to_the_region_and_says_so(self):
        ev = unplaced()
        assign_coordinates([ev])
        self.assertEqual(ev["geo"], "region")
        self.assertEqual((ev["lat"], ev["lng"]), (round(CENTROIDS["VI"][0], 5), round(CENTROIDS["VI"][1], 5)))

    def test_geocoder_result_is_used_when_available(self):
        ev = unplaced()
        assign_coordinates([ev], geocoder=lambda commune, region, code: (-34.4, -71.6))
        self.assertEqual((ev["geo"], ev["lat"], ev["lng"]), ("geocoded", -34.4, -71.6))

    def test_hand_set_coordinates_are_respected(self):
        ev = unplaced(lat=-34.9, lng=-71.1)
        assign_coordinates([ev], geocoder=lambda *a: (0, 0))
        self.assertEqual((ev["geo"], ev["lat"]), ("manual", -34.9))

    def test_region_pins_are_retried_later(self):
        ev = unplaced()
        assign_coordinates([ev])                       # no geocoder yet: approximate
        assign_coordinates([ev], geocoder=lambda *a: (-34.4, -71.6))   # a later run finds it
        self.assertEqual(ev["geo"], "geocoded")

    def test_unconfirmed_location_gets_no_pin(self):
        ev = make_event(region=None, region_name=None, commune=None, location_unverified=True)
        ev.pop("lat"), ev.pop("lng")
        assign_coordinates([ev], geocoder=lambda *a: (-34.4, -71.6))
        self.assertNotIn("lat", ev)


class GeocoderTests(unittest.TestCase):
    FOUND = [{"lat": "-34.3668668", "lon": "-71.6421489"}]

    def test_lookup_is_cached_on_disk_and_not_repeated(self):
        geo, path = make_geocoder([self.FOUND])
        self.assertEqual(geo("Marchigüe", "O'Higgins", "VI"), (-34.36687, -71.64215))
        geo.save()
        again = Geocoder(CENTROIDS, cache_path=path, session=mock.Mock(side_effect=AssertionError("no network")))
        self.assertEqual(again("Marchigüe", "O'Higgins", "VI"), (-34.36687, -71.64215))
        os.unlink(path)

    def test_a_region_name_is_not_a_place(self):
        geo, _ = make_geocoder([self.FOUND])
        for name in ("Araucanía", "O'Higgins", "Los Lagos", "Metropolitana"):
            self.assertIsNone(geo(name, "La Araucanía", "IX"))
        self.assertEqual(geo.session.get.call_count, 0)

    def test_not_found_is_cached_too(self):
        geo, path = make_geocoder([[]])
        self.assertIsNone(geo("Lugar Zzz", "Maule", "VII"))
        self.assertIsNone(geo("Lugar Zzz", "Maule", "VII"))
        self.assertEqual(geo.session.get.call_count, 1)

    def test_namesake_far_from_the_region_is_rejected(self):
        far = [{"lat": "-18.5", "lon": "-70.3"}]   # Arica, nowhere near O'Higgins
        geo, _ = make_geocoder([far])
        self.assertIsNone(geo("Santa Cruz", "O'Higgins", "VI"))

    def test_budget_limits_requests_without_caching_the_skips(self):
        geo, _ = make_geocoder([self.FOUND], max_lookups=1)
        self.assertIsNotNone(geo("A", "O'Higgins", "VI"))
        self.assertIsNone(geo("B", "O'Higgins", "VI"))
        self.assertNotIn("B, O'Higgins, Chile", geo.cache)

    def test_network_errors_do_not_crash_or_poison_the_cache(self):
        geo, _ = make_geocoder([])
        geo.session.get.side_effect = RuntimeError("down")
        self.assertIsNone(geo("A", "O'Higgins", "VI"))
        self.assertEqual(geo.cache, {})


if __name__ == "__main__":
    unittest.main()
