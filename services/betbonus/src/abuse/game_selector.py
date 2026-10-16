"""
LLM-driven game selection for optimal bonus wagering.

Uses IronLLMClient to analyze the house's game catalog + bonus T&Cs
and select the optimal game for clearing rollover with minimum risk.

Falls back to deterministic heuristics when LLM is unavailable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from src.llm.json_extract import extract_json

log = logging.getLogger("betbonus.abuse.game_selector")

# Variance ordering (lower index = lower variance = safer for bonus clearing)
_VARIANCE_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "extreme": 3,
}

# LLM system prompt for game selection
_GAME_SELECT_SYSTEM = """You are an expert iGaming bonus-arbitrage strategist.
Given a list of candidate games and bonus T&C rules, select the SINGLE BEST game
for clearing the rollover requirement with minimum risk of busting the bankroll
or violating bonus terms.

Consider:
- RTP (higher is better for slow burn)
- Variance (lower is better for consistent rollover progress)
- Max bet cap (must fit within the bonus max_bet)
- Eligibility (game must be in the allowed game_types, or unrestricted)
- Rollover remaining (how many bets are needed at max_bet)

Respond with ONLY valid JSON (no markdown) in this schema:
{
  "game_id": "string or number (the selected game ID)",
  "game_name": "string",
  "provider": "string",
  "rtp": number,
  "variance": "low|medium|high|extreme",
  "reasoning": "string (2-4 sentences explaining why this game is optimal)",
  "confidence": number (0.0 to 1.0),
  "alternatives": [
    {"game_id": "...", "game_name": "...", "rtp": 0.0, "reason": "..."}
  ]
}
"""


@dataclass
class GameSelectionResult:
    """Result of game selection for bonus wagering."""

    game_id: int | str
    game_name: str
    provider: str
    rtp: float
    variance: str
    reasoning: str
    confidence: float = 0.5
    alternatives: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_name": self.game_name,
            "provider": self.provider,
            "rtp": self.rtp,
            "variance": self.variance,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "alternatives": self.alternatives,
        }


class GameSelector:
    """Selects optimal game for bonus rollover clearing.

    Parameters:
        llm: Optional IronLLMClient (or any object with .complete())
        profile: Optional HouseProfile for context (wagering rules, etc.)
    """

    def __init__(self, llm: Any = None, profile: Any = None):
        self.llm = llm
        self.profile = profile

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        candidates: list[dict],
        bonus_rules: dict,
        max_bet: float,
        rollover_remaining: float,
    ) -> GameSelectionResult:
        """Primary method: select the optimal game for clearing rollover.

        Args:
            candidates: list of game dicts with keys:
                game_id, name, provider, rtp, variance, eligible (bool)
            bonus_rules: dict with keys like:
                max_bet, game_types, wagering_multiple, slots_only
            max_bet: float — per-bet cap from bonus T&Cs
            rollover_remaining: float — remaining BRL to wager

        Returns:
            GameSelectionResult
        """
        if not candidates:
            return GameSelectionResult(
                game_id="", game_name="(none)", provider="",
                rtp=0.0, variance="unknown",
                reasoning="No candidate games available.",
                confidence=0.0,
            )

        # Try LLM path first
        if self.llm is not None:
            try:
                result = self._llm_select(candidates, bonus_rules, max_bet, rollover_remaining)
                if result is not None:
                    log.info("LLM selected game: %s (%s)", result.game_name, result.game_id)
                    return result
            except Exception as exc:
                log.warning("LLM game selection failed, falling back: %s", exc)

        # Deterministic fallback
        result = self._deterministic_select(candidates, max_bet, rollover_remaining)
        log.info("Deterministic selected game: %s (%s)", result.game_name, result.game_id)
        return result

    def rank_games(self, candidates: list[dict], max_bet: float) -> list[dict]:
        """Rank all candidate games by EV score (descending).

        Returns:
            list of dicts: {game_id, name, provider, rtp, variance, ev_score, eligible}
        """
        scored: list[dict] = []
        for g in candidates:
            rtp = float(g.get("rtp") or 0.96)
            variance = str(g.get("variance") or "medium")
            rounds_needed = max(1, int(100))  # default; caller can refine
            score = self.ev_score(rtp, variance, rounds_needed)
            eligible = bool(g.get("eligible", True))
            scored.append({
                "game_id": g.get("game_id"),
                "name": g.get("name") or g.get("game_name") or "",
                "provider": g.get("provider") or "",
                "rtp": rtp,
                "variance": variance,
                "ev_score": round(score, 6),
                "eligible": eligible,
            })
        scored.sort(key=lambda x: (x["eligible"], x["ev_score"]), reverse=True)
        return scored

    def ev_score(self, rtp: float, variance: str, rounds_needed: int) -> float:
        """Compute a composite EV score for a game.

        Higher score = better for bonus clearing (high RTP, low variance,
        sufficient rounds to clear without busting).

        Args:
            rtp: Return-to-player (0.90–1.00 typical)
            variance: "low" | "medium" | "high" | "extreme"
            rounds_needed: number of bets to clear rollover

        Returns:
            float score (higher is better)
        """
        # Base: RTP weight (higher RTP = slower loss)
        rtp_component = rtp * 0.6

        # Variance penalty (lower variance = safer)
        var_rank = _VARIANCE_ORDER.get(variance.lower(), 1)
        variance_component = (1.0 - var_rank / 4.0) * 0.25

        # Rounds factor: too few rounds = high variance risk;
        # too many rounds = time cost. Sweet spot ~50-500.
        if rounds_needed <= 0:
            rounds_component = 0.0
        elif rounds_needed < 10:
            rounds_component = 0.15  # very few rounds, high variance risk
        elif rounds_needed <= 500:
            rounds_component = 0.15  # sweet spot
        else:
            rounds_component = max(0.0, 0.15 - (rounds_needed - 500) / 10000)

        return rtp_component + variance_component + rounds_component

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_select(
        self,
        candidates: list[dict],
        bonus_rules: dict,
        max_bet: float,
        rollover: float,
    ) -> Optional[GameSelectionResult]:
        """Attempt LLM-based game selection. Returns None on failure."""
        prompt = self._build_prompt(candidates, bonus_rules, max_bet, rollover)
        messages = [
            {"role": "system", "content": _GAME_SELECT_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        # Call LLM — use .complete() if available, else .chat()
        try:
            if hasattr(self.llm, "complete"):
                result = self.llm.complete(
                    messages,
                    temperature=0.3,
                    max_tokens=2048,
                    timeout=60.0,
                    json_mode=True,
                )
                text = result.text if hasattr(result, "text") else str(result)
            elif hasattr(self.llm, "chat"):
                text = self.llm.chat(messages, temperature=0.3, max_tokens=2048)
            else:
                return None
        except Exception as exc:
            log.warning("LLM call failed: %s", exc)
            return None

        # Parse JSON from response
        parsed = extract_json(text)
        if not isinstance(parsed, dict) or parsed.get("parse_error"):
            log.warning("LLM returned invalid JSON: %s", str(parsed)[:200])
            return None

        # Validate game_id exists in candidates
        selected_id = parsed.get("game_id")
        if selected_id is None:
            return None

        # Find the matching candidate
        matched = None
        for c in candidates:
            if str(c.get("game_id")) == str(selected_id) or c.get("game_id") == selected_id:
                matched = c
                break

        if matched is None:
            # LLM hallucinated an ID — use deterministic fallback for ID
            log.warning("LLM selected unknown game_id=%s, using fallback", selected_id)
            return None

        return GameSelectionResult(
            game_id=matched.get("game_id", selected_id),
            game_name=str(parsed.get("game_name") or matched.get("name") or ""),
            provider=str(parsed.get("provider") or matched.get("provider") or ""),
            rtp=float(parsed.get("rtp") or matched.get("rtp") or 0.96),
            variance=str(parsed.get("variance") or matched.get("variance") or "medium"),
            reasoning=str(parsed.get("reasoning") or "LLM selection"),
            confidence=float(parsed.get("confidence") or 0.5),
            alternatives=[
                a for a in (parsed.get("alternatives") or [])
                if isinstance(a, dict)
            ],
        )

    def _build_prompt(
        self,
        candidates: list[dict],
        bonus_rules: dict,
        max_bet: float,
        rollover: float,
    ) -> str:
        """Construct the user prompt for LLM game selection."""
        # Limit candidates to top 30 by RTP to keep prompt manageable
        sorted_candidates = sorted(candidates, key=lambda g: float(g.get("rtp") or 0), reverse=True)
        top = sorted_candidates[:30]

        games_json = json.dumps(
            [
                {
                    "game_id": g.get("game_id"),
                    "name": g.get("name") or g.get("game_name"),
                    "provider": g.get("provider"),
                    "rtp": g.get("rtp"),
                    "variance": g.get("variance"),
                    "eligible": g.get("eligible", True),
                }
                for g in top
            ],
            ensure_ascii=False,
            indent=2,
        )

        rules_json = json.dumps(bonus_rules, ensure_ascii=False, indent=2, default=str)

        bets_needed = ""
        if max_bet > 0 and rollover > 0:
            bets_needed = int(-(-int(rollover * 100) // int(max_bet * 100)))

        return (
            f"BONUS RULES:\n{rules_json}\n\n"
            f"MAX BET: {max_bet}\n"
            f"ROLLOVER REMAINING: {rollover}\n"
            f"BETS NEEDED AT MAX BET: {bets_needed or 'N/A'}\n\n"
            f"CANDIDATE GAMES ({len(top)} shown, {len(candidates)} total):\n"
            f"{games_json}\n\n"
            "Select the single best game. Respond with JSON only."
        )

    # ------------------------------------------------------------------
    # Deterministic fallback
    # ------------------------------------------------------------------

    def _deterministic_select(
        self,
        candidates: list[dict],
        max_bet: float,
        rollover: float,
    ) -> GameSelectionResult:
        """Deterministic fallback: sort by RTP desc, variance asc, eligible first."""
        if not candidates:
            return GameSelectionResult(
                game_id="", game_name="(none)", provider="",
                rtp=0.0, variance="unknown",
                reasoning="No candidates.", confidence=0.0,
            )

        # Score and sort
        scored = self.rank_games(candidates, max_bet)
        best = scored[0]

        # Find original candidate for full details
        best_candidate = None
        for c in candidates:
            if c.get("game_id") == best["game_id"]:
                best_candidate = c
                break

        # Build alternatives (top 3 after best)
        alternatives = [
            {
                "game_id": s["game_id"],
                "game_name": s["name"],
                "rtp": s["rtp"],
                "reason": f"EV score {s['ev_score']:.4f}",
            }
            for s in scored[1:4]
        ]

        reasoning = (
            f"Selected {best['name']} (RTP {best['rtp']:.4f}, "
            f"variance {best['variance']}, EV score {best['ev_score']:.4f}). "
            f"Eligible: {best['eligible']}."
        )

        return GameSelectionResult(
            game_id=best["game_id"],
            game_name=best["name"],
            provider=best["provider"],
            rtp=best["rtp"],
            variance=best["variance"],
            reasoning=reasoning,
            confidence=0.6,  # deterministic = moderate confidence
            alternatives=alternatives,
        )
