from src.abuse.catalog_correlation import scan_offer_catalog
from src.integrity.report import build_integrity_markdown
from src.storage.wallet import WalletCredit, WalletLedger


def test_wallet_credit_is_internal_sim(tmp_path):
    path = tmp_path / "wallet.json"
    ledger = WalletLedger(path)
    item = ledger.credit(
        WalletCredit(platform="4play", title="Promo X", amount=10, currency="CRC")
    )
    assert item.reality == "internal_sim"
    summary = ledger.summary()
    assert summary["reality"] == "internal_sim"
    assert summary["internal_sim"] == 1
    assert summary["platform_observed"] == 0
    assert "não altera" in summary["disclaimer"].lower() or "NÃO" in summary["disclaimer"]


def test_catalog_correlation_no_fingerprint_fields():
    out = scan_offer_catalog(
        [
            {
                "id": "1",
                "title": "Torneio Evoplay",
                "raw_text": "Premiação em dinheiro real sem rollover.",
            }
        ]
    )
    assert out["scanned"] == 1
    assert out["scale_justifies_p0"] is False
    assert out["catalog_exposes_scale_controls"] is False


def test_integrity_report_marks_offline_plane():
    md = build_integrity_markdown(
        {
            "id": "x",
            "run_mode": "PROBE",
            "houses": ["4play"],
            "coverage": {"mode_counts": {"AUTOMATED": 2}},
            "results": [
                {
                    "scenario_id": "wallet.scale_cents",
                    "axis": "wallet",
                    "mode": "AUTOMATED",
                    "ok": True,
                    "severity": "info",
                    "vulnerability": "currency_scale_ok",
                },
                {
                    "scenario_id": "table.offline_ev",
                    "axis": "table",
                    "mode": "AUTOMATED",
                    "ok": True,
                    "severity": "info",
                    "vulnerability": "negative_ev_all_table_models",
                },
            ],
        }
    )
    assert "Plano de evidência" in md
    assert "plano=offline_model" in md
    assert "plano=platform_observed" in md
    assert "ledger.credit" in md
