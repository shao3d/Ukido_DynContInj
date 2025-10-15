#!/usr/bin/env python3
"""
Тестирование исправлений State Machine и социальных интентов
Версия 2.0: После внедрения фиксов
"""

import asyncio
import json
from typing import List, Dict

# Расширенные тестовые сценарии для проверки всех фиксов
TEST_CASES = [
    # Fix 1: Ready_to_buy с пустыми questions
    {
        "category": "Fix 1: Implicit Questions",
        "name": "Согласие без вопроса",
        "message": "Спасибо. Мы согласны.",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks",
        "expected_response_contains": ["записаться", "узнать"]  # Уточняющий вопрос
    },
    {
        "category": "Fix 1: Implicit Questions",
        "name": "Действие без вопроса",
        "message": "Спасибо. Действуем.",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks",
        "expected_response_contains": ["шаги", "записи"]
    },
    {
        "category": "Fix 1: Implicit Questions",
        "name": "Регистрация без вопроса",
        "message": "Благодарю! Регистрируйте меня",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks",
        "expected_response_contains": ["запис", "shao3d.github.io"]
    },
    
    # Fix 2: Repeated_greeting
    {
        "category": "Fix 2: Repeated Greeting",
        "name": "Повторное приветствие",
        "sequence": [
            {"message": "Привет! Есть курсы?", "user_id": "test_repeat_1"},
            {"message": "Привет! А цены какие?", "user_id": "test_repeat_1"}
        ],
        "check_second": True,
        "expected_no_duplicate_greeting": True
    },
    
    # Fix 4: State Machine усиление
    {
        "category": "Fix 4: State Machine",
        "name": "Price_sensitive начинает со скидки",
        "message": "Сколько стоит? Дорого наверное?",
        "expected_signal": "price_sensitive",
        "expected_response_contains": ["скидк", "10%", "15%", "20%"]
    },
    {
        "category": "Fix 4: State Machine",
        "name": "Anxiety начинает с эмпатии",
        "message": "Мой ребенок очень стеснительный, боится выступать",
        "expected_signal": "anxiety_about_child",
        "expected_response_contains": ["понимаем", "многие родители", "беспокойство"]
    },
    {
        "category": "Fix 4: State Machine",
        "name": "Ready_to_buy начинает с действия",
        "message": "Хочу записать ребенка на курс",
        "expected_signal": "ready_to_buy",
        "expected_response_contains": ["для записи", "следующий шаг", "shao3d.github.io/trial/"]
    },
    
    # Базовые проверки
    {
        "category": "Базовые",
        "name": "Чисто социальный: Спасибо",
        "message": "Спасибо!",
        "expected_status": "offtopic",
        "expected_signal": "exploring_only",
        "expected_social": "thanks"
    },
    {
        "category": "Базовые",
        "name": "Mixed: Привет + вопрос о цене",
        "message": "Привет! Сколько стоит курс?",
        "expected_status": "success",
        "expected_signal": "price_sensitive",
        "expected_social": "greeting"
    }
]

