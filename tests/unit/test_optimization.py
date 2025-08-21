#!/usr/bin/env python3
"""
Быстрый тест для проверки оптимизации промпта Router
"""

import asyncio
import httpx
import json

async def test_one_case():
    """Тестирует один случай ready_to_buy"""
    url = "http://localhost:8000/chat"
    
    # Тест implicit questions
    test = {
        "message": "Спасибо. Мы согласны.",
        "user_id": "test_optimization"
    }
    
    print(f"Тестируем: '{test['message']}'")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=test)
            response.raise_for_status()
            result = response.json()
            
            print(f"Status: {result.get('intent')}")
            print(f"Signal: {result.get('user_signal')}")
            print(f"Social: {result.get('social')}")
            print(f"Questions: {result.get('decomposed_questions', [])}")
            
            # Проверка
            if result.get('user_signal') == 'ready_to_buy':
                print("✅ Signal определен правильно")
            else:
                print(f"❌ Signal неверный: {result.get('user_signal')}")
                
            if result.get('decomposed_questions'):
                print("✅ Implicit questions добавлены")
            else:
                print("❌ Implicit questions НЕ добавлены!")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_one_case())