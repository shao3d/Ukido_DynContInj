"""LANG-07: UK-паритет CTA-гардов.

История диалога хранится уже переведённой на язык пользователя, поэтому
стоп-списки в ResponseGenerator._should_add_offer (all_cta_phrases,
skip_phrases, trial_phrases, anxiety_cta_phrases, recording_phrases,
ready_cta_phrases) и trial_words в generate() обязаны понимать украинскую
речь, иначе UK-пользователь получает CTA-спам подряд.

Все тесты полностью офлайн — ни одного LLM-вызова.
"""

import asyncio
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")
os.environ.setdefault("DETERMINISTIC_MODE", "true")

import pytest  # noqa: E402

from response_generator import ResponseGenerator  # noqa: E402


@pytest.fixture()
def generator():
    return ResponseGenerator()


class TestUkGlobalCtaSpacing:
    """Глобальное правило «минимум 3 сообщения между CTA» должно видеть uk."""

    def test_uk_discount_cta_two_messages_back_blocks(self, generator):
        history = [
            {"role": "assistant",
             "content": "Доступна розстрочка без відсотків на 3 місяці. Також є сімейні знижки до 20%.",
             "metadata": {}},
            {"role": "user", "content": "дякую"},
        ]
        assert generator._should_add_offer("price_sensitive", history, {}, "а що ще?") is False

    def test_uk_trial_cta_two_messages_back_blocks(self, generator):
        history = [
            {"role": "assistant",
             "content": "Перше заняття безкоштовне - можете оцінити, чи підходить.",
             "metadata": {}},
            {"role": "user", "content": "дякую"},
        ]
        assert generator._should_add_offer("exploring_only", history, {}, "розкажіть") is False

    def test_ru_discount_cta_spacing_regression(self, generator):
        history = [
            {"role": "assistant",
             "content": "Доступна рассрочка без процентов. Также есть скидки до 20%.",
             "metadata": {}},
            {"role": "user", "content": "спасибо"},
        ]
        assert generator._should_add_offer("price_sensitive", history, {}, "а что еще?") is False


class TestUkPriceSensitive:
    def test_uk_direct_discount_question_skips_cta(self, generator):
        for message in ("які є знижки?", "чи є розстрочка?", "є знижка на другу дитину?"):
            assert generator._should_add_offer("price_sensitive", [], {}, message) is False, message

    def test_uk_neutral_allows_cta(self, generator):
        assert generator._should_add_offer("price_sensitive", [], {}, "а що ще?") is True

    def test_ru_discount_question_regression(self, generator):
        assert generator._should_add_offer("price_sensitive", [], {}, "Какие есть скидки?") is False


class TestUkAnxiety:
    @staticmethod
    def _history():
        return [
            {"role": "assistant", "content": "Співчуваємо вашій турботі.",
             "metadata": {"user_signal": "anxiety_about_child"}},
            {"role": "assistant", "content": "Наші групи маленькі.",
             "metadata": {"user_signal": "anxiety_about_child"}},
        ]

    def test_uk_trial_question_skips_cta(self, generator):
        for message in ("мені потрібне пробне", "хочу спробувати", "скільки коштує перше заняття?"):
            assert generator._should_add_offer(
                "anxiety_about_child", self._history(), {}, message
            ) is False, message

    def test_uk_recent_anxiety_cta_rate_limited(self, generator):
        history = self._history() + [
            {"role": "assistant",
             "content": "Кстати, перше заняття безкоштовне, без зобов'язань.",
             "metadata": {"user_signal": "anxiety_about_child"}},
        ]
        assert generator._should_add_offer(
            "anxiety_about_child", history, {}, "розкажіть про викладачів"
        ) is False

    def test_uk_neutral_after_trust_allows_cta(self, generator):
        assert generator._should_add_offer(
            "anxiety_about_child", self._history(), {}, "розкажіть про викладачів"
        ) is True


class TestUkReadyToBuy:
    def test_uk_already_recorded_skips_cta(self, generator):
        for message in ("я вже записався", "я вже записалася", "заповнив форму"):
            assert generator._should_add_offer("ready_to_buy", [], {}, message) is False, message

    def test_uk_recent_ready_cta_rate_limited(self, generator):
        history = [
            {"role": "assistant",
             "content": "Переходьте на shao3d.github.io/trial/ для запису.",
             "metadata": {}},
        ]
        assert generator._should_add_offer("ready_to_buy", history, {}, "розкажіть") is False

    def test_uk_ready_neutral_allows_cta(self, generator):
        assert generator._should_add_offer("ready_to_buy", [], {}, "розкажіть про викладачів") is True

    def test_ru_already_recorded_regression(self, generator):
        assert generator._should_add_offer("ready_to_buy", [], {}, "я уже записался") is False


class TestUkTrialWordsInGenerate:
    """trial_words в generate() должен ловить uk-просьбу о пробном."""

    @staticmethod
    async def _generate(generator, message):
        generator._load_docs = lambda docs: {"faq.md": "Ukido facts"}

        async def fake_chat(messages):
            return "Це корисно для дитини."

        generator.client.chat = fake_chat
        router_result = {
            "status": "success",
            "documents": ["faq.md"],
            "decomposed_questions": ["Що таке soft skills?"],
            "user_signal": "exploring_only",
            "detected_language": "ru",
            "cta_blocked": True,
        }
        return await generator.generate(router_result, history=[], current_message=message)

    @pytest.mark.parametrize(
        "message",
        ["хочу спробувати", "можна спробувати?", "пробне заняття", "запишіть на пробне"],
    )
    def test_uk_trial_request_adds_contacts(self, generator, message):
        text, _ = asyncio.run(self._generate(generator, message))
        assert "ukido.com.ua/trial" in text, message

    def test_uk_neutral_message_does_not_add_contacts(self, generator):
        text, _ = asyncio.run(self._generate(generator, "просто розкажіть про школу"))
        assert "ukido.com.ua/trial" not in text
