from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from src.models.bonus import BonusOffer, ScrapeResult
from src.notify.notifier import ConsoleNotifier
from src.scoring.engine import BonusScoringEngine
from src.auth.credentials import CredentialsStore
from src.scrapers.base import BaseScraper
from src.scrapers.bet365_scraper import Bet365Scraper
from src.scrapers.betway_scraper import BetwayScraper
from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.generic_promo_scraper import GenericPromoScraper
from src.scrapers.pagol_scraper import PagolScraper
from src.storage.db import make_store


class BonusPipeline:
    """
    Scrape → Parse → NLP Analysis → Score → Classify → Store → Notify
    """

    def __init__(
        self,
        store_path: str | Path = "data/bonuses.json",
        credentials_path: str | Path = "data/credentials.json",
        scrapers: Optional[dict[str, BaseScraper]] = None,
    ):
        self.scoring = BonusScoringEngine()
        # GAP 4: Postgres when BETBONUS_DATABASE_URL is set, JSON otherwise.
        self.store = make_store(store_path)
        self.credentials = CredentialsStore(credentials_path)
        self.notifier = ConsoleNotifier()
        pagol = PagolScraper(delay=0.2)
        fourplay_br = FourPlayBrScraper(delay=0.2)
        self.scrapers = scrapers or {
            "bet365": Bet365Scraper(delay=0),
            "betway": BetwayScraper(delay=0),
            "888": GenericPromoScraper(platform="888", delay=0),
            "4play": FourPlayScraper(delay=0.3),
            "4play_bet_br": fourplay_br,
            "pagol_bet_br": pagol,
            "pagol": pagol,
            "generic": GenericPromoScraper(platform="generic", delay=0),
        }
        self._hydrate_tokens()

    def _hydrate_tokens(self) -> None:
        fp = self.scrapers.get("4play")
        token_4play = self.credentials.get_token("4play")
        if token_4play and isinstance(fp, FourPlayScraper):
            fp.set_token(token_4play)

        br = self.scrapers.get("4play_bet_br")
        if isinstance(br, FourPlayBrScraper):
            br.set_token(
                self.credentials.get_token("4play_bet_br"),
                self.credentials.get_refresh_token("4play_bet_br"),
            )

        pagol_token = (
            self.credentials.get_token("pagol_bet_br")
            or self.credentials.get_token("pagol")
        )
        for key in ("pagol_bet_br", "pagol"):
            scraper = self.scrapers.get(key)
            if pagol_token and isinstance(scraper, PagolScraper):
                scraper.set_token(pagol_token)

    def process_offers(self, offers: Iterable[BonusOffer], notify: bool = True) -> list[BonusOffer]:
        scored = self.scoring.score_many(list(offers))
        self.store.upsert(scored)
        if notify:
            self.notifier.notify(scored)
        return scored

    def run_html(self, platform: str, html: str, source_url: str = "fixture://local") -> list[BonusOffer]:
        scraper = self.scrapers.get(platform) or self.scrapers["generic"]
        if platform not in self.scrapers:
            scraper = GenericPromoScraper(platform=platform, delay=0)
        result = scraper.scrape_html(html, source_url=source_url)
        return self.process_offers(result.offers)

    def run_file(self, platform: str, path: str | Path) -> list[BonusOffer]:
        scraper = self.scrapers.get(platform) or GenericPromoScraper(platform=platform, delay=0)
        result = scraper.scrape_file(path)
        return self.process_offers(result.offers)

    def run_url(self, platform: str, url: str, delay: float = 2.0) -> ScrapeResult:
        scraper = self.scrapers.get(platform) or GenericPromoScraper(platform=platform, delay=delay)
        scraper.delay = delay
        result = scraper.scrape_url(url)
        if result.ok and result.offers:
            self.process_offers(result.offers)
        return result

    def run_live_platform(self, platform: str) -> ScrapeResult:
        """Run platform-native live scrape (API scrapers like 4play/pagol)."""
        self._hydrate_tokens()
        key = "pagol_bet_br" if platform in {"pagol", "pagol_bet_br"} else platform
        scraper = self.scrapers.get(key) or self.scrapers.get(platform)
        if scraper is None:
            return ScrapeResult(
                platform=platform,
                source_url="",
                offers=[],
                ok=False,
                error=f"Unknown platform: {platform}",
            )
        if hasattr(scraper, "scrape_live"):
            result = scraper.scrape_live()  # type: ignore[attr-defined]
        else:
            result = scraper.scrape_url("")
        if result.ok and result.offers:
            self.process_offers(result.offers)
        # Keep ok=True even with 0 offers when live API succeeded (notes in error field)
        return result
