#!/usr/bin/env python3
"""
Тест API ключа OpenRouter
Запустите: python test_openrouter_key.py
"""

import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_key():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле!")
        return
    
    print(f"🔑 Тестирую ключ: {api_key[:15]}...{api_key[-10:]}")
    print(f"📏 Длина ключа: {len(api_key)} символов")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": "Say 'API works!'"}],
        "max_tokens": 10
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10.0
            )
            
            print(f"📡 HTTP статус: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ API ключ работает!")
                result = response.json()
                if 'choices' in result:
                    print(f"🤖 Ответ: {result['choices'][0]['message']['content']}")
            else:
                print(f"❌ Ошибка: {response.text}")
                
    except Exception as e:
        print(f"❌ Исключение: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())