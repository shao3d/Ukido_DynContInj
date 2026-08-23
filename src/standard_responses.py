"""
standard_responses.py - Единое место для всех заготовленных ответов системы.

Фразы и их переводы живут в localization.py; этот модуль сохраняет
исторический API (без параметра языка) для существующих вызовов.
"""

import random
from config import Config
from localization import (
    get_fallback,
    get_offtopic_response as _get_offtopic_response,
    get_need_simplification as _get_need_simplification,
    get_error_response as _get_error_response,
    FALLBACK,
    OFFTOPIC_RESPONSES,
    NEED_SIMPLIFICATION,
    ERROR_RESPONSES,
)

# Устанавливаем seed для детерминированности (только если включен детерминированный режим)
config = Config()
if config.DETERMINISTIC_MODE:
    random.seed(config.SEED)

# Единый fallback для всех ошибок и неопределённых ситуаций
DEFAULT_FALLBACK = get_fallback("ru")

# Ответы для офтопик вопросов (экономим токены, не генерируем через LLM)
OFFTOPIC_RESPONSES = OFFTOPIC_RESPONSES["ru"]

# Ответ для need_simplification (слишком много вопросов)
NEED_SIMPLIFICATION_MESSAGE = _get_need_simplification("ru")

# Ответы при технических ошибках
ERROR_RESPONSES = ERROR_RESPONSES["ru"]

def get_offtopic_response(lang: str = "ru") -> str:
    """Возвращает случайный ответ для офтопика на нужном языке"""
    return _get_offtopic_response(lang)

def get_need_simplification_message(lang: str = "ru") -> str:
    """Возвращает фразу про слишком много вопросов на нужном языке"""
    return _get_need_simplification(lang)

def get_error_response(error_type: str = "default", lang: str = "ru") -> str:
    """Возвращает ответ для конкретного типа ошибки на нужном языке"""
    return _get_error_response(error_type, lang)

def get_default_fallback(lang: str = "ru") -> str:
    """Возвращает универсальный fallback на нужном языке"""
    return get_fallback(lang)
