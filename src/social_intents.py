"""
social_intents.py — лёгкий детектор социальных интентов по правилам.

Интенты: greeting, farewell, thanks, unknown.
Используется как быстрый путь до вызова LLM.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from difflib import SequenceMatcher


class SocialIntent(str, Enum):
    GREETING = "greeting"
    FAREWELL = "farewell"
    THANKS = "thanks"
    APOLOGY = "apology"
    UNKNOWN = "unknown"


# Базовые паттерны RU+EN для MVP
GREETING_PATTERNS = [
    r"\bпривет(ик|ики|ствую)?\b",  # Добавлено "приветствую"
    r"\bздравств(уй|уйте)\b",
    # Варианты приветствий с "добрый/доброе"
    r"\bдоброе\s+(утро)\b",
    r"\bдобрый\s+(день|вечер)\b",
    r"\bхай\b",
    r"\bhi\b",
    r"\bhello\b",
    r"\bалло\b",  # Добавлено "алло"
]

FAREWELL_PATTERNS = [
    r"\bпока\b",
    r"\bдо\s+свидан(ья|ия)\b",
    r"\bувидим(ся)?\b",
    r"\bвсего\s+(доброго|хорошего)\b",
    r"\bbye\b",
]

THANKS_PATTERNS = [
    r"\bспасибо(\s+большое)?\b",
    r"\bблагодар(ю|им|ен|на|ны)\b",  # Улучшенный паттерн для всех форм
    r"\bмерси\b",
    r"\bthanks\b",
    r"\bthank\s+you\b",
]

_COMPILED = {
    SocialIntent.GREETING: [re.compile(p, re.IGNORECASE) for p in GREETING_PATTERNS],
    SocialIntent.FAREWELL: [re.compile(p, re.IGNORECASE) for p in FAREWELL_PATTERNS],
    SocialIntent.THANKS: [re.compile(p, re.IGNORECASE) for p in THANKS_PATTERNS],
}


# Бизнес-маркеры, при наличии считаем запрос смешанным и отдаём в бизнес-ветку
BUSINESS_HINTS = [
    r"\bкурс(ы|а|ов)?\b",
    r"\bстоимост[ьи]\b",
    r"\bцен[аы]\b",
    r"\bсколько\s+стоит\b",
    r"\bпоч[её]м\b",
    # Оплата/платёж/оплачивать
    r"\bоплат(а|ить|ы)\b",
    r"\bоплач\w*\b",
    r"\bплат\w*\b",
    r"\bкарт(а|ой|у|ы)\b",  # Добавлено для оплаты картой
    r"\bбезнал\w*\b",  # Безналичный расчёт
    r"\bюрлиц\w*\b",  # Юридические лица
    r"\bюридическ\w*\b",
    r"\bкак\s+записать(ся)?\b",
    r"\bзаписать(ся)?\b",
    r"\bкогда\b",
    r"\bпрограмма\b",
    r"\bпреподавател(ь|и)\b",
    r"\bучител(ь|я|ей|ям)\b",  # Добавлено для вопросов об учителях
    # Время и расписание
    r"\bпо\s+времени\b",
    r"\bвечером\b",
    r"\bутром\b",
    r"\bрасписани[ея]\b",
    # Скидки и льготы
    r"\bскидк[а-я]*\b",
    r"\bльгот[а-я]*\b",
    r"\bмалоимущ\w*\b",
    r"\bмногодетн\w*\b",
    # Рассрочка/частями
    r"\bрассрочк[а-я]*\b",
    r"\bв\s+рассрочку\b",
    r"\bчастями\b",
    r"\bпо\s+частям\b",
    # Пробные занятия и уроки
    r"\bпробн(ый|ое|ая|ые)\b",
    r"\bзанят(ие|ия)\b",
    r"\bурок(и)?\b",
    r"\bсертификат\b",
    r"\bесть\s+ли\b",  # Вопросительная конструкция
    # Безопасность и буллинг
    r"\bобижа(ть|ют|ли)\b",
    r"\bбуллинг\b",
    r"\bбезопасност[ьи]\b",
    r"\bконфликт\b",
    r"\bзащит[аы]\b",
    # Партнёры и сотрудничество
    r"\bпартн[её]р\w*\b",
    r"\bсотруднича\w*\b",
    r"\bшкол(а|ы|ами)\b",  # Школы-партнёры
    # Гарантии и результаты
    r"\bгарант\w*\b",
    r"\bрезультат\w*\b",
    r"\bэффективност\w*\b",
    r"\bROI\b",  # Return on Investment
    r"\bметрик\w*\b",
    # Описание детей и проблем
    r"\bзамкнут\w*\b",
    r"\bстесн[яи]\w*\b",
    r"\bзастенчив\w*\b",
    r"\bотлични\w*\b",
    r"\bволну\w*\b",
    r"\bвыступлен\w*\b",
    r"\bдочь\b",
    r"\bдочк\w*\b",
    r"\bсын\w*\b",
    r"\bвнук\w*\b",
    r"\bвнучк\w*\b",
    r"\bребен\w*\b",
    r"\bребёнк\w*\b",
    r"\bдет(и|ей|ям|ьми|ях)\b",
    # Домашние задания
    r"\bдомашн\w*\b",
    r"\bдомашк\w*\b",
    r"\bзадан\w*\b",
    # Вопросы о школе
    r"\bчто\s+(посоветуете|предложите|порекомендуете)\b",
    r"\bчто\s+нужно\b",
    r"\bсофт\s*скилл?[сз]?\b",
    r"\bsoft\s*skills?\b",
    # Онлайн и формат
    r"\bонлайн\b",
    r"\bоффлайн\b",
    r"\bформат\w*\b",
    # География
    r"\bпольш\w*\b",
    r"\bчасов\w*\s+пояс\w*\b",
    r"\bвремени\s+разниц\w*\b",
]

_COMPILED_BUSINESS = [re.compile(p, re.IGNORECASE) for p in BUSINESS_HINTS]

# Критичные бизнес-слова для fuzzy matching
CRITICAL_BUSINESS_KEYWORDS = [
    "курс", "курсы", "курса",
    "цена", "цены", "стоимость", "стоит",
    "оплата", "оплатить", "платить", "плата",
    "скидка", "скидки", "льгота", "льготы",
    "малоимущие", "многодетные",
    "занятие", "занятия", "урок", "уроки",
    "записать", "запись", "записаться",
    "ребенок", "ребёнок", "дети", "дочь", "сын",
    "преподаватель", "учитель",
    "расписание", "время", "когда",
    "онлайн", "офлайн",
    "секта",  # Добавляем для обработки скептических вопросов
]


@dataclass
class SocialDetection:
    intent: SocialIntent
    confidence: float
    matches: List[str]


def detect_social_intent(text: str) -> SocialDetection:
    """Возвращает социальный интент по простым правилам.

    Если найдены бизнес-маркеры одновременно с social-словами — помечаем как UNKNOWN (mixed),
    чтобы отдать дальше в бизнес-ветку.
    """
    if not text or not text.strip():
        return SocialDetection(SocialIntent.UNKNOWN, 0.0, [])

    text_norm = text.strip()

    # Проверка на бизнес-маркеры (mixed intent) - теперь с fuzzy matching
    has_business = has_business_signals(text_norm)

    for intent, regs in _COMPILED.items():
        matches: List[str] = []
        for rgx in regs:
            m = rgx.search(text_norm)
            if m:
                matches.append(m.group(0))
        if matches:
            if has_business:
                # смешанный случай → пусть идёт в бизнес
                return SocialDetection(SocialIntent.UNKNOWN, 0.49, matches)
            # базовая эвристика уверенности: больше совпадений → выше доверие
            conf = min(0.95, 0.6 + 0.1 * len(matches))
            return SocialDetection(intent, conf, matches)

    return SocialDetection(SocialIntent.UNKNOWN, 0.0, [])


def fuzzy_match_word(word: str, pattern: str, threshold: float = 0.8) -> bool:
    """Проверяет схожесть слов с учётом опечаток.
    
    Примеры:
    - "крус" -> "курс" (0.86) ✓
    - "цина" -> "цена" (0.75) ✗
    - "оплта" -> "оплата" (0.83) ✓
    """
    if len(word) < 3 or len(pattern) < 3:  # Слишком короткие слова - только точное совпадение
        return word.lower() == pattern.lower()
    
    # Слова должны быть примерно одной длины (±1 символ)
    if abs(len(word) - len(pattern)) > 1:
        return False
    
    # Дополнительная проверка: первая буква должна совпадать (исключаем сцена->цена)
    if word[0].lower() != pattern[0].lower():
        return False
    
    ratio = SequenceMatcher(None, word.lower(), pattern.lower()).ratio()
    return ratio >= threshold


def has_business_signals(text: str) -> bool:
    """True если в тексте есть маркеры бизнес-вопроса.
    
    Сначала проверяет точные regex паттерны (быстро).
    Если не нашли - проверяет критичные слова через fuzzy matching (медленнее).
    """
    if not text:
        return False
    
    # 1. Быстрая проверка через regex
    if any(rgx.search(text) for rgx in _COMPILED_BUSINESS):
        return True
    
    # 2. Fuzzy matching для критичных слов (обработка опечаток)
    words = text.lower().split()
    for word in words:
        # Убираем знаки препинания с краёв слова
        word_clean = word.strip('.,!?;:')
        if len(word_clean) < 3:  # Пропускаем слишком короткие
            continue
            
        for keyword in CRITICAL_BUSINESS_KEYWORDS:
            if fuzzy_match_word(word_clean, keyword, threshold=0.85):
                return True
    
    return False


def has_business_signals_extended(text: str) -> tuple[bool, bool]:
    """Версия с отслеживанием fuzzy matching.
    
    Returns:
        (has_business, fuzzy_matched)
    """
    if not text:
        return False, False
    
    # 1. Быстрая проверка через regex
    if any(rgx.search(text) for rgx in _COMPILED_BUSINESS):
        return True, False
    
    # 2. Fuzzy matching для критичных слов (обработка опечаток)
    words = text.lower().split()
    for word in words:
        # Убираем знаки препинания с краёв слова
        word_clean = word.strip('.,!?;:')
        if len(word_clean) < 3:  # Пропускаем слишком короткие
            continue
            
        for keyword in CRITICAL_BUSINESS_KEYWORDS:
            if fuzzy_match_word(word_clean, keyword, threshold=0.85):
                return True, True  # Нашли через fuzzy
    
    return False, False

