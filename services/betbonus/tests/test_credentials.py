from src.auth.credentials import CredentialsStore


def test_save_and_list_roundtrip(tmp_path):
    store = CredentialsStore(tmp_path / "credentials.json")
    saved = store.save("4play", token="abcdef1234567890", email="u@test.com", label="u")
    assert saved["has_token"] is True
    assert saved["platform"] == "4play"

    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["token_preview"].startswith("abcdef")
    assert store.get_token("4play") == "abcdef1234567890"


def test_list_tolerates_legacy_nested_platform(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(
        '{"4play":{"platform":"4play","token":"tokentoken1234","email":"a@b.c","label":"","updated_at":"2026-07-27T00:00:00Z"}}',
        encoding="utf-8",
    )
    store = CredentialsStore(path)
    listed = store.list()
    assert listed[0]["platform"] == "4play"
    assert listed[0]["has_token"] is True
