"""GAPs 1/5/6/7/9/10: config-driven scraper registry, aliases, 888 adapter,
unified scrape_url semantics, batch scraping, and exports."""

from pathlib import Path

from src.scrapers import (
    BetwayScraper,
    EightEightEightScraper,
    FourPlayBrScraper,
    FourPlayScraper,
    PagolScraper,
    ScraperRegistry,
)
from src.scrapers.bet365_scraper import Bet365Scraper
from src.scrapers.generic_promo_scraper import GenericPromoScraper
from src.scrapers.registry import ScraperSpec
from src.pipeline.runner import BonusPipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_promos.html"


# ---------------------------------------------------------------------------
# Registry: aliases + factory
# ---------------------------------------------------------------------------

class TestScraperRegistry:
    def test_normalize_aliases(self):
        reg = ScraperRegistry()
        assert reg.normalize("4play.game") == "4play"
        assert reg.normalize("4play_game") == "4play"
        assert reg.normalize("4play.bet.br") == "4play_bet_br"
        assert reg.normalize("4playbr") == "4play_bet_br"
        assert reg.normalize("pagol") == "pagol_bet_br"
        assert reg.normalize("pagol.bet.br") == "pagol_bet_br"
        assert reg.normalize("888bet") == "888"
        assert reg.normalize("betway.com.br") == "betway"
        assert reg.normalize("bet365br") == "bet365"

    def test_normalize_unknown_passthrough(self):
        reg = ScraperRegistry()
        assert reg.normalize("unknown_house") == "unknown_house"
        assert reg.normalize("") == "4play"  # fallback

    def test_build_returns_expected_classes(self):
        reg = ScraperRegistry()
        assert isinstance(reg.build("bet365"), Bet365Scraper)
        assert isinstance(reg.build("betway"), BetwayScraper)
        assert isinstance(reg.build("888"), EightEightEightScraper)
        assert isinstance(reg.build("4play"), FourPlayScraper)
        assert isinstance(reg.build("4play_bet_br"), FourPlayBrScraper)
        assert isinstance(reg.build("pagol_bet_br"), PagolScraper)
        assert isinstance(reg.build("pagol"), PagolScraper)  # alias

    def test_build_unknown_falls_back_to_generic(self):
        reg = ScraperRegistry()
        scraper = reg.build("mystery_house")
        assert isinstance(scraper, GenericPromoScraper)
        assert scraper.platform == "mystery_house"

    def test_is_api(self):
        reg = ScraperRegistry()
        assert reg.is_api("4play")
        assert reg.is_api("4play.bet.br")
        assert reg.is_api("pagol")
        assert not reg.is_api("bet365")
        assert not reg.is_api("betway")

    def test_platforms(self):
        reg = ScraperRegistry()
        platforms = reg.platforms()
        for key in ("bet365", "betway", "888", "4play", "4play_bet_br", "pagol_bet_br", "generic"):
            assert key in platforms

    def test_yaml_config_overrides(self, tmp_path):
        """A YAML config can tweak delay/aliases without touching code."""
        cfg = tmp_path / "scrapers.yaml"
        cfg.write_text(
            "scrapers:\n"
            "  bet365:\n"
            "    class: Bet365Scraper\n"
            "    mode: html\n"
            "    delay: 1.5\n"
            "    aliases: [bet365.custom]\n",
            encoding="utf-8",
        )
        reg = ScraperRegistry(config_path=cfg)
        spec = reg.get("bet365")
        assert spec is not None
        assert spec.delay == 1.5
        assert reg.normalize("bet365.custom") == "bet365"
        assert reg.build("bet365").delay == 1.5

    def test_yaml_bad_class_ignored(self, tmp_path):
        cfg = tmp_path / "scrapers.yaml"
        cfg.write_text(
            "scrapers:\n"
            "  betway:\n"
            "    class: NotAScraper\n",
            encoding="utf-8",
        )
        reg = ScraperRegistry(config_path=cfg)
        assert isinstance(reg.build("betway"), BetwayScraper)  # default kept

    def test_spec_build_default_delay(self):
        spec = ScraperSpec(platform="x", cls=GenericPromoScraper, delay=0.7, kwargs={"platform": "x"})
        assert spec.build().delay == 0.7
        assert spec.build(delay=0.1).delay == 0.1


