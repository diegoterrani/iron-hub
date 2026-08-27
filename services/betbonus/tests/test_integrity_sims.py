from src.integrity.sims import (
    baccarat_ev,
    blackjack_action,
    blackjack_risk,
    crash_cashout_ev,
    roulette_martingale_ruin,
    table_suite,
)


def test_blackjack_basic_strategy_deterministic():
    assert blackjack_action(player_total=16, dealer_up=10) == "HIT"
    assert blackjack_action(player_total=12, dealer_up=6) == "STAND"
    assert blackjack_action(player_total=11, dealer_up=6) == "DOUBLE"
    assert blackjack_action(player_total=16, dealer_up=10, pair=8) == "SPLIT"
    assert blackjack_action(player_total=18, dealer_up=9, soft=True) == "HIT"


def test_blackjack_risk_negative_ev():
    risk = blackjack_risk(bankroll=100, unit=1, hands=100, house_edge=0.005)
    assert risk["expected_pnl"] < 0
    assert risk["sample_actions"]["16_vs_10"] == "HIT"


def test_baccarat_banker_better_than_player():
    banker = baccarat_ev("banker")
    player = baccarat_ev("player")
    tie = baccarat_ev("tie")
    assert banker["expected_pnl"] > player["expected_pnl"]
    assert tie["house_edge"] > player["house_edge"]


def test_roulette_european_edge():
    eu = roulette_martingale_ruin(bankroll=100, unit=1, table_limit=50, pockets=37)
    us = roulette_martingale_ruin(bankroll=100, unit=1, table_limit=50, pockets=38)
    assert abs(eu["house_edge"] - 1 / 37) < 1e-6
    assert us["house_edge"] > eu["house_edge"]
    assert 0 < eu["p_bust_sequence"] < 1


def test_crash_ev_independent_of_multiplier():
    a = crash_cashout_ev(cashout=2.0, house_edge=0.04)
    b = crash_cashout_ev(cashout=10.0, house_edge=0.04)
    assert abs(a["expected_pnl_per_unit"] - b["expected_pnl_per_unit"]) < 1e-9
    assert abs(a["expected_pnl_per_unit"] + 0.04) < 1e-9


def test_table_suite_keys():
    suite = table_suite()
    assert "blackjack" in suite
    assert "crash_2x" in suite
    assert suite["roulette_eu"]["variant"] == "european"
