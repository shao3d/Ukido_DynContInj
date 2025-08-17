"""
social_responder.py — шаблонные ответы для социальных интентов.
"""
from datetime import datetime
from typing import Optional
import random

from social_intents import SocialIntent
from social_state import SocialStateManager


def _tod_greeting(now: Optional[datetime] = None) -> str:
    # Убираем временные маркеры - всегда нейтральное приветствие
    return "Здравствуйте"


class SocialResponder:
    def __init__(self, state: SocialStateManager):
        self._state = state

    def make_prefix(self, session_id: str, intent: SocialIntent) -> str:
        """
        Короткая вежливая вставка перед бизнес-ответом в mixed-кейсе.
        GREETING: "Здравствуйте!\n" + отметка, что поздоровались
        THANKS:   "Пожалуйста!\n" (без изменения состояния)
        APOLOGY:  Вариативные ответы
        """
        if intent == SocialIntent.GREETING:
            st = self._state.get(session_id)
            if not st.greeting_exchanged:
                self._state.mark_greeting(session_id)
            return f"{_tod_greeting()}!\n"
        if intent == SocialIntent.THANKS:
            return "Пожалуйста!\n"
        if intent == SocialIntent.APOLOGY:
            # Вариативные префиксы для извинений в mixed-кейсах
            prefixes = [
                "Ничего страшного!\n",
                "Всё в порядке!\n",
                "Не беспокойтесь!\n",
                "Всё хорошо!\n",
                "Не переживайте!\n",
                "Ничего!\n",
                "Да что вы!\n"
            ]
            return random.choice(prefixes)
        return ""

    def respond(self, session_id: str, intent: SocialIntent, user_name: Optional[str] = None) -> str:
        if intent == SocialIntent.GREETING:
            st = self._state.get(session_id)
            if st.greeting_exchanged:
                return "Да, я на связи. Чем помочь?"
            self._state.mark_greeting(session_id)
            base = f"{_tod_greeting()}!"
            return f"{base} Чем помочь?"

        if intent == SocialIntent.THANKS:
            # Вариативные ответы на благодарность
            responses = [
                "Пожалуйста! Всегда рады помочь.",
                "Пожалуйста! Обращайтесь.",
                "Не за что! Рады помочь.",
                "Пожалуйста! Удачи!",
                "Всегда пожалуйста!"
            ]
            return random.choice(responses)

        if intent == SocialIntent.FAREWELL:
            self._state.mark_farewell(session_id)
            # Вариативные ответы на прощание
            responses = [
                "Хорошего дня! Обращайтесь.",
                "Всего доброго! Будем рады помочь.",
                "До свидания! Удачи!",
                "Удачи! До встречи."
            ]
            return random.choice(responses)
        
        if intent == SocialIntent.APOLOGY:
            # Вариативные ответы на извинения
            responses = [
                "Ничего страшного! Чем помочь?",
                "Всё в порядке! Как могу помочь?",
                "Не переживайте! Чем могу быть полезен?",
                "Ничего, бывает! Что вас интересует?"
            ]
            return random.choice(responses)

        return "Принято."
