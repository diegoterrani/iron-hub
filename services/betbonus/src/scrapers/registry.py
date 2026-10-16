"""Config-driven scraper registry.

Single source of truth for:
- platform name normalization (aliases)
- scraper class factory (per-platform kwargs)
- optional YAML config override (configs/scrapers.yaml)

Semantics (unified across all scrapers):
- HTML scrapers (bet365/betway/888/generic): ``scrape_url(url)`` fetches the
  URL and parses the returned HTML.
- API scrapers (4play, 4play_bet_br, pagol_bet_br): ``scrape_url(url)``
  ignores the URL and calls ``scrape_live()`` against the authenticated API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.scrapers.bet365_scraper import Bet365Scraper
from src.scrapers.betway_scraper import BetwayScraper
from src.scrapers.eighteighteight_scraper import EightEightEightScraper
from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.generic_promo_scraper import GenericPromoScraper
from src.scrapers.pagol_scraper import PagolScraper

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "scrapers.yaml"

FALLBACK_PLATFORM = "4play"


@dataclass(frozen=True)
class ScraperSpec:
    """Declarative description of one platform's scraper."""

    platform: str
    cls: type
    mode: str = "html"  # "html" | "api"
    delay: float = 0.0
    aliases: tuple[str, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def build(self, *, delay: Optional[float] = None) -> Any:
        return self.cls(delay=delay if delay is not None else self.delay, **self.kwargs)


def _default_specs() -> list[ScraperSpec]:
    return [
        ScraperSpec(
            platform="bet365",
            cls=Bet365Scraper,
            mode="html",
            delay=0.0,
            aliases=("bet365.com.br", "bet365br"),
        ),
        ScraperSpec(
            platform="betway",
            cls=BetwayScraper,
            mode="html",
            delay=0.0,
            aliases=("betway.com.br", "betwaybr"),
        ),
        ScraperSpec(
            platform="888",
            cls=EightEightEightScraper,
            mode="html",
            delay=0.0,
            aliases=("888.com.br", "888br", "888bet"),
        ),
        ScraperSpec(
            platform="4play",
            cls=FourPlayScraper,
            mode="api",
            delay=0.3,
            aliases=("4play.game", "4play_game", "4play.com.br"),
        ),
        ScraperSpec(
            platform="4play_bet_br",
            cls=FourPlayBrScraper,
            mode="api",
            delay=0.2,
            aliases=("4play.bet.br", "4playbr", "4play_br"),
        ),
        ScraperSpec(
            platform="pagol_bet_br",
            cls=PagolScraper,
            mode="api",
            delay=0.2,
            aliases=("pagol", "pagol.bet.br"),
        ),
        ScraperSpec(
            platform="generic",
            cls=GenericPromoScraper,
            mode="html",
            delay=0.0,
            aliases=(),
        ),
    ]


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None
    if yaml is None:
        return {}
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _spec_from_config(platform: str, row: dict[str, Any], specs: dict[str, ScraperSpec]) -> Optional[ScraperSpec]:
    """Build/override a spec from a YAML row. Unknown class names are ignored."""
    if not isinstance(row, dict):
        return None
    cls_name = str(row.get("class") or "")
    cls = None
    for spec in specs.values():
        if spec.cls.__name__ == cls_name:
            cls = spec.cls
            break
    if cls is None:
        return None
    return ScraperSpec(
        platform=platform,
        cls=cls,
        mode=str(row.get("mode") or "html"),
        delay=float(row.get("delay", 0.0)),
        aliases=tuple(str(a) for a in (row.get("aliases") or [])),
        kwargs=dict(row.get("kwargs") or {}),
    )


class ScraperRegistry:
    """Maps platform names (and aliases) to scraper specs and builds instances."""

    def __init__(self, config_path: Optional[str | Path] = None):
        self.specs: dict[str, ScraperSpec] = {s.platform: s for s in _default_specs()}
        self._alias_map: dict[str, str] = {}
        self._rebuild_alias_map()

        target = Path(config_path) if config_path else DEFAULT_CONFIG
        if target.is_file():
            raw = _load_yaml(target)
            for platform, row in (raw.get("scrapers") or {}).items():
                spec = _spec_from_config(str(platform), row, self.specs)
                if spec is not None:
                    self.specs[str(platform)] = spec
            self._rebuild_alias_map()

    def _rebuild_alias_map(self) -> None:
        self._alias_map = {}
        for spec in self.specs.values():
            self._alias_map[spec.platform] = spec.platform
            for alias in spec.aliases:
                self._alias_map[alias] = spec.platform

    def normalize(self, platform: str) -> str:
        """Normalize a platform name/alias to its canonical name."""
        p = (platform or "").strip().lower()
        return self._alias_map.get(p, p or FALLBACK_PLATFORM)

    def get(self, platform: str) -> Optional[ScraperSpec]:
        return self.specs.get(self.normalize(platform))

    def build(self, platform: str, *, delay: Optional[float] = None) -> Any:
        spec = self.get(platform)
        if spec is None:
            # Unknown platform → generic fallback (matches legacy behavior)
            return GenericPromoScraper(
                delay=delay if delay is not None else 0.0,
                platform=self.normalize(platform),
            )
        return spec.build(delay=delay)

    def platforms(self) -> list[str]:
        return sorted(self.specs)

    def is_api(self, platform: str) -> bool:
        spec = self.get(platform)
        return spec is not None and spec.mode == "api"
