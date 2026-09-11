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
    looks_ukrainian,
    looks_russian,
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
def test_list_dictionaries_have_ru_en_uk(name, dictionary):
    assert set(dictionary.keys()) == {"ru", "en", "uk"}, f"{name}: ждём ru, en и uk, есть {sorted(dictionary.keys())}"
    assert len(dictionary["ru"]) == len(dictionary["en"]) == len(dictionary["uk"]) > 0, (
        f"{name}: разное число фраз ru/en/uk"
    )
    for lang in ("ru", "en", "uk"):
        assert all(isinstance(p, str) and p.strip() for p in dictionary[lang]), f"{name}[{lang}]: пустые фразы"


@pytest.mark.parametrize("name,dictionary", [(getattr(d, "__name__", f"str_{i}"), d) for i, d in enumerate(STR_DICTS)])
def test_string_dictionaries_have_ru_en_uk(name, dictionary):
    assert set(dictionary.keys()) == {"ru", "en", "uk"}
    assert all(dictionary[lang].strip() for lang in ("ru", "en", "uk"))


RUSSIAN_ONLY_LETTERS = re.compile(r"[ыэёъЫЭЁЪ]")


def test_uk_phrases_have_no_russian_only_letters():
    """LANG-02: uk-заготовки не должны содержать букв, которых нет в украинском."""
    phrases = []
    for dictionary in LIST_DICTS + STR_DICTS:
        values = dictionary["uk"]
        phrases.extend(values if isinstance(values, list) else [values])
    phrases.extend(ERROR_RESPONSES["uk"].values())
    for phrase in phrases:
        match = RUSSIAN_ONLY_LETTERS.search(phrase)
        assert not match, f"Русская буква {match.group(0)!r} в uk-фразе: {phrase!r}"


def test_uk_farewell_and_thanks_helpers_do_not_fall_back_to_ru():
    from localization import (
        get_farewell,
        get_farewell_addon,
        get_thanks_response,
        get_thanks_prefix_success,
        has_farewell_marker,
        has_thanks_marker,
    )

    assert not RUSSIAN_ONLY_LETTERS.search(get_farewell("uk"))
    assert not RUSSIAN_ONLY_LETTERS.search(get_farewell_addon("uk"))
    assert not RUSSIAN_ONLY_LETTERS.search(get_thanks_response("uk"))
    assert not RUSSIAN_ONLY_LETTERS.search(get_thanks_prefix_success("uk"))
    # Маркеры uk должны распознаваться (защита от дублей)
    assert has_farewell_marker("До побачення! Гарного дня", "uk")
    assert has_thanks_marker("Будь ласка, звертайтеся", "uk")


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

    @pytest.mark.parametrize("greeting", ["Hi", "hi!", "Hey"])
    def test_short_english_greeting_survives_router_failure(self, greeting):
        assert resolve_language("ru", greeting, None) == "en"

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


class TestLooksUkrainian:
    """LANG-01: uk-реплики без і/ї/є/ґ распознаются по словесным маркерам."""

    @pytest.mark.parametrize("message", [
        "Дякую!",
        "Добрий день",
        "Доброго ранку, будь ласка",
        "А можна записатися?",
        "Навчання для батьків",
        "Чому так дорого?",
        "Що це?",
        "Скільки коштує?",  # уже ловится по букве і — контроль паритета
    ])
    def test_positive_markers_without_unique_letters(self, message):
        assert looks_ukrainian(message), f"uk-маркер не распознан: {message!r}"

    @pytest.mark.parametrize("message", [
        "",
        "ok",
        "Hello there friend",
        "Сколько стоит курс?",           # чистый русский
        "Спасибо, так и сделаем",        # «так» общий — не маркер
        "Доброго дня!",                  # валидно и в русском — не маркер
        "Привет, расскажите о школе",
    ])
    def test_negative_cases_stay_non_ukrainian(self, message):
        assert not looks_ukrainian(message), f"ложное срабатывание uk: {message!r}"


class TestResolveLanguageUkrainianCorrection:
    """Правило «только повышение»: ru-роутер + uk-маркер → uk, ru не трогаем."""

    def test_router_ru_with_uk_marker_promoted(self):
        assert resolve_language("ru", "Дякую!", None) == "uk"
        assert resolve_language("ru", "Добрий день", "ru") == "uk"
        assert resolve_language("ru", "будь ласка, підкажіть", "en") == "uk"

    def test_marker_wins_over_stale_ru_session(self):
        # Сессия была ru, но родитель явно написал по-украински
        assert resolve_language("ru", "Дякую за відповідь", "ru") == "uk"

    def test_pure_russian_unchanged(self):
        assert resolve_language("ru", "Сколько стоит курс?", "en") == "ru"
        assert resolve_language("ru", "Спасибо, так и сделаем", "ru") == "ru"
        assert resolve_language("ru", "Доброго дня!", None) == "ru"

    def test_uk_marker_is_confident_to_update_session(self):
        assert is_confident_language_signal("uk", "Дякую!")


