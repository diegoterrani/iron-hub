from src.integrity.models import AXES, HOUSES, build_coverage
from src.integrity.planner import heuristic_next
from src.integrity.runner import IntegrityRunner
from src.integrity.catalog import load_catalog
from tests.fake_house import FakeHouse


def test_dry_run_does_not_call_house():
    called = {"n": 0}

    def factory(platform: str) -> FakeHouse:
        called["n"] += 1
        house = FakeHouse()
        house.platform = platform
        return house

    runner = IntegrityRunner(factory)
    run = runner.run(houses=["pagol_bet_br"], run_mode="DRY")
    assert called["n"] == 1
    assert run.results
    assert all(r.mode in {"DRY", "AUTOMATED"} for r in run.results)
    # Offline sims still run as AUTOMATED even in DRY? Looking at run_worker:
    # if ctx.run_mode == "DRY" and spec.mode != "DRY": return DRY
    # specs with mode DRY (crash.cashout_model, table.offline_ev) still execute workers.
    dry = [r for r in run.results if r.mode == "DRY"]
    auto = [r for r in run.results if r.mode == "AUTOMATED"]
    assert dry
    assert auto  # offline models
    assert all("token" not in str(r.evidence).lower() for r in run.results)


def test_probe_fake_house_covers_axes():
    def factory(platform: str) -> FakeHouse:
        h = FakeHouse()
        h.platform = platform
        return h

    runner = IntegrityRunner(factory)
    run = runner.run(houses=["pagol_bet_br"], run_mode="PROBE")
    axes = {r.axis for r in run.results}
    assert set(AXES) <= axes
    assert all(r.mode != "BLOCKED" for r in run.results)
    automated = [r for r in run.results if r.mode == "AUTOMATED"]
    semi = [r for r in run.results if r.mode == "SEMI_AUTO"]
    assert automated
    assert semi  # bonus buy gap
    cov = run.coverage["cells"]["pagol_bet_br"]
    assert cov["session"]["mode"] in {"AUTOMATED", "SEMI_AUTO"}
    assert cov["promo"]["count"] >= 1


def test_unsupported_list_games():
    def factory(platform: str) -> FakeHouse:
        h = FakeHouse(games=False, start=False)
        h.platform = platform
        return h

    runner = IntegrityRunner(factory)
    run = runner.run(
        houses=["pagol_bet_br"],
        axes=["catalog"],
        run_mode="PROBE",
    )
    assert run.results
    assert any(r.mode == "UNSUPPORTED" for r in run.results)


def test_kill_switch():
    cat = load_catalog()
    cat.safety.kill_switch["pagol_bet_br"] = True

    def factory(platform: str) -> FakeHouse:
        raise AssertionError("não deve instanciar casa com kill_switch")

    runner = IntegrityRunner(factory, catalog=cat)
    run = runner.run(houses=["pagol_bet_br"], run_mode="PROBE")
    assert run.results
    assert all(r.mode == "SKIPPED" for r in run.results)
    assert all(r.vulnerability == "kill_switch" for r in run.results)


def test_coverage_matrix_shape():
    from src.integrity.models import ScenarioResult

    rows = [
        ScenarioResult(
            id="1",
            scenario_id="session.validate",
            axis="session",
            platform="pagol_bet_br",
            title="t",
            mode="AUTOMATED",
            ok=True,
            severity="info",
        ),
        ScenarioResult(
            id="2",
            scenario_id="slots.gap",
            axis="slots",
            platform="pagol_bet_br",
            title="t",
            mode="SEMI_AUTO",
            ok=True,
            severity="medium",
        ),
    ]
    cov = build_coverage(rows, list(HOUSES[:1]), ["session", "slots", "crash"])
    assert cov["cells"]["pagol_bet_br"]["session"]["mode"] == "AUTOMATED"
    assert cov["cells"]["pagol_bet_br"]["slots"]["mode"] == "SEMI_AUTO"
    assert cov["cells"]["pagol_bet_br"]["crash"]["mode"] == "SKIPPED"


def test_probe_without_session_is_auth_required():
    def factory(platform: str):
        raise PermissionError("Sem token PAGOL")

    runner = IntegrityRunner(factory)
    run = runner.run(houses=["pagol_bet_br"], run_mode="PROBE", require_auth=True)
    blocked = [r for r in run.results if r.vulnerability == "auth_required"]
    assert blocked
    assert all(r.mode in {"BLOCKED", "SKIPPED"} for r in run.results)


