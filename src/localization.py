"""
localization.py — Языковая логика и двуязычные заготовленные фразы.

P0 мультиязычности: английский пользователь не должен получать русские
ответы ни в одной ветке диалога. Все canned-фразы живут здесь в двух
вариантах (ru/en), украинский идёт через LLM-перевод на финальном шлюзе.
"""

import random
import re
from typing import Dict, List

SUPPORTED_LANGUAGES = ("ru", "uk", "en")
DEFAULT_LANGUAGE = "ru"

# Кириллица (включая украинские буквы — для uk-текста has_cyrillic тоже True,
# поэтому шлюз перевода для uk не полагается на эту проверку)
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁіІїЇєЄґҐ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


def has_cyrillic(text: str) -> bool:
    """True, если в тексте есть хотя бы одна кириллическая буква."""
    return bool(_CYRILLIC_RE.search(text or ""))


def latin_letter_count(text: str) -> int:
    return len(_LATIN_RE.findall(text or ""))


def normalize_language(lang: str) -> str:
    return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def resolve_language(raw: str, message: str, session_lang: str = None) -> str:
    """Сводит определение языка роутера с памятью сессии.

    Роутер определяет язык посимвольно и ошибается на неоднозначных репликах
    (эмодзи, "ok", смешанный ввод). Правила:

    1. Роутер сказал 'ru', но кириллицы в сообщении нет вообще (эмодзи,
       цифры) — доверяем установленному языку сессии (en/uk).
    2. Явно латинское сообщение (5+ латинских букв) без кириллицы при
       ошибке/сбое роутера → 'en'.
    3. Роутер сказал 'en' на короткой латинской реплике ("ok", "yes") в
       УСТАНОВЛЕННОЙ русской сессии — остаёмся на русском, чтобы не
       переключать язык русскоязычного родителя из-за одного латинского
       слова. Для нового пользователя без сессии верим роутеру.
    В остальных случаях верим роутеру.
    """
    raw = normalize_language(raw)
    # session_lang=None означает, что язык сессии ещё не установлен
    session = normalize_language(session_lang) if session_lang else None
    msg_has_cyrillic = has_cyrillic(message)

    if raw == "ru" and not msg_has_cyrillic:
        if session in ("en", "uk"):
            return session
        # Явно латинское сообщение без кириллицы: роутер ошибся или упал
        if latin_letter_count(message) >= 5:
            return "en"

    if (raw == "en" and session == "ru" and not msg_has_cyrillic
            and latin_letter_count(message) <= 4):
        return session

    return raw


def is_confident_language_signal(lang: str, message: str) -> bool:
    """Достаточно ли сообщения, чтобы обновить память языка сессии.

    Короткие латинские реплики ("ok") не считаются уверенным сигналом:
    их пишут и русскоязычные пользователи.
    """
    lang = normalize_language(lang)
    if lang in ("ru", "uk"):
        return has_cyrillic(message)
    # en: уверенный сигнал — достаточно длинная латинская реплика без кириллицы
    return not has_cyrillic(message) and latin_letter_count(message) >= 5


# ============================================================================
# Двуязычные заготовленные фразы
# ============================================================================

FALLBACK = {
    "ru": "Не совсем понял вопрос. Расскажите, что вас интересует о школе Ukido?",
    "en": "I'm not sure I got that. What would you like to know about Ukido school?",
}

OFFTOPIC_RESPONSES = {
    "ru": [
        "Интересный вопрос! Но давайте вернёмся к теме школы Ukido. Чем могу помочь?",
        "Это выходит за рамки моей компетенции. Расскажу лучше о наших курсах?",
        "Давайте сосредоточимся на развитии soft skills для детей. Что вас интересует?",
        "Я специализируюсь на вопросах о школе Ukido. Какую информацию подсказать?",
        "Предлагаю вернуться к теме обучения. Рассказать о программах или ценах?",
        "Это не моя область. Могу рассказать о курсах, преподавателях или методиках.",
        "Давайте обсудим что-то связанное со школой. Что именно интересует?",
    ],
    "en": [
        "Interesting question! But let's get back to Ukido — what can I help you with?",
        "That's a bit outside my expertise. Want to hear about our courses instead?",
        "Let's stay on kids' soft skills — what would you like to know?",
        "I focus on questions about Ukido school. What info can I share?",
        "How about we get back to learning? Programs, pricing — interested?",
        "Not really my area. I can tell you about our courses, teachers, or methods.",
        "Let's talk school — what are you curious about?",
    ],
}