class TestFinalSanitize:
    """BUG-17/LANG-A4: нормализация EN/UK→RU по границам слов, без порчи текста."""

    @staticmethod
    def _generator():
        from response_generator import ResponseGenerator
        return ResponseGenerator.__new__(ResponseGenerator)

    def test_replace_terms_respects_word_boundaries(self):
        from response_generator import ResponseGenerator

        mapping = {"mentor": "наставник", "feedback": "обратную связь"}
        replace = ResponseGenerator._replace_terms
        assert replace("mentoring is key", mapping) == "mentoring is key"
        assert replace("Mentor here", mapping) == "Наставник here"
        assert replace("FEEDBACK, pls", mapping) == "ОБРАТНУЮ СВЯЗЬ, pls"
        assert replace("get feedback.", mapping) == "get обратную связь."

    def test_final_sanitize_does_not_corrupt_words(self):
        gen = self._generator()
        assert "mentoring" in gen._final_sanitize("Мы даём mentoring.")
        out = gen._final_sanitize("Багато батьків підтримують дітей.")
        assert "детей" in out and "родителей" in out and "поддерживают" in out
        assert "діт" not in out


class TestLooksRussian:
    """LANG-04: отличаем русские вопросы декомпозиции от украинских."""

    @pytest.mark.parametrize("text", [
        "Сколько стоит курс?",
        "Ребёнок не слушается",
        "Есть ли скидки?",
        "Как проходят занятия?",
        "Что нужно для записи?",
    ])
    def test_detects_russian(self, text):
        assert looks_russian(text), f"Не распознан русский: {text!r}"

    @pytest.mark.parametrize("text", [
        "Скільки коштує курс?",
        "Скільки триває заняття?",
        "Дитина не слухається",
        "Як проходять заняття?",
        "Що потрібно для запису?",
        "Добрий день, розкажіть про курси",
    ])
    def test_ukrainian_stays_ukrainian(self, text):
        assert not looks_russian(text), f"Ложное срабатывание ru на uk: {text!r}"


class TestUkrainianHeuristics:
    """LANG-03/LANG-05/LANG-06: uk понимается в эвристиках, а не только ru/en."""

    def test_cta_blocker_detects_uk_completed_action(self):
        from simple_cta_blocker import SimpleCTABlocker

        blocker = SimpleCTABlocker()
        assert blocker.check_completed_action("uk_paid", "Я оплатив курс Ukido") == "paid"
        assert blocker.check_completed_action("uk_reg", "Записався на пробне заняття") == "registered"

    def test_cta_blocker_detects_uk_refusals(self):
        from simple_cta_blocker import SimpleCTABlocker

        blocker = SimpleCTABlocker()
        assert blocker.check_refusal("uk_hard", "Не треба пропонувати курс") == "hard"
        assert blocker.check_refusal("uk_soft", "Я подумаю, можливо пізніше") == "soft"

    def test_completed_actions_handler_detects_uk(self):
        from completed_actions_handler import CompletedActionsHandler

        handler = CompletedActionsHandler()
        result = handler.detect_completed_action(
            "Я оплатив курс Ukido",
            {"status": "offtopic", "detected_language": "uk"},
            [],
        )
        assert result.get("_action_detected") == "payment"
        assert result.get("status") == "success"

    def test_uk_negation_and_conditional_guards(self):
        from completed_actions_handler import is_negated_before, is_conditional_after

        assert is_negated_before("ще не оплатив курс", "оплатив")
        assert not is_negated_before("я оплатив курс", "оплатив")
        assert is_conditional_after("записався б на курс", "записався")
        assert not is_conditional_after("я записався на курс", "записався")

    def test_router_acknowledgment_and_question_words_include_uk(self):
        from router import ACKNOWLEDGMENT_PATTERNS, QUESTION_WORDS

        assert "добре" in ACKNOWLEDGMENT_PATTERNS
        assert "дякую" in ACKNOWLEDGMENT_PATTERNS
        assert "скільки" in QUESTION_WORDS
        assert "чому" in QUESTION_WORDS

    def test_ultra_short_uk_expansion_uses_ukrainian(self):
        from router import Router

        router = Router.__new__(Router)
        history = [{"role": "assistant", "content": "Наші курси тривають 90 хвилин."}]
        assert router._expand_ultra_short_question("і все?", history) == (
            "Розкажіть детальніше про курси"
        )


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
            return await generate(router_result, history, current_message)
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
    assert "natural American English" in prompt
    assert "Preserve all formatting" in prompt


