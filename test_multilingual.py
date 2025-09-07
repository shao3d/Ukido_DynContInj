#!/usr/bin/env python3
"""
Тестовый скрипт для проверки мультиязычной поддержки (украинский/английский/русский)
MVP версия для базового тестирования
"""

import asyncio
import json
import httpx
from datetime import datetime
from typing import Dict, List, Tuple

# Конфигурация
API_URL = "http://localhost:8000/chat"
TIMEOUT = 30.0

# Тестовые сообщения с ожидаемым языком ответа
TEST_CASES: List[Tuple[str, str, str]] = [
    # (сообщение, ожидаемый язык, описание)
    
    # Украинский язык
    ("Привіт! Розкажіть про вашу школу", "uk", "Украинское приветствие"),
    ("Які курси у вас є для дітей 10 років?", "uk", "Вопрос о курсах на украинском"),
    ("Дякую за інформацію", "uk", "Благодарность на украинском"),
    
    # Английский язык
    ("Hello! Tell me about your school", "en", "Английское приветствие"),
    ("What courses do you have for 10 year olds?", "en", "Вопрос о курсах на английском"),
    ("Thanks for the information", "en", "Благодарность на английском"),
    
    # Русский язык
    ("Привет! Расскажите о вашей школе", "ru", "Русское приветствие"),
    ("Какие курсы у вас есть для детей 10 лет?", "ru", "Вопрос о курсах на русском"),
    ("Спасибо за информацию", "ru", "Благодарность на русском"),
    
    # Смешанные случаи (должны отвечать на русском)
    ("Hi, расскажите о ценах", "ru", "Смешанный en+ru → русский"),
    ("Hello, які у вас курси?", "uk", "Смешанный en+uk → украинский"),
    
    # Переключение языков
    ("Привет! А теперь Hello!", "en", "Переключение ru→en"),
    ("Hello! А тепер привіт!", "uk", "Переключение en→uk"),
]

def detect_response_language(text: str) -> str:
    """Простое определение языка ответа по характерным символам и словам"""
    text_lower = text.lower()
    
    # Украинские маркеры
    uk_chars = ['і', 'ї', 'є', 'ґ']
    uk_words = ['привіт', 'дякую', 'ваш', 'наш', 'для', 'дітей', 'школа']
    
    # Английские маркеры (проверяем что большинство букв латинские)
    latin_count = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    total_alpha = sum(1 for c in text if c.isalpha())
    
    # Подсчет маркеров
    has_uk_chars = any(char in text for char in uk_chars)
    has_uk_words = any(word in text_lower for word in uk_words)
    
    # Определение языка
    if has_uk_chars or has_uk_words:
        return "uk"
    elif total_alpha > 0 and latin_count / total_alpha > 0.8:
        return "en"
    else:
        return "ru"

async def test_message(user_id: str, message: str) -> Dict:
    """Отправляет сообщение в API и возвращает ответ"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(
                API_URL,
                json={"user_id": user_id, "message": message}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

def print_result(test_case: Tuple[str, str, str], response: Dict, detected_lang: str):
    """Красиво выводит результат теста"""
    message, expected_lang, description = test_case
    success = detected_lang == expected_lang
    
    # Цветовые коды для терминала
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Символы результата
    status = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
    
    print(f"\n{status} {BOLD}{description}{RESET}")
    print(f"   Сообщение: {message[:50]}...")
    print(f"   Ожидаемый язык: {expected_lang}")
    print(f"   Определённый язык: {detected_lang}")
    
    if "response" in response:
        response_preview = response["response"][:100].replace("\n", " ")
        print(f"   Ответ: {response_preview}...")
    
    if not success:
        print(f"   {RED}ОШИБКА: Язык ответа не соответствует ожидаемому!{RESET}")
    
    # Дополнительная информация
    if "intent" in response:
        print(f"   Intent: {response.get('intent')}")
    if "user_signal" in response:
        print(f"   User signal: {response.get('user_signal')}")

async def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ МУЛЬТИЯЗЫЧНОЙ ПОДДЕРЖКИ")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Количество тестов: {len(TEST_CASES)}")
    print("=" * 60)
    
    # Счетчики результатов
    total = len(TEST_CASES)
    passed = 0
    failed = 0
    errors = 0
    
    # Генерируем уникальный user_id для каждого теста
    base_user_id = f"test_multilingual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Прогоняем тесты
    for i, test_case in enumerate(TEST_CASES, 1):
        message, expected_lang, description = test_case
        user_id = f"{base_user_id}_{i}"
        
        print(f"\n[{i}/{total}] Тестируем: {description}")
        
        # Отправляем запрос
        response = await test_message(user_id, message)
        
        # Проверяем на ошибки
        if "error" in response:
            print(f"   ❌ ОШИБКА API: {response['error']}")
            errors += 1
            continue
        
        # Определяем язык ответа
        if "response" in response:
            detected_lang = detect_response_language(response["response"])
            
            # Выводим результат
            print_result(test_case, response, detected_lang)
            
            # Обновляем счетчики
            if detected_lang == expected_lang:
                passed += 1
            else:
                failed += 1
        else:
            print(f"   ❌ Нет поля 'response' в ответе API")
            errors += 1
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 60)
    
    # Цвета для статистики
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"
    
    print(f"Всего тестов: {total}")
    print(f"{GREEN}Успешно: {passed}{RESET}")
    print(f"{RED}Неудачно: {failed}{RESET}")
    print(f"{YELLOW}Ошибки: {errors}{RESET}")
    
    # Процент успеха
    if total > 0:
        success_rate = (passed / total) * 100
        color = GREEN if success_rate >= 80 else YELLOW if success_rate >= 60 else RED
        print(f"\nУспешность: {color}{success_rate:.1f}%{RESET}")
    
    # Рекомендации
    if success_rate < 80:
        print("\n⚠️  Рекомендации:")
        print("   - Проверьте правила определения языка в промптах")
        print("   - Убедитесь что LLM модели поддерживают нужные языки")
        print("   - Проверьте логи сервера на наличие ошибок")
    elif success_rate == 100:
        print("\n🎉 Отлично! Все тесты пройдены успешно!")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())