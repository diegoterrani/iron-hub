from __future__ import annotations

from src.models.bonus import BonusCategory, BonusOffer, BonusType


def classify_score(score: float) -> BonusCategory:
    if score >= 80:
        return BonusCategory.EXCELLENT
    if score >= 65:
        return BonusCategory.GOOD
    if score >= 45:
        return BonusCategory.AVERAGE
    if score >= 25:
        return BonusCategory.POOR
    return BonusCategory.AVOID


class BonusScoringEngine:
    """
    Heuristic score in [0, 100].

    Components:
    - real value (amount / effective cost of wagering)
    - expiry penalty
    - min deposit friction
    - game restriction penalty
    - type priors (no-deposit / free spins / cashback)
    """

    def value_score(self, offer: BonusOffer) -> float:
        wager = max(offer.wagering_multiple, 1.0)
        # Effective bonus value shrinks with high wagering
        raw = offer.amount
        if offer.free_spins and offer.amount <= 0:
            raw = offer.free_spins * 0.2  # rough EV proxy per spin
        if offer.match_percent and offer.amount <= 0:
            raw = min(offer.match_percent, 200) * 0.35

        effective = raw / (wager / 10.0)
        # Map roughly $0–100 effective → 0–40 points
        return max(0.0, min(40.0, effective * 0.4))

    def wagering_score(self, offer: BonusOffer) -> float:
        w = offer.wagering_multiple
        if w <= 10:
            return 20.0
        if w <= 20:
            return 16.0
        if w <= 30:
            return 12.0
        if w <= 40:
            return 8.0
        if w <= 50:
            return 4.0
        return 0.0

    def expiry_score(self, offer: BonusOffer) -> float:
        days = offer.effective_expiry_days
        if days >= 30:
            return 15.0
        if days >= 14:
            return 12.0
        if days >= 7:
            return 8.0
        if days >= 3:
            return 4.0
        if days >= 1:
            return 2.0
        return 0.0

    def deposit_score(self, offer: BonusOffer) -> float:
        if offer.bonus_type == BonusType.NO_DEPOSIT:
            return 10.0
        md = offer.min_deposit
        if md <= 0:
            return 8.0
        if md <= 10:
            return 7.0
        if md <= 25:
            return 5.0
        if md <= 50:
            return 3.0
        return 1.0

    def restriction_score(self, offer: BonusOffer) -> float:
        n = len(offer.game_restrictions)
        if n == 0:
            return 10.0
        if n <= 2:
            return 7.0
        if n <= 4:
            return 4.0
        return 1.0

    def type_bonus(self, offer: BonusOffer) -> float:
        priors = {
            BonusType.NO_DEPOSIT: 5.0,
            BonusType.FREE_SPINS: 3.0,
            BonusType.CASHBACK: 2.0,
            BonusType.WELCOME_BONUS: 2.0,
            BonusType.DEPOSIT_MATCH: 1.0,
            BonusType.LOYALTY: 1.0,
            BonusType.UNKNOWN: 0.0,
        }
        return priors.get(offer.bonus_type, 0.0)

    def max_bet_penalty(self, offer: BonusOffer) -> float:
        if offer.max_bet_during_bonus is None:
            return 0.0
        if offer.max_bet_during_bonus < 1:
            return -5.0
        if offer.max_bet_during_bonus < 5:
            return -2.0
        return 0.0

    def score(self, offer: BonusOffer) -> BonusOffer:
        breakdown = {
            "value": self.value_score(offer),
            "wagering": self.wagering_score(offer),
            "expiry": self.expiry_score(offer),
            "deposit": self.deposit_score(offer),
            "restrictions": self.restriction_score(offer),
            "type": self.type_bonus(offer),
            "max_bet_penalty": self.max_bet_penalty(offer),
        }
        total = sum(breakdown.values())
        total = max(0.0, min(100.0, total))
        offer.score = round(total, 2)
        offer.category = classify_score(offer.score)
        offer.score_breakdown = {k: round(v, 2) for k, v in breakdown.items()}
        return offer

    def score_many(self, offers: list[BonusOffer]) -> list[BonusOffer]:
        return [self.score(o) for o in offers]
