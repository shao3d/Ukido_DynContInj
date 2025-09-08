"""
Расширение OpenRouterClient для поддержки стриминга
"""

import json
import httpx
from typing import List, Dict, Optional, Any, AsyncGenerator

async def chat_stream(
    client, 
    messages: List[Dict[str, str]], 
    *, 
    model: Optional[str] = None, 
    temperature: Optional[float] = None, 
    max_tokens: Optional[int] = None, 
    seed: Optional[int] = None
) -> AsyncGenerator[str, None]:
    """
    Стримит ответ от модели по частям
    
    Args:
        client: Экземпляр OpenRouterClient
        messages: История диалога
    Yields:
        Части текста по мере генерации
    """
    headers = {
        "Authorization": f"Bearer {client.api_key}",
        "Content-Type": "application/json"
    }
    
    data: Dict[str, Any] = {
        "model": model or client.model,
        "messages": messages,
        "temperature": client.temperature if temperature is None else temperature,
        "stream": True  # Включаем стриминг!
    }
    
    # Добавляем опциональные параметры
    if seed is not None:
        data["seed"] = seed
    elif client.seed is not None:
        data["seed"] = client.seed
    if max_tokens is not None:
        data["max_tokens"] = max_tokens
    elif client.max_tokens is not None:
        data["max_tokens"] = client.max_tokens
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            async with http_client.stream("POST", client.api_url, headers=headers, json=data) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            chunk_data = line[6:]  # Убираем "data: "
                            if chunk_data == "[DONE]":
                                break
                            
                            chunk = json.loads(chunk_data)
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                choice = chunk["choices"][0]
                                if "delta" in choice and "content" in choice["delta"]:
                                    content = choice["delta"]["content"]
                                    if content:
                                        yield content
                        except json.JSONDecodeError:
                            continue
                            
    except Exception as e:
        print(f"❌ Ошибка стриминга: {e}")
        # В случае ошибки возвращаем пустую строку
        return