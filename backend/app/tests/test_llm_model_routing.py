from app.services import llm_client


def test_title_uses_gpt_4o_even_when_base_and_utility_use_gpt_5(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL_CALL_TITLE", raising=False)
    monkeypatch.setenv("OPENAI_MODEL_UTILITY", "gpt-5")
    monkeypatch.setattr(llm_client, "OPENAI_MODEL", "gpt-5")

    assert llm_client._model_for("title") == "gpt-4o"


def test_title_per_call_override_remains_available(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL_CALL_TITLE", "gpt-4o-mini")

    assert llm_client._model_for("title") == "gpt-4o-mini"
