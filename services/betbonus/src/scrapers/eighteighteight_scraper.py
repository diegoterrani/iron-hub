"""888 Brazil (888.com.br) promo scraper — dedicated adapter.

Extends GenericPromoScraper with 888-specific promo card selectors.
Live pages are JS-heavy; Playwright rendering is available via the base
scraper's ``render_js`` support for JS-rendered promo listings.
"""

from __future__ import annotations

from typing import Optional

from bs4 import BeautifulSoup, Tag

from src.models.bonus import BonusOffer, ScrapeResult
from src.scrapers.generic_promo_scraper import GenericPromoScraper


class EightEightEightScraper(GenericPromoScraper):
    """
    888 Brazil (888.com.br) promo scraper.

    888 renders promo tiles with class names in the ``promo``/``offer``
    family. Selectors below cover the observed patterns; the generic
    keyword fallback still applies when none match.
    """

    platform = "888"
    default_delay = 2.5

    def __init__(self, **kwargs):
        kwargs.setdefault("platform", "888")
        super().__init__(**kwargs)

    EIGHT888_SELECTORS = [
        "div[data-testid='promo-card']",
        "div[class*='promo-card']",
        "div[class*='PromoCard']",
        "div[class*='offer-tile']",
        "div[class*='PromoTile']",
        "div[class*='banner-promo']",
        "article[class*='promotion']",
        "section[class*='promotion']",
        "div[class*='888-promo']",
    ]

    def _candidate_elements(self, soup: BeautifulSoup) -> list[Tag]:
        """Find 888 promo elements with fallback to generic selectors."""
        seen: set[int] = set()
        hits: list[Tag] = []
        for selector in self.EIGHT888_SELECTORS:
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
        return super()._candidate_elements(soup)

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        offers = super().extract_offers(soup, source_url=source_url)
        for offer in offers:
            offer.platform = "888"
        return offers

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


def scrape_result_from_fixture(path: str) -> ScrapeResult:
    """Load an 888 HTML fixture file and extract offers."""
    return EightEightEightScraper(delay=0).scrape_file(path, source_url="fixture://888")
