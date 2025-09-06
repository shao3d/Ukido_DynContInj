#!/usr/bin/env python3
"""
Простой тест API ключа OpenRouter
Запустите: python3 test_key_simple.py
"""

import os
import json
from urllib import request
from dotenv import load_dotenv

load_dotenv()

def test_key():
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY не найден в .env файле!")
        return
    
    print(f"🔑 Тестирую ключ: {api_key[:15]}...{api_key[-10:]}")
    print(f"📏 Длина ключа: {len(api_key)} символов")
    print(f"🔍 Первые 5 символов: '{api_key[:5]}' (должно быть 'sk-or')")
    
    data = json.dumps({
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": "Say 'API works!'"}],
        "max_tokens": 10
    }).encode('utf-8')
    
    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with request.urlopen(req) as response:
            status = response.getcode()
            print(f"📡 HTTP статус: {status}")
            
            if status == 200:
                print("✅ API ключ работает!")
                result = json.loads(response.read())
                if 'choices' in result:
                    print(f"🤖 Ответ: {result['choices'][0]['message']['content']}")
                    
    except request.HTTPError as e:
        print(f"❌ HTTP ошибка {e.code}: {e.read().decode()[:500]}")
    except Exception as e:
        print(f"❌ Исключение: {e}")

if __name__ == "__main__":
    test_key()