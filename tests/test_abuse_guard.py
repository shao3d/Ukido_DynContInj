"""SEC-05: анти-абьюз — лимиты по ключу/IP, общий бюджет, самоочистка.

Проверяем и сам лимитер (на фейковых часах), и интеграцию в main:
ротация user_id больше не обходит защиту (есть лимит по IP), /trial-signup
ограничен, а создание/обновление контакта не раскрывается.
"""

import importlib
import os
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rate_limiter import GlobalMinuteBudget, RateLimiter, RateLimitExceeded  # noqa: E402


class FakeClock:
    def __init__(self, t: float = 1_700_000_000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# ============================================================================
# Лимитер (фейковые часы)
# ============================================================================

def test_per_minute_limit():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=3, per_day=100, clock=clock)
    for _ in range(3):
        limiter.hit("k")
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.hit("k")
    assert exc.value.retry_after == 60


def test_minute_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=2, per_day=100, clock=clock)
    limiter.hit("k")
    limiter.hit("k")
    clock.advance(61)
    limiter.hit("k")  # окно уехало — снова можно


def test_per_day_limit_and_reset():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=100, per_day=3, clock=clock)
    for _ in range(3):
        limiter.hit("k")
    with pytest.raises(RateLimitExceeded):
        limiter.hit("k")
    clock.advance(86401)
    limiter.hit("k")  # новый день


def test_stale_keys_are_swept():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=10, per_day=10, max_keys=100, clock=clock)
    for i in range(5):
        limiter.hit(f"k{i}")
    clock.advance(86401)
    limiter.hit("fresh")  # триггерит sweep? нужен интервал
    clock.advance(301)
    limiter.hit("fresh")
    assert limiter.tracked_keys() <= 2


def test_max_keys_cap():
    clock = FakeClock()
    limiter = RateLimiter(per_minute=5, per_day=5, max_keys=3, clock=clock)
    for i in range(5):
        limiter.hit(f"k{i}")
    assert limiter.tracked_keys() == 3


def test_global_budget():
    clock = FakeClock()
    budget = GlobalMinuteBudget(per_minute=2, clock=clock)
    budget.hit()
    budget.hit()
    with pytest.raises(RateLimitExceeded):
        budget.hit()


# ============================================================================
# Интеграция в main
# ============================================================================

def _reload_main(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test_key_for_ci")
    monkeypatch.setenv("DETERMINISTIC_MODE", "true")
    monkeypatch.setenv("PERSISTENCE_BASE_PATH", str(tmp_path))
    for name in (
        "main", "config", "router", "gemini_cached_client", "response_generator",
        "translator", "standard_responses", "localization", "social_state",
        "persistence_manager", "completed_actions_handler", "simple_cta_blocker",
    ):
        sys.modules.pop(name, None)
    return importlib.import_module("main")


def test_check_rate_limits_raises_429(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=2, per_day=100)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=100, per_day=100)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=1000)
    main._CLIENT_IP.set("203.0.113.10")

    main.check_rate_limits("u1")
    main.check_rate_limits("u1")
    with pytest.raises(HTTPException) as exc:
        main.check_rate_limits("u1")
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "60"


def test_ip_limit_is_not_bypassed_by_rotating_user_id(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=100, per_day=1000)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=3, per_day=1000)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=1000)
    main._CLIENT_IP.set("203.0.113.11")

    for i in range(3):
        main.check_rate_limits(f"rotating-{i}")
    with pytest.raises(HTTPException) as exc:
        main.check_rate_limits("rotating-99")
    assert exc.value.status_code == 429


def test_local_ip_is_not_ip_limited(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=100, per_day=1000)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=1, per_day=1000)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=1000)
    main._CLIENT_IP.set("127.0.0.1")

    for i in range(10):
        main.check_rate_limits(f"local-{i}")  # не должно троттлить


def test_user_signals_history_is_capped(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    main.MAX_USER_SIGNALS = 3
    for i in range(5):
        main.remember_user_signal(f"u{i}", "price_sensitive")
    assert len(main.user_signals_history) <= 3


# --- HTTP-слой ---------------------------------------------------------------

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("abuse_states"))
    for name in (
        "main", "config", "router", "gemini_cached_client", "response_generator",
        "translator", "standard_responses", "localization", "social_state",
        "persistence_manager", "completed_actions_handler", "simple_cta_blocker",
    ):
        sys.modules.pop(name, None)
    app = importlib.import_module("main").app
    return TestClient(app)


