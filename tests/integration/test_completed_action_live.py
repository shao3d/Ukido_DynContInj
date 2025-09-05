#!/usr/bin/env python3
"""
Тест обработки завершённых действий в реальном диалоге.
Проверяет сообщение "Оплатила перевод. Жду подтверждения"
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_completed_action_response():
    """Тестирует обработку завершённого действия через API"""
    
    # Очищаем историю
    response = requests.post(f"{BASE_URL}/clear_history", 
                            json={"user_id": "test_completed_action"})
    print("✅ История очищена\n")
    
    # История диалога для контекста
    messages = [
        "Здравствуйте! Хочу записать дочку сразу на два курса - лидерство и эмоциональный интеллект",
        "Запишите нас! Когда можно начать и как оплатить?"
    ]
    
    # Создаём контекст школы
    print("Создаю контекст диалога о школе...")
    for msg in messages:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"message": msg, "user_id": "test_completed_action"}
        )
        result = response.json()
        print(f"USER: {msg[:50]}...")
        print(f"BOT: {result['response'][:80]}...")
        print(f"Intent: {result.get('intent')}\n")
        time.sleep(0.5)
    
    # Теперь тестируем завершённое действие
    print("=" * 60)
    print("ТЕСТИРУЕМ ЗАВЕРШЁННОЕ ДЕЙСТВИЕ")
    print("=" * 60)
    
    test_message = "Оплатила перевод. Жду подтверждения"
    
    print(f"\n📝 Отправляем: '{test_message}'")
    
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"message": test_message, "user_id": "test_completed_action"}
    )
    
    result = response.json()
    
    print(f"\n📊 Результат:")
    print(f"Intent: {result.get('intent')}")
    print(f"Signal: {result.get('user_signal')}")
    print(f"\n🤖 Ответ бота:")
    print(result['response'])
    
    # Проверяем, что это готовый ответ из обработчика
    expected_phrases = [
        "Оплата обрабатывается",
        "платёж пройдёт",
        "подтверждение оплаты"
    ]
    
    response_lower = result['response'].lower()
    is_from_handler = any(phrase in response_lower for phrase in expected_phrases)
    
    print("\n" + "=" * 60)
    if is_from_handler:
        print("✅ Обработчик завершённых действий работает корректно!")
        print("   Использован готовый ответ вместо генерации через Claude")
    else:
        print("⚠️ Возможно используется генерация через Claude")
        print("   Ожидались фразы из обработчика")
    
    # Проверка, что статус success
    if result.get('intent') == 'success':
        print("✅ Статус корректно изменён на success")
    else:
        print(f"❌ Неверный статус: {result.get('intent')}")
    
    return result


if __name__ == "__main__":
    try:
        result = test_completed_action_response()
    except requests.exceptions.ConnectionError:
        print("❌ Ошибка: сервер не запущен на http://localhost:8000")
        print("   Запустите: python src/main.py")
        exit(1)