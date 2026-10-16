"""
Wagering Strategy Engine — adaptive bonus→cash conversion.

Key insight: For bonus→cash, the optimal strategy is NOT "win big."
It's: use low-variance high-RTP games, stake at max_bet, accept ~5%
house edge over N rounds, stop immediately when remaining_rollover ≤ 0.

Game selection priority:
1. Crash games with 1x-1.5x cashout (Mines 1 mine, Aviator 1.01x) → ~99% RTP
2. High-RTP slots (96-97% RTP)
3. Any eligible game at max_bet

Wires in sims.py for EV calculations.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

from src.integrity.sims import crash_cashout_ev


@dataclass
class GameCandidate:
    """A game available for wagering."""

    game_id: int | str
    name: str
    provider: str = ""
    rtp: float = 0.96
    variance: str = "medium"  # "low" | "medium" | "high"
    eligible: bool = True
    max_bet: float = 0.0  # 0 = no limit
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WagerPlan:
    """Computed plan for executing a bonus→cash wagering session."""

    game: GameCandidate
    stake: float
    rounds_needed: int
    expected_loss: float
    estimated_time_s: float
    strategy: str
    remaining_rollover: float
    max_bet: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WagerResult:
    """Outcome of an executed wagering plan."""

    success: bool
    rounds_played: int
    total_wagered: float
    balance_start: float
    balance_end: float
    net_loss: float
    rollover_cleared: bool
    error: str = ""
    duration_s: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WageringStrategyEngine:
    """
    Adaptive wagering engine for bonus→cash conversion.

    Strategy:
    - Select lowest-variance, highest-RTP eligible game
    - Stake at max_bet (or just below) to minimize rounds
    - Accept house edge as cost of conversion
    - Stop immediately when rollover ≤ 0
    - Adaptive: switch game if losing streak > 3σ
    """

    def __init__(self, scraper: Any, profile: Any = None) -> None:
        self.scraper = scraper
        self.profile = profile

    def select_game(
        self,
        candidates: list[GameCandidate],
        max_bet: float,
        rollover_remaining: float,
    ) -> GameCandidate:
        """
        Pick the best game for wagering.

        Priority:
        1. Lowest variance + highest RTP (eligible, respects max_bet)
        2. Crash games with low cashout (Mines 1, Aviator 1.01x)
        3. High-RTP slots (96-97%)
        4. Any eligible game
        """
        eligible = [
            c
            for c in candidates
            if c.eligible
            and (c.max_bet == 0 or c.max_bet >= min(max_bet, 1.0))
        ]
        if not eligible:
            # Fall back to any candidate
            eligible = list(candidates)
        if not eligible:
            raise ValueError("No game candidates available")

        # Score: prefer low variance, high RTP, crash-style games
        variance_order = {"low": 0, "medium": 1, "high": 2}

        def score(c: GameCandidate) -> tuple[int, float, str]:
            v = variance_order.get(c.variance, 1)
            # Bonus for crash-style (very low variance)
            is_crash = "crash" in c.name.lower() or "aviator" in c.name.lower() or "mines" in c.name.lower()
            if is_crash and c.variance == "low":
                v = -1
            return (v, -c.rtp, c.name)

        eligible.sort(key=score)
        return eligible[0]

    def build_plan(
        self,
        wallet: Any,
        max_bet: float,
        candidates: list[GameCandidate] | None = None,
    ) -> WagerPlan:
        """
        Compute the wagering plan from current wallet state.

        Args:
            wallet: WalletSnapshot or dict with balance, bonus, rollover.
            max_bet: Maximum bet per round (from bonus rules).
            candidates: Optional list of game candidates. If None, uses default.
        """
        # Extract wallet fields
        if hasattr(wallet, "balance"):
            balance = float(wallet.balance)
            bonus = float(wallet.bonus)
            rollover = float(wallet.rollover)
        elif isinstance(wallet, dict):
            balance = float(wallet.get("balance", 0))
            bonus = float(wallet.get("bonus", 0))
            rollover = float(wallet.get("rollover", 0))
        else:
            raise TypeError(f"Unsupported wallet type: {type(wallet)}")

        if rollover <= 0:
            return WagerPlan(
                game=GameCandidate(game_id=0, name="none", provider="", rtp=1.0),
                stake=0.0,
                rounds_needed=0,
                expected_loss=0.0,
                estimated_time_s=0.0,
                strategy="no_rollover_remaining",
                remaining_rollover=0.0,
                max_bet=max_bet,
            )

        # Select game
        if candidates is None:
            candidates = self._default_candidates()

        game = self.select_game(candidates, max_bet, rollover)

        # Stake: use max_bet to minimize rounds
        stake = max_bet
        if game.max_bet > 0 and game.max_bet < stake:
            stake = game.max_bet

        # Effective RTP
        rtp = game.rtp
        house_edge = 1.0 - rtp

        # Rounds needed: rollover / stake (each bet counts toward rollover)
        rounds_needed = max(1, math.ceil(rollover / stake)) if stake > 0 else 0

        # Expected loss: house_edge * total_wagered
        total_wagered = stake * rounds_needed
        expected_loss = house_edge * total_wagered

        # Estimate time (default: API at 0.5s/bet)
        estimated_time = self.estimate_time(
            WagerPlan(
                game=game,
                stake=stake,
                rounds_needed=rounds_needed,
                expected_loss=expected_loss,
                estimated_time_s=0.0,
                strategy="flat_stake_max_bet",
                remaining_rollover=rollover,
                max_bet=max_bet,
            ),
            method="api",
        )

        # Use crash EV model for crash games
        strategy = "flat_stake_max_bet"
        if game.variance == "low" and "crash" in game.name.lower():
            ev_info = crash_cashout_ev(cashout=1.01, house_edge=house_edge)
            strategy = "crash_1x_cashout"

        return WagerPlan(
            game=game,
            stake=stake,
            rounds_needed=rounds_needed,
            expected_loss=round(expected_loss, 4),
            estimated_time_s=estimated_time,
            strategy=strategy,
            remaining_rollover=rollover,
            max_bet=max_bet,
        )

    def execute(
        self,
        plan: WagerPlan,
        *,
        auto_bet_fn: Optional[Callable[..., Any]] = None,
        browser_farm: Any = None,
        ws_client: Any = None,
        poll_interval: float = 2.0,
        max_rounds: int = 500,
    ) -> WagerResult:
        """
        Execute the wagering plan.

        Loop: place bet → poll wallet → check if rollover cleared → stop.

        Stop conditions:
        - Rollover ≤ 0 (success)
        - Balance < stake (broke)
        - max_rounds reached
        - Error from bet placement

        Adaptive: if losing streak > 3σ, switch game (if candidates available).
        """
        start_time = time.time()
        rounds_played = 0
        total_wagered = 0.0
        history: list[float] = []  # per-round P&L

        # Get starting balance
        balance_start = 0.0
        try:
            wallet = self._get_wallet()
            balance_start = self._get_balance(wallet)
        except Exception:  # noqa: BLE001
            balance_start = 0.0

        error = ""
        rollover_cleared = False

        for round_num in range(max_rounds):
            # Check stop conditions before betting
            if plan.stake <= 0:
                error = "stake is zero"
                break

            # Place bet
            bet_ok = False
            try:
                if auto_bet_fn:
                    result = auto_bet_fn(
                        game_id=plan.game.game_id,
                        stake=plan.stake,
                        use_bonus_balance=True,
                    )
                    bet_ok = bool(result.get("ok", result.get("bet_armed", False))) if isinstance(result, dict) else bool(result)
                elif ws_client and hasattr(ws_client, "send_spin"):
                    resp = ws_client.send_spin(plan.stake)
                    bet_ok = bool(resp.get("ok", False))
                elif browser_farm and hasattr(browser_farm, "click_spin"):
                    # Browser farm: click spin
                    if hasattr(browser_farm, "contexts"):
                        ctx = list(browser_farm._contexts.values())[0] if browser_farm._contexts else None
                        if ctx:
                            browser_farm.click_spin(ctx, clicks=1)
                            bet_ok = True
                elif self.scraper and hasattr(self.scraper, "auto_bet"):
                    result = self.scraper.auto_bet(
                        plan.game.game_id,
                        clicks=1,
                        use_bonus_balance=True,
                    )
                    bet_ok = bool(result.get("ok", result.get("bet_armed", False))) if isinstance(result, dict) else bool(result)
                elif self.scraper and hasattr(self.scraper, "start_game"):
                    result = self.scraper.start_game(plan.game.game_id, mode="REAL")
                    bet_ok = bool(result.get("ok", False)) if isinstance(result, dict) else bool(result)
                else:
                    error = "no bet method available"
                    break
            except Exception as exc:  # noqa: BLE001
                error = f"bet_error: {str(exc)[:200]}"
                break

            if not bet_ok:
                error = f"bet_failed_round_{round_num}"
                break

            rounds_played += 1
            total_wagered += plan.stake

            # Poll wallet
            time.sleep(poll_interval)
            try:
                wallet = self._get_wallet()
                current_balance = self._get_balance(wallet)
                round_pnl = current_balance - (balance_start + total_wagered - plan.stake)
                history.append(round_pnl)
            except Exception:  # noqa: BLE001
                history.append(0.0)

            # Check rollover
            remaining = self._check_rollover(wallet)
            if remaining <= 0:
                rollover_cleared = True
                break

            # Adaptive: check losing streak
            if len(history) >= 5 and self._losing_streak_check(history):
                # Switch game strategy — reduce stake slightly
                plan.stake = max(plan.stake * 0.8, 0.5)
                history = history[-3:]  # reset window

        # Final balance
        balance_end = 0.0
        try:
            wallet = self._get_wallet()
            balance_end = self._get_balance(wallet)
        except Exception:  # noqa: BLE001
            balance_end = balance_start

        duration = time.time() - start_time
        net_loss = balance_start - balance_end

        return WagerResult(
            success=rollover_cleared,
            rounds_played=rounds_played,
            total_wagered=round(total_wagered, 4),
            balance_start=round(balance_start, 4),
            balance_end=round(balance_end, 4),
            net_loss=round(net_loss, 4),
            rollover_cleared=rollover_cleared,
            error=error,
            duration_s=round(duration, 2),
        )

    def _check_rollover(self, wallet: Any) -> float:
        """Get remaining rollover from wallet."""
        if hasattr(wallet, "rollover"):
            return float(wallet.rollover)
        if isinstance(wallet, dict):
            return float(wallet.get("rollover", 0))
        return 0.0

    def _losing_streak_check(self, history: list[float]) -> bool:
        """
        Detect a losing streak by comparing the most recent 3 results
        against the mean of the *earlier* history.

        Returns True if the last 3 values are all positive but
        significantly below the mean of the preceding values
        (i.e. a downward trend relative to prior performance).
        """
        if len(history) < 5:
            return False

        last_3 = history[-3:]
        # All must be positive (losses in P&L terms)
        if any(x <= 0 for x in last_3):
            return False

        # Compare against the mean of everything before the last 3
        prior = history[:-3]
        if not prior:
            return False
        prior_mean = sum(prior) / len(prior)
        return all(x < prior_mean for x in last_3)

    def estimate_time(self, plan: WagerPlan, method: str = "api") -> float:
        """
        Estimate total execution time in seconds.

        Methods:
        - api: 0.5s per bet (HTTP call)
        - ws: 1.0s per bet (WebSocket round-trip)
        - browser: 3.0s per bet (Playwright click + render)
        """
        per_bet = {"api": 0.5, "ws": 1.0, "browser": 3.0}.get(method, 0.5)
        return round(plan.rounds_needed * per_bet, 1)

    def _get_wallet(self) -> Any:
        """Get current wallet snapshot from scraper."""
        try:
            return self.scraper.get_wallet_snapshot()
        except TypeError:
            return self.scraper.get_wallet_snapshot()
        except Exception:  # noqa: BLE001
            return {"balance": 0, "bonus": 0, "rollover": 0}

    def _get_balance(self, wallet: Any) -> float:
        """Extract balance from wallet object or dict."""
        if hasattr(wallet, "balance"):
            return float(wallet.balance)
        if isinstance(wallet, dict):
            return float(wallet.get("balance", 0))
        return 0.0

    def _default_candidates(self) -> list[GameCandidate]:
        """Default game candidates when none provided."""
        return [
            GameCandidate(
                game_id=1624,
                name="Mines",
                provider="Spribe",
                rtp=0.99,
                variance="low",
                notes="1 mine = ~99% RTP, lowest variance",
            ),
            GameCandidate(
                game_id=0,
                name="Aviator",
                provider="Spribe",
                rtp=0.99,
                variance="low",
                notes="1.01x cashout ≈ 99% RTP",
            ),
            GameCandidate(
                game_id=0,
                name="Baccarat",
                provider="Generic",
                rtp=0.989,
                variance="low",
                notes="Banker bet, 1.06% house edge",
            ),
            GameCandidate(
                game_id=0,
                name="High-RTP Slot",
                provider="Generic",
                rtp=0.965,
                variance="medium",
                notes="Generic 96.5% RTP slot",
            ),
        ]
