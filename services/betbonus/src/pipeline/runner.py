from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable, Optional

from src.models.bonus import BonusOffer, ScrapeResult
from src.notify.notifier import ConsoleNotifier
from src.scoring.engine import BonusScoringEngine
from src.auth.credentials import CredentialsStore
from src.scrapers.base import BaseScraper
from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.pagol_scraper import PagolScraper
from src.scrapers.registry import ScraperRegistry
from src.storage.db import make_store

log = logging.getLogger("betbonus.pipeline")


class BonusPipeline:
    """
    Scrape → Parse → NLP Analysis → Score → Classify → Store → Notify
    """

    def __init__(
        self,
        store_path: str | Path = "data/bonuses.json",
        credentials_path: str | Path = "data/credentials.json",
        scrapers: Optional[dict[str, BaseScraper]] = None,
        registry: Optional[ScraperRegistry] = None,
        registry_config: Optional[str | Path] = None,
    ):
        self.scoring = BonusScoringEngine()
        # GAP 4: Postgres when BETBONUS_DATABASE_URL is set, JSON otherwise.
        self.store = make_store(store_path)
        self.credentials = CredentialsStore(credentials_path)
        self.notifier = ConsoleNotifier()
        self.registry = registry or ScraperRegistry(registry_config)
        self.scrapers: dict[str, BaseScraper] = {}
        if scrapers is not None:
            self.scrapers = dict(scrapers)
        else:
            for platform in self.registry.platforms():
                self.scrapers[platform] = self.registry.build(platform)
        self._hydrate_tokens()

    # ------------------------------------------------------------------
    # Token hydration (API scrapers)
    # ------------------------------------------------------------------

    def _hydrate_tokens(self) -> None:
        for key, scraper in list(self.scrapers.items()):
            if isinstance(scraper, FourPlayScraper):
                token = self.credentials.get_token("4play")
                if token:
                    scraper.set_token(token)
            elif isinstance(scraper, FourPlayBrScraper):
                scraper.set_token(
                    self.credentials.get_token("4play_bet_br"),
                    self.credentials.get_refresh_token("4play_bet_br"),
                )
            elif isinstance(scraper, PagolScraper):
                token = (
                    self.credentials.get_token("pagol_bet_br")
                    or self.credentials.get_token("pagol")
                )
                if token:
                    scraper.set_token(token)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_offers(self, offers: Iterable[BonusOffer], notify: bool = True) -> list[BonusOffer]:
        scored = self.scoring.score_many(list(offers))
        self.store.upsert(scored)
        if notify:
            self.notifier.notify(scored)
        return scored

    def _scraper_for(self, platform: str) -> BaseScraper:
        """Resolve a platform (or alias) to a scraper instance."""
        canonical = self.registry.normalize(platform)
        scraper = self.scrapers.get(canonical)
        if scraper is None:
            scraper = self.registry.build(canonical)
            self.scrapers[canonical] = scraper
        return scraper

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_html(self, platform: str, html: str, source_url: str = "fixture://local") -> list[BonusOffer]:
        scraper = self._scraper_for(platform)
        result = scraper.scrape_html(html, source_url=source_url)
        return self.process_offers(result.offers)

    def run_file(self, platform: str, path: str | Path) -> list[BonusOffer]:
        scraper = self._scraper_for(platform)
        result = scraper.scrape_file(path)
        return self.process_offers(result.offers)

    def run_url(self, platform: str, url: str, delay: float = 2.0, render_js: bool = False) -> ScrapeResult:
        scraper = self._scraper_for(platform)
        scraper.delay = delay
        result = scraper.scrape_url(url, render_js=render_js)
        if result.ok and result.offers:
            self.process_offers(result.offers)
        return result

    def run_many(
        self,
        targets: Iterable[dict[str, Any]],
        max_workers: int = 4,
    ) -> list[ScrapeResult]:
        """Concurrent batch scrape.

        Each target is a dict with:
          - ``platform`` (required)
          - ``url`` (for HTML mode) or ``mode`` ("url" | "html" | "file" | "live")
          - ``html`` / ``path`` / ``delay`` / ``render_js`` as applicable

        Returns one ScrapeResult per target (ok=False + error for failures).
        """
        def _run_one(target: dict[str, Any]) -> ScrapeResult:
            platform = str(target.get("platform") or "")
            mode = str(target.get("mode") or "auto")
            if mode == "auto":
                if self.registry.is_api(platform):
                    mode = "live"
                elif target.get("html"):
                    mode = "html"
                elif target.get("path"):
                    mode = "file"
                else:
                    mode = "url"
            try:
                if mode == "html":
                    html = str(target.get("html") or "")
                    offers = self.run_html(platform, html, source_url=str(target.get("source_url") or ""))
                    return ScrapeResult(
                        platform=self.registry.normalize(platform),
                        source_url=str(target.get("source_url") or ""),
                        offers=offers,
                        ok=True,
                    )
                if mode == "file":
                    offers = self.run_file(platform, target.get("path") or "")
                    return ScrapeResult(
                        platform=self.registry.normalize(platform),
                        source_url=str(target.get("path") or ""),
                        offers=offers,
                        ok=True,
                    )
                if mode == "live":
                    return self.run_live_platform(platform)
                url = str(target.get("url") or "")
                return self.run_url(
                    platform,
                    url,
                    delay=float(target.get("delay", 2.0)),
                    render_js=bool(target.get("render_js", False)),
                )
            except Exception as exc:  # noqa: BLE001 — batch keeps going per target
                return ScrapeResult(
                    platform=self.registry.normalize(platform),
                    source_url=str(target.get("url") or target.get("path") or ""),
                    offers=[],
                    ok=False,
                    error=str(exc),
                )

        targets = list(targets)
        if not targets:
            return []
        if max_workers <= 1:
            return [_run_one(t) for t in targets]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(_run_one, targets))

    def run_live_platform(self, platform: str) -> ScrapeResult:
        """Run platform-native live scrape (API scrapers like 4play/pagol)."""
        self._hydrate_tokens()
        scraper = self._scraper_for(platform)
        if hasattr(scraper, "scrape_live"):
            result = scraper.scrape_live()  # type: ignore[attr-defined]
        else:
            result = scraper.scrape_url("")
        if result.ok and result.offers:
            self.process_offers(result.offers)
        # Keep ok=True even with 0 offers when live API succeeded (notes in error field)
        return result
