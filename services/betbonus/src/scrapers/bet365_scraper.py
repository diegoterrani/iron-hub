from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup

from src.models.bonus import BonusOffer, ScrapeResult
from src.scrapers.generic_promo_scraper import GenericPromoScraper


class Bet365Scraper(GenericPromoScraper):
    """
    Bet365-oriented scraper.

    Live pages are heavily JS/anti-bot protected. Prefer fixtures or authorized
    HTML dumps during development; live URL scraping is best-effort only.
    """

    platform = "bet365"
    default_delay = 3.0

    def scrape_promo_page(self, url: str, delay: Optional[float] = None) -> Optional[BonusOffer]:
        if delay is not None:
            previous = self.delay
            self.delay = delay
            try:
                result = self.scrape_url(url)
            finally:
                self.delay = previous
        else:
            result = self.scrape_url(url)

        if result.offers:
            return result.offers[0]
        return None

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        offers = super().extract_offers(soup, source_url=source_url)
        for offer in offers:
            offer.platform = "bet365"
        return offers


def scrape_result_from_fixture(path: str) -> ScrapeResult:
    return Bet365Scraper(delay=0).scrape_file(path, source_url="fixture://bet365")
