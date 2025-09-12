#!/usr/bin/env python3
"""
Тест для проверки исправления обработки смайликов и acknowledgment сообщений
"""

import httpx
import json
import time

BASE_URL = "http://localhost:8000"

def test_emoji_handling():
    """Тестируем обработку смайликов и коротких acknowledgment сообщений"""
    
    test_messages = [
        ("👍", "emoji thumbs up"),
        ("😊", "emoji smile"),
        ("ok", "acknowledgment ok"),
        ("спасибо", "acknowledgment thanks"),
        (":)", "text smile"),
        ("ага", "acknowledgment aga"),
        ("✅", "emoji checkmark"),
    ]
    
    user_id = f"test_emoji_{int(time.time())}"
    
    print("=" * 60)
    print("Тестирование обработки смайликов и acknowledgment")
    print("=" * 60)
    
    # Сначала отправим обычное сообщение для контекста
    initial_message = {
        "user_id": user_id,
        "message": "Какие курсы есть?"
    }
    
    response = httpx.post(f"{BASE_URL}/chat", json=initial_message, timeout=30.0)
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Начальный запрос: '{initial_message['message']}'")
        print(f"   Status: {data.get('intent', 'unknown')}")
        print(f"   Signal: {data.get('user_signal', 'unknown')}")
    else:
        print(f"❌ Ошибка начального запроса: {response.status_code}")
        return
    
    time.sleep(1)  # Небольшая пауза между запросами
    
    # Теперь тестируем смайлики и acknowledgment
    for msg, description in test_messages:
        print(f"\n🧪 Тест: {description}")
        print(f"   Сообщение: '{msg}'")
        
        request_data = {
            "user_id": user_id,
            "message": msg
        }
        
        try:
            response = httpx.post(f"{BASE_URL}/chat", json=request_data, timeout=30.0)
            
            if response.status_code == 200:
                data = response.json()
                intent = data.get('intent', 'unknown')
                social_context = data.get('social', 'none')
                response_text = data.get('response', '')[:100]
                
                print(f"   ✅ Status: {intent}")
                print(f"   Social: {social_context}")
                
                # Проверяем, что смайлики правильно обрабатываются
                if "emoji" in description or "smile" in description:
                    if social_context == "acknowledgment" or "интересует" in response_text:
                        print(f"   ✅ Правильная обработка эмодзи!")
                    else:
                        print(f"   ⚠️ Эмодзи обработан как offtopic, а не acknowledgment")
                        print(f"   Response: {response_text}...")
                
                # Проверяем acknowledgment сообщения
                if "acknowledgment" in description:
                    if "интересует" in response_text or "помочь" in response_text:
                        print(f"   ✅ Правильная обработка acknowledgment!")
                    else:
                        print(f"   ⚠️ Acknowledgment не распознан")
                        print(f"   Response: {response_text}...")
                        
            else:
                print(f"   ❌ Ошибка: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
        
        time.sleep(0.5)  # Пауза между запросами
    
    print("\n" + "=" * 60)
    print("Тестирование завершено")
    print("=" * 60)

if __name__ == "__main__":
    print("🚀 Запуск тестов обработки смайликов...")
    print("⚠️  Убедитесь, что сервер запущен на localhost:8000")
    print()
    
    try:
        # Проверяем доступность сервера
        response = httpx.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Сервер доступен\n")
            test_emoji_handling()
        else:
            print(f"❌ Сервер вернул статус {response.status_code}")
    except httpx.ConnectError:
        print("❌ Не удалось подключиться к серверу")
        print("   Запустите сервер командой: python src/main.py")