"""BUG-04: ошибки API больше не возвращаются как ответ.

Таймаут/не-200/пустой ответ — это типизированные исключения, а не строки
«Превышено время ожидания ответа», которые бот показывал родителю как
свою реплику. Генератор отдаёт честное извинение, роутер помечает сбой.
"""

import asyncio
import importlib
import os
import re
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openrouter_client import (
    OpenRouterClient,
    OpenRouterEmptyResponse,
    OpenRouterError,
    OpenRouterHTTPError,
    OpenRouterTimeout,
)

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        if self._exc is not None:
            raise self._exc
        return self._response


def patch_session(monkeypatch, response=None, exc=None):
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: FakeSession(response, exc)
    )


def ok_payload(text):
    return {"choices": [{"message": {"content": text}}]}


# --- Клиент: типы ошибок -------------------------------------------------------

def test_non_200_raises_http_error_with_status(monkeypatch):
    patch_session(monkeypatch, FakeResponse(500, text="internal"))
    client = OpenRouterClient("key")
    with pytest.raises(OpenRouterHTTPError) as caught:
        run(client.chat([{"role": "user", "content": "hi"}]))
    assert caught.value.status_code == 500


def test_timeout_raises_not_string(monkeypatch):
    """Главный кейс BUG-04: таймаут — исключение, а не реплика бота."""
    patch_session(monkeypatch, exc=httpx.TimeoutException("slow"))
    client = OpenRouterClient("key")
    with pytest.raises(OpenRouterTimeout):
        run(client.chat([{"role": "user", "content": "hi"}]))


def test_missing_choices_raises(monkeypatch):
    patch_session(monkeypatch, FakeResponse(200, {}))
    client = OpenRouterClient("key")
    with pytest.raises(OpenRouterEmptyResponse):
        run(client.chat([{"role": "user", "content": "hi"}]))


def test_empty_content_raises(monkeypatch):
    patch_session(monkeypatch, FakeResponse(200, ok_payload("   ")))
    client = OpenRouterClient("key")
    with pytest.raises(OpenRouterEmptyResponse):
        run(client.chat([{"role": "user", "content": "hi"}]))


def test_valid_response_still_returns_string(monkeypatch):
    patch_session(monkeypatch, FakeResponse(200, ok_payload("Hello!")))
    client = OpenRouterClient("key")
    assert run(client.chat([{"role": "user", "content": "hi"}])) == "Hello!"


def test_all_errors_share_base_type():
    assert issubclass(OpenRouterTimeout, OpenRouterError)
    assert issubclass(OpenRouterHTTPError, OpenRouterError)
    assert issubclass(OpenRouterEmptyResponse, OpenRouterError)


# --- Генератор: честное извинение вместо строки сбоя ----------------------------

def test_generator_timeout_yields_error_tuple_not_timeout_text():
    from response_generator import ResponseGenerator

    generator = ResponseGenerator()

    async def failing_chat(messages, **kwargs):
        raise OpenRouterTimeout("timeout after 30s")

    generator.client.chat = failing_chat
    text, metadata = run(generator.generate(
        {
            "status": "success",
            "documents": ["faq.md"],
            "decomposed_questions": ["Как проходят занятия?"],
            "user_signal": "exploring_only",
            "detected_language": "ru",
        },
        [],
        "Как проходят занятия?",
    ))
    assert metadata["intent"] == "error"
    assert "Превышено" not in text and "Произошла ошибка при обработке" not in text


# --- Роутер: транспортный сбой помечается ---------------------------------------

def test_router_transport_error_marks_failure():
    from router import Router

    router = Router(use_cache=False)

    async def failing_chat(messages, **kwargs):
        raise OpenRouterTimeout("timeout after 30s")

    router.client.chat = failing_chat
    result = run(router.route("Сколько стоит курс?", [], "test_user"))
    assert result["status"] == "offtopic"
    assert result.get("_router_failed") is True


# --- Сквозной: падение роутера — английское извинение -----------------------------

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("api_states"))

    for module_name in (
        "main", "config", "router", "gemini_cached_client",
        "response_generator", "translator", "standard_responses",
        "localization", "social_state", "persistence_manager",
    ):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


def test_transport_failure_english_user_gets_english_apology(client, monkeypatch):
    main = sys.modules["main"]

    async def failing_route(user_message, history=None, user_id="anonymous"):
        raise OpenRouterTimeout("timeout after 30s")

    monkeypatch.setattr(main.router, "route", failing_route)
    body = client.post(
        "/chat", json={"user_id": "api_en_fail", "message": "Hello there my friend"}
    ).json()
    assert not CYRILLIC_RE.search(body["response"]), body["response"]
    assert body["detected_language"] == "en"
