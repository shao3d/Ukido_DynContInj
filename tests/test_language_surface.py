"""P0 мультиязычности: английский пользователь не получает русские ответы.

Два уровня проверки:
1. Юнит-тесты localization.py (словари, resolve_language, has_cyrillic).
2. Сквозные тесты /chat с замоканным LLM. Главный инвариант P0:
   для effective_language=en в финальном ответе НЕТ кириллических символов —
   ни в одной ветке (social, offtopic, need_simplification, ошибки,
   pre-generated ответы, юмор).
"""

import importlib
import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def assert_no_cyrillic(text: str, scenario: str):
    match = CYRILLIC_RE.search(text or "")
    assert not match, (
        f"[{scenario}] В ответе для EN-пользователя осталась кириллица "
        f"('{match.group(0)}' рядом с '...{text[max(0, match.start()-20):match.start()+20]}...'): {text!r}"
    )


# ============================================================================
# Уровень 1: юнит-тесты localization
# ============================================================================

from localization import (  # noqa: E402
    FALLBACK,
    OFFTOPIC_RESPONSES,
    NEED_SIMPLIFICATION,
    ERROR_RESPONSES,
    GREETINGS,
    THANKS_RESPONSES,
    APOLOGY_RESPONSES,
    ACKNOWLEDGMENT_RESPONSES,
    FAREWELLS,
    FAREWELL_ADDONS,
    THANKS_PREFIXES_SUCCESS,
    has_cyrillic,
    resolve_language,
    is_confident_language_signal,
    get_offtopic_response,
    get_error_response,
)

LIST_DICTS = [
    OFFTOPIC_RESPONSES,
    GREETINGS,
    THANKS_RESPONSES,
    APOLOGY_RESPONSES,
    ACKNOWLEDGMENT_RESPONSES,
    FAREWELLS,
    FAREWELL_ADDONS,
    THANKS_PREFIXES_SUCCESS,
]

STR_DICTS = [FALLBACK, NEED_SIMPLIFICATION]


@pytest.mark.parametrize("name,dictionary", [(getattr(d, "__name__", f"dict_{i}"), d) for i, d in enumerate(LIST_DICTS)])
def test_list_dictionaries_have_ru_and_en(name, dictionary):
    assert set(dictionary.keys()) == {"ru", "en"}, f"{name}: ждём ровно ru и en, есть {sorted(dictionary.keys())}"
    assert len(dictionary["ru"]) == len(dictionary["en"]) > 0, f"{name}: разное число фраз ru/en"
    for lang in ("ru", "en"):
        assert all(isinstance(p, str) and p.strip() for p in dictionary[lang]), f"{name}[{lang}]: пустые фразы"


@pytest.mark.parametrize("name,dictionary", [(getattr(d, "__name__", f"str_{i}"), d) for i, d in enumerate(STR_DICTS)])
def test_string_dictionaries_have_ru_and_en(name, dictionary):
    assert set(dictionary.keys()) == {"ru", "en"}
    assert all(dictionary[lang].strip() for lang in ("ru", "en"))


def test_error_responses_cover_same_keys_for_ru_and_en():
    assert set(ERROR_RESPONSES["ru"].keys()) == set(ERROR_RESPONSES["en"].keys())


def test_en_phrases_contain_no_cyrillic():
    """Каждая английская фраза действительно без кириллицы."""
    phrases = []
    for dictionary in LIST_DICTS + STR_DICTS:
        values = dictionary["en"]
        phrases.extend(values if isinstance(values, list) else [values])
    phrases.extend(ERROR_RESPONSES["en"].values())
    for phrase in phrases:
        assert isinstance(phrase, str) and phrase.strip()
        assert not CYRILLIC_RE.search(phrase), f"Кириллица в EN-фразе: {phrase!r}"


def test_has_cyrillic():
    assert has_cyrillic("Привет")
    assert has_cyrillic("українська")
    assert not has_cyrillic("Hello, world!")
    assert not has_cyrillic("👍 ok 123")
    assert not has_cyrillic("")


