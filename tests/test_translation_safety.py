"""BUG-01: ложный успех перевода.

Сбой перевода больше не маскируется под успех: переводчик бросает
TranslationError вместо молчаливого возврата русского оригинала,
translated_to ставится только при реальном успехе, шлюз повторяет
попытку, а остаточная кириллица для en И uk даёт извинение на языке
диалога вместо русского текста.
"""

import asyncio
import importlib
import os
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from translator import SmartTranslator, TranslationError

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


class StubClient:
    model = "test/model"

    def __init__(self, reply=None, exc=None):
        self.reply = reply
        self.exc = exc
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.reply


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- Юнит: контракт переводчика ------------------------------------------------

def test_empty_api_response_raises_not_silent_russian():
    """Пустой ответ API (openrouter отдаёт '' при не-200) — сбой, не успех."""
    translator = SmartTranslator(StubClient(reply=""))
    with pytest.raises(TranslationError):
        run(translator.translate("Русский текст", "en"))


def test_whitespace_response_raises():
    translator = SmartTranslator(StubClient(reply="   \n  "))
    with pytest.raises(TranslationError):
        run(translator.translate("Русский текст", "uk"))


def test_client_exception_raises_not_original():
    """Таймаут/сбой LLM больше не возвращается как «перевод»-оригинал."""
    translator = SmartTranslator(StubClient(exc=TimeoutError("slow")))
    with pytest.raises(TranslationError):
        run(translator.translate("Русский текст", "en"))


def test_success_still_returns_plain_string():
    """Интерфейс не менялся: успех — это str (контракт со старыми тестами)."""
    translator = SmartTranslator(StubClient(reply="Translated text."))
    result = run(translator.translate("Русский текст", "en"))
    assert result == "Translated text."
    assert isinstance(result, str)


def test_same_language_no_call():
    client = StubClient(reply="whatever")
    translator = SmartTranslator(client)
    assert run(translator.translate("Той самий текст", "ru")) == "Той самий текст"
    assert client.calls == 0


# --- Сквозные: шлюз в main -------------------------------------------------------

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("tr_states"))

    for module_name in (
        "main", "config", "router", "gemini_cached_client",
        "response_generator", "translator", "standard_responses",
        "localization", "social_state", "persistence_manager",
    ):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


def make_route(lang, questions=None):
    return {
        "status": "success",
        "detected_language": lang,
        "decomposed_questions": questions or ["q"],
        "documents": ["faq.md"],
        "user_signal": "exploring_only",
        "fuzzy_matched": False,
        "original_message": "hi",
    }


def install(route_result, generate, translator, monkeypatch):
    main = sys.modules["main"]

    async def fake_route(user_message, history=None, user_id="anonymous"):
        result = dict(route_result)
        result["original_message"] = user_message
        return result

    monkeypatch.setattr(main.router, "route", fake_route)
    monkeypatch.setattr(main.response_generator, "generate", generate)
    monkeypatch.setattr(main.response_generator, "translator", translator)


class RaisingTranslator:
    """Перевод всегда падает — как упавший LLM."""

    def __init__(self):
        self.calls = 0

    async def translate(self, text, target_language, **kwargs):
        self.calls += 1
        raise TranslationError("boom")


def russian_failed_generate(router_result, history=None, current_message=None):
    """Честная metadata нового формата: успеха не было."""
    return "Русский ответ, перевод которого упал.", {
        "intent": "success", "user_signal": "exploring_only",
        "cta_added": False, "cta_type": None, "humor_generated": False,
        "translation_failed": True, "detected_language": router_result.get("detected_language"),
    }


def test_en_translation_failure_yields_apology_not_russian(client, monkeypatch):
    install(make_route("en"), russian_failed_generate, RaisingTranslator(), monkeypatch)
    body = client.post(
        "/chat", json={"user_id": "tr_en_fail", "message": "What courses do you have?"}
    ).json()
    assert not CYRILLIC_RE.search(body["response"]), body["response"]
    assert "translated_to" not in (body.get("metadata") or {})


def test_uk_translation_failure_yields_ukrainian_apology(client, monkeypatch):
    """Страховка остаточной кириллицы теперь работает и для uk."""
    install(make_route("uk"), russian_failed_generate, RaisingTranslator(), monkeypatch)
    body = client.post(
        "/chat", json={"user_id": "tr_uk_fail", "message": "Скільки коштує курс?"}
    ).json()
    assert "Переформулюйте" in body["response"], body["response"]
    assert "translated_to" not in (body.get("metadata") or {})


def test_gateway_retries_after_generator_failure(client, monkeypatch):
    """Ложный успех больше не блокирует шлюз: повторная попытка удаётся."""

    class RetryTranslator:
        async def translate(self, text, target_language, **kwargs):
            return "[translated-to-uk]"

    install(make_route("uk"), russian_failed_generate, RetryTranslator(), monkeypatch)
    body = client.post(
        "/chat", json={"user_id": "tr_uk_retry", "message": "Скільки коштує курс?"}
    ).json()
    assert body["response"] == "[translated-to-uk]"
    assert (body.get("metadata") or {}).get("translated_to") == "uk"
    assert "translation_failed" not in (body.get("metadata") or {})


def test_uk_error_responses_exist():
    from localization import ERROR_RESPONSES, get_error_response
    assert set(ERROR_RESPONSES["uk"].keys()) == set(ERROR_RESPONSES["en"].keys())
    assert "Переформулюйте" in get_error_response("invalid_response", "uk")
