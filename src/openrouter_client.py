"""
openrouter_client.py - Клиент для OpenRouter API
MVP версия: минимум кода для работы
"""

import httpx
from typing import List, Dict, Optional, Any

class OpenRouterClient:
    """Клиент для работы с OpenRouter API"""
    
    def __init__(self, api_key: str, seed: int = None, max_tokens: int = None, temperature: float = 0.3, model: Optional[str] = None):
        """Инициализация с API ключом и параметрами для оптимальной классификации"""
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = model or "google/gemini-2.5-flash"
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
            async with httpx.AsyncClient() as client:
                print(f"🔍 Отправляю запрос к OpenRouter: {data.get('model')}")
                print(f"🔍 Размер промпта: {len(str(data))} символов")
                
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                
                print(f"🔍 HTTP статус: {response.status_code}")
                
                # Проверяем HTTP статус
                if response.status_code != 200:
                    print(f"❌ API ошибка {response.status_code}: {response.text[:500]}")
                    return ""
                
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
                    return content or ""
                else:
                    print("❌ API не вернул choices")
                    print(f"🔍 Структура ответа: {list(result.keys())}")
                    return ""
                    
        except httpx.TimeoutException:
            return "Превышено время ожидания ответа"
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return "Произошла ошибка при обработке запроса"