"""Betway Brazil scraper — 3rd house validation target.

Betway (betway.com.br) is a major Brazilian iGaming operator (sports + casino).
This scraper extends GenericPromoScraper with Betway-specific selectors and
bonus page patterns. Live pages are JS-heavy, so fixture-based validation is
the primary test path.
"""

from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup, Tag

from src.models.bonus import BonusOffer, ScrapeResult
from src.scrapers.generic_promo_scraper import GenericPromoScraper


class BetwayScraper(GenericPromoScraper):
    """
    Betway Brazil (betway.com.br) promo scraper.

    Betway uses a Next.js frontend with SSR-rendered promo cards.
    Selectors target their common promo/offer card patterns.
    """

    platform = "betway"
    default_delay = 2.5

    def __init__(self, **kwargs):
        kwargs.setdefault("platform", "betway")
        super().__init__(**kwargs)

    BETWAY_SELECTORS = [
        "div[data-testid='promo-card']",
        "div.promo-tile",
        "div[class*='PromoCard']",
        "div[class*='promo-card']",
        "div[class*='offer-tile']",
        "section[class*='promotion']",
        "div.betway-promo",
        "article[data-cy='offer']",
    ]

    def _candidate_elements(self, soup: BeautifulSoup) -> list[Tag]:
        """Find Betway promo elements with fallback to generic selectors."""
        seen: set[int] = set()
        hits: list[Tag] = []

        # Try Betway-specific selectors first
        for selector in self.BETWAY_SELECTORS:
            for el in soup.select(selector):
                if not isinstance(el, Tag):
                    continue
                marker = id(el)
                if marker in seen:
                    continue
                hits.append(el)
                seen.add(marker)

        if hits:
            return hits

        # Fall back to generic promo selectors
        return super()._candidate_elements(soup)

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        offers = super().extract_offers(soup, source_url=source_url)
        # Tag all offers as Betway
        for offer in offers:
            offer.platform = "betway"
        return offers

    def scrape_promo_page(self, url: str, delay: Optional[float] = None) -> Optional[BonusOffer]:
        """Scrape a single promo page and return the first offer found."""
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


def scrape_result_from_fixture(path: str) -> ScrapeResult:
    """Load a Betway HTML fixture file and extract offers."""
    return BetwayScraper(delay=0).scrape_file(path, source_url="fixture://betway")