def _mock_pipeline(monkeypatch):
    main = sys.modules["main"]

    async def fake_route(user_message, history=None, user_id="anonymous"):
        return {
            "status": "offtopic", "detected_language": "ru",
            "decomposed_questions": [], "user_signal": "exploring_only",
            "social_context": None, "original_message": user_message,
        }

    async def fake_generate(router_result, history=None, current_message=None):
        return "Ответ.", {"intent": "offtopic", "user_signal": "exploring_only",
                          "cta_added": False, "cta_type": None, "humor_generated": False}

    monkeypatch.setattr(main.router, "route", fake_route)
    monkeypatch.setattr(main.response_generator, "generate", fake_generate)
    return main


def test_chat_endpoint_returns_429_for_same_user(client, monkeypatch):
    main = _mock_pipeline(monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=3, per_day=1000)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=1000, per_day=1000)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=100000)

    for _ in range(3):
        assert client.post("/chat", json={"user_id": "rl_user", "message": "привет"}).status_code == 200
    blocked = client.post("/chat", json={"user_id": "rl_user", "message": "привет"})
    assert blocked.status_code == 429
    assert blocked.headers.get("retry-after") == "60"


def test_chat_endpoint_ip_limit_via_forwarded_for(client, monkeypatch):
    main = _mock_pipeline(monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=1000, per_day=10000)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=2, per_day=10000)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=100000)

    headers = {"X-Forwarded-For": "198.51.100.23"}
    assert client.post("/chat", json={"user_id": "ip_a", "message": "hi"}, headers=headers).status_code == 200
    assert client.post("/chat", json={"user_id": "ip_b", "message": "hi"}, headers=headers).status_code == 200
    blocked = client.post("/chat", json={"user_id": "ip_c", "message": "hi"}, headers=headers)
    assert blocked.status_code == 429


def test_chat_stream_is_rate_limited(client, monkeypatch):
    """SSE-эндпоинт идёт через chat(), поэтому лимит применяется и там."""
    main = _mock_pipeline(monkeypatch)
    main._CHAT_USER_LIMITER = RateLimiter(per_minute=1, per_day=1000)
    main._CHAT_IP_LIMITER = RateLimiter(per_minute=1000, per_day=1000)
    main._GLOBAL_MINUTE_BUDGET = GlobalMinuteBudget(per_minute=100000)

    first = client.get(
        "/chat/stream", params={"user_id": "stream_rl", "message": "привет"}
    )
    assert first.status_code == 200
    assert "event: done" in first.text

    blocked = client.get(
        "/chat/stream", params={"user_id": "stream_rl", "message": "привет"}
    )
    assert blocked.status_code == 200  # SSE: лимит отдаётся как error-событие
    assert "Ошибка при обработке сообщения" in blocked.text
    assert "event: done" not in blocked.text


class _FakeHubSpot:
    async def create_or_update_contact(self, **kwargs):
        return {"contact_id": "secret-id", "action": "created", "existing": False}

    async def close(self):
        return None


def test_trial_signup_rate_limited_by_ip(client, monkeypatch):
    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "HUBSPOT_PRIVATE_APP_TOKEN", "token")
    monkeypatch.setitem(sys.modules, "hubspot_client", types.SimpleNamespace(HubSpotClient=_FakeHubSpot))
    main._SIGNUP_IP_LIMITER = RateLimiter(per_minute=2, per_day=100)

    headers = {"X-Forwarded-For": "198.51.100.77"}
    payload = {"firstName": "Anna", "lastName": "Ivanova", "email": "a@example.com"}
    assert client.post("/trial-signup", json=payload, headers=headers).status_code == 200
    assert client.post("/trial-signup", json=payload, headers=headers).status_code == 200
    blocked = client.post("/trial-signup", json=payload, headers=headers)
    assert blocked.status_code == 429


def test_trial_signup_is_not_creation_oracle(client, monkeypatch):
    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "HUBSPOT_PRIVATE_APP_TOKEN", "token")
    monkeypatch.setitem(sys.modules, "hubspot_client", types.SimpleNamespace(HubSpotClient=_FakeHubSpot))
    main._SIGNUP_IP_LIMITER = RateLimiter(per_minute=100, per_day=1000)

    headers = {"X-Forwarded-For": "198.51.100.88"}
    body = client.post(
        "/trial-signup",
        json={"firstName": "Anna", "lastName": "Ivanova", "email": "oracle@example.com"},
        headers=headers,
    ).json()
    assert body["success"] is True
    assert body.get("action") is None
    assert "contact_id" not in body
