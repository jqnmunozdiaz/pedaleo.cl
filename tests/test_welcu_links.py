"""
Tests for the Welcu link helpers (generic links, tracking parameters, event lookup).
Run from the project root:  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from unittest import mock

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import welcu_links as w  # noqa: E402

PROFILE = """
<a href="/demaria/contact_modal.js">Contacta al organizador</a>
<a href="https://welcu.com/demaria/past">Eventos pasados</a>
<a href="https://welcu.com/demaria/climbingtour6">Climbing Tour 6ª Fecha</a>
<a href="https://welcu.com/demaria/mtbtour6?utm_source=x">Mountain Bike Tour 6º fecha</a>
<a href="https://welcu.com/demaria/desafiosubaru">Desafío Bci Subaru 2026</a>
"""


class GenericLinkTests(unittest.TestCase):
    def test_generic_links(self):
        for url in ("https://welcu.com", "https://welcu.com/", "https://welcu.com/es/directory", "https://welcu.com/demaria", "https://www.welcu.com/es"):
            self.assertTrue(w.is_generic_welcu(url), url)

    def test_specific_links_and_other_hosts(self):
        for url in ("https://welcu.com/demaria/mtbtour6", "https://welcu.com/es/demaria/mtbtour6", "https://example.cl/", ""):
            self.assertFalse(w.is_generic_welcu(url), url)

    def test_organizer_slug(self):
        self.assertEqual(w.organizer_slug("https://welcu.com/demaria"), "demaria")
        self.assertIsNone(w.organizer_slug("https://welcu.com"))
        self.assertIsNone(w.organizer_slug("https://welcu.com/es/directory"))


class CleaningTests(unittest.TestCase):
    def test_tracking_parameters_are_removed(self):
        self.assertEqual(w.clean_link("https://welcu.com/demaria/-1k67?utm_source=directory"), "https://welcu.com/demaria/-1k67")
        self.assertEqual(w.clean_link("https://x.cl/a?id=3&utm_medium=z&fbclid=abc"), "https://x.cl/a?id=3")

    def test_welcu_links_are_upgraded_to_https_but_others_untouched(self):
        self.assertEqual(w.clean_link("http://welcu.com/a/b"), "https://welcu.com/a/b")
        self.assertEqual(w.clean_link("http://granfondofindelmundo.cl/x"), "http://granfondofindelmundo.cl/x")


class LookupTests(unittest.TestCase):
    def find(self, title):
        return w.best_event_link(PROFILE, "demaria", title)

    def test_matches_the_right_event(self):
        self.assertEqual(self.find("MTB Tour 2026 - Fecha 6"), "https://welcu.com/demaria/mtbtour6")
        self.assertEqual(self.find("Desafío Subaru"), "https://welcu.com/demaria/desafiosubaru")

    def test_does_not_match_on_generic_words(self):
        # "Tour" and "Fecha" alone must not pick the Climbing Tour
        self.assertIsNone(self.find("Tour Fecha 6"))

    def test_other_edition_number_is_not_the_same_race(self):
        self.assertIsNone(self.find("MTB Tour 2026 - Fecha 5"))

    def test_race_with_extra_distinctive_words_is_not_forced_onto_another_event(self):
        self.assertIsNone(self.find("MTB Tour 2026 - Fecha Chicureo"))

    def test_resolve_uses_the_profile_and_falls_back_to_the_original(self):
        ok = mock.Mock(status_code=200, text=PROFILE)
        with mock.patch("welcu_links.requests.get", return_value=ok):
            self.assertEqual(w.resolve_generic_link("https://welcu.com/demaria", "Desafío Subaru"), "https://welcu.com/demaria/desafiosubaru")
            self.assertEqual(w.resolve_generic_link("https://welcu.com/demaria", "Carrera Inexistente"), "https://welcu.com/demaria")
        with mock.patch("welcu_links.requests.get", side_effect=Exception("down")):
            self.assertEqual(w.resolve_generic_link("https://welcu.com/demaria", "Desafío Subaru"), "https://welcu.com/demaria")
        with mock.patch("welcu_links.requests.get", side_effect=AssertionError("must not be called")):
            self.assertEqual(w.resolve_generic_link("https://welcu.com", "Algo"), "https://welcu.com")  # bare home page


if __name__ == "__main__":
    unittest.main()
