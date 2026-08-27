#!/usr/bin/env python3
"""Entry point do BetBonus AI Bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.runner import BonusPipeline
from src.scoring.engine import BonusScoringEngine
from src.scrapers.bet365_scraper import Bet365Scraper


FIXTURES = ROOT / "tests" / "fixtures"


def run_fixture_demo() -> None:
    print("=" * 60)
    print("BetBonus AI Bot — Pipeline Demo (fixtures)")
    print("=" * 60)

    pipeline = BonusPipeline(store_path=ROOT / "data" / "bonuses.json")
    fixture = FIXTURES / "sample_promos.html"
    if not fixture.exists():
        print(f"Fixture missing: {fixture}")
        sys.exit(1)

    for platform in ("bet365", "betway", "888"):
        print(f"\n[{platform}] scraping {fixture.name}...")
        offers = pipeline.run_file(platform, fixture)
        if not offers:
            print("  ⚠ nenhum bônus encontrado")
            continue
        for offer in offers:
            print(
                f"  ✓ {offer.bonus_type.value} | {offer.amount} {offer.currency} | "
                f"{offer.wagering_multiple}x | {offer.expiry_days}d | "
                f"score={offer.score:.1f} ({offer.category.value})"
            )

    print("\n" + "=" * 60)
    print("Demo completed — results in data/bonuses.json")
    print("=" * 60)


def run_score_examples() -> None:
    from src.models.bonus import BonusOffer, BonusType

    engine = BonusScoringEngine()
    samples = [
        BonusOffer(
            platform="demo",
            bonus_type=BonusType.NO_DEPOSIT,
            title="No deposit $25",
            amount=25,
            wagering_multiple=20,
            expiry_days=14,
            min_deposit=0,
        ),
        BonusOffer(
            platform="demo",
            bonus_type=BonusType.DEPOSIT_MATCH,
            title="100% up to $200",
            amount=200,
            match_percent=100,
            wagering_multiple=50,
            expiry_days=3,
            min_deposit=50,
            game_restrictions=["slots only", "excluded: roulette"],
            max_bet_during_bonus=2,
        ),
        BonusOffer(
            platform="demo",
            bonus_type=BonusType.FREE_SPINS,
            title="50 free spins",
            amount=0,
            free_spins=50,
            wagering_multiple=35,
            expiry_hours=24,
            expiry_days=0,
        ),
    ]
    print("Scoring examples:")
    for offer in engine.score_many(samples):
        print(f"  {offer.title}: {offer.score:.1f} ({offer.category.value}) {offer.score_breakdown}")


def run_live_urls(urls: list[str], delay: float) -> None:
    print("Live scrape is best-effort (JS/anti-bot common). Prefer fixtures.")
    scraper = Bet365Scraper(delay=delay)
    pipeline = BonusPipeline(store_path=ROOT / "data" / "bonuses.json")
    for url in urls:
        print(f"\nScraping: {url}")
        result = scraper.scrape_url(url)
        if not result.ok:
            print(f"  ⚠ error: {result.error}")
            continue
        if not result.offers:
            print("  ⚠ no bonus found")
            continue
        scored = pipeline.process_offers(result.offers)
        for offer in scored:
            print(f"  ✓ score={offer.score:.1f} {offer.title[:70]}")


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="BetBonus AI Bot")
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=["demo", "score", "live", "api"],
        help="demo (default) | score | live | api",
    )
    parser.add_argument("--url", action="append", default=[], help="URL for live mode")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args(argv)

    if args.command == "demo":
        run_fixture_demo()
    elif args.command == "score":
        run_score_examples()
    elif args.command == "live":
        urls = args.url or ["https://www.bet365.com/promotions/"]
        run_live_urls(urls, delay=args.delay)
    elif args.command == "api":
        import uvicorn

        print(f"BetBonus AI dashboard → http://{args.host}:{args.port}/")
        print(f"API docs              → http://{args.host}:{args.port}/api/docs")
        uvicorn.run("src.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    cli()
