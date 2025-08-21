#!/usr/bin/env python3
"""
Тестирование обработки mixed интентов после рефакторинга
"""

import asyncio
import json
from typing import List, Dict

# Тестовые сценарии
TEST_CASES = [
    {
        "name": "Mixed: Спасибо + готовность записаться",
        "message": "Спасибо, запишите нас",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks"
    },
    {
        "name": "Mixed: Спасибо + согласие",
        "message": "Спасибо. Мы согласны.",
        "expected_status": "success", 
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks"
    },
    {
        "name": "Mixed: Привет + вопрос о цене",
        "message": "Привет! Сколько стоит курс?",
        "expected_status": "success",
        "expected_signal": "price_sensitive",
        "expected_social": "greeting"
    },
    {
        "name": "Чисто социальный: Спасибо",
        "message": "Спасибо!",
        "expected_status": "offtopic",
        "expected_signal": "exploring_only",
        "expected_social": "thanks"
    },
    {
        "name": "Чисто социальный: Привет",
        "message": "Привет",
        "expected_status": "offtopic",
        "expected_signal": "exploring_only",
        "expected_social": "greeting"
    },
    {
        "name": "Ready to buy: Хочу записать ребенка",
        "message": "Хочу записать ребенка на курс",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": None
    },
    {
        "name": "Mixed: Благодарю + регистрация",
        "message": "Благодарю! Регистрируйте меня",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks"
    },
    {
        "name": "Mixed: Спасибо + действие",
        "message": "Спасибо. Действуем.",
        "expected_status": "success",
        "expected_signal": "ready_to_buy",
        "expected_social": "thanks"
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

async def run_tests():
    """Запускает все тесты"""
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ MIXED ИНТЕНТОВ ПОСЛЕ РЕФАКТОРИНГА")
    print("=" * 60)
    
    results = []
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n📝 Тест #{i}: {test['name']}")
        print(f"   Сообщение: '{test['message']}'")
        
        # Отправляем запрос
        response = await test_endpoint(test['message'], f"test_user_{i}")
        
        if "error" in response:
            print(f"   ❌ Ошибка: {response['error']}")
            results.append({"test": test['name'], "status": "ERROR", "error": response['error']})
            continue
        
        # Проверяем результаты
        actual_status = response.get("intent", "unknown")
        actual_signal = response.get("user_signal", "unknown")
        actual_social = response.get("social")
        
        status_match = actual_status == test['expected_status']
        signal_match = actual_signal == test['expected_signal']
        social_match = actual_social == test['expected_social']
        
        # Выводим результаты
        print(f"   Ожидаемый статус: {test['expected_status']}")
        print(f"   Фактический статус: {actual_status} {'✅' if status_match else '❌'}")
        
        print(f"   Ожидаемый signal: {test['expected_signal']}")
        print(f"   Фактический signal: {actual_signal} {'✅' if signal_match else '❌'}")
        
        print(f"   Ожидаемый social: {test['expected_social']}")
        print(f"   Фактический social: {actual_social} {'✅' if social_match else '❌'}")
        
        # Показываем ответ
        print(f"   Ответ: {response.get('response', '')[:100]}...")
        
        # Сохраняем результат
        test_passed = status_match and signal_match and social_match
        results.append({
            "test": test['name'],
            "status": "PASS" if test_passed else "FAIL",
            "details": {
                "status": f"{actual_status} ({'✅' if status_match else '❌'})",
                "signal": f"{actual_signal} ({'✅' if signal_match else '❌'})",
                "social": f"{actual_social} ({'✅' if social_match else '❌'})"
            }
        })
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    
    print(f"Всего тестов: {total}")
    print(f"✅ Пройдено: {passed} ({passed/total*100:.1f}%)")
    print(f"❌ Провалено: {failed} ({failed/total*100:.1f}%)")
    print(f"⚠️ Ошибки: {errors} ({errors/total*100:.1f}%)")
    
    # Детали проваленных тестов
    if failed > 0:
        print("\n🔴 ПРОВАЛЕННЫЕ ТЕСТЫ:")
        for r in results:
            if r['status'] == 'FAIL':
                print(f"  - {r['test']}")
                for key, value in r['details'].items():
                    print(f"    {key}: {value}")
    
    return results

if __name__ == "__main__":
    print("🚀 Запуск тестов...")
    print("⚠️ Убедитесь, что сервер запущен: python src/main.py")
    
    try:
        results = asyncio.run(run_tests())
        
        # Сохраняем результаты в файл
        with open("test_results_mixed_intents.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в test_results_mixed_intents.json")
        
    except KeyboardInterrupt:
        print("\n⛔ Тестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")