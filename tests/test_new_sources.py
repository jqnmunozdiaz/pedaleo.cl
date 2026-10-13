"""
Tests for the Tusdesafios and CiclismoChile scrapers and for the dead-link filter.
Run from the project root:  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from unittest import mock

import requests
from bs4 import BeautifulSoup

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import link_check  # noqa: E402
from scrapers.base_scraper import BaseScraper  # noqa: E402
from scrapers.ciclismochile_scraper import CiclismoChileScraper  # noqa: E402
from scrapers.tusdesafios_scraper import TusdesafiosScraper  # noqa: E402
from test_pipeline import make_event  # noqa: E402


class RegionOrderTests(unittest.TestCase):
    def test_first_named_place_wins_over_longer_names(self):
        # "Santa Cruz" is longer than "Talca" but the race is in Talca
        self.assertEqual(BaseScraper.commune_region("Talca, Iloca, Santa Cruz"), "VII")
        self.assertEqual(BaseScraper.commune_region("Santa Cruz, Talca"), "VI")

    def test_longest_name_wins_at_the_same_position(self):
        self.assertEqual(BaseScraper.commune_region("Chillán Viejo"), "XVI")


class TusdesafiosTests(unittest.TestCase):
    LIST = """
    <a class="event-card" href="/events/ruta-tour-maule-2026"><div class="event-body">
      <div class="event-sport">Ciclismo Ruta</div><div class="event-name">Ruta Tour Maule</div>
      <div class="event-tags"><span class="event-tag">400K</span></div>
      <div class="event-location">R. del Maule</div></div></a>
    <a class="event-card" href="/ads/other"><div class="event-name">Not an event</div></a>
    """

    DETAIL = """
    <html><head><script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Event","name":"Ruta Tour Maule",
     "startDate":"2026-10-15T09:00:00Z","endDate":"2026-10-18T14:00:00Z",
     "location":{"@type":"Place","name":"Talca, Iloca, Santa Cruz",
       "address":{"addressLocality":"","addressRegion":"R. Del Maule","addressCountry":"CL"}},
     "description":"Tour exclusivo de mas de 400 km."}
    </script></head><body>
      <a class="show2-left-btn" href="http://granfondofindelmundo.cl/producto/ruta-tour-maule/">Inscripciones</a>
      <a class="show2-left-btn" href="https://tusdesafios.com/x">Sitio oficial</a>
    </body></html>
    """

    def card(self):
        cards = TusdesafiosScraper().parse_cards(BeautifulSoup(self.LIST, "html.parser"), "Ruta")
        self.assertEqual(len(cards), 1)  # the non-event link is ignored
        return cards[0]

    def parse(self, html=None):
        return TusdesafiosScraper().parse_detail(
            BeautifulSoup(html or self.DETAIL, "html.parser"), self.card(), "https://tusdesafios.com/events/ruta-tour-maule-2026"
        )

    def test_card_fields(self):
        card = self.card()
        self.assertEqual((card["name"], card["tags"], card["location"]), ("Ruta Tour Maule", ["400K"], "R. del Maule"))

    def test_detail_gives_dates_place_distances_and_official_link(self):
        ev = self.parse()
        self.assertEqual((ev["date"], ev["end_date"], ev["region"], ev["commune"]), ("2026-10-15", "2026-10-18", "VII", "Talca"))
        self.assertEqual(ev["distances"], ["400 km"])
        self.assertEqual(ev["registration_url"], "http://granfondofindelmundo.cl/producto/ruta-tour-maule/")
        self.assertEqual(ev["url"], "https://tusdesafios.com/events/ruta-tour-maule-2026")
        self.assertEqual(ev["organizer"], "Organización oficial")

    def test_without_official_link_the_page_itself_is_used(self):
        html = self.DETAIL.replace("granfondofindelmundo.cl/producto/ruta-tour-maule/", "tusdesafios.com/events/ruta-tour-maule-2026")
        self.assertEqual(self.parse(html)["registration_url"], "https://tusdesafios.com/events/ruta-tour-maule-2026")

    def test_missing_date_is_skipped(self):
        self.assertIsNone(self.parse(self.DETAIL.replace('"startDate":"2026-10-15T09:00:00Z",', "")))

    def test_foreign_country_is_skipped(self):
        self.assertIsNone(self.parse(self.DETAIL.replace('"addressCountry":"CL"', '"addressCountry":"AR"')))

    def test_region_falls_back_to_the_region_text(self):
        html = self.DETAIL.replace("Talca, Iloca, Santa Cruz", "Parque Sin Nombre")
        self.assertEqual(self.parse(html)["region"], "VII")


class CiclismoChileTests(unittest.TestCase):
    def test_date_formats(self):
        parse = CiclismoChileScraper.parse_dates
        self.assertEqual(parse("23 ago 2026"), ("2026-08-23", "2026-08-23"))
        self.assertEqual(parse("17-10-2026"), ("2026-10-17", "2026-10-17"))
        self.assertEqual(parse("24 de octubre de 2026"), ("2026-10-24", "2026-10-24"))
        self.assertEqual(parse("21 al 22 de noviembre de 2026"), ("2026-11-21", "2026-11-22"))
        self.assertEqual(parse("10 de abril de 2023 a 31 de diciembre de 2026"), (None, None))  # ongoing course
        self.assertEqual(parse("15 Oct"), (None, None))  # no year: never guessed
        self.assertEqual(parse("31 feb 2026"), (None, None))

    def item(self, **kw):
        base = {"id": "x", "name": "Rally Demo", "date": "18 oct 2026", "location": "Talca, Región del Maule",
                "category": "bike", "source": "bikerace", "link": "https://bikerace.cl/evento?id=1"}
        base.update(kw)
        return base

    def event(self, **kw):
        return CiclismoChileScraper().event_from_item(self.item(**kw))

    def test_item_becomes_event(self):
        ev = self.event()
        self.assertEqual((ev["date"], ev["region"], ev["commune"], ev["disciplines"]), ("2026-10-18", "VII", "Talca", ["MTB"]))
        self.assertEqual(ev["registration_url"], "https://bikerace.cl/evento?id=1")

    def test_sources_scraped_directly_are_skipped(self):
        for source in ("guca", "tusdesafios", "bicineta"):
            self.assertIsNone(self.event(source=source))

    def test_running_foreign_and_dateless_items_are_skipped(self):
        self.assertIsNone(self.event(name="Corrida Trail Running Talca", category="Trail Running"))
        self.assertIsNone(self.event(location="La Paz, Bolivia"))
        self.assertIsNone(self.event(date="15 Oct"))
        self.assertIsNone(self.event(link="javascript:alert(1)"))

    def test_category_without_bikes_is_skipped_but_title_can_save_it(self):
        self.assertIsNone(self.event(name="Gran Evento Deportivo", category="Deportes"))
        self.assertIsNotNone(self.event(name="Gran Rally MTB", category="Deportes"))

    def test_mixed_category_keeps_the_cycling_parts(self):
        ev = self.event(category="Mountain Bike y Gravel")
        self.assertEqual(ev["disciplines"], ["MTB", "Gravel"])

    def test_unknown_place_is_kept_unverified(self):
        self.assertTrue(self.event(location="Lugar Misterioso")["location_unverified"])


class LinkCheckTests(unittest.TestCase):
    def resp(self, status):
        r = mock.Mock()
        r.status_code = status
        return r

    def test_status_classification(self):
        with mock.patch("link_check.requests.head", return_value=self.resp(200)):
            self.assertEqual(link_check.check_url("https://ok.cl/x", pause=0), link_check.OK)
        with mock.patch("link_check.requests.head", return_value=self.resp(404)), \
                mock.patch("link_check.requests.get", return_value=self.resp(404)):
            self.assertEqual(link_check.check_url("https://gone.cl/x", pause=0), link_check.DEAD)
        with mock.patch("link_check.requests.head", return_value=self.resp(403)), \
                mock.patch("link_check.requests.get", return_value=self.resp(403)):
            self.assertEqual(link_check.check_url("https://blocks-bots.cl/x", pause=0), link_check.OK)

    def test_head_404_is_confirmed_with_get(self):
        with mock.patch("link_check.requests.head", return_value=self.resp(404)), \
                mock.patch("link_check.requests.get", return_value=self.resp(200)):
            self.assertEqual(link_check.check_url("https://odd-head.cl/x", pause=0), link_check.OK)

    def test_dns_failure_is_dead_but_timeouts_are_not(self):
        dns = requests.exceptions.ConnectionError("Failed to resolve: [Errno -2] Name or service not known")
        with mock.patch("link_check.requests.head", side_effect=dns):
            self.assertEqual(link_check.check_url("https://nodomain.cl/", pause=0), link_check.DEAD)
        with mock.patch("link_check.requests.head", side_effect=requests.exceptions.Timeout()):
            self.assertEqual(link_check.check_url("https://slow.cl/", pause=0), link_check.UNKNOWN)

    def test_social_and_non_http_links_are_never_checked(self):
        with mock.patch("link_check.requests.head", side_effect=AssertionError("must not be called")):
            self.assertEqual(link_check.check_url("https://www.instagram.com/p/abc/"), link_check.UNKNOWN)
            self.assertEqual(link_check.check_url("mailto:a@b.cl"), link_check.UNKNOWN)

    def events(self):
        return [
            make_event(id="alive", url="https://alive.cl/a", registration_url="https://alive.cl/a", date="2099-01-01", end_date="2099-01-01"),
            make_event(id="dead", url="https://dead.cl/a", registration_url="https://dead.cl/a", date="2099-01-02", end_date="2099-01-02"),
            make_event(id="past-dead", url="https://dead.cl/c", registration_url="https://dead.cl/c", date="2000-01-01", end_date="2000-01-01"),
        ]

    @staticmethod
    def checker(url):
        return link_check.DEAD if "dead.cl" in url else link_check.OK

    def test_race_with_dead_site_is_dropped(self):
        kept, removed, cache = link_check.filter_dead_links(self.events(), today="2026-10-13", checker=self.checker)
        self.assertEqual([e["id"] for e in removed], ["dead"])
        self.assertEqual({e["id"] for e in kept}, {"alive", "past-dead"})
        self.assertEqual(cache["https://dead.cl/a"]["verdict"], link_check.DEAD)

    def test_past_races_are_not_checked(self):
        calls = []
        link_check.filter_dead_links(self.events(), today="2026-10-13", checker=lambda u: calls.append(u) or link_check.OK)
        self.assertNotIn("https://dead.cl/c", calls)

    def test_unknown_verdicts_never_remove_a_race(self):
        kept, removed, _ = link_check.filter_dead_links(self.events(), today="2026-10-13", checker=lambda u: link_check.UNKNOWN)
        self.assertEqual((len(kept), removed), (3, []))

    def test_mass_failure_is_treated_as_a_network_problem(self):
        many = [make_event(id=f"e{i}", url=f"https://dead.cl/{i}", registration_url=f"https://dead.cl/{i}", date="2099-01-01", end_date="2099-01-01")
                for i in range(10)]
        kept, removed, _ = link_check.filter_dead_links(many, today="2026-10-13", checker=self.checker)
        self.assertEqual((len(kept), removed), (10, []))

    def test_server_errors_count_as_dead_after_retries(self):
        with mock.patch("link_check.requests.head", return_value=self.resp(500)), \
                mock.patch("link_check.requests.get", return_value=self.resp(500)):
            self.assertEqual(link_check.check_url("https://broken.cl/x", pause=0), link_check.DEAD)


if __name__ == "__main__":
    unittest.main()
