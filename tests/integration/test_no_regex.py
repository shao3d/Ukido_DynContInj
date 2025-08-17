#!/usr/bin/env python3
"""
Тестирование системы без Quick Regex
Проверяем что все mixed запросы работают корректно
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"

# Тестовые сценарии
TEST_CASES = [
    {
        "name": "Чистое приветствие",
        "user_id": "test_user_1",
        "messages": ["Привет!"],
        "expected": "приветствие"
    },
    {
        "name": "Mixed: приветствие + вопрос",
        "user_id": "test_user_2", 
        "messages": ["Привет! Есть курсы для детей 10 лет?"],
        "expected": "ответ про курсы"
    },
    {
        "name": "Повторное приветствие",
        "user_id": "test_user_3",
        "messages": [
            "Привет!",
            "Сколько стоит обучение?",
            "Привет!"
        ],
        "expected": "распознавание повторного приветствия"
    },
    {
        "name": "Контекстуальный вопрос",
        "user_id": "test_user_4",
        "messages": [
            "Расскажите про цены",
            "А?"
        ],
        "expected": "продолжение темы про цены"
    },
    {
        "name": "Mixed: благодарность + вопрос",
        "user_id": "test_user_5",
        "messages": ["Спасибо! А есть скидки?"],
        "expected": "ответ про скидки"
    },
    {
        "name": "Прощание",
        "user_id": "test_user_6",
        "messages": [
            "Какие есть курсы?",
            "До свидания!"
        ],
        "expected": "корректное прощание без offtopic"
    }
]

async def send_message(session, user_id, message):
    """Отправляет сообщение в чат"""
    data = {
        "user_id": user_id,
        "message": message
    }
    
    try:
        async with session.post(f"{BASE_URL}/chat", json=data) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"Status {response.status}"}
    except Exception as e:
        return {"error": str(e)}

async def run_test_case(session, test_case):
    """Запускает один тестовый сценарий"""
    print(f"\n{'='*60}")
    print(f"📝 Тест: {test_case['name']}")
    print(f"👤 User ID: {test_case['user_id']}")
    print(f"🎯 Ожидается: {test_case['expected']}")
    print('-'*60)
    
    for i, message in enumerate(test_case['messages'], 1):
        print(f"\n💬 Сообщение {i}: {message}")
        
        result = await send_message(session, test_case['user_id'], message)
        
        if 'error' in result:
            print(f"❌ Ошибка: {result['error']}")
        else:
            print(f"🤖 Ответ: {result.get('response', 'Нет ответа')[:200]}...")
            print(f"📊 Статус: {result.get('intent', 'unknown')}")
            
            if result.get('social'):
                print(f"👋 Социальный контекст: {result['social']}")
            
            if result.get('decomposed_questions'):
                print(f"❓ Вопросы: {', '.join(result['decomposed_questions'])}")
            
            if result.get('relevant_documents'):
                print(f"📄 Документы: {', '.join(result['relevant_documents'])}")
    
    print(f"\n{'='*60}")

async def main():
    """Основная функция тестирования"""
    print("🚀 Тестирование Ukido AI Assistant без Quick Regex")
    print("⚠️  Убедитесь что сервер запущен на localhost:8000")
    print("✅ Quick Regex должен быть ОТКЛЮЧЕН (USE_QUICK_REGEX = False)")
    
    # Проверяем доступность сервера
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    health = await response.json()
                    print(f"\n✅ Сервер доступен: {health}")
                else:
                    print(f"\n❌ Сервер недоступен: статус {response.status}")
                    return
        except Exception as e:
            print(f"\n❌ Не могу подключиться к серверу: {e}")
            print("Запустите сервер командой: python src/main.py")
            return
        
        # Запускаем тесты
        for test_case in TEST_CASES:
            await run_test_case(session, test_case)
            await asyncio.sleep(1)  # Пауза между тестами
        
        print("\n✅ Все тесты завершены!")
        print("\n📋 Проверьте результаты:")
        print("1. Mixed запросы должны обрабатываться полностью")
        print("2. Повторные приветствия должны распознаваться")
        print("3. Контекстуальные вопросы должны работать")
        print("4. История должна сохраняться для всех запросов")

if __name__ == "__main__":
    asyncio.run(main())