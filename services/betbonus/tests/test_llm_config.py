from src.llm.abuse_assist import _extract_json
from src.llm.client import (
    DOLPHIN_MODEL,
    LLM_MODELS,
    _message_text,
    load_iron_llm_config,
    normalize_model_id,
    resolve_llm_model,
    set_iron_llm_model,
)
from src.llm.json_extract import extract_json, llm_json_ok


def test_catalog_includes_dolphin():
    ids = {e["id"] for e in LLM_MODELS}
    assert "deepseek/deepseek-chat-v3.1" in ids
    assert DOLPHIN_MODEL in ids
    assert resolve_llm_model("dolphin-venice")["id"] == DOLPHIN_MODEL


def test_load_shared_maverick_config():
    cfg = load_iron_llm_config()
    assert cfg.model
    assert cfg.api_base.endswith("/api/v1") or "openrouter" in cfg.api_base


def test_extract_json_fenced():
    raw = '```json\n{"summary":"ok","abuse_vectors":[]}\n```'
    data = _extract_json(raw)
    assert data["summary"] == "ok"
    assert data["abuse_vectors"] == []


def test_extract_json_prose_and_think_tags():
    raw = '<think>scratch</think>\nAqui:\n```json\n{"summary":"ok","abuse_vectors":[{"id":"a"}]}\n```\n'
    data = extract_json(raw)
    assert data["abuse_vectors"][0]["id"] == "a"


def test_extract_json_trailing_comma():
    data = extract_json('{"summary":"ok","abuse_vectors":[{"id":"a",}],}')
    assert data["abuse_vectors"][0]["id"] == "a"


def test_extract_json_repairs_truncated_vector():
    raw = """```json
{
  "rules": {"wagering_multiple": 30.0, "notes": "foo"},
  "abuse_vectors": [
    {
      "id": "zero_bonus_rollover_bypass",
      "title": "Bonus Zero",
      "severity": "critical",
      "rationale": "Bonus de R$0,00 com rollover 30x pode ser
"""
    data = extract_json(raw)
    assert not data.get("parse_error")
    assert data.get("repaired") is True
    assert data["abuse_vectors"][0]["id"] == "zero_bonus_rollover_bypass"
    assert llm_json_ok(data, require_vectors=True)


def test_extract_json_production_truncated_fence():
    """DeepSeek wrap + cut mid-key — pagol auto-journey 2026-08-18."""
    raw = (
        '\n```json\n{\n  "rules": {\n    "wagering_multiple": 30.0,\n'
        '    "notes": "Promoção extremamente vulnerável"\n  },\n'
        '  "abuse_vectors": [\n    {\n      "id": "zero_bonus_instant_rollover'
    )
    data = extract_json(raw)
    assert llm_json_ok(data, require_vectors=True)
    assert data["abuse_vectors"][0]["id"].startswith("zero_bonus_instant")


def test_message_text_falls_back_to_reasoning():
    assert _message_text({"content": None, "reasoning": " { } "}) == "{ }"
    assert _message_text({"content": [{"text": '{"a":1}'}]}) == '{"a":1}'


def test_chat_model_strips_prefix():
    cfg = load_iron_llm_config()
    assert not cfg.chat_model.startswith("openrouter/")


def test_set_iron_llm_model_persist(tmp_path, monkeypatch):
    path = tmp_path / "llm_config.json"
    monkeypatch.setattr("src.llm.client.LLM_CONFIG_PATH", path)
    monkeypatch.delenv("BETBONUS_LLM", raising=False)
    cfg = set_iron_llm_model("dolphin-venice")
    assert cfg.chat_model == DOLPHIN_MODEL
    assert cfg.max_tokens == 8192
    again = load_iron_llm_config()
    assert again.chat_model == DOLPHIN_MODEL
    back = set_iron_llm_model("deepseek/deepseek-chat-v3.1")
    assert normalize_model_id(back.chat_model) == "deepseek/deepseek-chat-v3.1"


def test_default_model_is_dolphin(tmp_path, monkeypatch):
    path = tmp_path / "missing-llm-config.json"
    monkeypatch.setattr("src.llm.client.LLM_CONFIG_PATH", path)
    monkeypatch.delenv("BETBONUS_LLM", raising=False)
    cfg = load_iron_llm_config()
    assert cfg.chat_model == DOLPHIN_MODEL
    assert cfg.max_tokens == 8192


def test_analyze_retries_on_truncated_json():
    from src.llm.abuse_assist import AbuseLLMAssist
    from src.llm.client import ChatResult
    from src.models.bonus import BonusOffer

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0
            self.config = type("C", (), {"chat_model": "deepseek/deepseek-chat-v3.1"})()

        def complete(self, messages, **kwargs):  # noqa: ANN001
            self.calls += 1
            if self.calls == 1:
                return ChatResult(text='{"rules": {', finish_reason="length")
            return ChatResult(
                text=(
                    '{"summary":"ok","abuse_vectors":'
                    '[{"id":"x","title":"t","severity":"low"}]}'
                ),
                finish_reason="stop",
            )

    fake = FakeClient()
    assist = AbuseLLMAssist(client=fake)  # type: ignore[arg-type]
    out = assist.analyze_offer(
        BonusOffer(platform="4play", title="Evoplay", raw_text="wagering 30x sticky CRC 25")
    )
    assert fake.calls == 2
    assert out["retried"] is True
    assert out["llm"]["abuse_vectors"][0]["id"] == "x"
    assert not out["llm"].get("parse_error")
