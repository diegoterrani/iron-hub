from __future__ import annotations

from typing import Any

from src.models.abuse import AbuseSeverity, RulesCanon
from src.models.bonus import BonusOffer
from src.scoring.game_bonus_vectors import detect_game_bonus_vectors, score_game_bonus_gap


def classify_abuse_severity(score: float) -> AbuseSeverity:
    if score >= 80:
        return AbuseSeverity.CRITICAL
    if score >= 65:
        return AbuseSeverity.HIGH
    if score >= 45:
        return AbuseSeverity.MEDIUM
    if score >= 25:
        return AbuseSeverity.LOW
    return AbuseSeverity.INFO


class AbuseScoringEngine:
    """
    Score de abusabilidade 0–100 (alto = mais fácil abusar / maior EV para atacante).

    Complementa o score de 'atratividade' do monitor — aqui o CISO prioriza risco.
    Inclui gap de jogos jogáveis com bônus sem rollover / sem depósito.
    """

    def score_offer(self, offer: BonusOffer) -> tuple[float, dict[str, float]]:
        game_gap, _vectors = score_game_bonus_gap(offer)
        parts: dict[str, float] = {
            "wagering_ease": self._wagering_ease(offer.wagering_multiple),
            "value_attractiveness": self._value(offer),
            "expiry_pressure": self._expiry(offer.effective_expiry_days),
            "deposit_friction": self._deposit(offer),
            "restriction_gaps": self._restrictions(offer),
            "max_bet_gap": self._max_bet(offer),
            "bonus_game_gap": game_gap,
        }
        total = round(min(100.0, sum(parts.values())), 2)
        return total, parts

    def score_offer_with_vectors(
        self, offer: BonusOffer
    ) -> tuple[float, dict[str, float], list[dict[str, Any]]]:
        score, parts = self.score_offer(offer)
        return score, parts, detect_game_bonus_vectors(offer)

    def score_rules(self, rules: RulesCanon) -> tuple[float, dict[str, float]]:
        proxy = BonusOffer(
            platform=rules.platform,
            title=rules.title,
            amount=rules.amount,
            currency=rules.currency,
            wagering_multiple=rules.wagering_multiple,
            min_deposit=rules.min_deposit,
            max_bet_during_bonus=rules.max_bet_during_bonus,
            expiry_days=int(rules.expiry_days),
            game_restrictions=list(rules.game_restrictions),
        )
        return self.score_offer(proxy)

    def _wagering_ease(self, w: float) -> float:
        if w <= 5:
            return 30.0
        if w <= 10:
            return 24.0
        if w <= 20:
            return 16.0
        if w <= 30:
            return 10.0
        if w <= 40:
            return 5.0
        return 1.0

    def _value(self, offer: BonusOffer) -> float:
        raw = offer.amount
        if offer.free_spins and raw <= 0:
            raw = offer.free_spins * 0.2
        if offer.match_percent and raw <= 0:
            raw = min(offer.match_percent, 300) * 0.25
        return max(0.0, min(25.0, raw * 0.0025 + (8.0 if raw > 0 else 0.0)))

    def _expiry(self, days: float) -> float:
        if days <= 1:
            return 5.0
        if days <= 3:
            return 8.0
        if days <= 7:
            return 12.0
        if days <= 14:
            return 10.0
        return 6.0

    def _deposit(self, offer: BonusOffer) -> float:
        # No-deposit / low min deposit = higher abuse surface for multi-account
        if offer.min_deposit <= 0 and "no_deposit" in offer.bonus_type.value:
            return 18.0
        if offer.min_deposit <= 0:
            return 12.0
        if offer.min_deposit <= 5000:
            return 10.0
        if offer.min_deposit <= 25000:
            return 6.0
        return 2.0

    def _restrictions(self, offer: BonusOffer) -> float:
        # Few/no game restrictions → easier optimal clearing
        n = len(offer.game_restrictions)
        if n == 0:
            return 10.0
        if n <= 2:
            return 6.0
        return 2.0

    def _max_bet(self, offer: BonusOffer) -> float:
        mb = offer.max_bet_during_bonus
        if mb is None:
            return 8.0  # unspecified max-bet is a common abuse/gap vector
        if mb <= 0:
            return 8.0
        if mb >= 50_000:
            return 7.0
        if mb >= 10_000:
            return 4.0
        return 2.0