NEED_SIMPLIFICATION = {
    "ru": "Пожалуйста, задавайте не более трёх вопросов за раз. Например, начните с самого важного для вас.",
    "en": "Could you keep it to three questions at a time? Start with the one that matters most to you.",
}

ERROR_RESPONSES = {
    "ru": {
        "generation_failed": "Извините, не могу ответить сейчас. Попробуйте переформулировать вопрос.",
        "timeout": "Превышено время ожидания. Попробуйте ещё раз.",
        "invalid_response": "Получен некорректный ответ. Переформулируйте вопрос.",
        "router_failed": "Временная проблема. Попробуйте позже.",
    },
    "en": {
        "generation_failed": "Sorry, I can't answer right now. Could you rephrase the question?",
        "timeout": "That took too long. Please try again.",
        "invalid_response": "Something went wrong on my side. Could you rephrase?",
        "router_failed": "Temporary hiccup on our side. Please try again in a moment.",
    },
}

GREETINGS = {
    "ru": [
        "Здравствуйте! Я помощник школы Ukido. Чем могу помочь?",
        "Добрый день! Рад помочь с вопросами о наших курсах.",
        "Приветствую! Готов рассказать о программах школы Ukido.",
    ],
    "en": [
        "Hello! I'm the Ukido school assistant. How can I help you today?",
        "Hi there! Happy to answer any questions about our courses.",
        "Welcome! I'd be glad to tell you about Ukido's programs.",
    ],
}

GREETING_PREFIX = {
    "ru": "Здравствуйте! ",
    "en": "Hello! ",
}

ONLINE_FALLBACK = {
    "ru": "Я на связи. Чем помочь?",
    "en": "I'm here. What can I help you with?",
}

THANKS_RESPONSES = {
    "ru": [
        "Пожалуйста! Обращайтесь, если будут вопросы.",
        "Рады помочь! Если нужна дополнительная информация - спрашивайте.",
        "Всегда пожалуйста! Готов ответить на другие вопросы.",
    ],
    "en": [
        "You're welcome! Reach out any time you have questions.",
        "Happy to help! Let me know if you need more details.",
        "Any time! Glad to answer anything else.",
    ],
}

THANKS_PREFIX = {
    "ru": "Пожалуйста! ",
    "en": "You're welcome! ",
}

APOLOGY_RESPONSES = {
    "ru": [
        "Ничего страшного! Чем могу помочь?",
        "Всё в порядке! Готов ответить на ваши вопросы.",
        "Не переживайте! Расскажите, что вас интересует.",
    ],
    "en": [
        "No worries at all! How can I help?",
        "All good! Ready to answer your questions.",
        "Nothing to apologize for! Tell me what you're interested in.",
    ],
}

APOLOGY_PREFIX = {
    "ru": "Ничего страшного! ",
    "en": "No worries at all! ",
}

ACKNOWLEDGMENT_RESPONSES = {
    "ru": [
        "Отлично! Что ещё вас интересует о наших курсах?",
        "Хорошо! Есть ещё вопросы по школе Ukido?",
        "Какая информация ещё нужна?",
        "Супер! Чем ещё могу помочь?",
        "Рада, что понятно! Что ещё рассказать?",
    ],
    "en": [
        "Great! Anything else you'd like to know about our courses?",
        "Okay! Any other questions about Ukido school?",
        "What else would be helpful to know?",
        "Awesome! What else can I help with?",
        "Glad that's clear! What should I cover next?",
    ],
}

FAREWELLS = {
    "ru": [
        "Было приятно помочь! До свидания!",
        "Спасибо за обращение! Всего доброго!",
        "Рады были проконсультировать! До встречи!",
        "Удачи вам! До свидания!",
        "Будем рады видеть вас в нашей школе! До связи!",
    ],
    "en": [
        "Glad I could help! Goodbye!",
        "Thanks for reaching out! Take care!",
        "Happy to answer your questions! See you!",
        "Good luck! Bye for now!",
        "Hope to see you at our school! Stay in touch!",
    ],
}

