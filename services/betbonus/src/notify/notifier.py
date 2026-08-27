from __future__ import annotations

from src.models.bonus import BonusCategory, BonusOffer


class ConsoleNotifier:
    """MVP notifier — prints high-score bonuses. Extend for email/SMS/push."""

    def __init__(self, min_category: BonusCategory = BonusCategory.GOOD):
        self.min_category = min_category
        self._rank = {
            BonusCategory.AVOID: 0,
            BonusCategory.POOR: 1,
            BonusCategory.AVERAGE: 2,
            BonusCategory.GOOD: 3,
            BonusCategory.EXCELLENT: 4,
        }

    def should_notify(self, offer: BonusOffer) -> bool:
        return self._rank[offer.category] >= self._rank[self.min_category]

    def notify(self, offers: list[BonusOffer]) -> list[BonusOffer]:
        sent: list[BonusOffer] = []
        for offer in offers:
            if not self.should_notify(offer):
                continue
            print(
                f"[NOTIFY] {offer.platform} | {offer.category.value} "
                f"| score={offer.score:.1f} | {offer.title[:70]} "
                f"| {offer.amount} {offer.currency} @ {offer.wagering_multiple}x"
            )
            sent.append(offer)
        return sent
