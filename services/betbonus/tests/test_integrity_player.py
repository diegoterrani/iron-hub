from src.integrity.player import (
    catalog_vs_client,
    classify_host,
    classify_salsa_slug,
    classify_url,
    map_launch_html,
    redact_url,
    summarize_endpoints,
)
from src.integrity.report import build_integrity_markdown
from src.integrity.runner import IntegrityRunner
from tests.fake_house import FakeHouse


def test_redact_url_drops_query_tokens():
    url = "https://api.salsagator.com/game?token=SECRET&game=prag-brf-X"
    assert redact_url(url) == "https://api.salsagator.com/game"
    assert "SECRET" not in redact_url(url)


def test_classify_pragmatic_and_salsa():
    assert classify_host("api.salsagator.com") == "aggregator"
    assert classify_url("https://gs2c.pragmaticplay.net/gs2c/ge/v4/gameService") == "pragmatic"
    assert classify_salsa_slug("prag-brf-GatesofOlympusSuperScatter") == "pragmatic"
    assert classify_salsa_slug("pate-gates") == "patagonia"


def test_catalog_mismatch_patagonia_vs_pragmatic_slug():
    row = catalog_vs_client(
        "PATAGONIA_ENTERTAINMENT",
        "prag-brf-GatesofOlympusSuperScatter",
        "pragmatic",
    )
    assert row["mismatch"] is True
    assert row["salsa_vendor"] == "pragmatic"


def test_summarize_endpoints_groups_hosts():
    out = summarize_endpoints(
        [
            "https://api.salsagator.com/game?token=x",
            "https://gs2c.pragmaticplay.net/gs2c/html5Game.do?mgckey=leak",
            "wss://gs2c.pragmaticplay.net/game",
        ]
    )
    assert out["game_client"] == "pragmatic"
    hosts = {h["host"] for h in out["hosts"]}
    assert "gs2c.pragmaticplay.net" in hosts
    blob = str(out)
    assert "mgckey" not in blob
    assert "token=x" not in blob


def test_oops_html_exposes_spe_and_gs2c_iframe():
    from src.integrity.player import extract_http_urls, merge_launch_maps, parse_launch_error

    oops = (
        'Oops! Error: I/O error on POST request for '
        '"https://api-spe-11.pragmaticplay.net/IntegrationService/v3/http/CasinoGameAPI/game/url/"'
    )
    html = (
        oops
        + '<iframe src="https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do?mgckey=SECRET"></iframe>'
    )
    urls = extract_http_urls(oops)
    assert any("api-spe-11.pragmaticplay.net" in u for u in urls)
    assert "SECRET" not in str([redact_url(u) for u in urls])
    mapped = map_launch_html(html)
    assert mapped["game_client"] == "pragmatic"
    merged = merge_launch_maps(mapped, {"urls": urls})
    hosts = {h["host"] for h in merged["hosts"]}
    assert "api-spe-11.pragmaticplay.net" in hosts
    assert "hmzflri0qj.btrzmbdurg.net" in hosts
    assert "oops" in parse_launch_error(oops).lower()
    assert classify_url("https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do") == "pragmatic"


def test_uniq_iframes_and_drop_w3():
    from src.integrity.player import uniq_redacted

    urls = [
        "https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do?a=1",
        "https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do?a=2",
        "https://www.w3.org/1999/xhtml",
    ]
    merged = summarize_endpoints(urls)
    hosts = {h["host"] for h in merged["hosts"]}
    assert "www.w3.org" not in hosts
    assert uniq_redacted(urls) == [
        "https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do",
        "https://www.w3.org/1999/xhtml",
    ]


def test_report_shows_launch_error_and_iframe():
    md = build_integrity_markdown(
        {
            "id": "x",
            "run_mode": "PROBE",
            "houses": ["pagol_bet_br"],
            "kind": "game_session",
            "target_game": {
                "game_id": 1435,
                "name": "Gates of Olympus Super Scatter",
                "provider": "PATAGONIA_ENTERTAINMENT",
                "house": "pagol_bet_br",
            },
            "coverage": {"mode_counts": {"AUTOMATED": 1}},
            "results": [
                {
                    "scenario_id": "slots.provider_map",
                    "axis": "slots",
                    "mode": "AUTOMATED",
                    "ok": True,
                    "severity": "high",
                    "title": "Endpoints iframe",
                    "vulnerability": "catalog_provider_mismatch_iframe",
                    "evidence": {
                        "launch_host": "api.salsagator.com",
                        "salsa_game": "prag-brf-GatesofOlympusSuperScatter",
                        "game_client": "pragmatic",
                        "launch_error": "Oops! I/O error on POST api-spe-11.pragmaticplay.net",
                        "chain": {
                            "catalog_provider": "PATAGONIA_ENTERTAINMENT",
                            "salsa_game": "prag-brf-GatesofOlympusSuperScatter",
                            "game_client": "pragmatic",
                            "mismatch": True,
                        },
                        "hosts": [
                            {
                                "host": "hmzflri0qj.btrzmbdurg.net",
                                "role": "pragmatic",
                                "paths": ["/gs2c/playGame.do"],
                            }
                        ],
                        "iframes": ["https://hmzflri0qj.btrzmbdurg.net/gs2c/playGame.do"],
                    },
                }
            ],
        }
    )
    assert "Cadeia iframe / provedor" in md
    assert "btrzmbdurg.net" in md
    assert "Erro Salsa" in md
    assert "pragmatic" in md


def test_map_launch_html_iframes():
    html = """
    <iframe src="https://demogamesfree.pragmaticplay.net/gs2c/html5Game.do?foo=1"></iframe>
    <script src="https://api.salsagator.com/static/app.js"></script>
    """
    mapped = map_launch_html(html, base_url="https://api.salsagator.com/game?token=noleak")
    assert mapped["game_client"] == "pragmatic"
    assert all("noleak" not in (src or "") for src in mapped["iframes"])


def test_provider_map_fake_and_report_section():
    runner = IntegrityRunner(lambda p: FakeHouse())
    run = runner.run(
        houses=["pagol_bet_br"],
        scenario_ids=["slots.provider_map"],
        run_mode="PROBE",
        target_game={
            "game_id": 1435,
            "name": "Gates of Olympus Super Scatter",
            "house": "pagol_bet_br",
            "provider": "PATAGONIA_ENTERTAINMENT",
        },
    )
    row = run.results[0]
    assert row.mode == "AUTOMATED"
    assert row.vulnerability == "provider_map_simulated"
    md = build_integrity_markdown(run.to_dict())
    assert "Cadeia iframe / provedor" in md
    assert "salsa.example" in md