def test_probe_expired_session_blocks_live_workers():
    class DeadSession(FakeHouse):
        def validate_session(self):
            raise PermissionError("JWT expirado")

    runner = IntegrityRunner(lambda p: DeadSession())
    run = runner.run(houses=["pagol_bet_br"], run_mode="PROBE", require_auth=True)
    blocked = [r for r in run.results if r.vulnerability == "auth_required"]
    offline = [r for r in run.results if r.mode == "AUTOMATED"]
    assert blocked
    assert offline
    assert all(r.mode == "BLOCKED" for r in blocked)


def test_heuristic_planner_prefers_blocked():
    cat = load_catalog()
    runner = IntegrityRunner(lambda p: FakeHouse())
    run = runner.run(houses=["pagol_bet_br"], axes=["slots"], run_mode="PROBE")
    run.results[0].mode = "BLOCKED"
    run.results[0].ok = False
    plan = heuristic_next(run, cat)
    assert plan["next_scenario_id"] == run.results[0].scenario_id
    assert plan["source"] == "heuristic"


def test_game_session_pins_target_and_report():
    runner = IntegrityRunner(lambda p: FakeHouse())
    run = runner.run(
        houses=["pagol_bet_br", "4play"],
        run_mode="PROBE",
        target_game={"game_id": 777, "name": "Sweet Lab", "house": "pagol_bet_br", "provider": "lab"},
    )
    assert run.kind == "game_session"
    assert run.houses == ["pagol_bet_br"]
    pinned = [r for r in run.results if r.evidence.get("game_id") == 777]
    assert pinned
    from src.integrity.report import build_integrity_markdown

    md = build_integrity_markdown(run.to_dict())
    assert "Sweet Lab" in md
    assert "777" in md
    assert "game_session" in md


def test_free_mode_not_available_is_policy_not_blocked():
    class NoDemo(FakeHouse):
        def start_game(self, game_id, *, mode: str = "REAL", use_bonus=None, **kwargs):
            if mode == "FREE":
                raise RuntimeError(
                    'HTTP 400 on /games/start.do: free_mode_not_available Free mode is not available'
                )
            return super().start_game(game_id, mode=mode, use_bonus=use_bonus)

    runner = IntegrityRunner(lambda p: NoDemo())
    run = runner.run(
        houses=["pagol_bet_br"],
        axes=["catalog"],
        scenario_ids=["catalog.launch_free_vs_real"],
        run_mode="PROBE",
    )
    row = run.results[0]
    assert row.mode == "AUTOMATED"
    assert row.ok
    assert row.vulnerability == "demo_disabled_by_provider"


def test_lab_play_skips_without_confirm_and_runs_on_fake():
    runner = IntegrityRunner(lambda p: FakeHouse())
    skipped = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="PROBE",
    )
    assert skipped.results[0].mode == "SKIPPED"
    played = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    assert played.confirm_real_bet
    assert played.results[0].mode == "AUTOMATED"
    assert played.results[0].vulnerability == "lab_play_simulated"


def test_fourplay_house_maps_casino_catalog():
    from src.integrity.adapters import FourPlayHouse

    class FakeScraper:
        def list_casino_games(self, **kwargs):
            q = str(kwargs.get("search") or "").lower()
            items = [
                {
                    "id": 3007,
                    "gameName": "Gates of Olympus",
                    "gameCode": "prag-slot-GatesofOlympus",
                    "provider": "PRAGMATIC",
                    "aggregator": "salsa",
                    "category": "Slot",
                    "live": 0,
                    "banner": "https://cdn.4play.game/x.webp",
                },
                {
                    "id": 15,
                    "gameName": "JetX",
                    "gameCode": "sms-tb-jetx",
                    "provider": "SMARTSOFT",
                    "aggregator": "salsa",
                    "category": "Crash",
                    "live": 0,
                },
            ]
            if q:
                items = [i for i in items if q in i["gameName"].lower()]
            if kwargs.get("category") == "Crash":
                items = [i for i in items if i["category"] == "Crash"]
            return {"items": items, "total": len(items), "page": 1, "perPage": 50}

    house = FourPlayHouse(FakeScraper())  # type: ignore[arg-type]
    catalog = house.list_catalog(query="olympus", limit=10)
    assert catalog[0]["game_id"] == 3007
    assert catalog[0]["slug"] == "prag-slot-GatesofOlympus"
    crash = house.list_games("crash", limit=5)
    assert crash[0]["name"] == "JetX"
    assert house.capabilities()["start_game"]