def test_translator_uk_prompt_has_parity_few_shot():
    """LANG-03: uk-промпт перевода должен иметь few-shot и запрет суржика."""
    from translator import SmartTranslator

    class DummyClient:
        model = "test/model"

    translator = SmartTranslator(DummyClient())
    prompt = translator._build_translation_prompt("uk", {"uk": "Ukrainian"}, "Ukido, soft skills")

    assert "native Ukrainian copywriter" in prompt
    assert "surzhyk" in prompt
    assert "BEFORE/AFTER EXAMPLES" in prompt
    assert "Ukido, soft skills" in prompt
    assert "Return ONLY the rewritten Ukrainian text" in prompt
    # Защищённые термины переданы в промпт
    assert "KEEP EXACTLY AS-IS" in prompt


def test_router_requires_decomposition_in_user_language():
    from router import Router

    role = Router._get_role_section(None)
    response_format = Router._get_response_format_section(None)

    assert "НА ЯЗЫКЕ ПОЛЬЗОВАТЕЛЯ" in role
    assert "decomposed_questions пиши на detected_language" in role
    assert "How much does the course cost?" in response_format


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


def test_uk_success_farewell_addon_is_ukrainian(client, monkeypatch):
    """LANG-02: прощание в uk success-ответе не должно быть русским."""
    main = sys.modules["main"]
    translator = RecordingTranslator()

    async def uk_generate(router_result, history=None, current_message=None):
        return "Наші заняття проходять у міні-групах до шести дітей.", {
            "intent": "success", "user_signal": "exploring_only",
            "cta_added": False, "cta_type": None, "humor_generated": False,
            "translated_to": "uk",
        }

    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="uk", social_context="farewell"),
        generate=uk_generate,
        translator=translator,
    )

    body = post_chat(client, "lang_uk_farewell", "Дякую, до побачення!")
    assert body["detected_language"] == "uk"
    lowered = body["response"].lower()
    assert "до свидания" not in lowered, f"Русское прощание в uk-ответе: {body['response']!r}"
    assert "добрый" not in lowered, f"Русское слово в uk-ответе: {body['response']!r}"
    # Любой украинский маркер прощания (get_farewell_addon выбирает случайно)
    from localization import FAREWELL_MARKERS
    assert any(marker in lowered for marker in FAREWELL_MARKERS["uk"]), (
        f"Нет украинского прощания: {body['response']!r}"
    )


def test_uk_success_thanks_prefix_is_ukrainian(client, monkeypatch):
    """LANG-02: благодарность-префикс в uk success-ответе не русская."""
    main = sys.modules["main"]
    translator = RecordingTranslator()

    async def uk_generate(router_result, history=None, current_message=None):
        return "Курс допомагає дітям розвивати навички спілкування.", {
            "intent": "success", "user_signal": "exploring_only",
            "cta_added": False, "cta_type": None, "humor_generated": False,
            "translated_to": "uk",
        }

    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="uk", social_context="thanks"),
        generate=uk_generate,
        translator=translator,
    )

    body = post_chat(client, "lang_uk_thanks", "Дякую за відповідь!")
    assert body["detected_language"] == "uk"
    assert body["response"].startswith(("Раді допомогти! ", "Будь ласка! ")), (
        f"Не украинский префикс благодарности: {body['response']!r}"
    )


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


# ============================================================================
# Пакет косметики: кеш удалён, фоллбек перевода, контакты записи, UI
# ============================================================================

def test_translator_has_no_cache_and_always_calls_client():
    """Кеш переводов удалён: одинаковый текст переводится каждый раз заново."""
    from translator import SmartTranslator

    calls = {"count": 0}

    class CountingClient:
        model = "test/model"

        async def chat(self, messages, **kwargs):
            calls["count"] += 1
            return "Translated text."

    translator = SmartTranslator(CountingClient())
    assert not hasattr(SmartTranslator, "translation_cache")

    import asyncio
    loop = asyncio.new_event_loop()
    try:
        first = loop.run_until_complete(translator.translate("Один и тот же текст", "en"))
        second = loop.run_until_complete(translator.translate("Один и тот же текст", "en"))
    finally:
        loop.close()

    assert first == second == "Translated text."
    assert calls["count"] == 2, "Без кеша каждый перевод должен идти в модель"


def test_config_has_no_dead_cache_setting():
    from config import Config
    assert not hasattr(Config, "TRANSLATION_CACHE_SIZE")


