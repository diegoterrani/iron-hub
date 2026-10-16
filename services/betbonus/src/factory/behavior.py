"""
Per-account behavioral fingerprint for anti-detection.

Each account gets a unique behavioral profile that mimics a real human:
- Session duration, inter-bet delays, stake patterns, idle gaps,
  daily activity windows. No two accounts behave identically.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# User-Agent / device pools
# ---------------------------------------------------------------------------

_DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{minor}.{patch} Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{minor}.{patch} Safari/537.36 Edg/{edge}",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{safari}.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:{firefox}.0) Gecko/20100101 Firefox/{firefox}.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{minor}.{patch} Safari/537.36 OPR/{opera}",
]

_MOBILE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS {ios}_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ios}.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android {android}; {model}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{minor}.{patch} Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android {android}; {model}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome}.0.{minor}.{patch} Mobile Safari/537.36 OPR/{opera}.0",
    "Mozilla/5.0 (iPad; CPU OS {ios}_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ios}.0 Mobile/15E148 Safari/604.1",
]

_ANDROID_MODELS = [
    "SM-G991B", "SM-A525F", "SM-S908B", "Pixel 6", "Pixel 7",
    "Pixel 8", "Pixel 8 Pro", "M2102K2G", "CPH2581", "V2247",
    "23049RAD8", "SM-N986B", "SM-A325F", "RMX3355", "22081212C",
]

_SCREEN_SIZES = [
    (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
    (2560, 1440), (3840, 2160), (1080, 1920), (1080, 2340),
    (1080, 2400), (1170, 2532), (1290, 2796), (834, 1194),
]


# ---------------------------------------------------------------------------
# Profile dataclass
# ---------------------------------------------------------------------------

@dataclass
class BehavioralProfile:
    """A per-account behavioral fingerprint."""
    account_id: str
    seed: int
    session_duration_range: tuple[float, float]   # seconds
    inter_bet_delay: tuple[float, float]          # (mean_s, std_s)
    stake_pattern: str                            # "steady" | "variable" | "aggressive"
    idle_gap_range: tuple[float, float]           # (min_gap_s, max_gap_s)
    activity_window: tuple[int, int]              # (start_hour, end_hour), 0-23
    user_agent: str
    device_info: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fingerprint generator
# ---------------------------------------------------------------------------

class BehavioralFingerprint:
    """Generates unique behavioral profiles per account.

    Usage:
        fp = BehavioralFingerprint(seed=42)
        profile = fp.generate_profile("acct-1")
        duration = fp.session_duration(profile)
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Profile generation
    # ------------------------------------------------------------------

    def generate_profile(self, account_id: str, state: str = "BR") -> BehavioralProfile:
        """Create a unique behavioral profile for an account."""
        acct_seed = self._derive_seed(account_id)
        rng = random.Random(acct_seed)

        # Session duration: 5-15 min to 30 min-3 hours
        sess_min = rng.uniform(300, 900)
        sess_max = rng.uniform(1800, 10800)
        sess_max = max(sess_max, sess_min + 60)

        # Inter-bet delay: mean 15-120s, std 5-60s
        delay_mean = rng.uniform(15, 120)
        delay_std = rng.uniform(5, min(60, delay_mean * 0.5))

        # Stake pattern
        stake_pattern = rng.choices(
            ["steady", "variable", "aggressive"],
            weights=[0.45, 0.40, 0.15],
        )[0]

        # Idle gaps: 2-5 min to 10-60 min
        idle_min = rng.uniform(120, 300)
        idle_max = rng.uniform(600, 3600)
        idle_max = max(idle_max, idle_min + 60)

        # Activity window: weighted toward evening/night
        window_start = rng.choices(
            [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            weights=[1, 1, 2, 2, 3, 3, 2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 8, 6],
        )[0]
        window_duration = rng.uniform(3, 12)
        window_end = int((window_start + window_duration) % 24)
        if window_end <= window_start:
            window_end = (window_start + int(window_duration)) % 24

        # User agent + device
        ua, device = self._generate_device(rng)

        return BehavioralProfile(
            account_id=account_id,
            seed=acct_seed,
            session_duration_range=(round(sess_min, 1), round(sess_max, 1)),
            inter_bet_delay=(round(delay_mean, 1), round(delay_std, 1)),
            stake_pattern=stake_pattern,
            idle_gap_range=(round(idle_min, 1), round(idle_max, 1)),
            activity_window=(window_start, window_end),
            user_agent=ua,
            device_info=device,
        )

    def _derive_seed(self, account_id: str) -> int:
        """Derive a stable per-account seed from the global seed + account_id.

        Uses a throwaway RNG seeded from the global RNG's state so repeated
        calls for the same account are deterministic (does not consume
        self.rng state).
        """
        import hashlib
        digest = hashlib.sha256(str(self.rng.getstate()[1]).encode()).digest()
        base = int.from_bytes(digest[:8], "big")
        h = base
        for ch in account_id:
            h = (h * 31 + ord(ch)) & 0xFFFFFFFF
        return h

    def _generate_device(self, rng: random.Random) -> tuple[str, dict]:
        """Generate a plausible user-agent + device info dict."""
        is_mobile = rng.random() < 0.55
        fmt = dict(
            ios=rng.randint(15, 17),
            android=rng.randint(10, 14),
            model=rng.choice(_ANDROID_MODELS),
            chrome=rng.randint(115, 131),
            minor=rng.randint(0, 99),
            patch=rng.randint(0, 999),
            edge=rng.randint(115, 131),
            firefox=rng.randint(115, 131),
            safari=rng.randint(16, 17),
            opera=rng.randint(90, 108),
        )

        if is_mobile:
            template = rng.choice(_MOBILE_UAS)
            ua = template.format(**fmt)
            os_name = "iOS" if ("iPhone" in ua or "iPad" in ua) else "Android"
            browser = "Chrome" if "Chrome" in ua else ("Opera" if "OPR" in ua else "Safari")
            w, h = rng.choice(_SCREEN_SIZES)
            device = {
                "os": os_name,
                "browser": browser,
                "is_mobile": True,
                "screen": {"width": w, "height": h},
                "device_type": "phone" if "iPhone" in ua or "Android" in ua else "tablet",
            }
        else:
            template = rng.choice(_DESKTOP_UAS)
            ua = template.format(**fmt)
            os_name = (
                "Windows 10" if "Windows NT 10" in ua else
                "macOS" if "Macintosh" in ua else
                "Linux" if "Linux" in ua else "Windows 11"
            )
            browser = (
                "Chrome" if "Chrome" in ua else
                "Firefox" if "Firefox" in ua else
                "Safari" if "Safari" in ua and "Chrome" not in ua else
                "Edge" if "Edg" in ua else "Opera"
            )
            w, h = rng.choice(_SCREEN_SIZES)
            device = {
                "os": os_name,
                "browser": browser,
                "is_mobile": False,
                "screen": {"width": w, "height": h},
                "device_type": "desktop",
            }

        return ua, device

    # ------------------------------------------------------------------
    # Per-session random values
    # ------------------------------------------------------------------

    def session_duration(self, profile: BehavioralProfile) -> float:
        """Return a random session duration in seconds (log-normal, bounded)."""
        lo, hi = profile.session_duration_range
        if hi <= lo:
            return float(lo)
        mu = (math.log(lo) + math.log(hi)) / 2
        sigma = (math.log(hi) - math.log(lo)) / 4
        val = random.Random(profile.seed + 1000).lognormvariate(mu, sigma)
        return max(lo, min(hi, val))

    def inter_bet_delay(self, profile: BehavioralProfile) -> float:
        """Return a Gaussian inter-bet delay in seconds (always > 0)."""
        mean, std = profile.inter_bet_delay
        val = random.Random(profile.seed + 2000).gauss(mean, std)
        return max(0.5, val)

    def bet_stake_sequence(
        self,
        profile: BehavioralProfile,
        base_stake: float,
        n: int,
    ) -> list[float]:
        """Generate a sequence of n bet stakes following the profile's pattern."""
        rng = random.Random(profile.seed + 3000)
        stakes = [base_stake]
        current = base_stake

        if profile.stake_pattern == "steady":
            p_same, p_step, p_jump = 0.70, 0.20, 0.10
            jump_mult = (0.5, 2.0)
            step_delta = 1.0
        elif profile.stake_pattern == "variable":
            p_same, p_step, p_jump = 0.50, 0.30, 0.20
            jump_mult = (0.4, 2.5)
            step_delta = 1.0
        else:  # aggressive
            p_same, p_step, p_jump = 0.30, 0.30, 0.40
            jump_mult = (0.3, 3.0)
            step_delta = 2.0

        for _ in range(max(0, n - 1)):
            r = rng.random()
            if r < p_same:
                pass
            elif r < p_same + p_step:
                step = (base_stake / 10) * step_delta
                direction = rng.choice([-1, 1])
                current = max(base_stake / 10, current + direction * step)
            else:
                mult = rng.uniform(*jump_mult)
                current = max(base_stake / 10, current * mult)
            stakes.append(round(current, 2))

        return stakes

    def idle_gaps(
        self,
        profile: BehavioralProfile,
        total_duration: float,
    ) -> list[tuple[float, float]]:
        """Return a list of (offset_s, duration_s) tuples for 2-4 idle pauses."""
        rng = random.Random(profile.seed + 4000)
        n_gaps = rng.randint(2, 4)
        gaps: list[tuple[float, float]] = []

        for i in range(n_gaps):
            slot_min = (total_duration / n_gaps) * i * 0.8
            slot_max = max(slot_min + 1, total_duration - 60)
            if slot_max <= slot_min:
                slot_min, slot_max = 0.0, max(1.0, total_duration)
            offset = rng.uniform(slot_min, slot_max)
            lo, hi = profile.idle_gap_range
            duration = rng.uniform(lo, min(hi, max(lo + 1, total_duration - offset)))
            gaps.append((round(offset, 1), round(duration, 1)))

        gaps.sort(key=lambda g: g[0])
        return gaps

    def activity_window(
        self,
        profile: BehavioralProfile,
    ) -> tuple[datetime, datetime]:
        """Return today's active window as (start_dt, end_dt)."""
        now = datetime.now(timezone.utc)
        start_h, end_h = profile.activity_window
        start_dt = now.replace(hour=start_h, minute=0, second=0, microsecond=0)
        end_dt = now.replace(hour=end_h, minute=0, second=0, microsecond=0)
        if end_dt <= start_dt:
            # Overnight window
            end_dt += timedelta(days=1)
        return start_dt, end_dt

    def is_active_now(self, profile: BehavioralProfile) -> bool:
        """Check if the current time falls within the profile's activity window."""
        now = datetime.now(timezone.utc)
        start_dt, end_dt = self.activity_window(profile)
        return start_dt <= now <= end_dt

    def to_dict(self, profile: BehavioralProfile) -> dict:
        """Serialize a profile to a JSON-friendly dict."""
        return {
            "account_id": profile.account_id,
            "seed": profile.seed,
            "session_duration_range": list(profile.session_duration_range),
            "inter_bet_delay": list(profile.inter_bet_delay),
            "stake_pattern": profile.stake_pattern,
            "idle_gap_range": list(profile.idle_gap_range),
            "activity_window": list(profile.activity_window),
            "user_agent": profile.user_agent,
            "device_info": profile.device_info,
        }
