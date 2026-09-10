from src.abuse.matrix import KillChainMatrix, MatrixStageResult, _dominant_blocker
from src.scrapers.pagol_scraper import PagolScraper


def test_normalize_bonus_rules_slots_only():
    sc = PagolScraper(delay=0, token="x")
    rules = sc.normalize_bonus_rules(
        {
            "id": 6608291,
            "name": "SALDO R$ 20 BÔNUS",
            "status": "ACTIVE",
            "balance": 500,
            "rollover": 1500,
            "targetRollover": 20000,
            "maxConvertValue": 4000,
            "maxSelectableBalanceBet": 300,
            "bonusGameTypes": ["SLOTS"],
            "bonusType": "INSTANT",
        }
    )
    assert rules["balance_brl"] == 5.0
    assert rules["rollover_brl"] == 15.0
    assert rules["target_rollover_brl"] == 200.0
    assert rules["remaining_rollover_brl"] == 185.0
    assert rules["max_convert_brl"] == 40.0
    assert rules["max_bet_brl"] == 3.0
    assert rules["slots_only"] is True
    assert rules["allows_high_ev"] is False


def test_bonus_play_strategy_bets_needed():
    sc = PagolScraper(delay=0, token="x")
    primary = sc.normalize_bonus_rules(
        {
            "id": 1,
            "balance": 500,
            "rollover": 1500,
            "targetRollover": 20000,
            "maxConvertValue": 4000,
            "maxSelectableBalanceBet": 300,
            "bonusGameTypes": ["SLOTS"],
        }
    )
    strategy = sc._bonus_play_strategy(primary)
    assert strategy["mode"] == "slots_under_max_bet"
    assert strategy["auto_bet_available"] is True
    assert strategy["auto_bet_method"] == "browser_spin_click"
    assert strategy["bets_needed_at_max_bet"] == 62  # ceil(185/3)


def test_bonus_play_strategy_auto_bet_disabled():
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"BETBONUS_AUTO_BET": "0"}):
        sc = PagolScraper(delay=0, token="x")
        sc.AUTO_BET_ENABLED = False
        primary = sc.normalize_bonus_rules(
            {
                "id": 1,
                "balance": 500,
                "rollover": 1500,
                "targetRollover": 20000,
                "maxConvertValue": 4000,
                "maxSelectableBalanceBet": 300,
                "bonusGameTypes": ["SLOTS"],
            }
        )
        strategy = sc._bonus_play_strategy(primary)
        assert strategy["auto_bet_available"] is False
        assert "disabled" in strategy["auto_bet_blocker"]


def test_dominant_blocker_priority():
    stages = [
        MatrixStageResult(
            id="a",
            title="t",
            mode="AUTOMATED",
            ok=True,
            vulnerability="slots_bonus_launch_ok_spin_manual",
        ),
        MatrixStageResult(
            id="b",
            title="t",
            mode="AUTOMATED",
            ok=False,
            vulnerability="repeated_bo_denied_on_cash_withdraw",
        ),
    ]
    assert _dominant_blocker(stages) == "repeated_bo_denied_on_cash_withdraw"


class _FakePagol(PagolScraper):
    def __init__(self):
        super().__init__(delay=0, token="fake")

    def validate_token(self):
        return {"user_id": 1, "currency": "BRL"}

    def get_wallet_snapshot(self, *, include_bonus_state: bool = True):
        from src.models.abuse import WalletSnapshot

        state = self.get_bonus_conversion_state() if include_bonus_state else {}
        primary = state.get("primary") or {}
        return WalletSnapshot(
            platform=self.platform,
            balance=100.29,
            bonus=float(primary.get("balance_brl") or 5),
            rollover=float(primary.get("remaining_rollover_brl") or 185),
            raw={"bonus_state": state},
        )

    def list_bonuses(self, statuses=("ACTIVE", "PENDING"), page_size=50, max_pages=10):
        return [
            {
                "id": 6608291,
                "name": "SALDO R$ 20 BÔNUS",
                "status": "ACTIVE",
                "balance": 500,
                "rollover": 1500,
                "targetRollover": 20000,
                "maxConvertValue": 4000,
                "maxSelectableBalanceBet": 300,
                "bonusGameTypes": ["SLOTS"],
                "bonusType": "INSTANT",
                "_status_query": "ACTIVE",
            }
        ]

    def get_bonus_balances(self):
        return [{"bonusId": 6608291, "balance": 500, "balance_brl": 5.0, "gameType": "SLOTS"}]

    def probe_high_ev_contribution(self, limit=6, include_bonus_flag=True):
        return {
            "probed": 2,
            "note": "soft",
            "findings": [],
            "probes": [{"game_id": 1624, "name": "Mines"}],
            "wallet_unchanged": True,
        }

    def probe_slots_for_bonus(self, limit=4, use_bonus_balance=True, search_terms=None, auto_spin=False, spin_clicks=1):
        return {
            "probe_kind": "slots_auto_spin" if auto_spin else "slots_soft_launch",
            "note": "launch only",
            "auto_spin": auto_spin,
            "launches_ok": 1,
            "probed": 1,
            "probes": [{"game_id": 1268, "ok": True}],
        }

    def withdraw_preflight(self):
        return {
            "have_opened": False,
            "withdrawal_allowed": True,
            "methods": ["PIX"],
            "day_totals_brl": 212.92,
            "min_withdraw": 20,
            "pix_type": "CPF",
        }

    def list_withdrawals(self, page=0, page_size=20):
        return {
            "items": [
                {"id": 1269741, "status": "DENIED", "amount_brl": 100.0},
                {"id": 1269655, "status": "DENIED", "amount_brl": 100.0},
            ]
        }


def test_matrix_run_fake_no_withdraw():
    report = KillChainMatrix(_FakePagol(), findings=None).run(
        confirm_real_withdraw=False,
        probe_high_ev=True,
        probe_slots=True,
        persist_findings=False,
    )
    ids = [s["id"] for s in report["stages"]]
    assert "wallet_bonus_inventory" in ids
    assert "probe_high_ev" in ids
    assert "probe_slots" in ids
    assert "withdraw_settle" in ids
    assert report["verdict"]["dominant_blocker"] in {
        "repeated_bo_denied_on_cash_withdraw",
        "rollover_gate_caps_extractable_value",
        "high_ev_launch_ok_but_bonus_game_type_blocks_stake",
    }
    # Auto-bet is now implemented (browser-based), so it should NOT be in not_automatable_yet
    assert "provider_slot_auto_spin" not in report["coverage"]["not_automatable_yet"]
    # BO operations remain not-automatable
    assert "bo_bonus_credit_claim" in report["coverage"]["not_automatable_yet"]
    assert "bo_approve_withdraw" in report["coverage"]["not_automatable_yet"]
