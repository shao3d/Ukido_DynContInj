"""P1: кодовые эвристики понимают английскую речь.

Все тесты полностью офлайн — ни одного LLM-вызова. Покрывают:
1. CompletedActionsHandler: EN-триггеры завершённых действий + EN-ответы.
2. SimpleCTABlocker: EN-триггеры отказов и завершённых действий.
3. ResponseGenerator._should_add_offer: EN skip-фразы и CTA-rate-limiting.
4. Router._expand_ultra_short_question: EN ультра-краткие реплики.
5. Фильтр EN offtopic из истории (сквозной, с замоканным LLM).
6. /trial-signup с полем language (с фейковым HubSpot).
"""

import importlib
import os
import re
import sys
import types

import pytest
from fastapi.testclient import TestClient

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")
os.environ.setdefault("DETERMINISTIC_MODE", "true")

from completed_actions_handler import CompletedActionsHandler  # noqa: E402
from simple_cta_blocker import SimpleCTABlocker  # noqa: E402
from localization import TRIAL_SIGNUP_MESSAGES  # noqa: E402


def assert_no_cyrillic(text: str, scenario: str):
    match = CYRILLIC_RE.search(text or "")
    assert not match, f"[{scenario}] кириллица в EN-ответе: {text!r}"


# ============================================================================
# 1. CompletedActionsHandler — EN-триггеры и EN-ответы
# ============================================================================

class TestCompletedActionsEnglish:
    def setup_method(self):
        self.handler = CompletedActionsHandler()

    @staticmethod
    def offtopic_route(lang="en"):
        return {"status": "offtopic", "detected_language": lang, "decomposed_questions": []}

    def test_en_paid_for_course_detected_with_en_response(self):
        result = self.handler.detect_completed_action(
            "I've paid for the course", self.offtopic_route("en"), []
        )
        assert result["status"] == "success"
        assert result["_action_detected"] == "payment"
        assert_no_cyrillic(result["completed_action_response"], "payment EN")
        assert all(not CYRILLIC_RE.search(q) for q in result["decomposed_questions"])
        assert result["documents"]

    def test_en_paid_with_school_history_only(self):
        history = [
            {"role": "user", "content": "How much are the courses?"},
            {"role": "assistant", "content": "Our courses cost 6,000 UAH per month."},
        ]
        result = self.handler.detect_completed_action(
            "I've paid", self.offtopic_route("en"), history
        )
        assert result["status"] == "success"
        assert result["_action_detected"] == "payment"
        assert_no_cyrillic(result["completed_action_response"], "payment по истории")

    def test_en_signed_up_detected(self):
        result = self.handler.detect_completed_action(
            "We signed up yesterday", self.offtopic_route("en"), []
        )
        assert result["status"] == "success"
        assert result["_action_detected"] == "registration"
        assert_no_cyrillic(result["completed_action_response"], "registration EN")

    def test_en_filled_the_form_detected(self):
        result = self.handler.detect_completed_action(
            "I filled out the form on your website", self.offtopic_route("en"), []
        )
        assert result["status"] == "success"
        assert result["_action_detected"] == "form"
        assert_no_cyrillic(result["completed_action_response"], "form EN")

    def test_en_paid_for_gas_stays_offtopic(self):
        # Оплата НЕ школьного контекста — исключение по слову 'gas'
        result = self.handler.detect_completed_action(
            "I paid for gas yesterday", self.offtopic_route("en"), []
        )
        assert result["status"] == "offtopic"
        assert "completed_action_response" not in result

    def test_ru_payment_still_russian_response(self):
        result = self.handler.detect_completed_action(
            "Оплатила курс", self.offtopic_route("ru"), []
        )
        assert result["status"] == "success"
        assert CYRILLIC_RE.search(result["completed_action_response"])

    def test_every_action_group_has_en_responses(self):
        for action_type, patterns in self.handler.ACTION_PATTERNS.items():
            assert patterns.get("responses_en"), f"{action_type}: нет responses_en"
            assert patterns.get("implicit_questions_en"), f"{action_type}: нет implicit_questions_en"
            assert len(patterns["responses_en"]) <= len(patterns["responses"])
            for phrase in patterns["responses_en"] + patterns["implicit_questions_en"]:
                assert not CYRILLIC_RE.search(phrase), f"{action_type}: кириллица в EN-фразе {phrase!r}"


# ============================================================================
# 2. SimpleCTABlocker — EN-отказы и завершённые действия
# ============================================================================

