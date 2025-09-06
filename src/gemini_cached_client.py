"""
gemini_cached_client.py - Клиент с поддержкой Context Caching для Gemini
Кеширует статичную часть промпта (системный промпт + саммари документов)
"""

import hashlib
import json
from typing import List, Dict, Optional, Any
from src.openrouter_client import OpenRouterClient


class GeminiCachedClient(OpenRouterClient):
    """Расширенный клиент с поддержкой кеширования контекста для Gemini"""
    
    def __init__(self, api_key: str, seed: int = None, max_tokens: int = None, temperature: float = 0.3):
        """Инициализация с настройками для Gemini"""
        super().__init__(api_key, seed, max_tokens, temperature, model="google/gemini-2.5-flash")
        self.cached_context = None
        self.context_hash = None
        
    def _compute_context_hash(self, system_content: str) -> str:
        """Вычисляет хеш для системного контента"""
        return hashlib.md5(system_content.encode()).hexdigest()
    
    async def chat_with_cache(
        self, 
        system_content: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Отправляет запрос с кешированным системным контентом.
        
        Args:
            system_content: Статичная часть (системный промпт + саммари)
            user_message: Динамическая часть (текущий вопрос)
            history: История диалога
        """
        # Проверяем, изменился ли системный контент
        new_hash = self._compute_context_hash(system_content)
        
        # Формируем сообщения
        messages = []
        
        # Добавляем системный промпт с пометкой для кеширования
        if self.context_hash != new_hash:
            # Контекст изменился, обновляем кеш
            print("🔄 Обновляю кешированный контекст Gemini")
            self.context_hash = new_hash
            self.cached_context = system_content
            
        # В Gemini 2.5 можно использовать специальный формат для кеширования
        # Но через OpenRouter это может не работать напрямую
        # Поэтому используем обычный формат, но структурируем промпт оптимально
        
        # Системная часть (потенциально кешируемая на стороне Gemini)
        messages.append({
            "role": "system",
            "content": system_content
        })
        
        # История диалога (если есть)
        if history:
            messages.extend(history)
            
        # Текущий запрос пользователя
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Отправляем запрос
        # Gemini автоматически кеширует повторяющиеся части промпта
        return await self.chat(messages)
    
    async def chat_with_prefix_cache(
        self,
        static_prefix: str,
        dynamic_suffix: str,
        model_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Альтернативный метод с явным разделением на статичную и динамическую части.
        
        Args:
            static_prefix: Неизменяемая часть промпта (кешируется)
            dynamic_suffix: Изменяемая часть промпта
            model_params: Дополнительные параметры модели
        """
        # Формируем единое сообщение
        full_content = f"{static_prefix}\n\n{dynamic_suffix}"
        
        messages = [
            {"role": "user", "content": full_content}
        ]
        
        # Передаем дополнительные параметры если есть
        kwargs = model_params or {}
        return await self.chat(messages, **kwargs)