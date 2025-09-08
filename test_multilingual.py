#!/usr/bin/env python3
"""
test_multilingual.py - Тестирование мультиязычности системы
Версия 2.0: Тестирует определение языка и перевод ответов
"""

import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, List

# Цвета для вывода
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


async def test_multilingual():
    """Тестирует мультиязычность системы"""
    
    # Тестовые кейсы для разных языков
    test_cases = [
        # Украинский
        {
            "user_id": "test_uk_1",
            "message": "Привіт! Розкажіть про вашу школу",
            "expected_lang": "uk",
            "description": "Украинский: приветствие и вопрос о школе"
        },
        {
            "user_id": "test_uk_2",
            "message": "Які курси у вас є для дітей 10 років?",
            "expected_lang": "uk",
            "description": "Украинский: вопрос о курсах"
        },
        {
            "user_id": "test_uk_3",
            "message": "Скільки коштує навчання?",
            "expected_lang": "uk",
            "description": "Украинский: вопрос о цене"
        },
        {
            "user_id": "test_uk_4",
            "message": "Дякую за інформацію",
            "expected_lang": "uk",
            "description": "Украинский: благодарность"
        },
        
        # Английский
        {
            "user_id": "test_en_1",
            "message": "Hello! Tell me about your school",
            "expected_lang": "en",
            "description": "Английский: приветствие и вопрос о школе"
        },
        {
            "user_id": "test_en_2",
            "message": "What courses do you have for kids?",
            "expected_lang": "en",
            "description": "Английский: вопрос о курсах"
        },
        {
            "user_id": "test_en_3",
            "message": "How much does it cost?",
            "expected_lang": "en",
            "description": "Английский: вопрос о цене"
        },
        {
            "user_id": "test_en_4",
            "message": "Thanks for the information",
            "expected_lang": "en",
            "description": "Английский: благодарность"
        },
        
        # Русский (контрольная группа)
        {
            "user_id": "test_ru_1",
            "message": "Привет! Расскажите о вашей школе",
            "expected_lang": "ru",
            "description": "Русский: приветствие и вопрос о школе"
        },
        {
            "user_id": "test_ru_2",
            "message": "Какие курсы у вас есть?",
            "expected_lang": "ru",
            "description": "Русский: вопрос о курсах"
        },
        
        # Смешанные языки
        {
            "user_id": "test_mix_1",
            "message": "Привет! What about soft skills курсы?",
            "expected_lang": "en",  # Ожидаем английский из-за латиницы
            "description": "Смешанный: русский + английский"
        },
        {
            "user_id": "test_mix_2",
            "message": "Добрий день! Розкажіть about Ukido",
            "expected_lang": "uk",  # Ожидаем украинский из-за уникальных букв
            "description": "Смешанный: украинский + английский"
        },
        
        # Edge cases
        {
            "user_id": "test_emoji_1",
            "message": "👍",
            "expected_lang": "ru",  # По умолчанию для эмодзи
            "description": "Edge case: только эмодзи"
        },
        {
            "user_id": "test_short_1",
            "message": "OK",
            "expected_lang": "en",  # Латиница
            "description": "Edge case: короткое подтверждение на английском"
        },
        {
            "user_id": "test_short_2",
            "message": "Так",
            "expected_lang": "uk",  # Может быть и русский, но проверим
            "description": "Edge case: короткое подтверждение на украинском"
        },
        
        # Последовательность сообщений (проверка сохранения языка)
        {
            "user_id": "test_seq_uk",
            "message": "Розкажіть про ціни",
            "expected_lang": "uk",
            "description": "Последовательность 1/2: украинский запрос"
        },
        {
            "user_id": "test_seq_uk",
            "message": "А знижки є?",
            "expected_lang": "uk",  # Должен сохранить украинский из контекста
            "description": "Последовательность 2/2: продолжение на украинском"
        },
    ]
    
    # Статистика
    stats = {
        "total": len(test_cases),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "by_language": {
            "uk": {"total": 0, "detected": 0},
            "en": {"total": 0, "detected": 0},
            "ru": {"total": 0, "detected": 0}
        }
    }
    
    print(f"\n{Colors.HEADER}{'='*60}")
    print(f"🌐 ТЕСТИРОВАНИЕ МУЛЬТИЯЗЫЧНОСТИ v2.0")
    print(f"{'='*60}{Colors.ENDC}\n")
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Всего тестов: {stats['total']}\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, test in enumerate(test_cases, 1):
            print(f"{Colors.BOLD}Тест {i}/{stats['total']}: {test['description']}{Colors.ENDC}")
            print(f"  User: {test['user_id']}")
            print(f"  Message: {test['message']}")
            print(f"  Expected language: {test['expected_lang']}")
            
            # Обновляем статистику по языкам
            stats["by_language"][test["expected_lang"]]["total"] += 1
            
            try:
                # Отправляем запрос
                response = await client.post(
                    "http://localhost:8000/chat",
                    json={
                        "user_id": test["user_id"],
                        "message": test["message"]
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Извлекаем detected_language из metadata или из основного ответа
                    detected_lang = result.get("detected_language", "unknown")
                    if detected_lang == "unknown" and "metadata" in result:
                        detected_lang = result["metadata"].get("detected_language", "unknown")
                    
                    # Проверяем результат
                    if detected_lang == test["expected_lang"]:
                        print(f"  {Colors.OKGREEN}✅ PASSED: Язык определён правильно: {detected_lang}{Colors.ENDC}")
                        stats["passed"] += 1
                        stats["by_language"][test["expected_lang"]]["detected"] += 1
                        
                        # Проверяем, есть ли перевод
                        if detected_lang != "ru":
                            if "translated_to" in result or (
                                "metadata" in result and "translated_to" in result["metadata"]
                            ):
                                print(f"  {Colors.OKCYAN}   ✓ Перевод выполнен на {detected_lang}{Colors.ENDC}")
                            else:
                                print(f"  {Colors.WARNING}   ⚠ Перевод не выполнен (но язык определён){Colors.ENDC}")
                    else:
                        print(f"  {Colors.FAIL}❌ FAILED: Ожидался {test['expected_lang']}, получен {detected_lang}{Colors.ENDC}")
                        stats["failed"] += 1
                    
                    # Показываем часть ответа (первые 100 символов)
                    response_text = result.get("response", "")[:100]
                    print(f"  Response preview: {response_text}...")
                    
                else:
                    print(f"  {Colors.FAIL}❌ ERROR: HTTP {response.status_code}{Colors.ENDC}")
                    stats["errors"] += 1
                    
            except Exception as e:
                print(f"  {Colors.FAIL}❌ EXCEPTION: {e}{Colors.ENDC}")
                stats["errors"] += 1
            
            print()  # Пустая строка между тестами
            
            # Небольшая задержка между запросами
            await asyncio.sleep(0.5)
    
    # Итоговая статистика
    print(f"\n{Colors.HEADER}{'='*60}")
    print(f"📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*60}{Colors.ENDC}\n")
    
    print(f"Всего тестов: {stats['total']}")
    print(f"{Colors.OKGREEN}✅ Passed: {stats['passed']}{Colors.ENDC}")
    print(f"{Colors.FAIL}❌ Failed: {stats['failed']}{Colors.ENDC}")
    print(f"{Colors.WARNING}⚠️  Errors: {stats['errors']}{Colors.ENDC}")
    
    # Процент успешности
    success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
    color = Colors.OKGREEN if success_rate >= 80 else Colors.WARNING if success_rate >= 60 else Colors.FAIL
    print(f"\n{color}Успешность: {success_rate:.1f}%{Colors.ENDC}")
    
    # Статистика по языкам
    print(f"\n{Colors.HEADER}Статистика по языкам:{Colors.ENDC}")
    for lang, data in stats["by_language"].items():
        if data["total"] > 0:
            detection_rate = (data["detected"] / data["total"] * 100)
            print(f"  {lang.upper()}: {data['detected']}/{data['total']} ({detection_rate:.1f}%)")
    
    # Рекомендации
    print(f"\n{Colors.HEADER}Рекомендации:{Colors.ENDC}")
    if success_rate >= 80:
        print(f"{Colors.OKGREEN}✅ Система готова к использованию!{Colors.ENDC}")
    elif success_rate >= 60:
        print(f"{Colors.WARNING}⚠️  Система работает, но требует доработки{Colors.ENDC}")
    else:
        print(f"{Colors.FAIL}❌ Система требует серьёзной доработки{Colors.ENDC}")
    
    # Известные проблемы
    if stats["failed"] > 0 or stats["errors"] > 0:
        print(f"\n{Colors.WARNING}Известные проблемы:{Colors.ENDC}")
        print("- GPT-4o Mini может не идеально переводить на украинский")
        print("- Смешанные языки могут определяться неточно")
        print("- Короткие сообщения могут классифицироваться неверно")


if __name__ == "__main__":
    print(f"{Colors.OKCYAN}🚀 Запуск тестов мультиязычности...{Colors.ENDC}")
    print(f"{Colors.WARNING}⚠️  Убедитесь, что сервер запущен на http://localhost:8000{Colors.ENDC}")
    
    try:
        asyncio.run(test_multilingual())
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️  Тестирование прервано пользователем{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Критическая ошибка: {e}{Colors.ENDC}")