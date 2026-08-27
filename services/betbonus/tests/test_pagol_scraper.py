from src.scrapers.pagol_scraper import PagolScraper, _as_float


def test_as_float():
    assert _as_float("3345") == 3345.0
    assert _as_float(None) == 0.0


def test_offer_from_promocode():
    scraper = PagolScraper(delay=0)
    offer = scraper.offer_from_promocode({"id": 1, "code": "ABC123"})
    assert offer.platform == "pagol_bet_br"
    assert "ABC123" in offer.title
    assert offer.currency == "BRL"


def test_offer_from_bonus_maps_title():
    scraper = PagolScraper(delay=0)
    offer = scraper.offer_from_bonus(
        {"id": 9, "name": "Welcome", "amount": 50, "status": "ACTIVE", "currency": "BRL"}
    )
    assert offer.title.startswith("[conta]")
    assert offer.amount == 50
