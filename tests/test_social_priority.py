#!/usr/bin/env python3
"""
Тесты для проверки правильной обработки mixed социальных интентов
и усиленных маркеров State Machine после внесенных изменений.
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import chat, ChatRequest

# Цвета для вывода
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

test_cases = [
    # === ФАЗА 1: Mixed социальные интенты ===
    {
        "name": "Farewell + Success",
        "message": "До свидания! А сколько стоит месяц занятий?",
        "expected": {
            "intent": "success",
            "social_context": "farewell",
            "user_signal": "price_sensitive",
            "check_farewell_in_response": True
        }
    },
    {
        "name": "Thanks + Ready to Buy",
        "message": "Спасибо за информацию! Запишите нас на пробное занятие",
        "expected": {
            "intent": "success",
            "social_context": "thanks",
            "user_signal": "ready_to_buy",
            "check_thanks_prefix": True
        }
    },
    {
        "name": "Greeting + Business Question",
        "message": "Привет! Какие курсы есть для детей 10 лет?",
        "expected": {
            "intent": "success", 
            "social_context": "greeting",
            "user_signal": "exploring_only"
        }
    },
    
    # === ФАЗА 2: Расширенные маркеры anxiety_about_child ===
    {
        "name": "Буллинг маркер",
        "message": "Моего сына травят в школе, он не хочет туда идти",
        "expected": {
            "intent": "success",
            "user_signal": "anxiety_about_child",
            "check_empathy_start": True
        }
    },
    {
        "name": "Эмоциональные проявления",
        "message": "Дочка постоянно плачет перед школой, у нее истерики",
        "expected": {
            "intent": "success",
            "user_signal": "anxiety_about_child",
            "check_empathy_start": True
        }
    },
    {
        "name": "Социальная изоляция",
        "message": "Сын одиночка, у него нет друзей, его не принимают",
        "expected": {
            "intent": "success",
            "user_signal": "anxiety_about_child",
            "check_empathy_start": True
        }
    },
    
    # === ФАЗА 3: Улучшенная дифференциация exploring_only ===
    {
        "name": "Пассивный интерес",
        "message": "Просто интересуюсь, что у вас за школа. Пока думаем",
        "expected": {
            "intent": "success",
            "user_signal": "exploring_only"
        }
    },
    {
        "name": "Информационный запрос",
        "message": "Пришлите информацию о ваших курсах на будущее",
        "expected": {
            "intent": "success",
            "user_signal": "exploring_only"
        }
    },
    {
        "name": "Временные маркеры",
        "message": "Еще не решили, рассматриваем варианты. Что у вас есть?",
        "expected": {
            "intent": "success",
            "user_signal": "exploring_only"
        }
    },
    
    # === Контрольные тесты ===
    {
        "name": "Price Sensitive остается",
        "message": "30 тысяч за курс?! Это развод какой-то!",
        "expected": {
            "intent": "success",
            "user_signal": "price_sensitive"
        }
    },
    {
        "name": "Ready to Buy остается",
        "message": "Мы согласны, запишите нас",
        "expected": {
            "intent": "success",
            "user_signal": "ready_to_buy"
        }
    }
]

async def run_test(test_case):
    """Запускает один тест"""
    try:
        request = ChatRequest(
            user_id=f"test_user_{test_case['name']}",
            message=test_case["message"]
        )
        
        response = await chat(request)
        
        # Проверяем результаты
        passed = True
        details = []
        
        # Проверка intent
        if response.intent != test_case["expected"]["intent"]:
            passed = False
            details.append(f"Intent: ожидался {test_case['expected']['intent']}, получен {response.intent}")
        
        # Проверка user_signal
        if "user_signal" in test_case["expected"]:
            if response.user_signal != test_case["expected"]["user_signal"]:
                passed = False
                details.append(f"Signal: ожидался {test_case['expected']['user_signal']}, получен {response.user_signal}")
        
        # Проверка social_context
        if "social_context" in test_case["expected"]:
            if response.social != test_case["expected"]["social_context"]:
                passed = False
                details.append(f"Social: ожидался {test_case['expected']['social_context']}, получен {response.social}")
        
        # Проверка прощания в ответе
        if test_case["expected"].get("check_farewell_in_response"):
            farewell_words = ["до свидания", "до встречи", "всего доброго", "удачи"]
            if not any(word in response.response.lower() for word in farewell_words):
                passed = False
                details.append("Прощание не найдено в конце ответа")
        
        # Проверка благодарности в начале
        if test_case["expected"].get("check_thanks_prefix"):
            thanks_words = ["рад", "пожалуйста"]
            if not any(response.response.lower().startswith(word) for word in thanks_words):
                passed = False
                details.append("Благодарность не найдена в начале ответа")
        
        # Проверка эмпатии для anxiety
        if test_case["expected"].get("check_empathy_start"):
            empathy_words = ["понима", "вижу", "тяжело", "сложн", "переживаете"]
            first_sentence = response.response.split('.')[0].lower()
            if not any(word in first_sentence for word in empathy_words):
                passed = False
                details.append("Эмпатия не найдена в первом предложении")
        
        return {
            "name": test_case["name"],
            "passed": passed,
            "details": details,
            "response": response.response[:100] + "..." if len(response.response) > 100 else response.response
        }
        
    except Exception as e:
        return {
            "name": test_case["name"],
            "passed": False,
            "details": [f"Ошибка: {str(e)}"],
            "response": ""
        }

async def main():
    """Запускает все тесты"""
    print(f"\n{BOLD}{'='*60}")
    print(f"🧪 ТЕСТИРОВАНИЕ ИСПРАВЛЕНИЙ СОЦИАЛКИ И STATE MACHINE")
    print(f"{'='*60}{RESET}\n")
    
    results = []
    for test_case in test_cases:
        print(f"▶️ Тест: {BLUE}{test_case['name']}{RESET}")
        print(f"  Сообщение: \"{test_case['message']}\"")
        
        result = await run_test(test_case)
        results.append(result)
        
        if result["passed"]:
            print(f"  {GREEN}✅ PASSED{RESET}")
        else:
            print(f"  {RED}❌ FAILED{RESET}")
            for detail in result["details"]:
                print(f"    • {detail}")
        
        if result["response"]:
            print(f"  Ответ: {result['response'][:80]}...")
        print()
    
    # Итоги
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{BOLD}{'='*60}")
    print(f"📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print(f"{'='*60}{RESET}\n")
    
    color = GREEN if percentage >= 80 else YELLOW if percentage >= 60 else RED
    print(f"{color}Пройдено: {passed}/{total} ({percentage:.1f}%){RESET}")
    
    # Группировка по фазам
    phase1 = results[:3]
    phase2 = results[3:6]
    phase3 = results[6:9]
    control = results[9:]
    
    print(f"\n📌 По фазам:")
    print(f"  Фаза 1 (Mixed социалка): {sum(1 for r in phase1 if r['passed'])}/{len(phase1)}")
    print(f"  Фаза 2 (Anxiety маркеры): {sum(1 for r in phase2 if r['passed'])}/{len(phase2)}")
    print(f"  Фаза 3 (Exploring дифференциация): {sum(1 for r in phase3 if r['passed'])}/{len(phase3)}")
    print(f"  Контрольные: {sum(1 for r in control if r['passed'])}/{len(control)}")
    
    # Сохранение результатов
    with open("test_results_social_priority.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в test_results_social_priority.json")
    
    return percentage >= 80

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)