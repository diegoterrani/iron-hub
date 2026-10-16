from .base import BaseScraper
from .bet365_scraper import Bet365Scraper
from .betway_scraper import BetwayScraper
from .eighteighteight_scraper import EightEightEightScraper
from .fourplay_br_scraper import FourPlayBrScraper
from .fourplay_scraper import FourPlayScraper
from .generic_promo_scraper import GenericPromoScraper
from .pagol_scraper import PagolScraper
from .registry import ScraperRegistry, ScraperSpec

__all__ = [
    "BaseScraper",
    "Bet365Scraper",
    "BetwayScraper",
    "EightEightEightScraper",
    "FourPlayBrScraper",
    "FourPlayScraper",
    "GenericPromoScraper",
    "PagolScraper",
    "ScraperRegistry",
    "ScraperSpec",
]
