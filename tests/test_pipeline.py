"""
Tests for the Pedaleo.cl data pipeline (scrapers helpers, merge/dedup, validator).
Run from the project root:  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import date

from bs4 import BeautifulSoup

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from scrapers.base_scraper import BaseScraper, infer_year  # noqa: E402
from scrapers.bicineta_scraper import BicinetaScraper  # noqa: E402
from scrapers.guca_scraper import GucaScraper  # noqa: E402
from scrapers.ticketsport_scraper import TicketSportScraper  # noqa: E402
from sync_events import is_same_event, merge_events, title_tokens  # noqa: E402
from validate_events import validate_event  # noqa: E402


def make_event(**overrides):
    ev = {
        "id": "carrera-demo-2026",
        "name": "Carrera Demo",
        "date": "2026-11-01",
        "end_date": "2026-11-01",
        "disciplines": ["MTB"],
        "region": "RM",
        "region_name": "Metropolitana",
        "commune": "Santiago",
        "url": "https://example.cl",
        "registration_url": "https://example.cl/inscripcion",
        "source": "bicineta",
        "lat": -33.45,
        "lng": -70.66,
    }
    ev.update(overrides)
    # Each race gets its own link unless a test sets one on purpose
    if "url" not in overrides:
        ev["url"] = ev["registration_url"] = f"https://example.cl/{ev['id']}"
    return ev


class RegionResolutionTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseScraper("test")

    def test_commune_table_resolves_region(self):
        self.assertEqual(self.scraper.resolve_region("Cholchol"), ("IX", "La Araucanía"))
        self.assertEqual(self.scraper.resolve_region("Calama"), ("II", "Antofagasta"))
        self.assertEqual(self.scraper.resolve_region("Los Ángeles"), ("VIII", "Biobío"))

    def test_accents_and_case_are_ignored(self):
        self.assertEqual(self.scraper.resolve_region("VALPARAISO")[0], "V")
        self.assertEqual(self.scraper.resolve_region("Requínoa")[0], "VI")

    def test_longest_commune_wins(self):
        self.assertEqual(self.scraper.resolve_region("Chillán Viejo")[0], "XVI")

    def test_unknown_place_is_not_defaulted_to_santiago(self):
        self.assertEqual(self.scraper.resolve_region("Trail Running"), (None, None))
        self.assertEqual(self.scraper.resolve_region("Ciclismo"), (None, None))

    def test_bare_roman_numerals_in_titles_are_ignored(self):
        self.assertEqual(self.scraper.resolve_region("III Ruta del los Indios"), (None, None))
        self.assertEqual(self.scraper.resolve_region("Región IV")[0], "IV")

    def test_fallback_text_is_used_when_place_is_unknown(self):
        self.assertEqual(self.scraper.resolve_region("Parque Metropolitano", "Copa Santiago")[0], "RM")


class FilterTests(unittest.TestCase):
    def test_foreign_places(self):
        self.assertTrue(BaseScraper.is_foreign("La Paz, Bolivia"))
        self.assertTrue(BaseScraper.is_foreign("Punta del Este, Uruguay"))
        self.assertFalse(BaseScraper.is_foreign("Puerto Varas"))

    def test_non_cycling_titles(self):
        self.assertTrue(BaseScraper.is_non_cycling("1° Desafío La Sepultura Trail Running"))
        self.assertTrue(BaseScraper.is_non_cycling("Desafío de los Canales Aguas Abiertas"))
        self.assertFalse(BaseScraper.is_non_cycling("Gran Fondo Matanzas 2026"))


class DateTests(unittest.TestCase):
    def test_infer_year_current_season(self):
        self.assertEqual(infer_year(10, 17, today=date(2026, 10, 13)), 2026)
        self.assertEqual(infer_year(11, 1, today=date(2026, 10, 13)), 2026)

    def test_infer_year_rolls_over_for_dates_far_in_the_past(self):
        self.assertEqual(infer_year(1, 15, today=date(2026, 10, 13)), 2027)

    def test_infer_year_recent_past_stays_in_year(self):
        self.assertEqual(infer_year(10, 4, today=date(2026, 10, 13)), 2026)

    def test_bicineta_date_fallback(self):
        scraper = BicinetaScraper()
        self.assertEqual(scraper._parse_date("2026-12-05T10:00:00", ""), "2026-12-05")
        self.assertIsNone(scraper._parse_date("", "sin fecha"))

    def test_bicineta_clean_url(self):
        self.assertEqual(BicinetaScraper._clean_url("httphttps://tickets.example.cl/x"), "https://tickets.example.cl/x")
        self.assertEqual(BicinetaScraper._clean_url("https://example.cl/?u=https://other.cl"), "https://example.cl/?u=https://other.cl")


class GucaParserTests(unittest.TestCase):
    CARD = """
    <div class="col-md-4"><a href="https://guca.cl/att_tickets/public/e/1/{slug}">ver</a>
      <p>{title}</p><p>{place}</p><p>{when}</p><p>Ciclismo MTB</p></div>
    """

    def parse(self, **kw):
        html = self.CARD.format(**kw)
        return GucaScraper().parse_html(BeautifulSoup(html, "html.parser"))

    def test_event_with_known_place_is_kept(self):
        events = self.parse(slug="gravel-cholchol", title="Desafío Gravel Cholchol", place="Cholchol", when="29-11-2026")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["region"], "IX")

    def test_event_with_unresolvable_place_is_kept_but_flagged(self):
        events = self.parse(slug="x", title="Desafío Misterio MTB", place="Lugar Desconocido", when="29-11-2026")
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]["location_unverified"])
        self.assertIsNone(events[0]["region"])

    def test_event_abroad_is_skipped(self):
        self.assertEqual(self.parse(slug="x", title="Desafío Gravel MTB Bolivia", place="La Paz, Bolivia", when="29-11-2026"), [])

    def test_non_cycling_event_is_skipped(self):
        self.assertEqual(self.parse(slug="x", title="Desafío La Sepultura Trail Running", place="Santiago", when="24-10-2026"), [])


class TicketSportParserTests(unittest.TestCase):
    CARD = """
    <a class="disc-2" href="/eventos/{slug}"><div class="item">
      <div class="datos"><div class="fecha"><p>{day}</p><p>{month}</p></div><div class="deporte"><p>{sport}</p></div></div>
      <div class="titulo"><p>{title}</p></div>
      <div class="lugar"><p>{place}</p></div>
      <div class="tags"><p>Gratis</p></div>
    </div></a>
    """

    def parse(self, **kw):
        defaults = dict(slug="demo", day="07", month="November 2026", sport="MTB", title="Rally MTB Lago Ranco", place="Lago Ranco")
        defaults.update(kw)
        return TicketSportScraper().parse_html(BeautifulSoup(self.CARD.format(**defaults), "html.parser"))

    def test_cycling_event_is_parsed(self):
        events = self.parse()
        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual((ev["date"], ev["region"], ev["commune"]), ("2026-11-07", "XIV", "Lago Ranco"))
        self.assertEqual(ev["url"], "https://ticketsport.cl/eventos/demo")
        self.assertEqual(ev["price_type"], "free")
        self.assertIsNone(ev["distance_min_km"])

    def test_running_and_unknown_sports_are_skipped(self):
        self.assertEqual(self.parse(sport="Trail Running", title="Trail Pucón"), [])
        self.assertEqual(self.parse(sport=".", title="Corremos por la Vida"), [])

    def test_invalid_date_is_skipped(self):
        self.assertEqual(self.parse(month="Smarch 2026"), [])


class MergeTests(unittest.TestCase):
    def test_title_tokens_ignore_generic_words_and_ordinals(self):
        self.assertEqual(title_tokens("1° Desafío Copa Chile Los Leones 2026"), {"leone"})

    def test_same_event_across_sources(self):
        a = make_event(id="a", name="AMT XCO #1 Temuco", region="IX", source="bicineta")
        b = make_event(id="b", name="AMT XCO SERIES 2026 - Temuco", region="IX", source="guca")
        self.assertTrue(is_same_event(a, b))

    def test_different_races_same_day_are_not_merged(self):
        a = make_event(id="a", name="Copa Chile MTB XCM #6", region="VI")
        b = make_event(id="b", name="Desafío Los Leones CRO #5", region="VI")
        self.assertFalse(is_same_event(a, b))

    def test_different_dates_or_regions_are_not_merged(self):
        a = make_event(id="a", name="Gran Fondo Sur")
        self.assertFalse(is_same_event(a, make_event(id="b", name="Gran Fondo Sur", date="2026-11-02")))
        self.assertFalse(is_same_event(a, make_event(id="c", name="Gran Fondo Sur", region="X")))

    def test_merge_adds_new_and_skips_duplicates(self):
        existing = [make_event(id="a", name="AMT XCO #1 Temuco", region="IX", source="bicineta")]
        scraped = [
            make_event(id="b", name="AMT XCO SERIES 2026 - Temuco", region="IX", source="guca", disciplines=["Ruta"]),
            make_event(id="c", name="Otra Carrera", region="V", source="guca"),
        ]
        merged, added, _ = merge_events(existing, scraped)
        self.assertEqual(added, 1)
        self.assertEqual({e["id"] for e in merged}, {"a", "c"})
        self.assertIn("Ruta", merged[0]["disciplines"])  # disciplines are combined

    def test_same_source_reschedule_updates_date(self):
        existing = [make_event(source="guca")]
        scraped = [make_event(source="guca", date="2026-11-15", end_date="2026-11-15")]
        merged, added, updated = merge_events(existing, scraped)
        self.assertEqual((added, updated), (0, 2))
        self.assertEqual(merged[0]["date"], "2026-11-15")

    def test_other_source_does_not_override_curated_date(self):
        existing = [make_event(source="organizer")]
        scraped = [make_event(source="guca", date="2026-11-15")]
        merged, _, _ = merge_events(existing, scraped)
        self.assertEqual(merged[0]["date"], "2026-11-01")


class ValidatorTests(unittest.TestCase):
    REGION_NAMES = {"RM": "Metropolitana", "IX": "La Araucanía"}

    def check(self, **overrides):
        return validate_event(0, make_event(**overrides), self.REGION_NAMES)

    def test_valid_event_passes(self):
        errors, _ = self.check()
        self.assertEqual(errors, [])

    def test_impossible_date_fails(self):
        errors, _ = self.check(date="2026-02-30", end_date="2026-02-30")
        self.assertTrue(any("fecha inválida" in e for e in errors))

    def test_end_before_start_fails(self):
        errors, _ = self.check(end_date="2026-10-01")
        self.assertTrue(any("anterior" in e for e in errors))

    def test_javascript_urls_are_rejected(self):
        errors, _ = self.check(url="javascript:alert(1)")
        self.assertTrue(any("'url'" in e for e in errors))

    def test_region_name_must_match_region(self):
        errors, _ = self.check(region_name="La Araucanía")
        self.assertTrue(any("region_name" in e for e in errors))

    def test_coordinates_outside_chile_fail(self):
        errors, _ = self.check(lat=48.85, lng=2.35)
        self.assertTrue(any("fuera de Chile" in e for e in errors))

    def test_null_distances_are_valid_but_nonsense_is_not(self):
        errors, _ = self.check(distance_min_km=None, distance_max_km=None)
        self.assertEqual(errors, [])
        errors, _ = self.check(distance_min_km=90, distance_max_km=45)
        self.assertTrue(any("mayor" in e for e in errors))
        errors, _ = self.check(distance_min_km="45 km")
        self.assertTrue(any("distance_min_km" in e for e in errors))

    def test_bad_slug_fails(self):
        errors, _ = self.check(id="Carrera Demo!")
        self.assertTrue(any("slug" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
