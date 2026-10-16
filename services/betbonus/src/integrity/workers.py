"""Workers por eixo do produto Casino Online."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter, sleep
from typing import Any, Callable
from uuid import uuid4

from src.integrity.house import HouseAdapter, UnsupportedCapability, wallet_delta
from src.integrity.models import ScenarioResult, ScenarioSpec
from src.integrity.sims import crash_cashout_ev, table_suite


def _result(
    spec: ScenarioSpec,
    platform: str,
    *,
    mode: str,
    ok: bool,
    severity: str = "info",
    vulnerability: str = "",
    note: str = "",
    evidence: dict[str, Any] | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        id=str(uuid4()),
        scenario_id=spec.id,
        axis=spec.axis,
        platform=platform,
        title=spec.title,
        mode=mode,
        ok=ok,
        severity=severity,
        vulnerability=vulnerability,
        note=note or spec.note,
        evidence=evidence or {},
    )


def _unsupported(spec: ScenarioSpec, platform: str, exc: UnsupportedCapability) -> ScenarioResult:
    return _result(
        spec,
        platform,
        mode="UNSUPPORTED",
        ok=True,
        severity="medium",
        vulnerability=exc.capability,
        note=str(exc),
        evidence={"capability": exc.capability, "stack_note": exc.note},
    )


def _blocked(spec: ScenarioSpec, platform: str, exc: Exception) -> ScenarioResult:
    msg = str(exc)[:300]
    mode = "BLOCKED"
    sev = "high"
    if isinstance(exc, PermissionError):
        sev = "critical"
    return _result(
        spec,
        platform,
        mode=mode,
        ok=False,
        severity=sev,
        vulnerability="session_or_api_error",
        note=msg,
        evidence={"error": msg},
    )


class WorkerContext:
    def __init__(
        self,
        *,
        run_mode: str,
        confirm_real_bet: bool,
        confirm_real_withdraw: bool,
        max_lab_stake_brl: float,
        target_game: dict[str, Any] | None = None,
    ):
        self.run_mode = run_mode
        self.confirm_real_bet = confirm_real_bet
        self.confirm_real_withdraw = confirm_real_withdraw
        self.max_lab_stake_brl = max_lab_stake_brl
        self.target_game = target_game or None


def pinned_games(
    house: HouseAdapter,
    ctx: WorkerContext,
    category: str,
    *,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Usa o jogo da sessão se a categoria bater; senão o catálogo da categoria."""
    target = ctx.target_game if isinstance(ctx.target_game, dict) else None
    gid = None if not target else target.get("game_id")
    if gid is not None and str(gid).strip() != "" and _target_fits_category(target, category):
        return [
            {
                "game_id": gid,
                "name": target.get("name") or "",
                "provider": target.get("provider"),
                "slug": target.get("slug") or target.get("game_code"),
                "game_code": target.get("game_code") or target.get("slug"),
                "aggregator": target.get("aggregator"),
                "category": target.get("category") or target.get("category_hint"),
                "category_hint": target.get("category_hint") or target.get("category"),
                "source": "session_target",
            }
        ]
    return house.list_games(category, limit=limit)


def _target_fits_category(target: dict[str, Any] | None, category: str) -> bool:
    if not target:
        return False
    hint = str(
        target.get("category_hint") or target.get("category") or target.get("axis") or ""
    ).lower()
    if not hint:
        return True
    cat = (category or "").strip().lower()
    aliases = {
        "slots": ("slot", "slots"),
        "crash": ("crash", "instant"),
        "table": ("table", "tables", "live", "mesa"),
        "jackpot": ("jackpot",),
        "live": ("live", "table"),
    }
    needles = aliases.get(cat, (cat,))
    return any(n in hint for n in needles)