class TestCTABlockerEnglish:
    def setup_method(self):
        self.blocker = SimpleCTABlocker()

    def test_en_hard_refusal(self):
        assert self.blocker.check_refusal("user_en", "No thanks, stop offering", 5) == "hard"

    def test_en_soft_refusal(self):
        assert self.blocker.check_refusal("user_en", "I'll think about it", 5) == "soft"

    def test_en_soft_refusal_consult_spouse(self):
        assert self.blocker.check_refusal("user_en", "Need to talk to my husband first", 5) == "soft"

    def test_en_completed_registration_blocks_cta(self):
        assert self.blocker.check_completed_action("user_en", "I already signed up for the course") == "registered"
        blocked, reason = self.blocker.should_block_cta("user_en", 6, "ready_to_buy")
        assert blocked, "посершение 'registered' должно блокировать CTA записи"
        assert reason == "user_already_registered"

    def test_en_paid_blocks_price_cta(self):
        assert self.blocker.check_completed_action("user_en2", "I've paid for the course") == "paid"
        blocked, reason = self.blocker.should_block_cta("user_en2", 6, "price_sensitive")
        assert blocked
        assert reason == "user_already_paid"

    def test_ru_refusal_regression(self):
        assert self.blocker.check_refusal("user_ru", "Не надо, хватит предлагать", 5) == "hard"

    def test_neutral_message_triggers_nothing(self):
        assert self.blocker.check_refusal("user_en3", "What is the price for the course?", 5) is None
        assert self.blocker.check_completed_action("user_en3", "What is the price for the course?") is None


# ============================================================================
# 3. ResponseGenerator._should_add_offer — EN skip-фразы
# ============================================================================

class TestShouldAddOfferEnglish:
    def setup_method(self):
        from response_generator import ResponseGenerator
        self.generator = ResponseGenerator()

    def test_exploring_price_mention_blocks_cta(self):
        history = [
            {"role": "user", "content": "How much does it cost?"},
            {"role": "assistant", "content": "The price depends on the program."},
        ]
        assert self.generator._should_add_offer("exploring_only", history, {}, "Sounds good") is False

    def test_price_sensitive_direct_discount_question_skips_cta(self):
        assert self.generator._should_add_offer(
            "price_sensitive", [], {}, "Do you have any discounts?"
        ) is False

    def test_ready_to_buy_already_signed_up_skips_cta(self):
        assert self.generator._should_add_offer(
            "ready_to_buy", [], {}, "I already signed up yesterday"
        ) is False

    def test_ready_to_buy_recent_en_cta_rate_limited(self):
        history = [
            {"role": "assistant", "content": "You can sign up on our website and book a free trial."},
        ]
        assert self.generator._should_add_offer("ready_to_buy", history, {}, "Tell me more") is False

    def test_global_spacing_en_cta(self):
        history = [
            {"role": "user", "content": "Tell me about teachers"},
            {"role": "assistant", "content": "Great question! The first class is free, so sign up anytime to meet them."},
        ]
        # Последний ответ ассистента содержит EN CTA — минимум 3 сообщения между CTA
        assert self.generator._should_add_offer("exploring_only", history, {}, "What else?") is False

    def test_ru_discount_question_regression(self):
        assert self.generator._should_add_offer("price_sensitive", [], {}, "Какие есть скидки?") is False


# ============================================================================
# 4. Router._expand_ultra_short_question — EN реплики
# ============================================================================

class TestUltraShortEnglish:
    def setup_method(self):
        from router import Router
        self.router = Router(use_cache=False)

    def test_en_and_after_price_answer(self):
        history = [{"role": "assistant", "content": "Our price is 6,000 UAH per month."}]
        expanded = self.router._expand_ultra_short_question("and?", history)
        assert expanded == "Tell me more about prices and discounts"
        assert_no_cyrillic(expanded, "and? про цены")

    def test_en_so_after_course_answer(self):
        history = [{"role": "assistant", "content": "We run three courses for different ages."}]
        expanded = self.router._expand_ultra_short_question("so?", history)
        assert expanded == "Tell me more about your courses"

    def test_en_generic_expansion(self):
        history = [{"role": "assistant", "content": "Our teachers are practicing psychologists."}]
        expanded = self.router._expand_ultra_short_question("that's it?", history)
        assert expanded == "Please tell me more details"
        assert_no_cyrillic(expanded, "generic EN")

    def test_ru_ultra_short_regression(self):
        history = [{"role": "assistant", "content": "Стоимость курса 6000 грн в месяц."}]
        expanded = self.router._expand_ultra_short_question("а?", history)
        assert expanded == "Расскажите подробнее о ценах и скидках"

    def test_no_history_unchanged(self):
        assert self.router._expand_ultra_short_question("and?", []) == "and?"

    def test_normal_message_unchanged(self):
        history = [{"role": "assistant", "content": "Prices are fine."}]
        assert self.router._expand_ultra_short_question("What about discounts?", history) == "What about discounts?"


