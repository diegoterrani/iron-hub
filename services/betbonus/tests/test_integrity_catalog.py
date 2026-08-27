from src.integrity.catalog import load_catalog
from src.integrity.models import AXES


def test_catalog_covers_all_casino_axes():
    cat = load_catalog()
    covered = {s.axis for s in cat.scenarios}
    assert set(AXES) <= covered
    assert set(cat.axes) == set(AXES)
    assert "pagol_bet_br" in cat.houses
    assert "4play_bet_br" in cat.houses
    assert "4play" in cat.houses
    assert cat.safety.max_lab_stake_brl <= 5.0
    assert cat.safety.confirm_real_withdraw_default is False
    ids = [s.id for s in cat.scenarios]
    assert len(ids) == len(set(ids))
    assert any(s.axis == "crash" for s in cat.scenarios)
    assert any(s.axis == "slots" for s in cat.scenarios)
    assert any(s.axis == "table" for s in cat.scenarios)
    promo = [s for s in cat.scenarios if s.axis == "promo"]
    assert len(promo) < len(cat.scenarios)
    assert len(promo) / len(cat.scenarios) < 0.3
