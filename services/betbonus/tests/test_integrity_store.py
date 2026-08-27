from src.integrity.store import IntegrityRunStore


def test_run_store_summaries(tmp_path):
    store = IntegrityRunStore(tmp_path / "runs.json")
    store.add(
        {
            "id": "abc-123",
            "started_at": "t0",
            "finished_at": "t1",
            "run_mode": "DRY",
            "houses": ["pagol_bet_br"],
            "axes": ["session"],
            "coverage": {
                "scenario_count": 3,
                "mode_counts": {"AUTOMATED": 1, "DRY": 2},
                "automated_ratio": 0.33,
            },
            "planner": {"next_scenario_id": "session.validate"},
            "results": [{}, {}, {}],
        }
    )
    rows = store.summaries(limit=5)
    assert len(rows) == 1
    assert rows[0]["id"] == "abc-123"
    assert rows[0]["scenario_count"] == 3
    assert rows[0]["planner"] == "session.validate"
