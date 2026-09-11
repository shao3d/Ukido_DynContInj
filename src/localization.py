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
_SHORT_ENGLISH_GREETINGS = {"hi", "hey"}

# LANG-01: буквы, встречающиеся только в украинском алфавите.
_UK_UNIQUE_LETTERS_RE = re.compile(r"[іІїЇєЄґҐ]")

# Однозначные украинские слова/фразы: их нет в русском, поэтому по ним
# можно безопасно повышать ru→uk. Намеренно НЕ включаем общие для двух
# языков слова и формы вроде «так»/«день»/«доброго дня» (это валидный
# русский), чтобы не переключать русскоязычного родителя.
_UK_MARKERS = (
    "дякую", "дякуємо", "будь ласка", "добрий день", "добрий ранок",
    "доброго ранку", "добрий вечір", "на добраніч", "вітаю", "до побачення",
    "вибачте", "перепрошую", "вчитель", "вчителі", "батьки", "батьків",
    "дитина", "заняття", "розклад", "безкоштовно", "пробне", "мабуть",
    "навчання", "можна", "чому", "що", "потрібно", "допоможіть",
    "розповісти", "підкажіть", "скільки коштує",
)


def _build_marker_re(markers) -> "re.Pattern":
    parts = [r"\s+".join(re.escape(tok) for tok in m.split()) for m in markers]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_UK_MARKER_RE = _build_marker_re(_UK_MARKERS)


def has_cyrillic(text: str) -> bool:
    """True, если в тексте есть хотя бы одна кириллическая буква."""
    return bool(_CYRILLIC_RE.search(text or ""))


def latin_letter_count(text: str) -> int:
    return len(_LATIN_RE.findall(text or ""))


# LANG-04: русские буквы, которых нет в украинском алфавите, и слова,
# которых нет в украинском. Нужны, чтобы вычистить/перевести метаданные
# (decomposed_questions), если роутер проигнорировал uk-инструкцию.
_RU_UNIQUE_LETTERS_RE = re.compile(r"[ыэёъЫЭЁЪ]")
_RU_MARKERS = (
    "сколько", "стоит", "стоимость", "почему", "зачем", "какой", "какая",
    "какие", "каких", "какую", "ребёнок", "ребенок", "детей", "дети",
    "учитель", "можно", "нужно", "нужны", "расскажите", "занятия",
    "обучение", "цена", "скидка", "расписание", "пробное", "бесплатно",
    "есть", "чем", "это", "если", "ответ", "перевод",
    "который", "которая", "которое", "которого", "которой", "котором",
    "которому", "которым", "которую", "которые", "которых", "которыми",
    "привет", "здравствуйте", "здравствуй", "спасибо", "пожалуйста",
    "до свидания", "хорошо", "понятно", "конечно", "очень", "сейчас",
    "потом", "также", "потому", "будет", "будут", "уже", "еще",
    "может", "хочет", "должен", "должна", "должны", "нет", "да",
    "меня", "тебя", "себя", "время", "такой", "такая", "такие",
    "этот", "эта", "эти", "здесь",
)


def _build_ru_marker_re(markers) -> "re.Pattern":
    parts = [r"\s+".join(re.escape(tok) for tok in m.split()) for m in markers]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_RU_MARKER_RE = _build_ru_marker_re(_RU_MARKERS)


def looks_russian(text: str) -> bool:
    """True, если текст похож на русский (а не на украинский).

    Используется для метаданных uk: русские вопросы декомпозиции нельзя
    отдавать украинскому пользователю. Ловит русские буквы ы/э/ё/ъ и
    русские слова, которых нет в украинском.
    """
    if not text:
        return False
    if _RU_UNIQUE_LETTERS_RE.search(text):
        return True
    return bool(_RU_MARKER_RE.search(text))


# F1: чистые приветствия (ровно приветствие, без вопроса/информации).
# Нужны для детерминированного fallback, когда LLM-роутер не распознал
# приветствие (или вернул мусор в social_context).
PURE_GREETING_MARKERS = frozenset({
    # ru
    "привет", "приветствую", "здравствуйте", "здравствуй",
    "добрый день", "доброе утро", "добрый вечер", "доброй ночи", "доброго дня",
    # uk
    "привіт", "вітаю", "добрий день", "доброго дня", "добрий ранок",
    "доброго ранку", "добрий вечір", "доброго вечора", "на добраніч",
    "доброго здоров'я",
    # en
    "hi", "hey", "hello", "greetings", "good morning", "good afternoon",
    "good evening", "hi there", "hello there",
})