def test_fourplay_start_game_posts_game_code_and_parses_salsa():
    from src.scrapers.fourplay_scraper import FourPlayScraper

    class LaunchScraper(FourPlayScraper):
        def __init__(self):
            super().__init__(delay=0, token="lab-token")
            self.posted = None

        def list_casino_games(self, **kwargs):
            return {
                "items": [
                    {
                        "id": 2677,
                        "gameName": "Joker´s Jewels",
                        "gameCode": "prag-slot-jokersJewels",
                        "provider": "PRAGMATIC",
                        "aggregator": "salsa",
                        "category": "Slot",
                    }
                ],
                "total": 1,
                "page": 1,
                "perPage": 50,
            }

        def _request(self, method, path, **kwargs):
            self.posted = (method, path, kwargs.get("json"))
            return {
                "status": 200,
                "data": {
                    "url": (
                        "https://api.salsagator.com/game?game=vs20jewels"
                        "&type=CHARGED&balance=97910&token=SECRET"
                    )
                },
            }

    scraper = LaunchScraper()
    out = scraper.start_game(
        2677,
        mode="REAL",
        game_code="prag-slot-jokersJewels",
        aggregator="salsa",
    )
    assert scraper.posted[0] == "POST"
    assert scraper.posted[1] == "/casino/game/launch"
    assert scraper.posted[2]["gameCode"] == "prag-slot-jokersJewels"
    assert scraper.posted[2]["walletType"] == 1
    assert scraper.posted[2]["aggregator"] == "salsa"
    assert out["launch"]["host"] == "api.salsagator.com"
    assert out["launch"]["game"] == "vs20jewels"
    assert "SECRET" not in str(out["launch"])
    scraper.start_game(2677, mode="FREE", game_code="prag-slot-jokersJewels")
    assert scraper.posted[2]["forFun"] is True
    scraper.start_game(2677, mode="REAL", use_bonus_balance=True, game_code="prag-slot-jokersJewels")
    assert scraper.posted[2]["walletType"] == 2


def test_pinned_games_does_not_force_slot_onto_crash():
    from src.integrity.workers import WorkerContext, pinned_games

    house = FakeHouse()
    ctx = WorkerContext(
        run_mode="PROBE",
        confirm_real_bet=False,
        confirm_real_withdraw=False,
        max_lab_stake_brl=5.0,
        target_game={
            "game_id": 2677,
            "name": "Joker´s Jewels",
            "slug": "prag-slot-jokersJewels",
            "category_hint": "slot",
        },
    )
    crash = pinned_games(house, ctx, "crash", limit=1)
    assert crash[0]["game_id"] != 2677
    slots = pinned_games(house, ctx, "slots", limit=1)
    assert slots[0]["game_id"] == 2677
    assert slots[0]["slug"] == "prag-slot-jokersJewels"


def test_launch_target_keeps_session_slot_off_crash_fallback():
    from src.integrity.workers import WorkerContext, launch_target

    house = FakeHouse()
    ctx = WorkerContext(
        run_mode="PROBE",
        confirm_real_bet=False,
        confirm_real_withdraw=False,
        max_lab_stake_brl=5.0,
        target_game={
            "game_id": 2677,
            "name": "Joker´s Jewels",
            "slug": "prag-slot-jokersJewels",
            "category_hint": "slot",
        },
    )
    games = launch_target(house, ctx, "crash", "slots", limit=1)
    assert games[0]["game_id"] == 2677


def test_slots_soft_launch_blocked_when_launches_fail():
    class DeadLaunch(FakeHouse):
        def start_game(self, game_id, *, mode: str = "REAL", use_bonus=None, **kwargs):
            raise RuntimeError("start_game UNSUPPORTED")

    runner = IntegrityRunner(lambda _p: DeadLaunch())
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.soft_launch"],
        run_mode="PROBE",
    )
    row = run.results[0]
    assert row.ok is False
    assert row.mode == "BLOCKED"
    assert row.vulnerability == "slots_launch_failed"
    assert row.evidence["launches_ok"] == 0


# ---------------------------------------------------------------------------
# GAP 04: stake worker — house.auto_bet() path
# ---------------------------------------------------------------------------