class TestResolveLanguage:
    def test_router_result_trusted_by_default(self):
        assert resolve_language("en", "How much does the course cost?", "ru") == "en"
        assert resolve_language("ru", "Сколько стоит курс?", "en") == "ru"
        assert resolve_language("uk", "Скільки коштує?", "ru") == "uk"

    def test_emoji_in_en_session_stays_en(self):
        # Роутер на эмодзи отвечает ru — сессия должна удержать английский
        assert resolve_language("ru", "👍", "en") == "en"
        assert resolve_language("ru", "👍", "uk") == "uk"

    def test_short_latin_reply_in_ru_session_stays_ru(self):
        # Русскоязычный родитель пишет "ok" — язык диалога не должен прыгать
        assert resolve_language("en", "ok", "ru") == "ru"
        assert resolve_language("en", "yes", "ru") == "ru"

    def test_short_latin_from_fresh_user_trusts_router(self):
        # Новому пользователю с неустановленной сессией верим роутеру
        assert resolve_language("en", "ok", None) == "en"

    def test_emoji_from_fresh_user_defaults_to_ru(self):
        assert resolve_language("ru", "👍", None) == "ru"

    def test_long_english_message_switches_to_en(self):
        assert resolve_language("en", "Sounds interesting, tell me more", "ru") == "en"

    def test_clearly_latin_message_with_ru_router_result_corrected(self):
        # Роутер упал или ошибся: сообщение явно латинское → en даже без сессии
        assert resolve_language("ru", "Hello there friend", "ru") == "en"

    def test_mixed_message_with_cyrillic_stays_ru(self):
        assert resolve_language("ru", "Hi! Сколько стоит?", "en") == "ru"

    def test_unknown_language_falls_back_to_latin_logic(self):
        # Неизвестный код языка нормализуется в ru, но латинский текст
        # корректируется до en — английский как разумный фоллбек для латиницы
        assert resolve_language("de", "Guten Tag", "ru") == "en"
        assert resolve_language("de", "Привет всем", "ru") == "ru"


class TestConfidentSignal:
    def test_cyrillic_message_is_confident_for_ru(self):
        assert is_confident_language_signal("ru", "Сколько стоит?")

    def test_short_latin_is_not_confident_for_en(self):
        assert not is_confident_language_signal("en", "ok")

    def test_long_latin_is_confident_for_en(self):
        assert is_confident_language_signal("en", "Hello there friend")

    def test_emoji_is_not_confident(self):
        assert not is_confident_language_signal("en", "👍")
        assert not is_confident_language_signal("ru", "👍")


# ============================================================================
# Уровень 2: сквозные тесты /chat с замоканным LLM
# ============================================================================

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("lang_states"))

    for module_name in (
        "main",
        "config",
        "router",
        "gemini_cached_client",
        "response_generator",
        "translator",
        "standard_responses",
        "localization",
        "social_state",
        "persistence_manager",
    ):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


class RecordingTranslator:
    """Мок переводчика: пишет вызовы, возвращает маркер без кириллицы."""

    def __init__(self):
        self.calls = []

    async def translate(self, text, target_language, source_language="ru", user_context=None):
        self.calls.append({"text": text, "target": target_language, "context": user_context})
        return f"[translated-to-{target_language}]"


def make_route(status="success", lang="en", documents=None, questions=None,
              user_signal="exploring_only", social_context=None, **extra):
    result = {
        "status": status,
        "detected_language": lang,
        "decomposed_questions": questions or ["What courses do you have?"],
        "user_signal": user_signal,
        "social_context": social_context,
        "fuzzy_matched": False,
        "original_message": "hello",
    }
    if status == "success":
        result["documents"] = documents or ["faq.md"]
    else:
        result["message"] = "Интересный вопрос! Но давайте вернёмся к теме школы Ukido. Чем могу помочь?"
    result.update(extra)
    return result


async def fake_generate_success(router_result, history=None, current_message=None):
    metadata = {
        "intent": "success",
        "user_signal": router_result.get("user_signal", "exploring_only"),
        "cta_added": False,
        "cta_type": None,
        "humor_generated": False,
    }
    if router_result.get("detected_language", "ru") != "ru":
        metadata["translated_to"] = router_result.get("detected_language")
        return "English answer about our courses and prices.", metadata
    return "Русский ответ о курсах и ценах.", metadata


