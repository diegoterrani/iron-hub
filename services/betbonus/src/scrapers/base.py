from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.models.bonus import BonusOffer, ScrapeResult


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BetBonusAI/0.1; +https://localhost/research)"
    ),
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper(ABC):
    platform: str = "unknown"
    default_delay: float = 2.0

    def __init__(self, delay: Optional[float] = None, session: Optional[requests.Session] = None):
        self.delay = self.default_delay if delay is None else delay
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_html(self, url: str, timeout: float = 15.0, render_js: bool = False) -> str:
        """Fetch a URL's HTML.

        ``render_js=True`` renders the page with a headless browser
        (Playwright) before returning the final HTML — required for
        JS-heavy promo pages that ship an empty shell to plain HTTP
        clients. Falls back to plain HTTP when Playwright is not
        installed or the browser fails to start.
        """
        if self.delay > 0:
            time.sleep(self.delay)
        if render_js:
            html = self._render_with_playwright(url, timeout=timeout)
            if html:
                return html
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text

    @staticmethod
    def _render_with_playwright(url: str, timeout: float = 15.0) -> Optional[str]:
        """Render ``url`` with headless Chromium. Returns "" when unavailable."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ""
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                try:
                    page = browser.new_page(
                        user_agent=DEFAULT_HEADERS["User-Agent"],
                        locale="pt-BR",
                    )
                    page.goto(url, wait_until="networkidle", timeout=int(timeout * 1000))
                    return page.content()
                finally:
                    browser.close()
        except Exception:  # noqa: BLE001 — rendering is best-effort
            return ""

    def load_html_file(self, path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    def parse_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    @abstractmethod
    def extract_offers(self, soup: BeautifulSoup, source_url: str = "") -> list[BonusOffer]:
        raise NotImplementedError

    def scrape_url(self, url: str, render_js: bool = False) -> ScrapeResult:
        """Fetch ``url`` and extract offers.

        Unified semantics: HTML scrapers fetch + parse the page; API
        scrapers override this to call ``scrape_live()`` (the URL is
        ignored). ``render_js=True`` renders JS-heavy pages with a
        headless browser before parsing.
        """
        try:
            html = self.fetch_html(url, render_js=render_js)
            offers = self.extract_offers(self.parse_soup(html), source_url=url)
            return ScrapeResult(platform=self.platform, source_url=url, offers=offers, ok=True)
        except Exception as exc:  # noqa: BLE001 — surface scrape errors as result
            return ScrapeResult(
                platform=self.platform,
                source_url=url,
                offers=[],
                ok=False,
                error=str(exc),
            )

    def scrape_html(self, html: str, source_url: str = "fixture://local") -> ScrapeResult:
        try:
            offers = self.extract_offers(self.parse_soup(html), source_url=source_url)
            return ScrapeResult(platform=self.platform, source_url=source_url, offers=offers, ok=True)
        except Exception as exc:  # noqa: BLE001
            return ScrapeResult(
                platform=self.platform,
                source_url=source_url,
                offers=[],
                ok=False,
                error=str(exc),
            )

    def scrape_file(self, path: str | Path, source_url: str = "") -> ScrapeResult:
        html = self.load_html_file(path)
        return self.scrape_html(html, source_url=source_url or f"file://{path}")
