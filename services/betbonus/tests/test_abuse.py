from src.abuse.oracle import classify_conversion
from src.models.abuse import ConversionStatus, WalletSnapshot
from src.models.bonus import BonusOffer, BonusType
from src.scoring.abuse import AbuseScoringEngine, classify_abuse_severity


def test_classify_withdrawable_blocked_below_min():
    snap = classify_conversion(
        WalletSnapshot(balance=979.1, bonus=0, rollover=0),
        account_bonuses=0,
    )
    assert snap.status == ConversionStatus.BLOCKED
    assert any("below_min_withdraw" in g for g in snap.gates)


def test_classify_wagering():
    snap = classify_conversion(WalletSnapshot(balance=100, bonus=50, rollover=5000))
    assert snap.status == ConversionStatus.WAGERING


def test_abuse_score_no_deposit_high():
    engine = AbuseScoringEngine()
    offer = BonusOffer(
        platform="4play",
        bonus_type=BonusType.NO_DEPOSIT,
        title="ND test",
        amount=5000,
        wagering_multiple=8,
        min_deposit=0,
        max_bet_during_bonus=None,
    )
    score, parts = engine.score_offer(offer)
    assert score >= 45
    assert "wagering_ease" in parts
    assert classify_abuse_severity(score).value in {"medium", "high", "critical"}
