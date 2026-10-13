# Pedaleo.cl Scrapers Module
from .bicineta_scraper import BicinetaScraper
from .ciclismochile_scraper import CiclismoChileScraper
from .guca_scraper import GucaScraper
from .ridechile_scraper import RidechileScraper
from .ticketsport_scraper import TicketSportScraper
from .tusdesafios_scraper import TusdesafiosScraper

__all__ = [
    "BicinetaScraper", "CiclismoChileScraper", "GucaScraper",
    "RidechileScraper", "TicketSportScraper", "TusdesafiosScraper",
]