def test_failed_translation_yields_english_apology_not_russian(client, monkeypatch):
    """Сбой перевода: в ответе не должно быть внезапного русского текста."""
    main = sys.modules["main"]

    async def russian_generate(router_result, history=None, current_message=None):
        return "Русский ответ, который не смог перевестись.", {
            "intent": "success", "user_signal": "exploring_only",
            "cta_added": False, "cta_type": None, "humor_generated": False,
        }

    class BrokenTranslator:
        async def translate(self, text, target_language, **kwargs):
            return text  # «перевод» не изменил текст — симуляция сбоя

    install_mocks(
        monkeypatch, main,
        route_result=make_route(status="success", lang="en"),
        generate=russian_generate,
        translator=BrokenTranslator(),
    )

    body = post_chat(client, "lang_en_translate_fail", "What courses do you have?")
    assert_no_cyrillic(body["response"], "сбой перевода")
    assert "rephrase" in body["response"].lower() or "wrong" in body["response"].lower()


def test_en_api_metadata_drops_russian_decomposed_questions(client, monkeypatch):
    main = sys.modules["main"]
    install_mocks(
        monkeypatch,
        main,
        route_result=make_route(
            status="success",
            lang="en",
            questions=["What does it cost?", "Сколько длится занятие?"],
        ),
    )

    body = post_chat(client, "lang_en_metadata", "What does it cost and how long is class?")

    assert body["decomposed_questions"] == ["What does it cost?"]
    assert_no_cyrillic(" ".join(body["decomposed_questions"]), "EN metadata")


def test_uk_api_metadata_translates_russian_decomposed_questions(client, monkeypatch):
    """LANG-04: русские вопросы декомпозиции не утекают в uk-метаданные."""
    main = sys.modules["main"]
    translator = RecordingTranslator()
    install_mocks(
        monkeypatch,
        main,
        route_result=make_route(
            status="success",
            lang="uk",
            questions=["Сколько стоит курс?", "Скільки триває заняття?"],
        ),
        translator=translator,
    )

    body = post_chat(client, "lang_uk_metadata", "Скільки коштує і як довго триває?")

    assert body["detected_language"] == "uk"
    assert body["decomposed_questions"] == ["[translated-to-uk]", "Скільки триває заняття?"]
    assert any(call["target"] == "uk" for call in translator.calls)


def test_uk_metadata_drops_question_when_translation_fails(client, monkeypatch):
    """LANG-04: сбой перевода метаданных — вопрос отбрасывается, не утекает русский."""
    main = sys.modules["main"]

    class BrokenTranslator:
        async def translate(self, text, target_language, **kwargs):
            from translator import TranslationError
            raise TranslationError("boom")

    install_mocks(
        monkeypatch,
        main,
        route_result=make_route(
            status="success",
            lang="uk",
            questions=["Сколько стоит курс?", "Скільки триває заняття?"],
        ),
        translator=BrokenTranslator(),
    )

    body = post_chat(client, "lang_uk_meta_fail", "Скільки коштує?")

    assert body["decomposed_questions"] == ["Скільки триває заняття?"]


def test_no_signup_contacts_for_user_who_just_signed_up():
    """«Меню человеку с тарелкой супа»: записавшемуся не предлагаем запись."""
    import asyncio
    from response_generator import ResponseGenerator

    generator = ResponseGenerator()

    async def fake_chat(messages, **kwargs):
        return "Занятия проходят в мини-группах до шести детей."

    generator.client.chat = fake_chat

    base_router_result = {
        "status": "success",
        "documents": ["faq.md"],
        "decomposed_questions": ["Как проходят занятия?"],
        "user_signal": "exploring_only",
        "detected_language": "ru",
        "cta_blocked": True,  # отключаем CTA-механику, проверяем только контакты
    }

    with_action = dict(base_router_result, user_completed_action="registered")
    text, _ = asyncio.run(generator.generate(
        with_action, [], "Я записался на пробное занятие"
    ))
    assert "ukido.com.ua/trial" not in text, f"Контакты записи предложены записавшемуся: {text!r}"

    without_action = dict(base_router_result)
    text_control, _ = asyncio.run(generator.generate(
        without_action, [], "Хочу попробовать пробное занятие"
    ))
    assert "ukido.com.ua/trial" in text_control, "Контроль: без флага контакты должны добавляться"


def test_ui_declares_english_and_has_no_russian_errors():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en">' in html
    for russian_string in (
        "Произошла ошибка при отправке",
        "Соединение прервано",
        "Не удалось получить ответ",
        "Ошибка: ${message}",
    ):
        assert russian_string not in html, f"Русская строка ошибки осталась: {russian_string!r}"
