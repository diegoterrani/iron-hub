from __future__ import annotations

from pathlib import Path
from typing import Any

from src.integrity.models import AXES, HOUSES, Catalog, SafetyCaps, ScenarioSpec

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "configs" / "integrity" / "scenarios.yaml"


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is not None:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
        raise ValueError("Catálogo YAML inválido")
    raise RuntimeError(
        "PyYAML é necessário para configs/integrity/scenarios.yaml. "
        "pip install pyyaml"
    )


def load_catalog(path: str | Path | None = None) -> Catalog:
    target = Path(path) if path else DEFAULT_CATALOG
    if not target.is_file():
        raise FileNotFoundError(f"Catálogo não encontrado: {target}")
    raw = _load_yaml(target)
    safety_raw = raw.get("safety") or {}
    kill = safety_raw.get("kill_switch") or {}
    if not isinstance(kill, dict):
        kill = {}
    safety = SafetyCaps(
        default_mode=str(safety_raw.get("default_mode") or "PROBE"),
        max_lab_stake_brl=float(safety_raw.get("max_lab_stake_brl") or 5.0),
        confirm_real_bet_default=_as_bool(safety_raw.get("confirm_real_bet_default")),
        confirm_real_withdraw_default=_as_bool(safety_raw.get("confirm_real_withdraw_default")),
        kill_switch={str(k): _as_bool(v) for k, v in kill.items()},
    )
    axes = [str(a) for a in (raw.get("axes") or list(AXES))]
    houses = [str(h) for h in (raw.get("houses") or list(HOUSES))]
    scenarios: list[ScenarioSpec] = []
    for row in raw.get("scenarios") or []:
        if not isinstance(row, dict):
            continue
        axis = str(row.get("axis") or "")
        if axis not in AXES:
            raise ValueError(f"Eixo inválido no catálogo: {axis}")
        houses_row = [str(h) for h in (row.get("houses") or houses)]
        scenarios.append(
            ScenarioSpec(
                id=str(row.get("id") or ""),
                axis=axis,
                title=str(row.get("title") or row.get("id") or ""),
                worker=str(row.get("worker") or ""),
                mode=str(row.get("mode") or "PROBE"),
                houses=houses_row,
                requires_stake=_as_bool(row.get("requires_stake")),
                requires_withdraw=_as_bool(row.get("requires_withdraw")),
                evidence=str(row.get("evidence") or ""),
                note=str(row.get("note") or ""),
            )
        )
    missing = [a for a in AXES if a not in axes]
    if missing:
        raise ValueError(f"Catálogo sem eixos do produto cassino: {missing}")
    if not scenarios:
        raise ValueError("Catálogo sem cenários")
    ids = [s.id for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("IDs de cenário duplicados")
    covered = {s.axis for s in scenarios}
    gap = [a for a in AXES if a not in covered]
    if gap:
        raise ValueError(f"Catálogo não cobre eixos: {gap}")
    return Catalog(safety=safety, axes=axes, houses=houses, scenarios=scenarios)