# ---------------------------------------------------------------------------
# 888 adapter
# ---------------------------------------------------------------------------

class TestEightEightEightScraper:
    def test_platform(self):
        assert EightEightEightScraper(delay=0).platform == "888"

    def test_platform_tagging(self):
        sc = EightEightEightScraper(delay=0)
        result = sc.scrape_file(FIXTURE)
        assert result.ok
        for offer in result.offers:
            assert offer.platform == "888"


# ---------------------------------------------------------------------------
# Pipeline wired to registry
# ---------------------------------------------------------------------------

class TestPipelineWithRegistry:
    def _pipeline(self, tmp_path):
        return BonusPipeline(
            store_path=tmp_path / "bonuses.json",
            credentials_path=tmp_path / "creds.json",
        )

    def test_registry_populates_scrapers(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        for key in ("bet365", "betway", "888", "4play", "4play_bet_br", "pagol_bet_br", "generic"):
            assert key in pipeline.scrapers
        assert isinstance(pipeline.scrapers["4play"], FourPlayScraper)
        assert isinstance(pipeline.scrapers["4play_bet_br"], FourPlayBrScraper)
        assert isinstance(pipeline.scrapers["pagol_bet_br"], PagolScraper)
        assert isinstance(pipeline.scrapers["888"], EightEightEightScraper)

    def test_alias_resolution_in_pipeline(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        # Alias "pagol" resolves to the pagol_bet_br scraper
        offers = pipeline.run_html("pagol", FIXTURE.read_text(encoding="utf-8"))
        assert isinstance(offers, list)
        # Unknown platform → generic fallback with the raw name
        offers = pipeline.run_html("mystery_house", FIXTURE.read_text(encoding="utf-8"))
        assert isinstance(offers, list)
        assert "mystery_house" in pipeline.scrapers

    def test_explicit_scrapers_still_override(self, tmp_path):
        pipeline = BonusPipeline(
            store_path=tmp_path / "b.json",
            credentials_path=tmp_path / "c.json",
            scrapers={"betway": BetwayScraper(delay=0)},
        )
        assert isinstance(pipeline.scrapers["betway"], BetwayScraper)
        assert "bet365" not in pipeline.scrapers

    def test_run_file_via_alias(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        offers = pipeline.run_file("bet365br", FIXTURE)
        assert len(offers) >= 2


# ---------------------------------------------------------------------------
# Batch scraping (run_many)
# ---------------------------------------------------------------------------

class TestRunMany:
    def _pipeline(self, tmp_path):
        return BonusPipeline(
            store_path=tmp_path / "bonuses.json",
            credentials_path=tmp_path / "creds.json",
        )

    def test_batch_html_targets(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        html = FIXTURE.read_text(encoding="utf-8")
        results = pipeline.run_many(
            [
                {"platform": "bet365", "mode": "html", "html": html},
                {"platform": "betway", "mode": "html", "html": html},
            ],
            max_workers=2,
        )
        assert len(results) == 2
        assert all(r.ok for r in results)
        assert sum(len(r.offers) for r in results) >= 2

    def test_batch_auto_mode_file(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        results = pipeline.run_many(
            [{"platform": "bet365", "mode": "auto", "path": str(FIXTURE)}],
            max_workers=1,
        )
        assert len(results) == 1
        assert results[0].ok
        assert len(results[0].offers) >= 2

    def test_batch_unknown_platform_ok(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        results = pipeline.run_many(
            [{"platform": "nope", "mode": "html", "html": "<html></html>"}],
        )
        assert len(results) == 1
        assert results[0].ok  # generic fallback still parses

    def test_batch_empty(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        assert pipeline.run_many([]) == []

    def test_batch_serial_with_max_workers_1(self, tmp_path):
        pipeline = self._pipeline(tmp_path)
        html = FIXTURE.read_text(encoding="utf-8")
        results = pipeline.run_many(
            [{"platform": "bet365", "mode": "html", "html": html}],
            max_workers=1,
        )
        assert len(results) == 1
        assert results[0].ok
