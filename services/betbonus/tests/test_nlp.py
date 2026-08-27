from src.nlp.analyzer import BonusNLPAnalyzer
from src.models.bonus import BonusType


def test_extract_deposit_match():
    text = (
        "Welcome Bonus — 100% up to $200. Wagering requirements: 30x. "
        "Minimum deposit $20. Valid for 14 days. Max bet during bonus $5. Only slots."
    )
    fields = BonusNLPAnalyzer().analyze(text)
    assert fields.bonus_type in {BonusType.WELCOME_BONUS, BonusType.DEPOSIT_MATCH, BonusType.FREE_SPINS}
    assert fields.amount == 200
    assert fields.currency == "USD"
    assert fields.wagering_multiple == 30
    assert fields.min_deposit == 20
    assert fields.expiry_days == 14
    assert fields.max_bet_during_bonus == 5
    assert fields.match_percent == 100


def test_extract_free_spins_hours():
    text = "Claim 50 free spins. 35x wagering. Expires in 48 hours."
    fields = BonusNLPAnalyzer().analyze(text)
    assert fields.bonus_type == BonusType.FREE_SPINS
    assert fields.free_spins == 50
    assert fields.wagering_multiple == 35
    assert fields.expiry_hours == 48


def test_no_deposit_beats_free_spins_label():
    text = "Claim 50 free spins with no deposit. 35x wagering. Expires in 48 hours."
    fields = BonusNLPAnalyzer().analyze(text)
    assert fields.bonus_type == BonusType.NO_DEPOSIT
    assert fields.free_spins == 50
