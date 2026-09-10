"""BUG-02: ложные подтверждения действий пользователя.

Бот не имеет права уверенно подтверждать то, чего не было:
отрицания («ещё не оплатили»), чужие школы («записались в бассейн»),
вопросы и планы — это НЕ завершённые действия.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from completed_actions_handler import CompletedActionsHandler
from simple_cta_blocker import SimpleCTABlocker


@pytest.fixture()
def handler():
    return CompletedActionsHandler()


@pytest.fixture()
def blocker():
    return SimpleCTABlocker()


def offroute(lang="ru"):
    return {"status": "offtopic", "detected_language": lang,
            "decomposed_questions": []}


def stays_offtopic(handler, message, history=None, lang="ru"):
    result = handler.detect_completed_action(message, offroute(lang), history or [])
    assert result["status"] == "offtopic", f"{message!r} подтвердили!"
    assert "completed_action_response" not in result


def gets_confirmed(handler, message, action, history=None, lang="ru"):
    result = handler.detect_completed_action(message, offroute(lang), history or [])
    assert result["status"] == "success", f"{message!r} не подтвердили"
    assert result["_action_detected"] == action
    assert result["completed_action_response"]
    return result


# --- Отрицания: главный кейс ревью -------------------------------------------

@pytest.mark.parametrize("message", [
    "Мы ещё не оплатили курс",
    "Мы еще не оплатили курс",  # без ё
    "Пока не заплатил",
    "Не оплатил",
    "Нет, не записывались",
    "Не успели оплатить",
    "Оплата пока не прошла",
])
def test_ru_negations_stay_offtopic(handler, message):
    stays_offtopic(handler, message)


@pytest.mark.parametrize("message", [
    "I haven't paid for the course",
    "We didn't sign up",
    "Not paid yet",
    "I have not filled the form",
])
def test_en_negations_stay_offtopic(handler, message):
    stays_offtopic(handler, message, lang="en")


# --- Чужие школы и места ------------------------------------------------------

@pytest.mark.parametrize("message", [
    "Записались в бассейн",
    "Записались на футбол",
    "Заполнил форму в поликлинике",
    "Заполнила анкету в больнице",
    "Оплатил интернет",
    "Оплатил счёт за свет",
    "Были на пробном в автошколе",
    "I paid for gas yesterday",
    "Signed up for football practice",
])
def test_foreign_context_stays_offtopic(handler, message):
    stays_offtopic(handler, message)


def test_explicit_ukido_beats_foreign_word(handler):
    gets_confirmed(handler, "Записались в школу Ukido", "registration")


# --- Вопросы и планы — не подтверждения ---------------------------------------

@pytest.mark.parametrize("message", [
    "Оплатил курс, что дальше?",
    "Как оплатить курс?",
    "Хочу записаться на курс",
    "Собираемся оплатить на днях",
    "Записались бы к вам",
    "Думаем записаться",
])
def test_questions_and_plans_stay_offtopic(handler, message):
    stays_offtopic(handler, message)


def test_conditional_without_history(handler):
    # «Оплатил, как договаривались» без школьной истории — не подтверждаем:
    # контекста нет, а врать нельзя (консервативное направление без лжи).
    stays_offtopic(handler, "Оплатил, как договаривались")


# --- Настоящие действия по-прежнему подтверждаются -----------------------------

@pytest.mark.parametrize("message,action", [
    ("Оплатил курс вчера", "payment"),
    ("Оплатила курс", "payment"),
    ("Оплатил счёт", "payment"),  # счёт = школьный контекст из дизайна
    ("Записался на курс", "registration"),
    ("Записалась на пробное", "registration"),
    ("Подал заявку", "registration"),
    ("Заполнил форму на сайте", "form"),
    ("Были на пробном занятии", "trial"),
    ("Отправил документы", "documents"),
])
def test_ru_real_actions_confirmed(handler, message, action):
    gets_confirmed(handler, message, action)


@pytest.mark.parametrize("message,action", [
    ("I've paid for the course", "payment"),
    ("We signed up yesterday", "registration"),
    ("I filled out the form on your website", "form"),
])
def test_en_real_actions_confirmed(handler, message, action):
    gets_confirmed(handler, message, action, lang="en")


# --- История: только реплики user ----------------------------------------------

def test_user_history_provides_context(handler):
    history = [
        {"role": "user", "content": "сколько стоит курс"},
        {"role": "assistant", "content": "Курс стоит 6000"},
    ]
    gets_confirmed(handler, "Оплатил вчера", "payment", history)


def test_assistant_only_history_is_not_context(handler):
    # BUG-02: ответы ассистента («Ukido soft skills») контекстом не считаются.
    history = [
        {"role": "assistant", "content": "Ukido — школа soft skills для детей"},
    ]
    stays_offtopic(handler, "Оплатил", history)


def test_exclusion_beats_school_history(handler):
    # Явное чужое место бьёт даже школьную историю.
    history = [{"role": "user", "content": "сколько стоит курс"}]
    stays_offtopic(handler, "Записались в бассейн", history)


def test_success_passthrough_untouched(handler):
    route = {"status": "success", "documents": ["faq.md"],
             "decomposed_questions": ["q"]}
    assert handler.detect_completed_action("Оплатил курс", route, []) is route


# --- SimpleCTABlocker: тот же экран ----------------------------------------------

@pytest.mark.parametrize("message", [
    "Мы ещё не оплатили курс",
    "Записались в бассейн",
    "I haven't paid for the course",
    "Хочу записаться",
    "Оплатил?",
])
def test_blocker_ignores_non_actions(blocker, message):
    assert blocker.check_completed_action("u", message) is None


@pytest.mark.parametrize("message,action", [
    ("Оплатил курс", "paid"),
    ("Внёс оплату за курс", "paid"),
    ("Записались на курс", "registered"),
    ("I already signed up for the course", "registered"),
    ("I've paid for the course", "paid"),
])
def test_blocker_keeps_real_actions(blocker, message, action):
    assert blocker.check_completed_action("u", message) == action
