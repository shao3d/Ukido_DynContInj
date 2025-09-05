#!/usr/bin/env python3
"""
Тест обработки mixed интентов (социалка + вопросы по школе)
Проверяет соответствие инструкциям из router.py строки 515-525
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_mixed_intent(message: str, expected_status: str, expected_has_questions: bool):
    """Тестирует один mixed intent"""
    
    user_id = f"test_mixed_{hash(message)}"
    
    # Очистка истории
    requests.post(f"{BASE_URL}/clear_history/{user_id}")
    time.sleep(0.5)
    
    # Отправка сообщения
    response = requests.post(
        f"{BASE_URL}/chat",
        json={"user_id": user_id, "message": message},
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        actual_status = data.get('intent', 'unknown')
        actual_questions = data.get('decomposed_questions', [])
        social = data.get('social')
        
        # Проверка результатов
        status_ok = actual_status == expected_status
        questions_ok = (len(actual_questions) > 0) == expected_has_questions
        
        # Символы для визуализации
        status_symbol = "✅" if status_ok else "❌"
        questions_symbol = "✅" if questions_ok else "❌"
        
        print(f"\n{'='*80}")
        print(f"📝 Сообщение: {message}")
        print(f"📊 Ожидания: status={expected_status}, has_questions={expected_has_questions}")
        print(f"📈 Результат: status={actual_status} {status_symbol}, questions={len(actual_questions)} {questions_symbol}")
        print(f"   Social: {social}")
        if actual_questions:
            print(f"   Questions: {actual_questions}")
        print(f"🤖 Ответ: {data.get('response', '')[:100]}...")
        
        return status_ok and questions_ok
    else:
        print(f"❌ Ошибка: {response.status_code}")
        return False

def main():
    print("="*80)
    print("🧪 ТЕСТИРОВАНИЕ MIXED ИНТЕНТОВ")
    print("="*80)
    print("\nСогласно router.py строки 515-525:")
    print("Приветствие + информация о школе/детях = SUCCESS с implicit questions")
    print("="*80)
    
    # Тестовые случаи согласно примерам из промпта
    test_cases = [
        # Примеры прямо из промпта Router'а (строки 520-523)
        ("Добрый день! У меня трое детей", "success", True),
        ("Привет! Мой ребенок стеснительный", "success", True),
        ("Здравствуйте! Интересует курс для 10-летнего", "success", True),
        ("Спасибо! У меня двое детей 7 и 12 лет", "success", True),
        
        # Наш проблемный случай
        ("Добрый день! Расскажите о вашей школе", "success", True),
        ("Привет! Что за школа у вас?", "success", True),
        
        # Контрольные случаи
        ("Привет!", "offtopic", False),  # Чистое приветствие
        ("Расскажите о вашей школе", "success", True),  # Без приветствия
    ]
    
    results = []
    for message, expected_status, expected_has_questions in test_cases:
        result = test_mixed_intent(message, expected_status, expected_has_questions)
        results.append((message, result))
        time.sleep(1)  # Пауза между запросами
    
    # Итоговая статистика
    print("\n" + "="*80)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nПройдено: {passed}/{total}")
    
    if passed < total:
        print("\n❌ FAILED тесты:")
        for message, result in results:
            if not result:
                print(f"  - {message}")
        
        print("\n⚠️ ВЫВОД: Router НЕ следует собственным инструкциям для mixed интентов!")
        print("Требуется исправление в обработке декомпозиции.")
    else:
        print("\n✅ Все тесты пройдены! Mixed интенты работают корректно.")

if __name__ == "__main__":
    main()