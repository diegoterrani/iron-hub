"""Testes live autenticados — skip sem token. Não imprimem segredos."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.auth.credentials import CredentialsStore
from src.integrity.adapters import FourPlayBrHouse, FourPlayHouse, PagolHouse
from src.integrity.house import wallet_delta
from src.scrapers.fourplay_br_scraper import FourPlayBrScraper
from src.scrapers.fourplay_scraper import FourPlayScraper
from src.scrapers.pagol_scraper import PagolScraper

CREDS = CredentialsStore(Path(__file__).resolve().parents[1] / "data" / "credentials.json")


def _has_token(*platforms: str) -> bool:
    return any(bool(CREDS.get_token(p)) for p in platforms)


skip_pagol = pytest.mark.skipif(
    not _has_token("pagol_bet_br", "pagol"),
    reason="sem token PAGOL — autentique no Admin",
)
skip_four_br = pytest.mark.skipif(
    not (_has_token("4play_bet_br") and CREDS.get_refresh_token("4play_bet_br")),
    reason="sem token+refresh 4play.bet.br",
)
skip_four = pytest.mark.skipif(not _has_token("4play"), reason="sem token 4play.game")


def _require_live_session(house):
    try:
        return house.validate_session()
    except PermissionError as exc:
        pytest.skip(f"sessão inválida/expirada — reautentique no Admin ({exc})")


@pytest.mark.live
@skip_pagol
def test_pagol_authenticated_session_and_wallet():
    token = CREDS.get_token("pagol_bet_br") or CREDS.get_token("pagol")
    house = PagolHouse(PagolScraper(delay=0, token=token))
    auth = _require_live_session(house)
    assert auth.get("currency") in {"BRL", "CRC"} or auth.get("user_id")
    snap = house.wallet_snapshot()
    assert snap.balance >= 0
    assert snap.bonus >= 0
    delta = wallet_delta(snap, house.wallet_snapshot())
    assert "changed" in delta


@pytest.mark.live
@skip_pagol
def test_pagol_authenticated_catalog_probe():
    token = CREDS.get_token("pagol_bet_br") or CREDS.get_token("pagol")
    house = PagolHouse(PagolScraper(delay=0, token=token))
    _require_live_session(house)
    games = house.list_games("slots", limit=2)
    assert isinstance(games, list)
    # catálogo autenticado pode ser vazio (geo/filtro), mas a API não pode 401 aqui
    if games:
        launch = house.start_game(games[0]["game_id"], mode="REAL", use_bonus=False)
        assert launch.get("url") or launch.get("launch") or launch.get("error") is not None


@pytest.mark.live
@skip_four
def test_fourplay_game_authenticated_session():
    house = FourPlayHouse(FourPlayScraper(delay=0, token=CREDS.get_token("4play")))
    auth = _require_live_session(house)
    assert auth.get("authenticated") or auth.get("user") or auth.get("platform")
    snap = house.wallet_snapshot()
    assert snap.balance >= 0


@pytest.mark.live
@skip_four
def test_fourplay_game_catalog_lists_titles():
    house = FourPlayHouse(FourPlayScraper(delay=0, token=CREDS.get_token("4play")))
    games = house.list_catalog(query="olympus", limit=8)
    assert games
    assert games[0].get("game_id")
    assert any("olympus" in str(g.get("name") or "").lower() for g in games)
    slots = house.list_games("slots", limit=3)
    assert slots
    crash = house.list_games("crash", limit=3)
    assert crash


@pytest.mark.live
@skip_four
def test_fourplay_game_start_game_opens_salsa():
    house = FourPlayHouse(FourPlayScraper(delay=0, token=CREDS.get_token("4play")))
    _require_live_session(house)
    games = house.list_catalog(query="jokersJewels", limit=8)
    assert games
    target = next(
        (g for g in games if "jewel" in str(g.get("name") or "").lower() or g.get("slug")),
        games[0],
    )
    launch = house.start_game(
        target["game_id"],
        mode="REAL",
        use_bonus=False,
        game_code=target.get("slug") or target.get("game_code"),
        aggregator=target.get("aggregator"),
        game_name=target.get("name"),
    )
    assert launch.get("url") or launch.get("error")
    if launch.get("url"):
        assert launch.get("launch", {}).get("host")
        blob = str(launch.get("launch") or {})
        assert "token=" not in blob.lower()


@pytest.mark.live
@skip_four_br
def test_fourplay_br_authenticated_session():
    house = FourPlayBrHouse(
        FourPlayBrScraper(
            delay=0,
            token=CREDS.get_token("4play_bet_br"),
            refresh_token=CREDS.get_refresh_token("4play_bet_br"),
        )
    )
    auth = _require_live_session(house)
    assert auth.get("platform") == "4play_bet_br" or auth.get("person_id") or auth.get("mode")
    snap = house.wallet_snapshot()
    assert snap.balance >= 0
