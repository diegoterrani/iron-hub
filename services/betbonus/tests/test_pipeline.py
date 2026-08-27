from pathlib import Path

from src.pipeline.runner import BonusPipeline

FIXTURE = Path(__file__).parent / "fixtures" / "sample_promos.html"


def test_fixture_pipeline(tmp_path):
    pipeline = BonusPipeline(store_path=tmp_path / "bonuses.json")
    offers = pipeline.run_file("bet365", FIXTURE)
    assert len(offers) >= 2
    assert all(o.score >= 0 for o in offers)
    stored = pipeline.store.load()
    assert len(stored) >= 2