def post_chat(client, user_id, message):
    response = client.post("/chat", json={"user_id": user_id, "message": message})
    assert response.status_code == 200, response.text
    return response.json()


def install_mocks(monkeypatch, main, route_result=None, route_exc=None, generate=None, translator=None):
    async def fake_route(user_message, history=None, user_id="anonymous"):
        if route_exc is not None:
            raise route_exc
        result = dict(route_result)
        result["original_message"] = user_message
        return result

    async def fake_generate(router_result, history=None, current_message=None):
        if generate is not None:
            return generate(router_result, history, current_message)
        return await fake_generate_success(router_result, history, current_message)

    monkeypatch.setattr(main.router, "route", fake_route)
    monkeypatch.setattr(main.response_generator, "generate", fake_generate)
    if translator is not None:
        monkeypatch.setattr(main.response_generator, "translator", translator)


def test_en_pure_thanks_gets_english_reply(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="offtopic", lang="en", social_context="thanks"),
        translator=translator,
    )

    body = post_chat(client, "lang_en_thanks", "Thanks a lot!")

    assert_no_cyrillic(body["response"], "pure thanks")
    assert body["detected_language"] == "en"
    assert translator.calls == [], "EN canned-фраза должна идти из словаря, без LLM-перевода"


def test_en_farewell_gets_english_reply(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="offtopic", lang="en", social_context="farewell"),
        translator=translator,
    )

    body = post_chat(client, "lang_en_bye", "Goodbye!")
    assert_no_cyrillic(body["response"], "farewell")
    assert translator.calls == []


def test_en_greeting_gets_english_reply(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="offtopic", lang="en", social_context="greeting"),
        translator=translator,
    )

    body = post_chat(client, "lang_en_hi", "Hello!")
    assert_no_cyrillic(body["response"], "greeting")
    assert translator.calls == []


def test_en_emoji_keeps_session_language_after_english_start(client, monkeypatch):
    """Сценарий демо: англоговорящий начал по-английски, потом прислал эмодзи.

    Роутер на эмодзи возвращает ru — sticky-память должна удержать английский.
    """
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="en"),
        translator=translator,
    )

    first = post_chat(client, "lang_en_sticky", "Hello, tell me about your school")
    assert_no_cyrillic(first["response"], "первое EN сообщение")

    async def emoji_route(user_message, history=None, user_id="anonymous"):
        # Роутер на "👍" отдаёт ru + acknowledgment (как реальный Gemini)
        return make_route(status="offtopic", lang="ru", social_context="acknowledgment")

    monkeypatch.setattr(main.router, "route", emoji_route)
    second = post_chat(client, "lang_en_sticky", "👍")
    assert_no_cyrillic(second["response"], "эмодзи после EN-сессии")
    assert translator.calls == []


def test_ru_session_short_ok_stays_russian(client, monkeypatch):
    """Регрессионная защита: русский родитель пишет 'ok' — ответ остаётся русским."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="ru"),
        translator=translator,
    )

    first = post_chat(client, "lang_ru_sticky", "Привет, расскажите о курсах")
    assert "Русский ответ" in first["response"]

    async def ok_route(user_message, history=None, user_id="anonymous"):
        return make_route(status="offtopic", lang="en", social_context="acknowledgment")

    monkeypatch.setattr(main.router, "route", ok_route)
    second = post_chat(client, "lang_ru_sticky", "ok")
    assert CYRILLIC_RE.search(second["response"]), (
        f"Короткая латинская реплика в русской сессии не должна переключать язык: {second['response']!r}"
    )
    assert second["detected_language"] == "ru"
    assert translator.calls == []


def test_en_offtopic_no_russian_humor(client, monkeypatch):
    """EN offtopic: юмор Жванецкого (русский) не должен вызываться."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    humor_calls = {"count": 0}

    class ExplodingHumorGenerator:
        async def generate_humor(self, **kwargs):
            humor_calls["count"] += 1
            return "Шутка Жванецкого на русском языке."

    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="offtopic", lang="en"),
        translator=translator,
    )
    monkeypatch.setattr(main, "zhvanetsky_generator", ExplodingHumorGenerator())

    body = post_chat(client, "lang_en_offtopic", "What is the weather like today?")
    assert_no_cyrillic(body["response"], "offtopic EN")
    assert humor_calls["count"] == 0, "Жванецкий не должен вызываться для EN-диалога"
    assert translator.calls == [], "EN offtopic-фраза должна идти из словаря"


