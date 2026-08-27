from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from src.models.bonus import BonusOffer
from src.nlp.analyzer import BonusNLPAnalyzer
from src.scrapers.base import BaseScraper


PROMO_SELECTORS = [
    "div.promo-card",
    "div.offer-box",
    "li.promo-item",
    "section.promotion",
    "article.promo",
    "div[class*='promo']",
    "div[class*='offer']",
]


class GenericPromoScraper(BaseScraper):
    """Selector-tolerant promo page scraper for smaller bookmakers / fixtures."""

    platform = "generic"

    def __init__(self, platform: str = "generic", **kwargs):
        super().__init__(**kwargs)
        self.platform = platform
        self.nlp = BonusNLPAnalyzer()

    def _candidate_elements(self, soup: BeautifulSoup) -> list[Tag]:
        seen: set[int] = set()
        hits: list[Tag] = []

        for selector in PROMO_SELECTORS:
            for el in soup.select(selector):
                if not isinstance(el, Tag):
                    continue
                marker = id(el)
                if marker in seen:
                    continue
                # Skip containers that clearly wrap multiple promo children
                child_promos = el.select("div.promo-card, div.offer-box, li.promo-item, section.promotion, article.promo")
                if len(child_promos) > 1:
                    continue
                seen.add(marker)
                hits.append(el)

        if hits:
            return hits

        # Fallback: blocks with bonus-like keywords
        for el in soup.find_all(["div", "article", "li", "section"]):
            if not isinstance(el, Tag):
                continue
            text = el.get_text(" ", strip=True).lower()
            if any(k in text for k in ("bonus", "free spins", "cashback", "wagering", "deposit")):
                if 40 <= len(text) <= 1200:
                    hits.append(el)
        return hits[:20]

    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        offers: list[BonusOffer] = []
        for elem in self._candidate_elements(soup):
            title_el = elem.find(["h1", "h2", "h3", "h4", "strong"])
            title = title_el.get_text(" ", strip=True) if title_el else ""
            text = elem.get_text(" ", strip=True)
            fields = self.nlp.analyze(text)
            link = elem.find("a", href=True)
            terms_url = ""
            if link and link.get("href"):
                terms_url = str(link["href"])

            offers.append(
                BonusOffer(
                    platform=self.platform,
                    bonus_type=fields.bonus_type,
                    title=title or text[:80],
                    amount=fields.amount,
                    currency=fields.currency,
                    match_percent=fields.match_percent,
                    free_spins=fields.free_spins,
                    wagering_multiple=fields.wagering_multiple,
                    min_deposit=fields.min_deposit,
                    max_bet_during_bonus=fields.max_bet_during_bonus,
                    expiry_days=fields.expiry_days,
                    expiry_hours=fields.expiry_hours,
                    game_restrictions=fields.game_restrictions,
                    terms_url=terms_url,
                    source_url=source_url,
                    raw_text=text,
                )
            )
        return offers
