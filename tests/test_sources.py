"""
Tests for source coverage: Bicineta feed, GUCA detail pages, Ridechile table,
unconfirmed locations and cross-source merging.
Run from the project root:  python -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from datetime import date

from bs4 import BeautifulSoup

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from scrapers.base_scraper import BaseScraper, parse_distances  # noqa: E402
from scrapers.bicineta_scraper import BicinetaScraper  # noqa: E402
from scrapers.guca_scraper import GucaScraper  # noqa: E402
from scrapers.ridechile_scraper import RidechileScraper  # noqa: E402
from sync_events import assign_coordinates, dedupe_existing, enrich_match, is_same_event, merge_events, url_key  # noqa: E402
from validate_events import validate_event  # noqa: E402
from test_pipeline import make_event  # noqa: E402


class BuildEventTests(unittest.TestCase):
    def setUp(self):
        self.scraper = BaseScraper("demo")

    def test_located_event_gets_region_and_location(self):
        ev = self.scraper.build_event(title="Gran Fondo Demo", date="2026-11-01", place="Pucón", region_code="IX")
        self.assertEqual((ev["region"], ev["region_name"], ev["commune"]), ("IX", "La Araucanía", "Pucón"))
        self.assertEqual(ev["location"], "Pucón, Región La Araucanía")
        self.assertNotIn("location_unverified", ev)

    def test_unlocated_event_is_flagged_and_has_no_region(self):
        ev = self.scraper.build_event(title="Carrera Demo", date="2026-11-01", place="", region_code=None)
        self.assertTrue(ev["location_unverified"])
        self.assertIsNone(ev["region"])
        self.assertEqual(ev["location"], "Ubicación por confirmar")

    def test_placeholder_places_are_treated_as_unknown(self):
        ev = self.scraper.build_event(title="Carrera Demo", date="2026-11-01", place="Pronto más info", region_code="V")
        self.assertEqual(ev["commune"], "Valparaíso")  # falls back to the region name
        self.assertEqual(ev["location"], "Valparaíso, Región Valparaíso")

    def test_locate_decisions(self):
        self.assertEqual(self.scraper.locate("Cholchol")[2], True)
        self.assertEqual(self.scraper.locate("Cusco, Perú"), (None, None, False))
        self.assertEqual(self.scraper.locate("Lugar Misterioso"), (None, None, True))
        self.assertEqual(self.scraper.locate("", "Desafío Bolivia MTB"), (None, None, False))

    def test_parse_distances(self):
        self.assertEqual(parse_distances(["120K y 60K"]), (["120 km", "60 km"], 60.0, 120.0))
        self.assertEqual(parse_distances(["7.5K, 400m"]), (["7.5 km"], 7.5, 7.5))
        self.assertEqual(parse_distances(["Ver bases"]), (None, None, None))
        self.assertEqual(parse_distances(None), (None, None, None))


class BicinetaFeedTests(unittest.TestCase):
    def feed(self, *pairs):
        return [{"start_at": s, "end_at": e} for s, e in pairs]

    def test_years_follow_the_chronological_order_of_the_feed(self):
        items = self.feed(("09 de octubre", None), ("24 de octubre", "25 de octubre"), ("20 de diciembre", None),
                          ("10 de enero", None), ("22 de agosto", None))
        BicinetaScraper._assign_dates(items, today=date(2026, 10, 13))
        self.assertEqual([i["_start"] for i in items],
                         ["2026-10-09", "2026-10-24", "2026-12-20", "2027-01-10", "2027-08-22"])
        self.assertEqual(items[1]["_end"], "2026-10-25")

    def test_first_item_far_in_the_past_means_next_year(self):
        items = self.feed(("10 de abril", None))
        BicinetaScraper._assign_dates(items, today=date(2026, 10, 13))
        self.assertEqual(items[0]["_start"], "2027-04-10")

    def test_range_crossing_new_year_and_time_suffix(self):
        items = self.feed(("30 de diciembre", "02 de enero"), ("24 de enero 09:00", None))
        BicinetaScraper._assign_dates(items, today=date(2026, 10, 13))
        self.assertEqual((items[0]["_start"], items[0]["_end"]), ("2026-12-30", "2027-01-02"))
        self.assertEqual(items[1]["_start"], "2027-01-24")

    def item(self, **kw):
        base = {"id": 1, "title": "Gran Fondo Demo", "area": "IX", "place": "Pucón", "start_at": "01 de noviembre",
                "end_at": None, "description": "Una carrera.\r\n", "organization": "Club", "external_url": "https://demo.cl/x",
                "tags": "competencias,ruta,gravel", "_start": "2026-11-01", "_end": "2026-11-01"}
        base.update(kw)
        return base

    def test_item_becomes_event_with_tag_disciplines(self):
        ev = BicinetaScraper()._feed_item_to_event(self.item())
        self.assertEqual(ev["disciplines"], ["Ruta", "Gravel"])
        self.assertEqual((ev["date"], ev["region"], ev["source"]), ("2026-11-01", "IX", "bicineta"))

    def test_known_commune_beats_organizer_area(self):
        ev = BicinetaScraper()._feed_item_to_event(self.item(area="IX", place="Lebu"))
        self.assertEqual(ev["region"], "VIII")

    def test_foreign_and_running_items_are_dropped(self):
        scraper = BicinetaScraper()
        self.assertIsNone(scraper._feed_item_to_event(self.item(area=None, place="La Paz, Bolivia")))
        self.assertIsNone(scraper._feed_item_to_event(self.item(title="Trail Running Pucón")))

    def test_unknown_place_without_area_is_kept_unverified(self):
        ev = BicinetaScraper()._feed_item_to_event(self.item(area=None, place="Lugar Misterioso"))
        self.assertTrue(ev["location_unverified"])

    def test_image_as_link_falls_back_to_a_real_url(self):
        ev = BicinetaScraper()._feed_item_to_event(self.item(external_url="data:image/png;base64,AAAA"))
        self.assertTrue(ev["url"].startswith("https://"))


class GucaDetailTests(unittest.TestCase):
    PAGE = """
    <html><body><h1>Desafío Pumanque</h1>
    <div class="event_organizer">GUCA Club Pumanque Presenta Desafío Pumanque</div>
    <div class="event_venue">domingo, 15 de noviembre de 2026 09:00 - 14:00 @ Pumanque TICKETS DETALLES</div>
    <div class="event_details">Carrera de ciclismo de ruta por caminos rurales.</div></body></html>
    """

    def parse(self, html=None, card="Ciclismo | Crono"):
        return GucaScraper().parse_detail(BeautifulSoup(html or self.PAGE, "html.parser"), "https://guca.cl/att_tickets/public/e/9/x", card)

    def test_detail_page_gives_real_place_date_and_organizer(self):
        ev = self.parse()
        self.assertEqual((ev["date"], ev["region"], ev["commune"]), ("2026-11-15", "VI", "Pumanque"))
        self.assertEqual(ev["organizer"], "Club Pumanque")

    def test_multi_day_range(self):
        html = self.PAGE.replace("domingo, 15 de noviembre de 2026 09:00 - 14:00", "viernes, 20 de noviembre de 2026 - domingo, 22 de noviembre de 2026")
        ev = self.parse(html)
        self.assertEqual((ev["date"], ev["end_date"]), ("2026-11-20", "2026-11-22"))

    def test_running_event_on_detail_page_is_skipped(self):
        html = self.PAGE.replace("Desafío Pumanque</h1>", "Trail Running Pumanque</h1>")
        self.assertIsNone(self.parse(html, card="Trail Running"))

    def test_unlabelled_non_bike_event_is_skipped(self):
        html = self.PAGE.replace("Carrera de ciclismo de ruta", "Corrida familiar").replace("Desafío Pumanque</h1>", "Corrida Pumanque</h1>")
        self.assertIsNone(self.parse(html, card="Corrida"))

    def test_unknown_venue_keeps_event_unverified(self):
        ev = self.parse(self.PAGE.replace("@ Pumanque", "@ Lugar Misterioso").replace("Desafío Pumanque", "Desafío Misterio MTB"))
        self.assertTrue(ev["location_unverified"])


class RidechileTests(unittest.TestCase):
    def test_date_cells(self):
        parse = RidechileScraper.parse_date_cell
        self.assertEqual(parse("03/10/2026"), ("2026-10-03", "2026-10-03"))
        self.assertEqual(parse("24 y 25/10/2026"), ("2026-10-24", "2026-10-25"))
        self.assertEqual(parse("22 al 27/11/2026"), ("2026-11-22", "2026-11-27"))
        self.assertEqual(parse("06, 07 y 08/11/2026"), ("2026-11-06", "2026-11-08"))
        self.assertEqual(parse("REPROGRAMADO"), (None, None))
        self.assertEqual(parse("2027"), (None, None))
        self.assertEqual(parse("32/13/2026"), (None, None))

    TABLE = """
    <table>
      <tr><th>FECHA</th><th>EVENTO</th><th>LUGAR</th><th>MODALIDAD</th><th>DISTANCIA(S)</th><th>ORGANIZA</th><th>INSCRIPCIONES</th><th>BASES</th></tr>
      <tr><td>10/10/2026</td><td>Gravel del Cobre</td><td>Machalí, región de O’Higgins</td><td>Gravel</td><td>90K y 60K</td><td>Iloca MTB</td><td><a href="https://insc.cl/cobre">AQUÍ</a></td><td>AQUÍ</td></tr>
      <tr><td>REPROGRAMADO</td><td>UCI World Series</td><td>Lago Ranco</td><td>Gravel</td><td>120K</td><td>X</td><td>AQUÍ</td><td>AQUÍ</td></tr>
      <tr><td>08 al 14/03/2027</td><td>Campeonato Panamericano de MTB XCO</td><td>Por confirmar</td><td>MTB</td><td></td><td>Fedenacich</td><td>PRONTO</td><td>PRONTO</td></tr>
      <tr><td>05/12/2026</td><td>Death Road</td><td>La Paz, Bolivia</td><td>Gravel</td><td>60K</td><td>X</td><td>PRONTO</td><td>PRONTO</td></tr>
    </table>
    """

    def test_table_rows(self):
        events = RidechileScraper().parse_html(BeautifulSoup(self.TABLE, "html.parser"))
        by_name = {e["name"]: e for e in events}
        self.assertEqual(set(by_name), {"Gravel del Cobre", "Campeonato Panamericano de MTB XCO"})

        cobre = by_name["Gravel del Cobre"]
        self.assertEqual((cobre["region"], cobre["distances"], cobre["registration_url"]), ("VI", ["90 km", "60 km"], "https://insc.cl/cobre"))

        pan = by_name["Campeonato Panamericano de MTB XCO"]
        self.assertTrue(pan["location_unverified"])
        self.assertEqual((pan["date"], pan["end_date"]), ("2027-03-08", "2027-03-14"))


class MergeCoverageTests(unittest.TestCase):
    def test_url_key_ignores_generic_links_and_tracking(self):
        self.assertIsNone(url_key("https://www.instagram.com/copachilexco/"))
        self.assertIsNone(url_key("https://www.bicineta.cl/eventos"))
        self.assertEqual(url_key("https://www.instagram.com/p/ABC123/"), "instagram.com/p/abc123")
        self.assertEqual(url_key("https://welcu.com/club/x?utm_source=directory"), url_key("https://welcu.com/club/x"))

    def test_same_link_same_day_merges_races_with_different_titles(self):
        link = "https://guca.cl/att_tickets/public/e/821/vuelta-master"
        existing = [make_event(id="a", name="Fecha 2 Gran Premio", source="ridechile", url=link, registration_url=link)]
        scraped = [make_event(id="b", name="Ruta Costa Oficial", source="guca", url=link, registration_url=link)]
        merged, added, _ = merge_events(existing, scraped)
        self.assertEqual((added, len(merged)), (0, 1))

    def test_same_link_on_another_day_is_a_different_edition(self):
        link = "https://organizador.cl/odisea"
        existing = [make_event(id="a", name="Odisea Uno", source="bicineta", url=link, registration_url=link, date="2027-01-06")]
        scraped = [make_event(id="b", name="Odisea Dos", source="bicineta", url=link, registration_url=link, date="2027-02-10")]
        merged, added, _ = merge_events(existing, scraped)
        self.assertEqual((added, len(merged)), (1, 2))

    def test_same_id_reschedule_updates_the_date(self):
        existing = [make_event(id="a", source="guca", date="2026-11-21", end_date="2026-11-21")]
        scraped = [make_event(id="a", source="guca", date="2026-11-28", end_date="2026-11-28")]
        merged, added, _ = merge_events(existing, scraped)
        self.assertEqual((added, merged[0]["date"]), (0, "2026-11-28"))

    def test_single_distinctive_word_matches_only_in_the_same_place(self):
        a = make_event(id="a", name="La Minga", commune="Puerto Varas", region="X", source="bicineta")
        b = make_event(id="b", name="La Minga Gravel Experience", commune="Puerto Varas", region="X", source="ridechile")
        c = make_event(id="c", name="La Minga Gravel Experience", commune="Frutillar", region="X", source="ridechile")
        self.assertTrue(is_same_event(a, b))
        self.assertFalse(is_same_event(a, c))

    def test_single_weak_word_never_matches(self):
        a = make_event(id="a", name="Copa XCO Temuco", commune="Temuco", region="IX")
        b = make_event(id="b", name="Campeonato XCO Amateur", commune="Temuco", region="IX")
        self.assertFalse(is_same_event(a, b))

    def test_unconfirmed_location_matches_overlapping_dates(self):
        a = make_event(id="a", name="Campeonato Panamericano de MTB XCO", date="2027-03-08", end_date="2027-03-14",
                       region=None, location_unverified=True, source="ridechile")
        b = make_event(id="b", name="Campeonato Panamericano MTB", date="2027-03-11", end_date="2027-03-14",
                       region="XIV", source="bicineta")
        self.assertTrue(is_same_event(a, b))
        # but located events on different start days are different races
        self.assertFalse(is_same_event(make_event(id="c", name="Gran Premio Sur", date="2027-03-08"),
                                       make_event(id="d", name="Gran Premio Sur", date="2027-03-11")))

    def test_dedupe_existing_folds_duplicates_keeping_the_older_entry(self):
        a = make_event(id="a", name="La Minga", commune="Puerto Varas", region="X", source="bicineta", distances=["Ver bases"])
        b = make_event(id="b", name="La Minga Gravel Experience", commune="Puerto Varas", region="X", source="ridechile",
                       distances=["240 km", "60 km"], distance_min_km=60.0, distance_max_km=240.0, disciplines=["Gravel"])
        kept, removed = dedupe_existing([a, b])
        self.assertEqual((removed, len(kept)), (1, 1))
        self.assertEqual(kept[0]["id"], "a")
        self.assertEqual(kept[0]["distances"], ["240 km", "60 km"])
        self.assertIn("Gravel", kept[0]["disciplines"])

    def test_races_of_a_series_sharing_a_social_post_stay_separate(self):
        post = "https://www.instagram.com/p/DWRbK8mEWEa/"
        existing = [make_event(id="amt-1", name="AMT XCO #1 Temuco", source="bicineta", url=post, registration_url=post,
                               date="2026-10-18", end_date="2026-10-18")]
        scraped = [make_event(id="amt-2", name="AMT XCO #2 Angol", source="bicineta", url=post, registration_url=post,
                              date="2026-11-08", end_date="2026-11-08", region="IX")]
        merged, added, _ = merge_events(existing, scraped)
        self.assertEqual((added, len(merged)), (1, 2))
        self.assertEqual({e["date"] for e in merged}, {"2026-10-18", "2026-11-08"})

    def test_mountain_bike_and_mtb_are_the_same_title(self):
        a = make_event(id="a", name="MTB Tour fecha 6", region=None, location_unverified=True, source="ridechile")
        b = make_event(id="b", name="Mountain Bike Tour #6", region="VI", source="bicineta")
        merged, added, updated = merge_events([a], [b])
        self.assertEqual(added, 0)
        self.assertEqual(merged[0]["region"], "VI")  # the unconfirmed location was upgraded
        self.assertNotIn("location_unverified", merged[0])
        self.assertGreaterEqual(updated, 1)

    def test_past_race_is_not_overwritten_by_next_edition_with_same_title(self):
        old = make_event(id="tour-dh-5-2026", name="Tour DH #5", date="2026-01-10", end_date="2026-01-11", source="bicineta")
        new = make_event(id="tour-dh-5-2026", name="Tour DH #5", date="2099-12-19", end_date="2099-12-19", source="bicineta")
        merged, added, _ = merge_events([old], [new])
        self.assertEqual(added, 1)
        self.assertEqual({e["date"] for e in merged}, {"2026-01-10", "2099-12-19"})
        self.assertEqual(len({e["id"] for e in merged}), 2)

    def test_distances_are_enriched_from_another_source(self):
        match = make_event(distances=["Ver bases"], distance_min_km=None, distance_max_km=None)
        new = make_event(distances=["90 km", "60 km"], distance_min_km=60.0, distance_max_km=90.0)
        self.assertEqual(enrich_match(match, new), 1)
        self.assertEqual((match["distances"], match["distance_max_km"]), (["90 km", "60 km"], 90.0))
        # real distances are never replaced
        self.assertEqual(enrich_match(match, make_event(distances=["10 km"])), 0)

    def test_unlocated_events_get_no_coordinates(self):
        ev = make_event(region=None, region_name=None, commune=None, location_unverified=True)
        ev.pop("lat"); ev.pop("lng")
        assign_coordinates([ev])
        self.assertNotIn("lat", ev)


class ValidatorUnverifiedTests(unittest.TestCase):
    REGION_NAMES = {"RM": "Metropolitana"}

    def test_unverified_event_may_lack_region(self):
        ev = make_event(region=None, region_name=None, location_unverified=True)
        ev.pop("lat"); ev.pop("lng")
        errors, _ = validate_event(0, ev, self.REGION_NAMES)
        self.assertEqual(errors, [])

    def test_missing_region_without_flag_is_an_error(self):
        ev = make_event(region=None, region_name=None)
        ev.pop("lat"); ev.pop("lng")
        errors, _ = validate_event(0, ev, self.REGION_NAMES)
        self.assertTrue(any("region" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
