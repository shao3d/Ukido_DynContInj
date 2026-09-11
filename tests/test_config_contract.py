"""Configuration contract tests for model selection."""

import importlib
import sys


def reload_module(module_name):
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def test_llm_model_defaults_preserve_runtime_models(monkeypatch):
    for env_name in (
        "MODEL",
        "ROUTER_MODEL",
        "MODEL_ANSWER",
        "ANSWER_MODEL",
        "TRANSLATION_MODEL",
        "ZHVANETSKY_MODEL",
        "HUMOR_MODEL",
    ):
        monkeypatch.delenv(env_name, raising=False)

    config = reload_module("config").Config

    # 2026-09-11: миграция 2.5-flash (сансет 16.10.2026) → 3.5-flash-lite.
    assert config.MODEL == "google/gemini-3.5-flash-lite"
    assert config.MODEL_ANSWER == "google/gemini-3.5-flash-lite"
    assert config.TRANSLATION_MODEL == "google/gemini-3.5-flash-lite"
    assert config.ZHVANETSKY_MODEL == "google/gemini-3.5-flash-lite"


def test_no_hardcoded_legacy_model_in_src():
    """Дефолт модели живёт только в Config.DEFAULT_GEMINI_MODEL."""
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "src"
    hits = [
        str(p) for p in src.glob("*.py")
        if "gemini-2.5-flash" in p.read_text(encoding="utf-8")
    ]
    assert hits == [], f"Захардкожен legacy-дефолт: {hits}"


def test_client_defaults_follow_config():
    from config import Config
    from openrouter_client import OpenRouterClient
    from gemini_cached_client import GeminiCachedClient

    assert OpenRouterClient("k").model == Config.DEFAULT_GEMINI_MODEL
    assert GeminiCachedClient("k").model == Config.DEFAULT_GEMINI_MODEL


def test_response_generator_uses_configured_answer_and_translation_models(monkeypatch):
    monkeypatch.setenv("MODEL_ANSWER", "test/answer-model")
    monkeypatch.setenv("TRANSLATION_MODEL", "test/translation-model")

    for module_name in ("config", "translator", "response_generator"):
        sys.modules.pop(module_name, None)

    generator = importlib.import_module("response_generator").ResponseGenerator()

    assert generator.client.model == "test/answer-model"
    assert generator.translator.model == "test/translation-model"


def test_router_uses_configured_router_model(monkeypatch):
    monkeypatch.setenv("ROUTER_MODEL", "test/router-model")

    for module_name in ("config", "gemini_cached_client", "router"):
        sys.modules.pop(module_name, None)

    router_module = importlib.import_module("router")

    assert router_module.Router(use_cache=False).client.model == "test/router-model"
    assert router_module.Router(use_cache=True).client.model == "test/router-model"
