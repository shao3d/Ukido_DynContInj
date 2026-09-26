"""P0: стражи против «невпопад» ответов.

Регрессии ревью диалогового качества:
1. CTA в агрессивном контексте («деньги выкачиваете» → скидка в лоб) — запрещён.
2. Шаблонные плейсхолдеры («это всего ... в месяц») не протекают в промпт.
3. Завершённое действие на success-ветке уходит в генератор инструкцией,
   а не приклеенным префиксом поверх противоречащего текста.
4. Контакты записи — только из Config (никаких выдуманных телефонов).
5. Чистые acknowledgments («ок», 👍) отвечаются детерминированно без роутера,
   кроме случая, когда последний ответ — вопрос (тогда это может быть согласие).
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")

from response_generator import ResponseGenerator, is_aggressive_message  # noqa: E402


# --- 1. Агрессия по стеммам ---------------------------------------------------

@pytest.mark.parametrize("message", [
    "Это лабуда, soft skills придумали чтобы деньги выкачивать",
    "Все ваши психологи — шарлатаны",
    "Это вообще развод?",
    "Враньё всё это",
    "Грабёж среди бела дня",
    "Это шахраї викрадають гроші",  # uk
    "Is this a scam?",
])
def test_aggressive_detection_stems(message):
    assert is_aggressive_message(message) is True


@pytest.mark.parametrize("message", [
    "Сколько стоит курс для 10-летнего?",
    "Дорого, но хочу понять что входит",
    None,
    "",
])
def test_aggressive_detection_no_false_positives(message):
    assert is_aggressive_message(message) is False


def test_should_add_offer_skips_aggressive_context():
    """CTA не предлагается в агрессивном контексте (раньше начинали со скидки)."""
    gen = ResponseGenerator()
    offer = {"text": "У нас скидка 10%", "priority": "medium"}
    assert gen._should_add_offer(
        "price_sensitive", [], offer,
        current_message="Это развод, вы просто деньги выкачиваете",
    ) is False


# --- 2. Промпт без императивов и плейсхолдеров --------------------------------

def _price_router_result(**overrides):
    result = {
        "status": "success",
        "user_signal": "price_sensitive",
        "decomposed_questions": ["Почему так дорого?"],
        "original_message": "7000 грн — это грабёж!",
        "social_context": None,
        "user_completed_action": None,
        "detected_language": "ru",
    }
    result.update(overrides)
    return result


def test_price_cta_no_imperative_start_and_no_placeholders():
    gen = ResponseGenerator()
    messages = gen._build_messages(
        {"pricing.md": "- Месяц: 6,000 грн"}, ["Почему так дорого?"],
        [], _price_router_result(), cta_text="Скидка 10% при полной оплате.",
    )
    whole = "\n".join(m["content"] for m in messages)
    assert "НАЧНИ ОТВЕТ С ИНФОРМАЦИИ О СКИДКЕ" not in whole
    assert "ПРОВАЛЬНЫМ" not in whole
    assert "🔴🔴🔴" not in whole
    # плейсхолдеры «...» (модель копировала их в ответ дословно)
    assert "это всего ... в месяц" not in whole
    assert "снижает стоимость до..." not in whole
    assert "скидка 15% на второго ребенка..." not in whole


# --- 3. Завершённое действие — инструкция в промпт ----------------------------

def test_completed_action_instructs_generator_instead_of_prefix_glue():
    gen = ResponseGenerator()
    messages = gen._build_messages(
        {"faq.md": "- Как записаться: через форму"}, ["Как записаться?"],
        [], _price_router_result(user_completed_action="registered"),
        cta_text=None,
    )
    user_tail = messages[-1]["content"]
    assert "УЖЕ выполнил действие" in user_tail
    assert "запись" in user_tail
    assert "НЕ предлагай" in user_tail


# --- 4. Контакты из Config ----------------------------------------------------

def test_contact_suffix_has_no_unverified_phone_by_default():
    gen = ResponseGenerator()
    gen.cfg.CONTACT_PHONE = ""
    suffix = gen._build_contact_suffix()
    assert "+380" not in suffix
    assert gen.cfg.TRIAL_SIGNUP_URL in suffix


def test_contact_suffix_includes_configured_phone():
    gen = ResponseGenerator()
    gen.cfg.CONTACT_PHONE = "+380 99 000 00 00"
    suffix = gen._build_contact_suffix()
    assert "+380 99 000 00 00" in suffix
    gen.cfg.CONTACT_PHONE = ""  # не трогаем других тестов


# --- 5. Детерминированный acknowledgment до роутера ---------------------------

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


def test_pure_ack_skips_router(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    route_calls = []

    async def fake_route(user_message, history=None, user_id="anonymous"):
        route_calls.append(user_message)
        return {"status": "offtopic", "detected_language": "ru",
                "decomposed_questions": [], "user_signal": "exploring_only",
                "social_context": None, "original_message": user_message}

    monkeypatch.setattr(main.router, "route", fake_route)

    from fastapi.testclient import TestClient
    with TestClient(main.app) as client:
        resp = client.post("/chat", json={"user_id": "ack_u1", "message": "ок"})
    assert resp.status_code == 200
    assert route_calls == []  # роутер не вызывался — ответ детерминированный
    assert resp.json()["social"] == "acknowledgment"


def test_consent_like_ack_after_question_goes_to_router(monkeypatch, tmp_path):
    main = _reload_main(tmp_path, monkeypatch)
    route_calls = []

    async def fake_route(user_message, history=None, user_id="anonymous"):
        route_calls.append(user_message)
        return {"status": "offtopic", "detected_language": "ru",
                "decomposed_questions": [], "user_signal": "exploring_only",
                "social_context": "acknowledgment", "original_message": user_message}

    monkeypatch.setattr(main.router, "route", fake_route)
    # Последний ответ ассистента — вопрос: «ок» может быть согласием
    main.history.add_message("ack_u2", "assistant", "Хотите, я расскажу подробнее?")

    from fastapi.testclient import TestClient
    with TestClient(main.app) as client:
        resp = client.post("/chat", json={"user_id": "ack_u2", "message": "ок"})
    assert resp.status_code == 200
    assert route_calls == ["ок"]  # роутер вызван — решение за LLM
