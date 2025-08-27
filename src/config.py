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
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    MODEL = "google/gemini-2.5-flash"
    # Отдельная модель для финальной генерации ответов
    MODEL_ANSWER = os.getenv("MODEL_ANSWER", "openai/gpt-4o-mini")
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
    
    # Уровень логирования
    LOG_LEVEL = "INFO"  # INFO для основных событий, DEBUG для детальной отладки
    
    # Настройки юмора Жванецкого
    ZHVANETSKY_ENABLED = True  # Включить/выключить функцию юмора
    ZHVANETSKY_PROBABILITY = 0.33  # Базовая вероятность использования юмора (33% от offtopic)
    ZHVANETSKY_TIMEOUT = 5.0  # Таймаут генерации юмора в секундах (увеличено с 3.0 для надёжности)
    ZHVANETSKY_TEMPERATURE = 1.0  # Температура для Claude Haiku (максимальная для креативности)
    ZHVANETSKY_MAX_PER_HOUR = 3  # Максимум шуток на пользователя в час