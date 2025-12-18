from .creek_cave import CreekCaveScraper
from .mothership import MothershipScraper
from .velveeta import VelveetaScraper
from .sunset_strip import SunsetStripScraper
from .east_austin import EastAustinScraper
from .rozcos import RozcosScraper
from .vulcan import VulcanScraper

SCRAPERS = {
    "creek_cave": CreekCaveScraper,
    "mothership": MothershipScraper,
    "velveeta": VelveetaScraper,
    "sunset_strip": SunsetStripScraper,
    "east_austin": EastAustinScraper,
    "rozcos": RozcosScraper,
    "vulcan": VulcanScraper,
}

__all__ = [
    "CreekCaveScraper",
    "MothershipScraper",
    "VelveetaScraper",
    "SunsetStripScraper",
    "EastAustinScraper",
    "RozcosScraper",
    "VulcanScraper",
    "SCRAPERS",
]
