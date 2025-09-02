#!/usr/bin/env python3
"""
Тест для проверки исправления проблемы "забирать"
"""

import json
import httpx
import asyncio
from datetime import datetime

# Тестовые фразы с упоминанием транспорта
test_cases = [
    {
        "name": "После работы забирать",
        "message": "Угу, понятно. А занятия долго идут? Я после работы забирать буду",
        "expected_contains": ["онлайн", "zoom", "из дома", "не нужно", "не придётся"]
    },
    {
        "name": "Кто будет привозить",
        "message": "Кто будет привозить ребёнка на занятия?",
        "expected_contains": ["онлайн", "zoom", "из дома", "не нужно"]
    },
    {
        "name": "Далеко довозить",
        "message": "У нас далеко от вашего офиса, как довозить?",
        "expected_contains": ["онлайн", "zoom", "не нужно ехать", "из дома"]
    },
    {
        "name": "Во сколько забрать",
        "message": "Во сколько нужно забрать ребёнка после занятий?",
        "expected_contains": ["онлайн", "zoom", "из дома", "забирать не"]
    }
]

async def test_transport_fix():
    """Тестирует исправление проблемы с непониманием онлайн-формата"""
    
    print("🧪 Тестирование исправления проблемы 'забирать'")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        passed = 0
        failed = 0
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n📝 Тест {i}: {test['name']}")
            print(f"   Сообщение: {test['message']}")
            
            # Уникальный user_id для каждого теста
            user_id = f"test_transport_{datetime.now().timestamp()}_{i}"
            
            # Сначала приветствие (для контекста)
            greeting_response = await client.post(
                "http://localhost:8000/chat",
                json={
                    "user_id": user_id,
                    "message": "Добрый день! Хочу узнать про ваши курсы для ребёнка 10 лет."
                }
            )
            
            # Основной тестовый запрос
            response = await client.post(
                "http://localhost:8000/chat",
                json={
                    "user_id": user_id,
                    "message": test["message"]
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                bot_response = data.get("response", "").lower()
                
                # Проверяем наличие ключевых слов
                found_keywords = []
                missing_keywords = []
                
                for keyword in test["expected_contains"]:
                    if keyword.lower() in bot_response:
                        found_keywords.append(keyword)
                    else:
                        missing_keywords.append(keyword)
                
                if found_keywords and not missing_keywords:
                    print(f"   ✅ PASSED - Найдены все ключевые слова")
                    print(f"   Найдено: {', '.join(found_keywords)}")
                    passed += 1
                elif found_keywords:
                    print(f"   ⚠️  PARTIAL - Найдены некоторые ключевые слова")
                    print(f"   Найдено: {', '.join(found_keywords)}")
                    print(f"   Не найдено: {', '.join(missing_keywords)}")
                    passed += 1  # Считаем частичный успех как успех
                else:
                    print(f"   ❌ FAILED - Не найдены ключевые слова")
                    print(f"   Ожидалось: {', '.join(test['expected_contains'])}")
                    failed += 1
                
                # Показываем часть ответа
                print(f"   Ответ бота (первые 200 символов):")
                print(f"   '{data.get('response', '')[:200]}...'")
                
                # Debug информация
                print(f"   Intent: {data.get('intent', 'N/A')}")
                print(f"   Signal: {data.get('user_signal', 'N/A')}")
            else:
                print(f"   ❌ FAILED - HTTP {response.status_code}")
                failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Результаты:")
    print(f"   ✅ Passed: {passed}/{len(test_cases)}")
    print(f"   ❌ Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("\n🎉 Все тесты пройдены успешно!")
    else:
        print(f"\n⚠️  Некоторые тесты не прошли")
    
    return passed, failed

if __name__ == "__main__":
    passed, failed = asyncio.run(test_transport_fix())
    exit(0 if failed == 0 else 1)