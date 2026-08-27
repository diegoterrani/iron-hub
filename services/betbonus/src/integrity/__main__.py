"""CLI: python -m src.integrity --help"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.integrity.catalog import load_catalog
from src.integrity.sims import table_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="casino-integrity",
        description=(
            "Harness de integridade do produto Casino Online (lab autorizado). "
            "Não cobre sportsbook. Não manipula RNG. Default DRY/PROBE sem saque."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog", help="Lista eixos e cenários do YAML")
    sub.add_parser("sims", help="Roda sims offline (blackjack/baccarat/roleta/crash)")
    args = parser.parse_args(argv)

    if args.cmd == "catalog":
        cat = load_catalog()
        print(json.dumps(
            {
                "product": "casino_online",
                "axes": cat.axes,
                "houses": cat.houses,
                "safety": {
                    "default_mode": cat.safety.default_mode,
                    "max_lab_stake_brl": cat.safety.max_lab_stake_brl,
                    "kill_switch": cat.safety.kill_switch,
                },
                "scenarios": [
                    {"id": s.id, "axis": s.axis, "title": s.title, "houses": s.houses}
                    for s in cat.scenarios
                ],
            },
            indent=2,
            ensure_ascii=False,
        ))
        return 0
    if args.cmd == "sims":
        print(json.dumps(table_suite(), indent=2, ensure_ascii=False))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