async def test_endpoint(message: str, user_id: str = "test_user") -> Dict:
    """Отправляет запрос на /chat endpoint"""
    import httpx
    
    url = "http://localhost:8000/chat"
    payload = {
        "message": message,
        "user_id": user_id
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

async def test_sequence(sequence: List[Dict]) -> List[Dict]:
    """Тестирует последовательность сообщений"""
    results = []
    for msg in sequence:
        result = await test_endpoint(msg["message"], msg["user_id"])
        results.append(result)
    return results

async def run_tests():
    """Запускает все тесты"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ STATE MACHINE И СОЦИАЛКИ")
    print("=" * 60)
    
    results = []
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n📝 Тест #{i}: {test.get('name', test.get('category'))}")
        
        # Обработка последовательностей
        if "sequence" in test:
            print(f"   Тестируем последовательность из {len(test['sequence'])} сообщений")
            seq_results = await test_sequence(test["sequence"])
            
            if test.get("check_second"):
                response = seq_results[1]
                print(f"   Проверяем второе сообщение")
                
                # Проверка на дублирование приветствия
                if test.get("expected_no_duplicate_greeting"):
                    greeting_words = ["привет", "здравств", "добр"]
                    has_greeting = any(word in response.get("response", "").lower()[:50] 
                                     for word in greeting_words)
                    
                    if not has_greeting:
                        print(f"   ✅ Нет повторного приветствия")
                        results.append({"test": test["name"], "status": "PASS"})
                    else:
                        print(f"   ❌ Обнаружено повторное приветствие!")
                        results.append({"test": test["name"], "status": "FAIL"})
        else:
            # Обычный тест
            print(f"   Сообщение: '{test['message']}'")
            response = await test_endpoint(test['message'], f"test_user_{i}")
            
            if "error" in response:
                print(f"   ❌ Ошибка: {response['error']}")
                results.append({"test": test['name'], "status": "ERROR"})
                continue
            
            # Проверки
            checks_passed = True
            
            # Проверка статуса
            if "expected_status" in test:
                actual = response.get("intent", "unknown")
                expected = test["expected_status"]
                if actual == expected:
                    print(f"   ✅ Статус: {actual}")
                else:
                    print(f"   ❌ Статус: {actual} (ожидался {expected})")
                    checks_passed = False
            
            # Проверка signal
            if "expected_signal" in test:
                actual = response.get("user_signal", "unknown")
                expected = test["expected_signal"]
                if actual == expected:
                    print(f"   ✅ Signal: {actual}")
                else:
                    print(f"   ❌ Signal: {actual} (ожидался {expected})")
                    checks_passed = False
            
            # Проверка содержимого ответа
            if "expected_response_contains" in test:
                response_text = response.get("response", "").lower()
                found = []
                not_found = []
                
                for keyword in test["expected_response_contains"]:
                    if keyword.lower() in response_text:
                        found.append(keyword)
                    else:
                        not_found.append(keyword)
                
                if not_found:
                    print(f"   ❌ В ответе НЕ найдено: {not_found}")
                    checks_passed = False
                else:
                    print(f"   ✅ Все ключевые слова найдены: {found}")
            
            # Показываем часть ответа
            print(f"   Ответ: {response.get('response', '')[:100]}...")
            
            # Сохраняем результат
            results.append({
                "test": test['name'],
                "category": test.get('category', 'Other'),
                "status": "PASS" if checks_passed else "FAIL"
            })
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    
    # Группировка по категориям
    categories = {}
    for r in results:
        cat = r.get('category', 'Other')
        if cat not in categories:
            categories[cat] = {"pass": 0, "fail": 0, "error": 0}
        
        status = r['status'].lower()
        if status in categories[cat]:
            categories[cat][status] += 1
    
    # Вывод по категориям
    for cat, stats in categories.items():
        total = sum(stats.values())
        passed = stats.get('pass', 0)
        print(f"\n{cat}:")
        print(f"  ✅ Пройдено: {passed}/{total} ({passed/total*100:.0f}%)")
        if stats.get('fail', 0) > 0:
            print(f"  ❌ Провалено: {stats['fail']}")
        if stats.get('error', 0) > 0:
            print(f"  ⚠️ Ошибки: {stats['error']}")
    
    # Общая статистика
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    
    print("\n" + "=" * 60)
    print(f"ИТОГО: {passed}/{total} тестов пройдено ({passed/total*100:.1f}%)")
    if failed > 0:
        print(f"❌ Провалено: {failed}")
    if errors > 0:
        print(f"⚠️ Ошибки: {errors}")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    print("🚀 Запуск тестов исправлений...")
    print("⚠️ Убедитесь, что сервер запущен: python src/main.py")
    
    try:
        results = asyncio.run(run_tests())
        
        # Сохраняем результаты
        with open("test_results_state_machine_fixes.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в test_results_state_machine_fixes.json")
        
    except KeyboardInterrupt:
        print("\n⛔ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")