class _AutoBetHouse(FakeHouse):
    """FakeHouse that provides auto_bet() like PagolHouse does."""

    stack = "salsa"

    def __init__(self, *, clicks: int = 1, delta_balance: float = 0.0, **kw):
        super().__init__(**kw)
        self._clicks = clicks
        self._delta_balance = delta_balance
        self.auto_bet_calls: list[dict] = []

    def auto_bet(self, game_id, *, clicks=1, use_bonus=False, mode="REAL", timeout_ms=45000):
        self.auto_bet_calls.append(
            {"game_id": game_id, "clicks": clicks, "use_bonus": use_bonus, "mode": mode}
        )
        wallet_before = self.wallet_snapshot()
        if self._delta_balance:
            self.balance += self._delta_balance
        wallet_after = self.wallet_snapshot()
        return {
            "ok": self._clicks > 0,
            "game_id": game_id,
            "clicks": self._clicks,
            "method": "iframe_button:spin" if self._clicks else "none",
            "launch_error": "",
            "wallet_before": wallet_before.model_dump(mode="json"),
            "wallet_after": wallet_after.model_dump(mode="json"),
            "wallet_delta": {
                "balance": self._delta_balance,
                "bonus": 0.0,
            },
        }


def test_stake_worker_uses_auto_bet_when_available():
    """When house has auto_bet, slots_lab_play uses it (Path A)."""
    house = _AutoBetHouse(clicks=1, delta_balance=-1.5)
    runner = IntegrityRunner(lambda _p: house)
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    row = run.results[0]
    assert row.mode == "AUTOMATED"
    assert row.vulnerability == "lab_spin_wallet_moved"
    assert row.evidence["auto_bet"] is True
    assert row.evidence["clicks"] == 1
    assert row.evidence["delta"]["balance"] == -1.5
    # auto_bet was called with correct params
    assert len(house.auto_bet_calls) == 1
    assert house.auto_bet_calls[0]["game_id"] == 1624
    assert house.auto_bet_calls[0]["use_bonus"] is False
    assert house.auto_bet_calls[0]["mode"] == "REAL"


def test_stake_worker_over_cap_detected():
    """Wallet delta exceeding max_lab_stake_brl → critical."""
    house = _AutoBetHouse(clicks=1, delta_balance=-9.99)
    runner = IntegrityRunner(lambda _p: house)
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    row = run.results[0]
    assert row.mode == "AUTOMATED"
    assert row.severity == "critical"
    assert row.vulnerability == "lab_spin_debit_above_cap"


def test_stake_worker_clicked_but_wallet_unchanged():
    """Clicks > 0 but no wallet delta → SEMI_AUTO."""
    house = _AutoBetHouse(clicks=1, delta_balance=0.0)
    runner = IntegrityRunner(lambda _p: house)
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    row = run.results[0]
    assert row.mode == "SEMI_AUTO"
    assert row.vulnerability == "spin_clicked_wallet_unchanged"
    assert row.evidence["auto_bet"] is True


def test_stake_worker_no_click_detected():
    """Clicks == 0 → SEMI_AUTO, not clicked."""
    house = _AutoBetHouse(clicks=0, delta_balance=0.0)
    runner = IntegrityRunner(lambda _p: house)
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    row = run.results[0]
    assert row.mode == "SEMI_AUTO"
    assert row.vulnerability == "lab_spin_iframe_not_clicked"


def test_stake_worker_auto_bet_error_blocked():
    """auto_bet raising → BLOCKED."""

    class _ErrAutoBet(FakeHouse):
        stack = "salsa"

        def auto_bet(self, game_id, *, clicks=1, use_bonus=False, mode="REAL", timeout_ms=45000):
            raise RuntimeError("browser crashed")

    runner = IntegrityRunner(lambda _p: _ErrAutoBet())
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.lab_play"],
        run_mode="CONFIRM_STAKE",
        confirm_real_bet=True,
        target_game={"game_id": 1624, "name": "Fake slots 1", "house": "pagol_bet_br"},
    )
    row = run.results[0]
    assert row.mode == "BLOCKED"
    assert row.ok is False


def test_pagol_house_has_auto_bet_capability():
    """PagolHouse exposes auto_bet delegating to scraper."""
    from src.integrity.adapters import PagolHouse

    class _FakeScraper:
        def auto_bet(self, game_id, *, clicks=1, use_bonus_balance=False, mode="REAL", timeout_ms=45000):
            return {"ok": True, "game_id": game_id, "clicks": clicks, "method": "iframe_button:spin"}

    house = PagolHouse(_FakeScraper())  # type: ignore[arg-type]
    out = house.auto_bet(99, clicks=3, use_bonus=True)
    assert out["clicks"] == 3
    assert out["game_id"] == 99
    assert out["method"] == "iframe_button:spin"