def test_en_need_simplification_gets_english_reply(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(
            status="need_simplification", lang="en",
            questions=["Q1?", "Q2?", "Q3?", "Q4?"],
            message="Пожалуйста, задавайте не более трёх вопросов за раз.",
        ),
        translator=translator,
    )

    body = post_chat(client, "lang_en_many", "What courses, prices, teachers and schedule?")
    assert_no_cyrillic(body["response"], "need_simplification")
    assert translator.calls == []


def test_en_pre_generated_completed_action_translated_by_gate(client, monkeypatch):
    """Pre-generated ответ завершённого действия (русский) обязан пройти шлюз."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(
            status="success", lang="en",
            completed_action_response="Отлично! Оплата обрабатывается. Менеджер свяжется с вами.",
        ),
        translator=translator,
    )

    body = post_chat(client, "lang_en_paid", "I have paid the invoice")
    assert_no_cyrillic(body["response"], "pre-generated completed action")
    assert len(translator.calls) == 1, "Шлюз должен перевести русский pre-generated ответ"
    assert translator.calls[0]["target"] == "en"


def test_en_generation_error_gets_english_reply(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()

    async def failing_generate(router_result, history=None, current_message=None):
        raise RuntimeError("LLM is down")

    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="en"),
        generate=failing_generate,
        translator=translator,
    )

    body = post_chat(client, "lang_en_err", "Tell me about teachers")
    assert_no_cyrillic(body["response"], "generation error")
    assert translator.calls == []


def test_router_failure_english_user_gets_english_apology(client, monkeypatch):
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_exc=RuntimeError("Gemini unavailable"),
        translator=translator,
    )

    body = post_chat(client, "lang_en_routerfail", "Hello there my friend")
    assert_no_cyrillic(body["response"], "router failure")
    assert body["detected_language"] == "en"
    assert translator.calls == []


def test_translator_en_prompt_forbids_cyrillic_hrn():
    """Контракт: EN-промпт переводчика должен требовать 'UAH', а не кириллическое 'грн'."""
    from translator import SmartTranslator

    class DummyClient:
        model = "test/model"

    translator = SmartTranslator(DummyClient())
    prompt = translator._build_translation_prompt("en", {"en": "English"}, "Ukido, soft skills")
    assert '"UAH"' in prompt
    assert "NEVER the Cyrillic" in prompt  # прямой запрет кириллического 'грн'


def test_uk_offtopic_phrase_goes_through_translator(client, monkeypatch):
    """Для украинского canned-фраз нет в словаре — шлюз обязан перевести ru-фразу."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="offtopic", lang="uk"),
        translator=translator,
    )

    body = post_chat(client, "lang_uk_offtopic", "Яка завтра погода?")
    assert translator.calls, "uk-фраза должна идти через переводчик"
    assert translator.calls[0]["target"] == "uk"
    assert body["response"].startswith("[translated-to-uk]")


def test_en_success_not_retranslated_at_gate(client, monkeypatch):
    """Уже переведённый success-ответ не должен переводиться повторно."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="en"),
        translator=translator,
    )

    body = post_chat(client, "lang_en_once", "How much are the courses?")
    assert translator.calls == [], "Шлюз не должен трогать уже переведённый ответ"
    assert body["response"] == "English answer about our courses and prices."


def test_mixed_ru_message_gets_russian_reply(client, monkeypatch):
    """Смешанное сообщение с кириллицей остаётся русским (как раньше)."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="ru"),
        translator=translator,
    )

    body = post_chat(client, "lang_ru_mixed", "Привет, сколько стоит курс?")
    assert "Русский ответ" in body["response"]
    assert body["detected_language"] == "ru"
    assert translator.calls == []
