#!/usr/bin/env python3
"""
Тест для отладки Router - почему "Расскажите о вашей школе" определяется как offtopic
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_message(message, user_id="test_debug"):
    """Отправляет сообщение и показывает детальный ответ"""
    print(f"\n{'='*60}")
    print(f"📝 Тестируем: {message}")
    print('='*60)
    
    # Очищаем историю
    requests.post(f"{BASE_URL}/clear_history", json={"user_id": user_id})
    
    # Отправляем сообщение
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        },
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Ответ: {data.get('response', 'No response')[:200]}...")
        
        # Показываем метаданные если есть
        if 'metadata' in data:
            meta = data['metadata']
            print(f"\n📊 Метаданные:")
            print(f"  - Intent: {meta.get('intent', 'N/A')}")
            print(f"  - Signal: {meta.get('user_signal', 'N/A')}")
            print(f"  - Questions: {meta.get('decomposed_questions', [])}")
            print(f"  - Documents: {[doc['title'] for doc in meta.get('documents', [])]}")
            print(f"  - Social: {meta.get('social_context', 'N/A')}")
    else:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("🔍 Тестирование обработки общих вопросов о школе\n")
    
    # Тестовые случаи
    test_cases = [
        "Расскажите о вашей школе",
        "Добрый день! Расскажите о вашей школе",
        "Что за школа у вас?",
        "Чем вы занимаетесь?",
        "Какие курсы есть?",
        "Расскажите про вашу методику",
        "Здравствуйте! Хочу узнать о вашей школе подробнее"
    ]
    
    for message in test_cases:
        test_message(message)
        
    print("\n✅ Тестирование завершено")