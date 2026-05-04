"""
config.py - Настройки приложения
MVP версия: только самое необходимое
"""

import os
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

class Config:
    """Настройки приложения"""
    APP_VERSION = os.getenv("APP_VERSION", "0.8.0-state-machine")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    ROUTER_MODEL = os.getenv("ROUTER_MODEL", os.getenv("MODEL", "google/gemini-2.5-flash"))
    MODEL = ROUTER_MODEL  # Backward-compatible alias for router model
    MODEL_ANSWER = os.getenv("MODEL_ANSWER", os.getenv("ANSWER_MODEL", "anthropic/claude-3.5-haiku"))
    ANSWER_MODEL = MODEL_ANSWER  # Backward-compatible alias for answer generation
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # Настройки для оптимальной производительности и классификации Gemini 2.5 Flash
    TEMPERATURE = 0.3  # Низкая температура для более последовательных результатов классификации
    MAX_TOKENS = 500   # Ограничиваем длину ответа для ускорения
    # Отдельный лимит для длинного финального ответа ассистента
    MAX_TOKENS_ANSWER = 1200
    SEED = 42          # Фиксированный seed для воспроизводимости результатов
    
    # Управление детерминированностью (для тестирования vs production)
    # Установите в "false" для production, чтобы юмор работал с истинной случайностью
    DETERMINISTIC_MODE = os.getenv("DETERMINISTIC_MODE", "false").lower() == "true"
    
    # Настройки истории диалогов
    HISTORY_LIMIT = 10  # Количество последних сообщений для хранения и использования
    PERSISTENCE_BASE_PATH = os.getenv("PERSISTENCE_BASE_PATH", "data/persistent_states")

    # Настройки публичной поверхности API
    CORS_ALLOW_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000,https://shao3d.github.io"
        ).split(",")
        if origin.strip()
    ]
    CORS_ALLOW_CREDENTIALS = (
        os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
        and "*" not in CORS_ALLOW_ORIGINS
    )
    ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
    
    # Уровень логирования
    LOG_LEVEL = "INFO"  # INFO для основных событий, DEBUG для детальной отладки
    
    # Настройки юмора Жванецкого
    ZHVANETSKY_ENABLED = True  # Включить/выключить функцию юмора
    ZHVANETSKY_MODEL = os.getenv("ZHVANETSKY_MODEL", os.getenv("HUMOR_MODEL", "anthropic/claude-3.5-haiku"))
    HUMOR_MODEL = ZHVANETSKY_MODEL  # Backward-compatible alias
    ZHVANETSKY_PROBABILITY = 0.60  # Базовая вероятность использования юмора (60% от offtopic) - оптимум для демо
    ZHVANETSKY_TIMEOUT = 10.0  # Таймаут генерации юмора в секундах (увеличено до 10.0 для Claude)
    ZHVANETSKY_TEMPERATURE = 1.0  # Температура для Claude Haiku (максимальная для креативности)
    ZHVANETSKY_MAX_PER_HOUR = 5  # Максимум шуток на пользователя в час (увеличено для демо)
    
    # Настройки обработчика завершённых действий
    ENABLE_COMPLETED_ACTIONS_HANDLER = True  # Включить/выключить обработку завершённых действий
    
    # Настройки мультиязычности
    TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "anthropic/claude-3.5-haiku")
    TRANSLATION_ENABLED = os.getenv("TRANSLATION_ENABLED", "true").lower() == "true"
    TRANSLATION_CACHE_SIZE = 1000  # Количество кешированных переводов
    SUPPORTED_LANGUAGES = ["ru", "uk", "en"]
    DEFAULT_LANGUAGE = "ru"

    # Настройки HubSpot CRM
    HUBSPOT_PRIVATE_APP_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
    HUBSPOT_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "")
