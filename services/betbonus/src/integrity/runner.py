from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional

from src.integrity.catalog import load_catalog
from src.integrity.house import HouseAdapter
from src.integrity.models import (
    AXES,
    HOUSES,
    Catalog,
    IntegrityRun,
    ScenarioResult,
    build_coverage,
)
from src.integrity.workers import OFFLINE_WORKERS, WorkerContext, run_worker

HouseFactory = Callable[[str], HouseAdapter]


class IntegrityRunner:
    def __init__(
        self,
        house_factory: HouseFactory,
        *,
        catalog: Optional[Catalog] = None,
        catalog_path: str | None = None,
    ):
        self.house_factory = house_factory
        self.catalog = catalog or load_catalog(catalog_path)

    def run(
        self,
        *,
        houses: Optional[list[str]] = None,
        axes: Optional[list[str]] = None,
        scenario_ids: Optional[list[str]] = None,
        run_mode: str = "PROBE",
        confirm_real_bet: bool = False,
        confirm_real_withdraw: bool = False,
        require_auth: bool = True,
        target_game: Optional[dict[str, Any]] = None,
    ) -> IntegrityRun:
        safety = self.catalog.safety
        selected_houses = [h for h in (houses or self.catalog.houses) if h in HOUSES]
        selected_axes = [a for a in (axes or self.catalog.axes) if a in AXES]
        mode = (run_mode or safety.default_mode or "PROBE").upper()
        if mode not in {"DRY", "PROBE", "CONFIRM_STAKE"}:
            mode = "PROBE"
        if mode != "CONFIRM_STAKE":
            confirm_real_bet = False
        confirm_real_bet = bool(confirm_real_bet and safety.max_lab_stake_brl > 0)
        confirm_real_withdraw = False  # integrity never withdraws

        if mode == "DRY":
            require_auth = False
        target = dict(target_game or {})
        if target.get("game_id") is not None:
            house_pin = str(target.get("house") or "")
            if house_pin in HOUSES:
                selected_houses = [house_pin]
            selected_houses = selected_houses[:1]
        run = IntegrityRun(
            run_mode=mode,
            confirm_real_bet=confirm_real_bet,
            confirm_real_withdraw=confirm_real_withdraw,
            houses=selected_houses,
            axes=selected_axes,
            target_game=target,
            kind="game_session" if target.get("game_id") is not None else "house",
        )
        run.notes.append(
            "PROBE autenticado" if require_auth and mode == "PROBE" else f"modo {mode} (auth opcional)"
        )
        if target.get("game_id") is not None:
            run.notes.append(
                f"Sessão de jogo: {target.get('name') or target.get('game_id')} "
                f"({selected_houses[0] if selected_houses else '?'})"
            )
        ctx = WorkerContext(
            run_mode=mode,
            confirm_real_bet=confirm_real_bet,
            confirm_real_withdraw=confirm_real_withdraw,
            max_lab_stake_brl=safety.max_lab_stake_brl,
            target_game=target or None,
        )
        results: list[ScenarioResult] = []

        for platform in selected_houses:
            if safety.killed(platform):
                for spec in self.catalog.for_house(platform):
                    if spec.axis not in selected_axes:
                        continue
                    if scenario_ids and spec.id not in scenario_ids:
                        continue
                    results.append(
                        ScenarioResult(
                            id=f"kill-{platform}-{spec.id}",
                            scenario_id=spec.id,
                            axis=spec.axis,
                            platform=platform,
                            title=spec.title,
                            mode="SKIPPED",
                            ok=True,
                            note="kill_switch da casa ativo no YAML",
                            vulnerability="kill_switch",
                        )
                    )
                continue

            try:
                house = self.house_factory(platform)
            except PermissionError as exc:
                run.notes.append(f"{platform}: sem sessão ({exc})")
                for spec in self.catalog.for_house(platform):
                    if spec.axis not in selected_axes:
                        continue
                    if scenario_ids and spec.id not in scenario_ids:
                        continue
                    if spec.worker in OFFLINE_WORKERS:
                        # offline ainda precisa de um adapter; pula se nem factory sobe
                        results.append(
                            ScenarioResult(
                                id=f"noauth-offline-{platform}-{spec.id}",
                                scenario_id=spec.id,
                                axis=spec.axis,
                                platform=platform,
                                title=spec.title,
                                mode="SKIPPED",
                                ok=True,
                                note="Sem adapter/sessão — sim offline não executado neste house",
                                vulnerability="auth_required",
                            )
                        )
                        continue
                    results.append(
                        ScenarioResult(
                            id=f"noauth-{platform}-{spec.id}",
                            scenario_id=spec.id,
                            axis=spec.axis,
                            platform=platform,
                            title=spec.title,
                            mode="BLOCKED",
                            ok=False,
                            severity="critical",
                            vulnerability="auth_required",
                            note=str(exc)[:300],
                        )
                    )
                continue
            except Exception as exc:  # noqa: BLE001
                run.notes.append(f"{platform}: adapter indisponível ({exc})")
                for spec in self.catalog.for_house(platform):
                    if spec.axis not in selected_axes:
                        continue
                    if scenario_ids and spec.id not in scenario_ids:
                        continue
                    results.append(
                        ScenarioResult(
                            id=f"noadapter-{platform}-{spec.id}",
                            scenario_id=spec.id,
                            axis=spec.axis,
                            platform=platform,
                            title=spec.title,
                            mode="BLOCKED",
                            ok=False,
                            severity="critical",
                            vulnerability="adapter_unavailable",
                            note=str(exc)[:300],
                        )
                    )
                continue

            session_ok = True
            session_note = ""
            if require_auth and mode == "PROBE":
                try:
                    auth = house.validate_session()
                    session_note = f"session ok currency={auth.get('currency')}"
                    run.notes.append(f"{platform}: {session_note}")
                except Exception as exc:  # noqa: BLE001
                    session_ok = False
                    session_note = str(exc)[:300]
                    run.notes.append(f"{platform}: sessão inválida ({session_note})")

            for spec in self.catalog.for_house(platform):
                if spec.axis not in selected_axes:
                    continue
                if scenario_ids and spec.id not in scenario_ids:
                    continue
                if require_auth and not session_ok and spec.worker not in OFFLINE_WORKERS:
                    results.append(
                        ScenarioResult(
                            id=f"authsess-{platform}-{spec.id}",
                            scenario_id=spec.id,
                            axis=spec.axis,
                            platform=platform,
                            title=spec.title,
                            mode="BLOCKED",
                            ok=False,
                            severity="critical",
                            vulnerability="auth_required",
                            note=session_note,
                        )
                    )
                    continue
                results.append(run_worker(house, spec, ctx))

        run.results = results
        run.coverage = build_coverage(results, selected_houses, selected_axes)
        run.finished_at = datetime.now(timezone.utc).isoformat()
        run.notes.append(
            "Produto = Casino Online. Bônus é um eixo. "
            "Sem manipulação de RNG; play no provider permanece SEMI_AUTO."
        )
        return run


def empty_matrix(catalog: Optional[Catalog] = None) -> dict[str, Any]:
    cat = catalog or load_catalog()
    return {
        "axes": cat.axes,
        "houses": cat.houses,
        "scenarios": [
            {
                "id": s.id,
                "axis": s.axis,
                "title": s.title,
                "worker": s.worker,
                "mode": s.mode,
                "houses": s.houses,
                "evidence": s.evidence,
            }
            for s in cat.scenarios
        ],
        "safety": {
            "default_mode": cat.safety.default_mode,
            "max_lab_stake_brl": cat.safety.max_lab_stake_brl,
            "confirm_real_bet_default": cat.safety.confirm_real_bet_default,
            "kill_switch": cat.safety.kill_switch,
        },
        "coverage": build_coverage([], cat.houses, cat.axes),
        "product": "casino_online",
    }
