"""
Persistent headless browser farm for game play automation.

Maintains N Chromium contexts (one per account) with pre-warmed game iframes.
Supports batch spin clicking with configurable stake, timing jitter, and
idle gaps to mimic human behavior.

Falls back to this when WS replay is not available (Tier 3).
"""

from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BrowserContext:
    """A single browser context representing one account session."""

    context_id: str
    page: Any  # Playwright Page
    game_loaded: bool = False
    spin_count: int = 0
    stake: float = 1.0
    provider: str = ""
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity = time.time()


class BrowserFarm:
    """
    Persistent headless browser farm.

    Manages N Chromium contexts (one per account) with pre-warmed game
    iframes. Supports batch spin clicking with configurable stake, timing
    jitter, and idle gaps to mimic human behavior.
    """

    def __init__(
        self,
        max_contexts: int = 8,
        headless: bool = True,
        user_agent: str = "",
    ) -> None:
        self.max_contexts = max_contexts
        self.headless = headless
        self.user_agent = user_agent
        self._playwright: Any = None
        self._browser: Any = None
        self._contexts: dict[str, BrowserContext] = {}
        self._total_clicks = 0
        self._launched_at: float = 0.0
        self._launched = False

    def launch(self) -> None:
        """Start Playwright + browser instance."""
        if self._launched:
            return
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=launch_args,
        )
        self._launched = True
        self._launched_at = time.time()

    def acquire_context(
        self,
        account_id: str,
        user_agent: str = "",
    ) -> BrowserContext:
        """
        Get or create a browser context for the given account.

        If the context already exists, returns it (pre-warmed).
        Otherwise creates a new one with the specified user agent.
        """
        if account_id in self._contexts:
            ctx = self._contexts[account_id]
            ctx.touch()
            return ctx

        if not self._launched:
            self.launch()

        if len(self._contexts) >= self.max_contexts:
            # Evict oldest idle context
            oldest_id = min(
                self._contexts,
                key=lambda k: self._contexts[k].last_activity,
            )
            self.release_context(self._contexts[oldest_id])

        ua = user_agent or self.user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        pw_context = self._browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 720},
            locale="en-US",
            timezone_id="America/Sao_Paulo",
        )
        page = pw_context.new_page()
        ctx = BrowserContext(
            context_id=f"ctx-{account_id[:20]}-{uuid.uuid4().hex[:6]}",
            page=page,
        )
        self._contexts[account_id] = ctx
        return ctx

    def load_game(self, ctx: BrowserContext, game_url: str) -> bool:
        """Navigate to game URL and wait for the game iframe to load."""
        try:
            ctx.page.goto(game_url, wait_until="domcontentloaded", timeout=30_000)
            # Wait for game iframe (provider embeds in iframes)
            try:
                ctx.page.wait_for_selector("iframe", timeout=15_000)
            except Exception:  # noqa: BLE001
                # Some games don't use iframes — still OK
                pass
            # Wait for spin button or canvas to appear
            try:
                ctx.page.wait_for_selector(
                    "button, canvas, [class*='spin'], [class*='play'], [data-testid*='spin']",
                    timeout=10_000,
                )
            except Exception:  # noqa: BLE001
                pass
            ctx.game_loaded = True
            ctx.touch()
            return True
        except Exception:  # noqa: BLE001
            return False

    def click_spin(
        self,
        ctx: BrowserContext,
        clicks: int = 1,
        delay_ms: int = 300,
        jitter_ms: int = 200,
    ) -> int:
        """
        Click the spin button N times with configurable delay and jitter.

        Returns the actual number of successful clicks.
        """
        actual = 0
        for _ in range(clicks):
            try:
                # Try multiple selectors for the spin button
                clicked = self._click_spin_button(ctx.page)
                if clicked:
                    actual += 1
                    ctx.spin_count += 1
                    self._total_clicks += 1
                    ctx.touch()
            except Exception:  # noqa: BLE001
                pass
            # Delay with jitter
            delay = max(0, delay_ms + random.randint(-jitter_ms, jitter_ms))
            if delay > 0:
                time.sleep(delay / 1000.0)
        return actual

    def _click_spin_button(self, page: Any) -> bool:
        """Attempt to click the spin/play button. Returns True if successful."""
        selectors = [
            "button:has-text('Spin')",
            "button:has-text('Play')",
            "button:has-text('spin')",
            "button:has-text('play')",
            "[class*='spin-btn']",
            "[class*='spinButton']",
            "[data-testid*='spin']",
            "[data-testid*='play']",
            "button.spin",
            "button.play",
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=1000):
                    btn.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        # Fallback: click any prominent button in the game area
        try:
            btns = page.locator("button")
            count = btns.count()
            if count > 0:
                # Click the largest button (likely the spin button)
                btns.last.click(timeout=3000)
                return True
        except Exception:  # noqa: BLE001
            pass
        return False

    def set_stake(self, ctx: BrowserContext, stake: float) -> bool:
        """
        Try to set the bet amount via UI.

        Looks for input fields, select elements, or +/- buttons to adjust
        the stake. Returns True if stake was likely set.
        """
        ctx.stake = stake
        page = ctx.page
        try:
            # Try to find a bet/stake input
            input_selectors = [
                "input[type='number']",
                "input[placeholder*='bet']",
                "input[placeholder*='stake']",
                "[class*='stake'] input",
                "[class*='bet'] input",
                "[data-testid*='stake']",
                "[data-testid*='bet-amount']",
            ]
            for sel in input_selectors:
                try:
                    inp = page.locator(sel).first
                    if inp.is_visible(timeout=500):
                        inp.click()
                        inp.fill(str(stake))
                        inp.press("Tab")
                        return True
                except Exception:  # noqa: BLE001
                    continue

            # Try select/dropdown
            for sel in ("select[class*='stake']", "select[class*='bet']", "[role='listbox']"):
                try:
                    select = page.locator(sel).first
                    if select.is_visible(timeout=500):
                        # Try to select by value
                        select.select_option(label=str(stake), timeout=1000)
                        return True
                except Exception:  # noqa: BLE001
                    continue

            # Try +/- buttons to adjust
            # This is a best-effort: click + until we reach the target
            plus_sel = "button:has-text('+'), button:has-text('▲'), [class*='increase']"
            minus_sel = "button:has-text('-'), button:has-text('▼'), [class*='decrease']"
            try:
                plus = page.locator(plus_sel).first
                if plus.is_visible(timeout=500):
                    # Click a reasonable number of times
                    for _ in range(min(20, int(stake * 10))):
                        plus.click(timeout=500)
                        time.sleep(0.05)
                    return True
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            pass
        return False

    def release_context(self, ctx: BrowserContext) -> None:
        """Release a context back to the pool (close page)."""
        try:
            if ctx.page:
                ctx.page.close()
        except Exception:  # noqa: BLE001
            pass
        # Remove from pool
        for key, val in list(self._contexts.items()):
            if val is ctx:
                del self._contexts[key]
                break

    def shutdown(self) -> None:
        """Close all contexts and the browser."""
        for ctx in list(self._contexts.values()):
            self.release_context(ctx)
        try:
            if self._browser:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:  # noqa: BLE001
            pass
        self._launched = False

    def farm_stats(self) -> dict[str, Any]:
        """Return farm statistics."""
        return {
            "active_contexts": len(self._contexts),
            "max_contexts": self.max_contexts,
            "total_clicks": self._total_clicks,
            "uptime_s": round(time.time() - self._launched_at, 2) if self._launched_at else 0.0,
            "contexts": [
                {
                    "id": c.context_id,
                    "game_loaded": c.game_loaded,
                    "spin_count": c.spin_count,
                    "stake": c.stake,
                    "provider": c.provider,
                }
                for c in self._contexts.values()
            ],
        }

    def idle_gap(self, ctx: BrowserContext, min_s: float = 3.0, max_s: float = 8.0) -> None:
        """Random pause to mimic human idle time between actions."""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
        ctx.touch()
