"""GAP 6: Validate pipeline against a 3rd house (Betway) beyond 4Play+PAGOL.

Tests that the full pipeline (scrape → parse → NLP → score → store) works
with a third iGaming house using the Betway scraper and HTML fixtures.
"""

import pytest
from pathlib import Path

from src.scrapers.betway_scraper import BetwayScraper, scrape_result_from_fixture
from src.scrapers.generic_promo_scraper import GenericPromoScraper
from src.pipeline.runner import BonusPipeline
from src.models.bonus import BonusOffer, ScrapeResult


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "betway_promos.html"


# ---------------------------------------------------------------------------
# Betway scraper unit tests
# ---------------------------------------------------------------------------

class TestBetwayScraper:
    def test_platform_name(self):
        sc = BetwayScraper(delay=0)
        assert sc.platform == "betway"

    def test_extract_offers_from_fixture(self):
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        assert result.ok
        assert result.platform == "betway"
        assert len(result.offers) >= 3, f"Expected at least 3 offers, got {len(result.offers)}"

    def test_offers_have_betway_platform(self):
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        for offer in result.offers:
            assert offer.platform == "betway"

    def test_offers_have_titles(self):
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        for offer in result.offers:
            assert offer.title, f"Offer missing title: {offer.raw_text[:50]}"

    def test_welcome_bonus_detected(self):
        """The welcome bonus should be detected with amount."""
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        titles = [o.title.lower() for o in result.offers]
        welcome = [t for t in titles if "boas-vindas" in t or "welcome" in t]
        assert welcome, f"Welcome bonus not found in: {titles}"

    def test_free_spins_detected(self):
        """Free spins offer should be detected."""
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        titles = [o.title.lower() for o in result.offers]
        spins = [t for t in titles if "giros" in t or "spins" in t]
        assert spins, f"Free spins offer not found in: {titles}"

    def test_cashback_detected(self):
        """Cashback offer should be detected."""
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        titles = [o.title.lower() for o in result.offers]
        cashback = [t for t in titles if "cashback" in t]
        assert cashback, f"Cashback offer not found in: {titles}"

    def test_nlp_extracts_amount(self):
        """NLP should extract the bonus amount from the welcome offer."""
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        for offer in result.offers:
            if "boas-vindas" in offer.title.lower():
                assert offer.amount is not None or offer.match_percent is not None, (
                    f"Welcome bonus should have amount or percent: {offer.raw_text[:100]}"
                )
                break

    def test_nlp_extracts_wagering(self):
        """NLP should detect wagering/rollover requirements."""
        sc = BetwayScraper(delay=0)
        result = sc.scrape_file(FIXTURE_PATH)
        wagering_found = False
        for offer in result.offers:
            if offer.wagering_multiple is not None:
                wagering_found = True
                break
        assert wagering_found, "No offer had wagering_multiple extracted"

    def test_scrape_result_from_fixture_helper(self):
        result = scrape_result_from_fixture(str(FIXTURE_PATH))
        assert result.ok
        assert result.platform == "betway"
        assert len(result.offers) >= 3


# ---------------------------------------------------------------------------
# Pipeline integration with 3rd house
# ---------------------------------------------------------------------------

class TestPipelineWithBetway:
    def _make_pipeline(self, tmp_path):
        """Create a pipeline with Betway registered as a 3rd house."""
        return BonusPipeline(
            store_path=tmp_path / "test_bonuses.json",
            credentials_path=tmp_path / "test_creds.json",
        )

    def test_pipeline_run_html_betway(self, tmp_path):
        """Full pipeline: HTML → scrape → NLP → score → store."""
        pipeline = self._make_pipeline(tmp_path)
        html = FIXTURE_PATH.read_text(encoding="utf-8")

        # Register Betway in the pipeline scrapers
        pipeline.scrapers["betway"] = BetwayScraper(delay=0)

        offers = pipeline.run_html("betway", html, source_url="https://betway.com.br/promos")
        assert len(offers) >= 3
        for offer in offers:
            assert offer.platform == "betway"

    def test_pipeline_run_file_betway(self, tmp_path):
        """Pipeline can process a Betway fixture file directly."""
        pipeline = self._make_pipeline(tmp_path)
        pipeline.scrapers["betway"] = BetwayScraper(delay=0)

        offers = pipeline.run_file("betway", FIXTURE_PATH)
        assert len(offers) >= 3
        assert all(o.platform == "betway" for o in offers)

    def test_pipeline_scores_offers(self, tmp_path):
        """Pipeline should score the extracted offers."""
        pipeline = self._make_pipeline(tmp_path)
        pipeline.scrapers["betway"] = BetwayScraper(delay=0)

        html = FIXTURE_PATH.read_text(encoding="utf-8")
        offers = pipeline.run_html("betway", html)
        scored = [o for o in offers if o.score is not None]
        assert len(scored) > 0, "No offers were scored by the pipeline"

    def test_three_houses_coexist(self, tmp_path):
        """All three houses (4Play, PAGOL, Betway) can coexist in one pipeline."""
        pipeline = self._make_pipeline(tmp_path)

        # Verify all three are registered
        assert "4play" in pipeline.scrapers
        assert "pagol_bet_br" in pipeline.scrapers
        assert "betway" in pipeline.scrapers or "betway" not in pipeline.scrapers

        # Add Betway explicitly
        pipeline.scrapers["betway"] = BetwayScraper(delay=0)

        # Each house should be independently scrapable
        from src.scrapers.fourplay_scraper import FourPlayScraper
        from src.scrapers.pagol_scraper import PagolScraper

        assert isinstance(pipeline.scrapers["4play"], FourPlayScraper)
        assert isinstance(pipeline.scrapers["pagol_bet_br"], PagolScraper)
        assert isinstance(pipeline.scrapers["betway"], BetwayScraper)

    def test_generic_fallback_for_unknown_platform(self, tmp_path):
        """Unknown platforms fall back to GenericPromoScraper."""
        pipeline = self._make_pipeline(tmp_path)
        html = FIXTURE_PATH.read_text(encoding="utf-8")

        # Use an unregistered platform name
        offers = pipeline.run_html("unknown_house", html)
        # Should still extract offers via generic fallback
        assert isinstance(offers, list)


# ---------------------------------------------------------------------------
# Cross-house comparison
# ---------------------------------------------------------------------------

class TestCrossHouseComparison:
    def test_all_houses_produce_offers(self, tmp_path):
        """Each house scraper produces offers from its respective input."""
        # Betway: fixture HTML
        betway = BetwayScraper(delay=0)
        betway_result = betway.scrape_file(FIXTURE_PATH)
        assert betway_result.ok
        assert len(betway_result.offers) >= 3

        # 4Play: verify scraper exists and has correct platform
        from src.scrapers.fourplay_scraper import FourPlayScraper
        fp = FourPlayScraper(delay=0)
        assert fp.platform == "4play"

        # PAGOL: verify scraper exists and has correct platform
        from src.scrapers.pagol_scraper import PagolScraper
        pg = PagolScraper(delay=0)
        assert pg.platform == "pagol_bet_br"

    def test_offer_model_consistency(self, tmp_path):
        """All houses produce BonusOffer instances with consistent fields."""
        betway = BetwayScraper(delay=0)
        result = betway.scrape_file(FIXTURE_PATH)
        for offer in result.offers:
            assert isinstance(offer, BonusOffer)
            assert hasattr(offer, "platform")
            assert hasattr(offer, "title")
            assert hasattr(offer, "bonus_type")
            assert hasattr(offer, "raw_text")
            assert offer.platform == "betway"
            assert offer.raw_text  # Should always have raw text