# Добавки к success-ответу (прощание в конец, благодарность в начало)
FAREWELL_ADDONS = {
    "ru": [
        "\n\nДо свидания! Будем рады видеть вас в нашей школе!",
        "\n\nВсего доброго! Обращайтесь, если появятся вопросы!",
        "\n\nДо встречи! Надеемся увидеть вашего ребенка на занятиях!",
        "\n\nУдачи вам! До связи!",
    ],
    "en": [
        "\n\nGoodbye! We'd love to see you at our school!",
        "\n\nTake care! Reach out if any questions come up!",
        "\n\nSee you! Hope to welcome your child to our classes!",
        "\n\nGood luck! Talk soon!",
    ],
}

THANKS_PREFIXES_SUCCESS = {
    "ru": ["Рады помочь! ", "Пожалуйста! "],
    "en": ["Happy to help! ", "You're welcome! "],
}

# Маркеры для защиты от дублей (проверка «уже есть прощание/благодарность»)
FAREWELL_MARKERS = {
    "ru": ["до свидания", "до встречи", "всего доброго", "удачи", "до связи"],
    "en": ["goodbye", "see you", "take care", "good luck", "bye"],
}

THANKS_MARKERS = {
    "ru": ["рад", "пожалуйста", "всегда пожалуйста"],
    "en": ["happy to help", "welcome", "glad"],
}


def _pick(variant: Dict[str, List[str]] or Dict[str, str], lang: str, key: str = None):
    """Выбирает фразу по языку с fallback на русский."""
    lang = normalize_language(lang)
    if lang not in variant:
        lang = "ru"
    value = variant[lang]
    if isinstance(value, list):
        return random.choice(value)
    return value


def get_fallback(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(FALLBACK, lang)


# Алиас для единого именования с standard_responses
get_default_fallback = get_fallback


def get_offtopic_response(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(OFFTOPIC_RESPONSES, lang)


def get_need_simplification(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(NEED_SIMPLIFICATION, lang)


# Алиас для единого именования с standard_responses
get_need_simplification_message = get_need_simplification


def get_error_response(error_type: str = "default", lang: str = DEFAULT_LANGUAGE) -> str:
    lang = normalize_language(lang)
    if lang not in ERROR_RESPONSES:
        lang = "ru"
    return ERROR_RESPONSES[lang].get(error_type, get_fallback(lang))


def get_greeting(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(GREETINGS, lang)


def get_greeting_prefix(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(GREETING_PREFIX, lang)


def get_online_fallback(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(ONLINE_FALLBACK, lang)


def get_thanks_response(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(THANKS_RESPONSES, lang)


def get_thanks_prefix(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(THANKS_PREFIX, lang)


def get_apology_response(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(APOLOGY_RESPONSES, lang)


def get_apology_prefix(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(APOLOGY_PREFIX, lang)


def get_acknowledgment_response(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(ACKNOWLEDGMENT_RESPONSES, lang)


def get_farewell(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(FAREWELLS, lang)


def get_farewell_addon(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(FAREWELL_ADDONS, lang)


def get_thanks_prefix_success(lang: str = DEFAULT_LANGUAGE) -> str:
    return _pick(THANKS_PREFIXES_SUCCESS, lang)


def has_farewell_marker(text: str, lang: str = DEFAULT_LANGUAGE) -> bool:
    lowered = (text or "").lower()
    markers = FAREWELL_MARKERS.get("ru", []) + FAREWELL_MARKERS.get("en", [])
    lang = normalize_language(lang)
    if lang in FAREWELL_MARKERS:
        markers = FAREWELL_MARKERS[lang] + markers
    return any(marker in lowered for marker in markers)


def has_thanks_marker(text: str, lang: str = DEFAULT_LANGUAGE) -> bool:
    lowered = (text or "").lower()
    lang = normalize_language(lang)
    markers = THANKS_MARKERS.get(lang, []) + THANKS_MARKERS.get("ru", []) + THANKS_MARKERS.get("en", [])
    return any(marker in lowered for marker in markers)