# ============================================================================
# 5-6. Сквозные: фильтр EN offtopic из истории + trial-signup language
# ============================================================================

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("p1_states"))
    for module_name in (
        "main", "config", "router", "gemini_cached_client", "response_generator",
        "translator", "standard_responses", "localization", "social_state",
        "persistence_manager", "completed_actions_handler", "simple_cta_blocker",
    ):
        sys.modules.pop(module_name, None)
    return TestClient(importlib.import_module("main").app)


def test_en_offtopic_filtered_from_history(client, monkeypatch):
    """EN offtopic-пары не должны попадать в историю для генератора."""
    main = sys.modules["main"]

    async def offtopic_route(user_message, history=None, user_id="anonymous"):
        return {
            "status": "offtopic", "detected_language": "en",
            "decomposed_questions": [], "user_signal": "exploring_only",
            "social_context": None, "original_message": user_message,
        }

    monkeypatch.setattr(main.router, "route", offtopic_route)
    first = client.post("/chat", json={"user_id": "p1_filter", "message": "Do you also teach cooking?"})
    assert first.status_code == 200
    assert_no_cyrillic(first.json()["response"], "EN offtopic")

    captured = {"history": None}

    async def success_route(user_message, history=None, user_id="anonymous"):
        return {
            "status": "success", "detected_language": "en",
            "documents": ["faq.md"],
            "decomposed_questions": ["What courses do you have?"],
            "user_signal": "exploring_only", "social_context": None,
            "original_message": user_message,
        }

    async def capture_generate(router_result, history=None, current_message=None):
        captured["history"] = list(history or [])
        return "English answer.", {"intent": "success", "user_signal": "exploring_only",
                                   "cta_added": False, "cta_type": None, "humor_generated": False}

    monkeypatch.setattr(main.router, "route", success_route)
    monkeypatch.setattr(main.response_generator, "generate", capture_generate)

    second = client.post("/chat", json={"user_id": "p1_filter", "message": "What courses do you have?"})
    assert second.status_code == 200

    passed_history = captured["history"] or []
    offtopic_leaked = any(
        CYRILLIC_RE.search(m.get("content", "")) is None
        and m.get("role") == "assistant"
        and any(marker in m.get("content", "") for marker in
                ("get back to Ukido", "outside my expertise", "Not really my area", "Let's talk school"))
        for m in passed_history
    )
    assert not offtopic_leaked, f"EN offtopic не отфильтрован из истории: {passed_history!r}"


class FakeHubSpotClient:
    async def create_or_update_contact(self, **kwargs):
        return {"contact_id": "hubspot-secret-id", "action": "created", "existing": False}

    async def close(self):
        return None


def _install_fake_hubspot(monkeypatch):
    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "HUBSPOT_PRIVATE_APP_TOKEN", "test-hubspot-token")
    monkeypatch.setitem(
        sys.modules, "hubspot_client",
        types.SimpleNamespace(HubSpotClient=FakeHubSpotClient),
    )


def test_trial_signup_english_message(client, monkeypatch):
    _install_fake_hubspot(monkeypatch)
    response = client.post("/trial-signup", json={
        "firstName": "John", "lastName": "Smith",
        "email": "john@example.com", "phone": "+1 555 123 4567",
        "language": "en",
    })
    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert_no_cyrillic(body["message"], "trial-signup EN")
    assert "contact_id" not in body


def test_trial_signup_default_is_russian(client, monkeypatch):
    _install_fake_hubspot(monkeypatch)
    response = client.post("/trial-signup", json={
        "firstName": "Anna", "lastName": "Ivanova", "email": "anna@example.com",
    })
    body = response.json()
    assert response.status_code == 200
    assert CYRILLIC_RE.search(body["message"]), "без language сообщение должно быть русским"


def test_trial_signup_rejects_bad_language(client, monkeypatch):
    _install_fake_hubspot(monkeypatch)
    response = client.post("/trial-signup", json={
        "firstName": "John", "lastName": "Smith", "email": "john@example.com",
        "language": "fr",
    })
    assert response.status_code == 422


def test_trial_signup_messages_complete():
    assert set(TRIAL_SIGNUP_MESSAGES["ru"].keys()) == set(TRIAL_SIGNUP_MESSAGES["en"].keys())
    for message in TRIAL_SIGNUP_MESSAGES["en"].values():
        assert message.strip()
        assert not CYRILLIC_RE.search(message)
