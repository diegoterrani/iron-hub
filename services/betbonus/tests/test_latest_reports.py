from src.api import _latest_reports_payload


def test_latest_reports_payload_has_both_bundles():
    data = _latest_reports_payload()
    assert data["ok"] is True
    for key in ("integrity", "promo"):
        bundle = data[key]
        assert "available" in bundle
        assert "markdown" in bundle
        assert "filename" in bundle
        assert "label" in bundle
    assert data["integrity"]["label"] == "Jornada de teste / Matriz"
    assert data["promo"]["label"] == "Jornada promo"
    if data["promo"]["available"]:
        assert "auto-journey" in data["promo"]["filename"] or data["promo"]["markdown"]
    if data["integrity"]["available"]:
        assert data["integrity"]["filename"].startswith("casino-integrity-")