_GREETING_PUNCT_RE = re.compile(r"[^\w\s']", re.UNICODE)


def _normalize_greeting(text: str) -> str:
    stripped = _GREETING_PUNCT_RE.sub("", (text or "").lower())
    return re.sub(r"\s+", " ", stripped).strip()


def is_pure_greeting(text: str) -> bool:
    """True, если сообщение — ровно приветствие (без вопроса/информации).

    «Привет!» и «Добрий день» → True. «Привет, сколько стоит?» → False.
    """
    normalized = _normalize_greeting(text)
    return bool(normalized) and normalized in PURE_GREETING_MARKERS


def looks_ukrainian(text: str) -> bool:
    """True, если текст несёт однозначные украинские признаки.

    Ловит uk-реплики без букв і/ї/є/ґ, которые старый промпт роутера
    помечал как ru («Дякую», «Добрий день», «будь ласка»). Маркеры
    подобраны так, чтобы слова не существовали в русском: правило
    применяется только для повышения ru→uk, чистый русский не трогается.
    """
    if not text:
        return False
    if _UK_UNIQUE_LETTERS_RE.search(text):
        return True
    return bool(_UK_MARKER_RE.search(text))


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
    4. Роутер сказал 'ru', но в сообщении однозначные украинские маркеры
       («Дякую», «Добрий день», «будь ласка») — повышаем до 'uk'. Старый
       промпт видел uk только по і/ї/є/ґ, и такие реплики падали в ru.
    В остальных случаях верим роутеру.
    """
    raw = normalize_language(raw)
    # session_lang=None означает, что язык сессии ещё не установлен
    session = normalize_language(session_lang) if session_lang else None
    msg_has_cyrillic = has_cyrillic(message)

    if raw == "ru" and looks_ukrainian(message):
        return "uk"

    if raw == "ru" and not msg_has_cyrillic:
        if session in ("en", "uk"):
            return session
        # A fresh English user may start with a two- or three-letter greeting.
        # Keep ambiguous replies such as "ok" Russian by default, but do not
        # let a router failure turn an explicit greeting into a Russian reply.
        short_latin_token = re.sub(r"[^a-z]", "", message.strip().lower())
        if session is None and short_latin_token in _SHORT_ENGLISH_GREETINGS:
            return "en"
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
    "uk": "Не зовсім зрозумів запитання. Розкажіть, що вас цікавить про школу Ukido?",
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
    "uk": [
        "Цікаве запитання! Але повернімося до теми школи Ukido. Чим можу допомогти?",
        "Це виходить за межі моєї компетенції. Розповім краще про наші курси?",
        "Зосередьмося на розвитку soft skills для дітей. Що вас цікавить?",
        "Я спеціалізуюся на питаннях про школу Ukido. Яку інформацію підказати?",
        "Пропоную повернутися до теми навчання. Розповісти про програми чи ціни?",
        "Це не моя сфера. Можу розповісти про курси, викладачів або методики.",
        "Обговорімо щось пов'язане зі школою. Що саме вас цікавить?",
    ],
}

NEED_SIMPLIFICATION = {
    "ru": "Пожалуйста, задавайте не более трёх вопросов за раз. Например, начните с самого важного для вас.",
    "en": "Could you keep it to three questions at a time? Start with the one that matters most to you.",
    "uk": "Будь ласка, ставте не більше трьох запитань за раз. Наприклад, почніть з найважливішого для вас.",
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
    # BUG-01: uk-извинения, чтобы сбой перевода не отдавал русский текст.
    "uk": {
        "generation_failed": "Вибачте, не можу відповісти просто зараз. Переформулюйте запитання.",
        "timeout": "Перевищено час очікування. Спробуйте ще раз.",
        "invalid_response": "Щось пішло не так з мого боку. Переформулюйте запитання, будь ласка.",
        "router_failed": "Тимчасова проблема. Спробуйте пізніше.",
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
    "uk": [
        "Вітаю! Я помічник школи Ukido. Чим можу допомогти?",
        "Добрий день! Радий допомогти з питаннями про наші курси.",
        "Вітаю! Готовий розповісти про програми школи Ukido.",
    ],
}

GREETING_PREFIX = {
    "ru": "Здравствуйте! ",
    "en": "Hello! ",
    "uk": "Вітаю! ",
}

ONLINE_FALLBACK = {
    "ru": "Я на связи. Чем помочь?",
    "en": "I'm here. What can I help you with?",
    "uk": "Я на зв'язку. Чим допомогти?",
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
    "uk": [
        "Будь ласка! Звертайтеся, якщо будуть запитання.",
        "Раді допомогти! Якщо потрібна додаткова інформація - запитуйте.",
        "Завжди будь ласка! Готовий відповісти на інші запитання.",
    ],
}

THANKS_PREFIX = {
    "ru": "Пожалуйста! ",
    "en": "You're welcome! ",
    "uk": "Будь ласка! ",
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
    "uk": [
        "Нічого страшного! Чим можу допомогти?",
        "Усе гаразд! Готовий відповісти на ваші запитання.",
        "Не хвилюйтеся! Розкажіть, що вас цікавить.",
    ],
}

APOLOGY_PREFIX = {
    "ru": "Ничего страшного! ",
    "en": "No worries at all! ",
    "uk": "Нічого страшного! ",
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
    "uk": [
        "Чудово! Що ще вас цікавить про наші курси?",
        "Гаразд! Є ще запитання про школу Ukido?",
        "Яка інформація ще потрібна?",
        "Супер! Чим ще можу допомогти?",
        "Радий, що зрозуміло! Що ще розповісти?",
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
    "uk": [
        "Було приємно допомогти! До побачення!",
        "Дякую за звернення! Усього доброго!",
        "Раді були проконсультувати! До зустрічі!",
        "Удачі вам! До побачення!",
        "Будемо раді бачити вас у нашій школі! До зв'язку!",
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
    "uk": [
        "\n\nДо побачення! Будемо раді бачити вас у нашій школі!",
        "\n\nУсього доброго! Звертайтеся, якщо виникнуть запитання!",
        "\n\nДо зустрічі! Сподіваємося побачити вашу дитину на заняттях!",
        "\n\nУдачі вам! До зв'язку!",
    ],
}

THANKS_PREFIXES_SUCCESS = {
    "ru": ["Рады помочь! ", "Пожалуйста! "],
    "en": ["Happy to help! ", "You're welcome! "],
    "uk": ["Раді допомогти! ", "Будь ласка! "],
}

# Маркеры для защиты от дублей (проверка «уже есть прощание/благодарность»)
FAREWELL_MARKERS = {
    "ru": ["до свидания", "до встречи", "всего доброго", "удачи", "до связи"],
    "en": ["goodbye", "see you", "take care", "good luck", "bye"],
    "uk": ["до побачення", "до зустрічі", "усього доброго", "удачі", "до зв'язку"],
}

THANKS_MARKERS = {
    "ru": ["рад", "пожалуйста", "всегда пожалуйста"],
    "en": ["happy to help", "welcome", "glad"],
    "uk": ["радий", "раді", "будь ласка", "завжди"],
}


# Сообщения эндпоинта /trial-signup (форма шлёт поле language)
TRIAL_SIGNUP_MESSAGES = {
    "ru": {
        "not_configured": "Сервис временно недоступен. Пожалуйста, попробуйте позже.",
        "success": "Спасибо за заявку! Мы свяжемся с вами в ближайшее время.",
        "failure": "Произошла ошибка при обработке заявки. Пожалуйста, попробуйте еще раз.",
        "critical": "Временная техническая проблема. Мы уже работаем над её решением.",
    },
    "en": {
        "not_configured": "The service is temporarily unavailable. Please try again later.",
        "success": "Thank you for signing up! We'll be in touch shortly.",
        "failure": "Something went wrong while processing your request. Please try again.",
        "critical": "A temporary technical issue on our side. We're already on it.",
    },
    "uk": {
        "not_configured": "Сервіс тимчасово недоступний. Будь ласка, спробуйте пізніше.",
        "success": "Дякуємо за заявку! Ми зв'яжемося з вами найближчим часом.",
        "failure": "Сталася помилка під час обробки заявки. Будь ласка, спробуйте ще раз.",
        "critical": "Тимчасова технічна проблема. Ми вже працюємо над її вирішенням.",
    },
}


def get_trial_signup_message(key: str, lang: str = DEFAULT_LANGUAGE) -> str:
    lang = normalize_language(lang)
    if lang not in TRIAL_SIGNUP_MESSAGES:
        lang = "ru"
    messages = TRIAL_SIGNUP_MESSAGES[lang]
    return messages.get(key, messages["critical"])


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