def launch_target(
    house: HouseAdapter,
    ctx: WorkerContext,
    *fallback_cats: str,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Em sessão de jogo, o alvo manda — senão o primeiro catálogo dos fallbacks."""
    target = ctx.target_game if isinstance(ctx.target_game, dict) else None
    if target and target.get("game_id") is not None and str(target.get("game_id")).strip() != "":
        hint = str(target.get("category_hint") or target.get("category") or "").lower()
        if any(n in hint for n in ("crash", "instant")):
            cat = "crash"
        elif any(n in hint for n in ("table", "tables", "live", "mesa")):
            cat = "table"
        elif "jackpot" in hint:
            cat = "jackpot"
        else:
            cat = "slots"
        return pinned_games(house, ctx, cat, limit=limit)
    for cat in fallback_cats or ("slots",):
        games = pinned_games(house, ctx, cat, limit=limit)
        if games:
            return games
    return []


def _game_launch_kwargs(game: Any) -> dict[str, Any]:
    if not isinstance(game, dict):
        return {}
    out: dict[str, Any] = {}
    code = game.get("slug") or game.get("game_code") or game.get("gameCode")
    if code:
        out["game_code"] = code
    if game.get("aggregator"):
        out["aggregator"] = game.get("aggregator")
    if game.get("name"):
        out["game_name"] = game.get("name")
    return out


def _call_start_game(house: HouseAdapter, game: Any, **kwargs: Any) -> dict[str, Any]:
    gid = game.get("game_id") if isinstance(game, dict) else game
    extra = _game_launch_kwargs(game)
    extra.update({k: v for k, v in kwargs.items() if v is not None})
    return house.start_game(gid, **extra)


def session_validate(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    auth = house.validate_session()
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        evidence={
            "keys": sorted(str(k) for k in auth.keys())[:20],
            "currency": auth.get("currency"),
            "mode": auth.get("mode"),
            "user_id": auth.get("user_id") or auth.get("person_id"),
            "warning": auth.get("warning"),
            "target_game": ctx.target_game,
        },
        note="Sessão válida (token omitido da evidência).",
    )


def session_zombie_launch(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    before = house.wallet_snapshot()
    games = launch_target(house, ctx, "crash", "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem jogo para launch")
    gid = games[0]["game_id"]
    launch = _call_start_game(house, games[0], mode="REAL", use_bonus=False)
    after = house.wallet_snapshot()
    delta = wallet_delta(before, after)
    vuln = "wallet_unchanged_after_real_launch" if not delta["changed"] else "wallet_moved_on_launch_only"
    sev = "medium" if not delta["changed"] else "high"
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity=sev,
        vulnerability=vuln,
        note="Launch não aposta no provider; delta de wallet mede sessão/ledger.",
        evidence={
            "game_id": gid,
            "launch_ok": bool(launch.get("url") or launch.get("token") or launch.get("ok")),
            "salsa": launch.get("launch") or {},
            "delta": delta,
        },
    )


def wallet_scale(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    snap = house.wallet_snapshot()
    raw = snap.raw if isinstance(snap.raw, dict) else {}
    raw_bal = raw.get("balance")
    ratio = None
    try:
        if raw_bal is not None and float(snap.balance) > 0:
            ratio = float(raw_bal) / float(snap.balance)
    except (TypeError, ValueError, ZeroDivisionError):
        ratio = None
    cents = ratio is not None and 90 <= ratio <= 110
    mixed = ratio is not None and not cents and abs(ratio - 1.0) > 0.05
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="high" if mixed else "info",
        vulnerability="currency_scale_mismatch" if mixed else "currency_scale_ok",
        evidence={
            "snapshot_balance": snap.balance,
            "snapshot_bonus": snap.bonus,
            "raw_balance": raw_bal,
            "ratio_raw_over_snapshot": ratio,
            "looks_like_cents": cents,
        },
    )


def wallet_double_fetch(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    a = house.wallet_snapshot()
    b = house.wallet_snapshot()
    delta = wallet_delta(a, b)
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if delta["changed"] else "info",
        vulnerability="ledger_moved_without_lab_action" if delta["changed"] else "ledger_stable",
        evidence={"delta": delta},
    )


def catalog_list(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for cat in ("slots", "crash", "table"):
        try:
            by_cat[cat] = house.list_games(cat, limit=4)
        except UnsupportedCapability as exc:
            by_cat[cat] = [{"unsupported": True, "note": str(exc)}]
    automated = any(
        isinstance(rows, list) and rows and not (isinstance(rows[0], dict) and rows[0].get("unsupported"))
        for rows in by_cat.values()
    )
    if not automated:
        raise UnsupportedCapability("list_games", house.platform, "nenhuma categoria listável")
    if ctx.target_game:
        by_cat["target"] = launch_target(house, ctx, "slots", limit=1)
    counts = {k: len(v) for k, v in by_cat.items()}
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        evidence={"counts": counts, "sample": {k: v[:2] for k, v in by_cat.items()}},
    )


def _launch_pair(house: HouseAdapter, game: Any, **kwargs: Any) -> dict[str, Any]:
    gid = game.get("game_id") if isinstance(game, dict) else game
    try:
        launch = _call_start_game(house, game, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:300], "mode": kwargs.get("mode"), "game_id": gid}
    salsa = launch.get("launch") or {}
    return {
        "ok": bool(launch.get("url") or launch.get("token") or salsa),
        "mode": launch.get("mode"),
        "use_bonus_balance": launch.get("use_bonus_balance"),
        "salsa_type": salsa.get("type"),
        "salsa_game": salsa.get("game"),
        "host": salsa.get("host"),
        "error": launch.get("error"),
        "url_host": salsa.get("host"),
        "game_id": gid,
        "game_code": launch.get("game_code"),
    }


def catalog_launch_modes(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    games = launch_target(house, ctx, "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem slot para launch")
    gid = games[0]["game_id"]
    free = _launch_pair(house, games[0], mode="FREE", use_bonus=False)
    real = _launch_pair(house, games[0], mode="REAL", use_bonus=False)
    free_err = str(free.get("error") or "")
    demo_off = "free_mode_not_available" in free_err.lower()
    if demo_off and real.get("ok"):
        return _result(
            spec,
            house.platform,
            mode="AUTOMATED",
            ok=True,
            severity="info",
            vulnerability="demo_disabled_by_provider",
            note="Provider recusou FREE/demo neste título. REAL lançou — política, não falha de sessão.",
            evidence={"game_id": gid, "free": free, "real": real},
        )
    if not real.get("ok"):
        return _result(
            spec,
            house.platform,
            mode="BLOCKED",
            ok=False,
            severity="high",
            vulnerability="real_launch_failed",
            note=str(real.get("error") or "REAL start.do falhou")[:300],
            evidence={"game_id": gid, "free": free, "real": real},
        )
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if free.get("ok") else "info",
        vulnerability="free_and_real_launch" if free.get("ok") else "free_mode_blocked",
        evidence={"game_id": gid, "free": free, "real": real},
    )


def catalog_bonus_flag(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    games = launch_target(house, ctx, "crash", "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem jogo para flag de bônus")
    gid = games[0]["game_id"]
    cash = _launch_pair(house, games[0], mode="REAL", use_bonus=False)
    bonus = _launch_pair(house, games[0], mode="REAL", use_bonus=True)
    both = bool(cash.get("ok") and bonus.get("ok"))
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="high" if both else "info",
        vulnerability="bonus_and_cash_both_launch" if both else "bonus_flag_restricted",
        evidence={"game_id": gid, "cash": cash, "bonus": bonus},
    )


def slots_soft_launch(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    games = launch_target(house, ctx, "slots", limit=3)
    probes = []
    for game in games:
        try:
            probes.append({**game, **_launch_pair(house, game, mode="REAL", use_bonus=True)})
        except UnsupportedCapability:
            raise
        except Exception as exc:  # noqa: BLE001
            probes.append({**game, "ok": False, "error": str(exc)[:200]})
    ok_n = sum(1 for p in probes if p.get("ok"))
    if not probes or ok_n == 0:
        err = next((str(p.get("error")) for p in probes if p.get("error")), "nenhum launch")
        return _result(
            spec,
            house.platform,
            mode="BLOCKED",
            ok=False,
            severity="high",
            vulnerability="slots_launch_failed",
            note=err[:300],
            evidence={"probed": len(probes), "launches_ok": ok_n, "probes": probes},
        )
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="info",
        vulnerability="slots_launch_ok_spin_manual",
        note="Spin no provider (Pragmatic/PG) não automatizado — SEMI no eixo play.",
        evidence={"probed": len(probes), "launches_ok": ok_n, "probes": probes},
    )


def slots_freespins(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    inv = house.freespin_inventory()
    count = int(inv.get("count") or 0)
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if count else "info",
        vulnerability="freespin_inventory_present" if count else "no_freespins_in_api",
        evidence=inv,
    )


def slots_bonus_buy_gap(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    return _result(
        spec,
        house.platform,
        mode="SEMI_AUTO",
        ok=True,
        severity="medium",
        vulnerability="provider_bonus_buy_not_automated",
        note=(
            "Bonus buy / autoplay / extra spin no cliente do provider exigem round-log "
            "oficial de operador. Sem reverse-engineer de WS."
        ),
        evidence={"confirm_real_bet": ctx.confirm_real_bet, "max_lab_stake_brl": ctx.max_lab_stake_brl},
    )


def slots_actor_surface(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    """Superfície que um ator usa sem girar: launch cash/bônus, demo, saldo Salsa vs wallet."""
    games = launch_target(house, ctx, "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem jogo alvo")
    gid = games[0]["game_id"]
    snap = house.wallet_snapshot()
    cash = _launch_pair(house, games[0], mode="REAL", use_bonus=False)
    bonus = _launch_pair(house, games[0], mode="REAL", use_bonus=True)
    free = _launch_pair(house, games[0], mode="FREE", use_bonus=False)
    race_a = _launch_pair(house, games[0], mode="REAL", use_bonus=False)
    race_b = _launch_pair(house, games[0], mode="REAL", use_bonus=False)
    basic: dict[str, Any] = {}
    scraper = getattr(house, "scraper", None)
    if scraper is not None and hasattr(scraper, "get_game_basic_info"):
        try:
            raw = scraper.get_game_basic_info(gid)
            if isinstance(raw, dict):
                basic = {
                    "name": raw.get("name"),
                    "provider": raw.get("gameProviderName"),
                    "volatility": raw.get("volatility"),
                    "max_win_amount": raw.get("maxWinAmount"),
                    "paid_today": raw.get("paidToday"),
                }
        except Exception as exc:  # noqa: BLE001
            basic = {"error": str(exc)[:160]}
    salsa_brl = None
    try:
        launch = _call_start_game(house, games[0], mode="REAL", use_bonus=False)
        salsa_brl = (launch.get("launch") or {}).get("balance_brl")
    except Exception:  # noqa: BLE001
        salsa_brl = None
    salsa_vs_wallet = None
    if salsa_brl is not None:
        salsa_vs_wallet = round(float(salsa_brl) - float(snap.balance), 4)
    bonus_flag_without_bonus = bool(bonus.get("ok") and float(snap.bonus or 0) <= 0.01)
    findings = []
    if bonus_flag_without_bonus:
        findings.append("useBonusBalance_true_with_empty_bonus")
    if cash.get("ok") and bonus.get("ok"):
        findings.append("cash_and_bonus_both_launch")
    if "free_mode_not_available" in str(free.get("error") or "").lower():
        findings.append("demo_disabled")
    if race_a.get("ok") and race_b.get("ok"):
        findings.append("double_start_accepted")
    if salsa_vs_wallet is not None and abs(salsa_vs_wallet) > 0.05:
        findings.append("salsa_balance_mismatch_wallet")
    sev = "high" if "useBonusBalance_true_with_empty_bonus" in findings or (
        salsa_vs_wallet is not None and abs(salsa_vs_wallet) > 0.05
    ) else "medium"
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity=sev,
        vulnerability="+".join(findings) or "actor_surface_ok",
        note="Probes de casa (launch/flag/race). Giro real está em slots.lab_play.",
        evidence={
            "game_id": gid,
            "wallet": {"balance": snap.balance, "bonus": snap.bonus, "rollover": snap.rollover},
            "salsa_balance_brl": salsa_brl,
            "salsa_minus_wallet": salsa_vs_wallet,
            "cash": cash,
            "bonus_flag": bonus,
            "free": {k: v for k, v in free.items() if k != "url"},
            "double_start": {"a": race_a.get("ok"), "b": race_b.get("ok")},
            "basic": basic,
            "findings": findings,
        },
    )


def _softswiss_hop(house: HouseAdapter, salsa_url: str) -> dict[str, Any]:
    """Salsa HTML → launch_options.game_url (SoftSwiss/a8r). Sem lobby_token na evidência."""
    from src.integrity.player import redact_url

    scraper = getattr(house, "scraper", None)
    if scraper is None or not hasattr(scraper, "resolve_provider_launch"):
        return {}
    try:
        raw = scraper.resolve_provider_launch(salsa_url)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}
    keys = [
        str(k)
        for k in (raw.get("raw_options_keys") or [])
        if "token" not in str(k).lower() and "session" not in str(k).lower()
    ]
    return {
        "provider_url": redact_url(str(raw.get("provider_url") or "")),
        "game": raw.get("game") or "",
        "option_keys": keys[:24],
        "error": raw.get("error"),
    }


def _provider_evidence(house: HouseAdapter, games: list[dict[str, Any]], launch: dict[str, Any], inspect: dict[str, Any]) -> dict[str, Any]:
    from src.integrity.player import catalog_vs_client, merge_launch_maps, redact_url

    salsa = launch.get("launch") or {}
    url = str(launch.get("url") or "")
    provider = inspect.get("provider") if isinstance(inspect.get("provider"), dict) else {}
    static = inspect.get("static") if isinstance(inspect.get("static"), dict) else {}
    merged = merge_launch_maps(provider, static)
    if provider.get("frames"):
        merged["frames"] = provider.get("frames")
    game = games[0] if games else {}
    chain = catalog_vs_client(
        str(game.get("provider") or ""),
        str(salsa.get("game") or ""),
        str(merged.get("game_client") or provider.get("game_client") or ""),
    )
    hop = {
        "has_softswiss_options": bool(provider.get("has_softswiss_options") or static.get("has_softswiss_options")),
        "note": "Sem segundo GET na URL Salsa (token de uso único).",
    }
    return {
        "game_id": game.get("game_id"),
        "name": game.get("name"),
        "salsa_game": salsa.get("game"),
        "salsa_type": salsa.get("type"),
        "launch_host": salsa.get("host") or redact_url(url),
        "launch_url": redact_url(url),
        "chain": chain,
        "softswiss": hop,
        "iframes": merged.get("iframes") or provider.get("iframes") or static.get("iframes") or [],
        "frames": merged.get("frames") or provider.get("frames") or [],
        "hosts": merged.get("hosts") or [],
        "endpoints": merged.get("endpoints") or [],
        "roles": merged.get("roles") or [],
        "game_client": chain.get("game_client") or merged.get("game_client"),
        "title": inspect.get("title"),
        "method": inspect.get("method"),
        "clicked": inspect.get("clicked"),
        "screenshot": inspect.get("screenshot"),
        "launch_error": inspect.get("launch_error") or "",
        "static": {k: v for k, v in static.items() if k != "endpoints"},
        "error": inspect.get("error") or inspect.get("reason"),
    }


def slots_provider_map(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    """Identifica iframe/hosts do provedor a partir do launch Salsa. Sem spin."""
    from src.integrity.player import inspect_launch

    games = launch_target(house, ctx, "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem jogo alvo")
    gid = games[0]["game_id"]
    if getattr(house, "stack", "") == "fake":
        return _result(
            spec,
            house.platform,
            mode="AUTOMATED",
            ok=True,
            vulnerability="provider_map_simulated",
            evidence={
                "game_id": gid,
                "simulated": True,
                "launch_host": "salsa.example",
                "game_client": "lab",
                "hosts": [{"host": "salsa.example", "role": "aggregator", "paths": ["/launch"]}],
                "endpoints": [{"host": "salsa.example", "path": "/launch", "role": "aggregator", "scheme": "https"}],
            },
        )
    try:
        launch = _call_start_game(house, games[0], mode="REAL", use_bonus=False)
    except Exception as exc:  # noqa: BLE001
        return _blocked(spec, house.platform, exc)
    url = str(launch.get("url") or "")
    inspect = inspect_launch(url, click_spin=False)
    ev = _provider_evidence(house, games, launch, inspect)
    mismatch = bool((ev.get("chain") or {}).get("mismatch"))
    client = str(ev.get("game_client") or "unknown")
    hosts_n = len(ev.get("hosts") or [])
    salsa_err = str(ev.get("launch_error") or "")
    flags: list[str] = []
    if mismatch:
        flags.append("catalog_provider_mismatch_iframe")
    if salsa_err:
        flags.append("salsa_provider_launch_error")
    if flags:
        sev = "high"
        vuln = "+".join(flags)
        note = (
            f"Catálogo={ev['chain'].get('catalog_provider')} · Salsa={ev['chain'].get('salsa_game')} "
            f"· cliente={client}."
        )
        if salsa_err:
            note += f" Launch Salsa falhou: {salsa_err}"
    elif client in {"unknown", "aggregator"} and hosts_n <= 1:
        sev, vuln = "medium", "provider_iframe_not_resolved"
        note = "Launch ficou no agregador (Salsa). Iframe do provedor não apareceu neste hop."
    else:
        sev, vuln = "info", "provider_endpoints_mapped"
        note = f"Cliente={client}; {hosts_n} hosts; query omitida."
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity=sev,
        vulnerability=vuln,
        note=note,
        evidence=ev,
    )


def slots_lab_play(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    """Stake real no iframe do provedor + medição de ledger.

    Usa house.auto_bet() quando disponível (multi-click, wallet polling
    integrada). Fallback: launch + try_player_spin (single-click).
    """
    from src.integrity.player import try_player_spin

    if not ctx.confirm_real_bet:
        return _result(
            spec,
            house.platform,
            mode="SKIPPED",
            ok=True,
            vulnerability="stake_cap",
            note="Marque «Jogar 1 spin» (CONFIRM_STAKE). Teto "
            f"R$ {ctx.max_lab_stake_brl:.2f}.",
        )
    games = launch_target(house, ctx, "slots", limit=1)
    if not games:
        raise UnsupportedCapability("list_games", house.platform, "sem jogo alvo")
    gid = games[0]["game_id"]
    if getattr(house, "stack", "") == "fake":
        return _result(
            spec,
            house.platform,
            mode="AUTOMATED",
            ok=True,
            vulnerability="lab_play_simulated",
            evidence={"game_id": gid, "simulated": True},
        )

    auto_bet_fn = getattr(house, "auto_bet", None)
    if callable(auto_bet_fn):
        # --- Path A: house provides auto_bet (multi-click + wallet polling) ---
        before = house.wallet_snapshot()
        try:
            bet = auto_bet_fn(gid, clicks=1, use_bonus=False, mode="REAL", timeout_ms=45000)
        except Exception as exc:  # noqa: BLE001
            return _blocked(spec, house.platform, exc)
        last = house.wallet_snapshot()
        delta = wallet_delta(before, last)
        abs_cash = abs(float(delta["balance"]))
        over_cap = abs_cash > float(ctx.max_lab_stake_brl) + 0.05
        n_clicks = int(bet.get("clicks") or 0)
        method = str(bet.get("method") or "")
        salsa_err = str(bet.get("launch_error") or "")
        empty_wallet = float(before.balance or 0) <= 0.01 and float(before.bonus or 0) <= 0.01
        ev: dict[str, Any] = {
            "game_id": gid,
            "max_lab_stake_brl": ctx.max_lab_stake_brl,
            "delta": delta,
            "moved": delta["changed"],
            "clicks": n_clicks,
            "method": method,
            "lab_wallet_empty": empty_wallet,
            "wallet_before": bet.get("wallet_before"),
            "wallet_after": bet.get("wallet_after"),
            "auto_bet": True,
        }
        if salsa_err:
            ev["launch_error"] = salsa_err
        if n_clicks > 0 and delta["changed"] and over_cap:
            sev, vuln, mode = "critical", "lab_spin_debit_above_cap", "AUTOMATED"
            note = (
                f"Ledger moveu R$ {delta['balance']} — acima do teto lab "
                f"R$ {ctx.max_lab_stake_brl:.2f}. Stake default do cliente pode ser alto."
            )
        elif delta["changed"]:
            sev, vuln, mode = "high", "lab_spin_wallet_moved", "AUTOMATED"
            note = (
                f"Spin/aposta refletiu no ledger (Δcash={delta['balance']} "
                f"Δbonus={delta['bonus']} Δroll={delta['rollover']}). "
                f"Conferir contribuição e maxBet."
            )
        elif salsa_err:
            sev, vuln, mode = "high", "salsa_provider_launch_error", "AUTOMATED"
            note = f"Salsa não entregou o iframe do jogo: {salsa_err}"
            if empty_wallet:
                note += " Carteira lab zerada."
        elif n_clicks > 0:
            sev, vuln, mode = "medium", "spin_clicked_wallet_unchanged", "SEMI_AUTO"
            note = (
                f"{n_clicks} clique(s) no provedor ({method}), carteira imóvel. "
                "Stake default pode estar em 0, overlay de intro, ou o giro não debitou."
            )
            if empty_wallet:
                note += " Carteira lab zerada — giro real não tem saldo."
        else:
            sev, vuln, mode = "medium", "lab_spin_iframe_not_clicked", "SEMI_AUTO"
            note = (
                str(bet.get("error") or "Sem alvo no iframe do provedor. ")
                + "Spin continua SEMI_AUTO."
            )
            if empty_wallet:
                note += " Carteira lab zerada."
        return _result(
            spec,
            house.platform,
            mode=mode,
            ok=True,
            severity=sev,
            vulnerability=vuln,
            note=note,
            evidence=ev,
        )

    # --- Path B: fallback — launch + try_player_spin (single-click) ---
    before = house.wallet_snapshot()
    try:
        launch = _call_start_game(house, games[0], mode="REAL", use_bonus=False)
    except Exception as exc:  # noqa: BLE001
        return _blocked(spec, house.platform, exc)
    url = str(launch.get("url") or "")
    play = try_player_spin(url, timeout_ms=45000)
    last = before
    moved = False
    for _ in range(6):
        sleep(2)
        last = house.wallet_snapshot()
        if wallet_delta(before, last)["changed"]:
            moved = True
            break
    delta = wallet_delta(before, last)
    abs_cash = abs(float(delta["balance"]))
    over_cap = abs_cash > float(ctx.max_lab_stake_brl) + 0.05
    ev = _provider_evidence(house, games, launch, play)
    ev["max_lab_stake_brl"] = ctx.max_lab_stake_brl
    ev["delta"] = delta
    ev["moved"] = moved
    empty_wallet = float(before.balance or 0) <= 0.01 and float(before.bonus or 0) <= 0.01
    ev["lab_wallet_empty"] = empty_wallet
    salsa_err = str(play.get("launch_error") or ev.get("launch_error") or "")
    if moved and over_cap:
        sev, vuln, mode = "critical", "lab_spin_debit_above_cap", "AUTOMATED"
        note = (
            f"Ledger moveu R$ {delta['balance']} — acima do teto lab "
            f"R$ {ctx.max_lab_stake_brl:.2f}. Stake default do cliente pode be alto."
        )
    elif moved:
        sev, vuln, mode = "high", "lab_spin_wallet_moved", "AUTOMATED"
        note = (
            f"Spin/aposta refletiu no ledger (Δcash={delta['balance']} Δbonus={delta['bonus']} "
            f"Δroll={delta['rollover']}). Conferir contribuição e maxBet."
        )
    elif salsa_err:
        sev, vuln, mode = "high", "salsa_provider_launch_error", "AUTOMATED"
        note = f"Salsa não entregou o iframe do jogo: {salsa_err}"
        if empty_wallet:
            note += " Carteira lab zerada."
    elif play.get("clicked"):
        sev, vuln, mode = "medium", "spin_clicked_wallet_unchanged", "SEMI_AUTO"
        note = (
            "Clique no canvas/iframe do provedor, carteira imóvel. "
            "Stake default pode estar em 0, overlay de intro, ou o giro não debitou."
        )
        if empty_wallet:
            note += " Carteira lab zerada — giro real não tem saldo."
    else:
        sev, vuln, mode = "medium", "lab_spin_iframe_not_clicked", "SEMI_AUTO"
        note = (
            str(play.get("reason") or play.get("error") or "Sem alvo no iframe do provedor. ")
            + f"Cliente mapeado={ev.get('game_client')}. Spin continua SEMI_AUTO."
        )
        if empty_wallet:
            note += " Carteira lab zerada."
    return _result(
        spec,
        house.platform,
        mode=mode,
        ok=True,
        severity=sev,
        vulnerability=vuln,
        note=note,
        evidence=ev,
    )


def crash_launch(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    games = pinned_games(house, ctx, "crash", limit=4)
    probes = []
    for game in games[:3]:
        try:
            probes.append({**game, **_launch_pair(house, game, mode="REAL", use_bonus=False)})
        except Exception as exc:  # noqa: BLE001
            probes.append({**game, "ok": False, "error": str(exc)[:200]})
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        vulnerability="crash_launch_ok_autobet_missing",
        note="Bet/cashout no Spribe SmartFox continua SEMI_AUTO.",
        evidence={"games": games[:4], "probes": probes},
    )


def crash_offline_model(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    model = {
        "2x": crash_cashout_ev(cashout=2.0),
        "5x": crash_cashout_ev(cashout=5.0),
        "10x": crash_cashout_ev(cashout=10.0),
    }
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        evidence=model,
        note="Modelo teórico. Live cashout vs tick = SEMI_AUTO.",
        vulnerability="crash_ev_independent_of_multiplier",
    )


def table_catalog(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    games = pinned_games(house, ctx, "table", limit=4)
    probes = []
    if games and house.capabilities().get("start_game"):
        try:
            probes.append(_launch_pair(house, games[0], mode="REAL", use_bonus=False))
        except UnsupportedCapability:
            probes.append({"mode": "UNSUPPORTED", "capability": "start_game"})
        except Exception as exc:  # noqa: BLE001
            probes.append({"ok": False, "error": str(exc)[:200]})
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        evidence={"games": games, "launch": probes},
        note="Bet-behind / side-bet live = SEMI_AUTO até round-log.",
    )


def table_offline_ev(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    suite = table_suite(bankroll=100.0, unit=1.0)
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        evidence=suite,
        vulnerability="negative_ev_all_table_models",
        note="Sims offline. Não apostam e não vencem house edge.",
    )


def timer_clock_skew(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    t0 = perf_counter()
    local_before = datetime.now(timezone.utc)
    snap = house.wallet_snapshot()
    elapsed_ms = round((perf_counter() - t0) * 1000, 1)
    fetched = snap.fetched_at
    skew_s = None
    if getattr(fetched, "tzinfo", None):
        skew_s = round((fetched - local_before).total_seconds(), 3)
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if elapsed_ms > 2500 else "info",
        evidence={
            "latency_ms": elapsed_ms,
            "local_utc": local_before.isoformat(),
            "fetched_at": fetched.isoformat() if hasattr(fetched, "isoformat") else str(fetched),
            "skew_seconds": skew_s,
        },
        vulnerability="slow_wallet_or_skew" if elapsed_ms > 2500 else "timer_ok",
    )


def timer_double_submit(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    t0 = perf_counter()
    a = house.wallet_snapshot()
    b = house.wallet_snapshot()
    elapsed_ms = round((perf_counter() - t0) * 1000, 1)
    delta = wallet_delta(a, b)
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="high" if delta["changed"] else "info",
        vulnerability="race_ledger_delta" if delta["changed"] else "double_get_stable",
        evidence={"elapsed_ms": elapsed_ms, "delta": delta},
    )


def promo_rules(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    inv = house.bonus_inventory()
    primary = inv.get("primary") if isinstance(inv, dict) else None
    exposed = bool(primary) or int(inv.get("count") or 0) > 0
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if exposed else "info",
        vulnerability="bonus_rules_exposed_via_api" if exposed else "no_active_bonus",
        evidence={
            "count": inv.get("count") if isinstance(inv, dict) else None,
            "primary": primary if isinstance(primary, dict) else None,
            "keys": sorted(inv.keys())[:20] if isinstance(inv, dict) else [],
        },
        note="Eixo promo — um vetor do produto cassino, não o produto inteiro.",
    )


def jackpot_catalog(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    try:
        state = house.jackpot_state()
    except UnsupportedCapability:
        games = house.list_games("jackpot", limit=4)
        state = {"games": games, "count": len(games), "source": "list_games"}
    count = int(state.get("count") or len(state.get("games") or []))
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="info",
        vulnerability="jackpot_titles_listed" if count else "jackpot_surface_empty",
        evidence=state,
        note="Crédito duplicado / desempate de torneio continua SEMI sem round-log.",
    )


def withdraw_preflight(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    if ctx.confirm_real_withdraw:
        return _result(
            spec,
            house.platform,
            mode="SKIPPED",
            ok=True,
            note="Integrity run não dispara saque real — use o oracle legado com confirm explícito.",
            vulnerability="withdraw_confirm_ignored_by_integrity",
        )
    data = house.withdraw_preflight()
    allowed = data.get("withdrawal_allowed")
    return _result(
        spec,
        house.platform,
        mode="AUTOMATED",
        ok=True,
        severity="medium" if allowed is False else "info",
        vulnerability="withdraw_preflight_gates",
        evidence={
            "keys": sorted(str(k) for k in data.keys())[:24],
            "withdrawal_allowed": allowed,
            "min_withdraw": data.get("min_withdraw"),
            "have_opened": data.get("have_opened"),
            "unsupported_full_preflight": data.get("unsupported_full_preflight"),
        },
        note="Sem POST de saque neste worker.",
    )


# Workers que não falam com a casa (modelo / gap documentado).
OFFLINE_WORKERS = {
    "crash_offline_model",
    "table_offline_ev",
    "slots_bonus_buy_gap",
}

WORKERS: dict[str, Callable[[HouseAdapter, ScenarioSpec, WorkerContext], ScenarioResult]] = {
    "session_validate": session_validate,
    "session_zombie_launch": session_zombie_launch,
    "wallet_scale": wallet_scale,
    "wallet_double_fetch": wallet_double_fetch,
    "catalog_list": catalog_list,
    "catalog_launch_modes": catalog_launch_modes,
    "catalog_bonus_flag": catalog_bonus_flag,
    "slots_soft_launch": slots_soft_launch,
    "slots_freespins": slots_freespins,
    "slots_bonus_buy_gap": slots_bonus_buy_gap,
    "slots_actor_surface": slots_actor_surface,
    "slots_provider_map": slots_provider_map,
    "slots_lab_play": slots_lab_play,
    "crash_launch": crash_launch,
    "crash_offline_model": crash_offline_model,
    "table_catalog": table_catalog,
    "table_offline_ev": table_offline_ev,
    "timer_clock_skew": timer_clock_skew,
    "timer_double_submit": timer_double_submit,
    "promo_rules": promo_rules,
    "jackpot_catalog": jackpot_catalog,
    "withdraw_preflight": withdraw_preflight,
}


def run_worker(house: HouseAdapter, spec: ScenarioSpec, ctx: WorkerContext) -> ScenarioResult:
    if ctx.run_mode == "DRY" and spec.mode != "DRY":
        return _result(
            spec,
            house.platform,
            mode="DRY",
            ok=True,
            note="Dry-run: worker não chamou a casa.",
            evidence={"worker": spec.worker, "would_mode": spec.mode},
        )
    if spec.requires_stake and not ctx.confirm_real_bet:
        return _result(
            spec,
            house.platform,
            mode="SKIPPED",
            ok=True,
            note="requires_stake sem confirm_real_bet",
            vulnerability="stake_cap",
        )
    fn = WORKERS.get(spec.worker)
    if fn is None:
        return _result(
            spec,
            house.platform,
            mode="UNSUPPORTED",
            ok=True,
            severity="low",
            vulnerability="missing_worker",
            note=f"Worker não implementado: {spec.worker}",
        )
    try:
        return fn(house, spec, ctx)
    except UnsupportedCapability as exc:
        return _unsupported(spec, house.platform, exc)
    except Exception as exc:  # noqa: BLE001
        return _blocked(spec, house.platform, exc)
