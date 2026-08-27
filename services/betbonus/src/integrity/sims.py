"""Sims determinísticos offline — modelo de risco, não aposta em produção e não prevê RNG."""

from __future__ import annotations

from typing import Any, Literal

Action = Literal["HIT", "STAND", "DOUBLE", "SPLIT"]

# Hard totals (player total, dealer up 2-A) — basic strategy compacta (H17).
# A = 11. Valores: H stand, h hit, D double else hit, d double else stand.
_HARD = {
    8: "hhhhhhhhhh",
    9: "hDDDDhhhhh",
    10: "DDDDDDDDDh",
    11: "DDDDDDDDDD",
    12: "hhSSShhhhh",
    13: "SSSSShhhhh",
    14: "SSSSShhhhh",
    15: "SSSSShhhhh",
    16: "SSSSShhhhh",
    17: "SSSSSSSSSS",
}
_SOFT = {
    13: "hhhDDhhhhh",  # A,2
    14: "hhhDDhhhhh",
    15: "hhDDDhhhhh",
    16: "hhDDDhhhhh",
    17: "hDDDDDhhhh",
    18: "SDDDDSShhh",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
}
# Pair chart vs 2-A: P split, else hard.
_PAIR = {
    2: "hPPPPPhhhh",
    3: "hPPPPPhhhh",
    4: "hhhhhhhhhh",
    5: "DDDDDDDDDh",
    6: "hPPPPPhhhh",
    7: "PPPPPPhhhh",
    8: "PPPPPPPPPP",
    9: "SPPPPSPPSS",
    10: "SSSSSSSSSS",
    11: "PPPPPPPPPP",  # aces
}

DEALER_UP = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)


def _col(dealer_up: int) -> int:
    if dealer_up >= 10:
        return 8 if dealer_up == 10 else 9
    return max(2, min(11, dealer_up)) - 2


def _decode(code: str, col: int) -> Action:
    ch = code[col]
    if ch in "P":
        return "SPLIT"
    if ch in "Dd":
        return "DOUBLE"
    if ch in "S":
        return "STAND"
    return "HIT"


def blackjack_action(
    *,
    player_total: int,
    dealer_up: int,
    soft: bool = False,
    pair: int | None = None,
) -> Action:
    col = _col(dealer_up)
    if pair is not None:
        row = _PAIR.get(int(pair))
        if row:
            return _decode(row, col)
    if soft:
        row = _SOFT.get(max(13, min(20, int(player_total))))
        if row:
            return _decode(row, col)
        return "STAND" if player_total >= 19 else "HIT"
    if player_total <= 8:
        return "HIT"
    if player_total >= 17:
        return "STAND"
    row = _HARD.get(int(player_total))
    if not row:
        return "STAND" if player_total >= 17 else "HIT"
    action = _decode(row, col)
    if action == "DOUBLE":
        return "DOUBLE"
    return action


def blackjack_risk(*, bankroll: float, unit: float, hands: int = 100, house_edge: float = 0.005) -> dict[str, Any]:
    """Ruin/EV com basic strategy — house edge ~0.5% H17 infinite deck. Sem rede."""
    if unit <= 0 or bankroll <= 0:
        raise ValueError("bankroll e unit devem ser > 0")
    ev_per_hand = -house_edge * unit
    expected = round(ev_per_hand * hands, 6)
    # Aproximação gaussiana de ruin: não é simulação RNG de cartas.
    units = bankroll / unit
    ruin = 1.0 if house_edge <= 0 else min(1.0, (1 - house_edge) ** units)
    return {
        "game": "blackjack",
        "strategy": "basic_h17",
        "house_edge": house_edge,
        "bankroll": bankroll,
        "unit": unit,
        "hands": hands,
        "expected_pnl": expected,
        "units_in_bankroll": round(units, 4),
        "approx_ruin": round(ruin, 6),
        "note": "Modelo de risco. Não joga na casa e não prevê cartas.",
        "sample_actions": {
            "16_vs_10": blackjack_action(player_total=16, dealer_up=10),
            "11_vs_6": blackjack_action(player_total=11, dealer_up=6),
            "A7_vs_9": blackjack_action(player_total=18, dealer_up=9, soft=True),
            "pair8_vs_10": blackjack_action(player_total=16, dealer_up=10, pair=8),
        },
    }


