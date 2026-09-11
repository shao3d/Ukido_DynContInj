"""
openrouter_client.py - Клиент для OpenRouter API
MVP версия: минимум кода для работы
"""

import asyncio
import httpx
import json
from typing import List, Dict, Optional, Any


class OpenRouterError(Exception):
    """BUG-04: базовая ошибка транспорта OpenRouter.

    Ответа от модели НЕТ. Текст ошибки запрещено показывать пользователю
    как контент — вызывающий обязан обработать явно (извинение/фолбэк).
    """


class OpenRouterTimeout(OpenRouterError):
    """Превышено время ожидания ответа API."""


class OpenRouterHTTPError(OpenRouterError):
    """API вернул не-200."""

    def __init__(self, status_code: int, body: str = ""):
        self.status_code = status_code
        self.body = (body or "")[:500]
        super().__init__(f"OpenRouter HTTP {status_code}")


class OpenRouterEmptyResponse(OpenRouterError):
    """API вернул 200 без usable content (нет choices / пустой content)."""


class OpenRouterClient:
    """Клиент для работы с OpenRouter API"""
    
    def __init__(self, api_key: str, seed: int = None, max_tokens: int = None, temperature: float = 0.3, model: Optional[str] = None):
        """Инициализация с API ключом и параметрами для оптимальной классификации"""
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        # Дефолт модели — только из Config (миграция 2.5→3.x правится в одном месте)
        if model is None:
            from config import Config
            model = Config.DEFAULT_GEMINI_MODEL
        self.model = model
        self.seed = seed
        self.max_tokens = max_tokens
        self.temperature = temperature
    
    async def chat(self, messages: List[Dict[str, str]], *, model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None, seed: Optional[int] = None, response_format: Optional[Dict[str, Any]] = None, top_p: Optional[float] = None, frequency_penalty: Optional[float] = None, presence_penalty: Optional[float] = None) -> str:
        """
        Отправляет сообщения в API и получает ответ
        
        Args:
            messages: История диалога [{"role": "user", "content": "..."}]
        Returns:
            Текст ответа от модели
        Raises:
            OpenRouterTimeout: таймаут запроса.
            OpenRouterHTTPError: API вернул не-200 (есть status_code).
            OpenRouterEmptyResponse: 200 без usable content.
            OpenRouterError: прочие транспортные сбои.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data: Dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        
        # Добавляем опциональные параметры если они заданы
        if seed is not None:
            data["seed"] = seed
        elif self.seed is not None:
            data["seed"] = self.seed
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        elif self.max_tokens is not None:
            data["max_tokens"] = self.max_tokens
        if response_format is not None:
            data["response_format"] = response_format
        # Добавляем параметры для креативности
        if top_p is not None:
            data["top_p"] = top_p
        if frequency_penalty is not None:
            data["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            data["presence_penalty"] = presence_penalty
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:  # 30 секунд таймаут для предотвращения зависания
                print(f"🔍 Отправляю запрос к OpenRouter: {data.get('model')}")
                print(f"🔍 Размер промпта: {len(str(data))} символов")
                
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                
                print(f"🔍 HTTP статус: {response.status_code}")

                # BUG-04: не-200 — это ошибка транспорта, а не «пустой ответ».
                if response.status_code != 200:
                    print(f"❌ API ошибка {response.status_code}: {response.text[:500]}")
                    raise OpenRouterHTTPError(response.status_code, response.text)

                # Парсим ответ
                result = response.json()

                # Безопасное извлечение ответа
                if "choices" in result and len(result["choices"]) > 0:
                    choice = result["choices"][0]
                    # Пробуем разные варианты получения контента
                    content = None

                    # Стандартный формат OpenAI
                    if "message" in choice and "content" in choice["message"]:
                        content = choice["message"]["content"]
                    # Альтернативный формат (некоторые модели)
                    elif "text" in choice:
                        content = choice["text"]
                    # Прямой content в choice
                    elif "content" in choice:
                        content = choice["content"]

                    if not content or content.strip() == "":
                        print("⚠️ API вернул пустой content")
                        print(f"🔍 Содержимое choices[0]: {choice}")
                        # Попробуем альтернативный подход для streaming ответов
                        if "delta" in choice and "content" in choice["delta"]:
                            content = choice["delta"]["content"]
                    else:
                        print(f"✅ Получен ответ длиной {len(content)} символов")
                    # BUG-04: пустого контента как успеха не бывает
                    if not content or not content.strip():
                        raise OpenRouterEmptyResponse("empty content in choices[0]")
                    return content
                else:
                    print("❌ API не вернул choices")
                    print(f"🔍 Структура ответа: {list(result.keys())}")
                    raise OpenRouterEmptyResponse("no choices in response")

        except (OpenRouterError, asyncio.CancelledError):
            raise
        except httpx.TimeoutException as e:
            # BUG-04: таймаут — исключение, а не строка «Превышено время...»
            raise OpenRouterTimeout(f"timeout after 30s: {e}") from e
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            raise OpenRouterError(f"transport failed: {e}") from e