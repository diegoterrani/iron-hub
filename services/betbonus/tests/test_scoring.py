from src.models.bonus import BonusCategory, BonusOffer, BonusType
from src.scoring.engine import BonusScoringEngine


def test_good_no_deposit_scores_higher_than_harsh_match():
    engine = BonusScoringEngine()
    good = engine.score(
        BonusOffer(
            platform="a",
            bonus_type=BonusType.NO_DEPOSIT,
            amount=25,
            wagering_multiple=20,
            expiry_days=14,
        )
    )
    harsh = engine.score(
        BonusOffer(
            platform="b",
            bonus_type=BonusType.DEPOSIT_MATCH,
            amount=200,
            wagering_multiple=50,
            expiry_days=2,
            min_deposit=50,
            game_restrictions=["slots", "excluded roulette", "blackjack", "baccarat", "poker"],
            max_bet_during_bonus=1,
        )
    )
    assert good.score > harsh.score
    assert good.category in {BonusCategory.GOOD, BonusCategory.EXCELLENT, BonusCategory.AVERAGE}