def baccarat_ev(bet: Literal["banker", "player", "tie"] = "banker", stake: float = 1.0) -> dict[str, Any]:
    edges = {"banker": 0.01058, "player": 0.01235, "tie": 0.1436}
    edge = edges[bet]
    return {
        "game": "baccarat",
        "bet": bet,
        "stake": stake,
        "house_edge": edge,
        "expected_pnl": round(-edge * stake, 6),
        "commission_banker": 0.05 if bet == "banker" else 0.0,
        "note": "Edge publicado de baccarat padrão. Não há vantagem no longo prazo.",
    }


def roulette_martingale_ruin(
    *,
    bankroll: float,
    unit: float,
    table_limit: float,
    pockets: int = 37,
) -> dict[str, Any]:
    """Europeu 37 / americano 38. Even-money. Martingale ruína no teto."""
    if pockets not in {37, 38}:
        raise ValueError("pockets deve ser 37 (EU) ou 38 (US)")
    p_win = 18 / pockets
    house_edge = 1 - 2 * p_win
    max_doubles = 0
    stake = unit
    while stake * 2 <= table_limit + 1e-9 and stake * 2 <= bankroll + 1e-9:
        stake *= 2
        max_doubles += 1
    # Prob de perder max_doubles+1 seguidas
    p_bust_seq = (1 - p_win) ** (max_doubles + 1)
    return {
        "game": "roulette",
        "variant": "european" if pockets == 37 else "american",
        "pockets": pockets,
        "house_edge": round(house_edge, 6),
        "p_even_money": round(p_win, 6),
        "unit": unit,
        "bankroll": bankroll,
        "table_limit": table_limit,
        "max_progression_steps": max_doubles,
        "p_bust_sequence": round(p_bust_seq, 8),
        "expected_loss_per_spin_flat": round(house_edge * unit, 6),
        "note": "Martingale não vence house edge; só concentra ruin no teto da mesa.",
    }


def crash_cashout_ev(*, cashout: float, house_edge: float = 0.04) -> dict[str, Any]:
    """
    Modelo clássico: P(crash > c) * c = 1 - house_edge.
    Qualquer cashout tem o mesmo EV negativo. Não é predição de round.
    """
    if cashout < 1.01:
        raise ValueError("cashout mínimo 1.01x")
    if not 0 <= house_edge < 1:
        raise ValueError("house_edge em [0, 1)")
    p_win = (1.0 - house_edge) / cashout
    ev = p_win * (cashout - 1.0) + (1.0 - p_win) * (-1.0)
    return {
        "game": "crash",
        "cashout": cashout,
        "house_edge": house_edge,
        "p_win_model": round(p_win, 6),
        "expected_pnl_per_unit": round(ev, 6),
        "rtp_model": round(1.0 - house_edge, 6),
        "invariant": "EV independe do multiplicador escolhido neste modelo",
        "note": "Não prevê o próximo crash. Live cashout vs tick = SEMI_AUTO na casa.",
    }


def table_suite(*, bankroll: float = 100.0, unit: float = 1.0) -> dict[str, Any]:
    return {
        "blackjack": blackjack_risk(bankroll=bankroll, unit=unit, hands=100),
        "baccarat_banker": baccarat_ev("banker", unit),
        "baccarat_player": baccarat_ev("player", unit),
        "roulette_eu": roulette_martingale_ruin(
            bankroll=bankroll, unit=unit, table_limit=max(unit * 16, 50.0), pockets=37
        ),
        "crash_2x": crash_cashout_ev(cashout=2.0),
        "crash_10x": crash_cashout_ev(cashout=10.0),
    }
