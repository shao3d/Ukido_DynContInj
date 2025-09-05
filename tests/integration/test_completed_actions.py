#!/usr/bin/env python3
"""
Тестирование обработчика завершённых действий.
Проверяет корректное распознавание и обработку завершённых действий пользователей.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from completed_actions_handler import CompletedActionsHandler


def test_completed_actions():
    """Тестирует обработку завершённых действий"""
    
    # Тестовые кейсы
    test_cases = [
        # === ДОЛЖНЫ распознаваться как completed actions ===
        {
            "message": "Оплатила курс",
            "expected_status": "success",
            "expected_action": "payment",
            "description": "Оплата курса"
        },
        {
            "message": "Заполнил форму на сайте",
            "expected_status": "success",
            "expected_action": "form",
            "description": "Заполнение формы"
        },
        {
            "message": "Были на пробном занятии",
            "expected_status": "success",
            "expected_action": "trial",
            "description": "Посещение пробного"
        },
        {
            "message": "Записались на курс",
            "expected_status": "success",
            "expected_action": "registration",
            "description": "Регистрация на курс"
        },
        {
            "message": "Перевела деньги за обучение",
            "expected_status": "success",
            "expected_action": "payment",
            "description": "Перевод денег за обучение"
        },
        {
            "message": "Отправил документы",
            "expected_status": "success",
            "expected_action": "documents",
            "description": "Отправка документов"
        },
        
        # === НЕ должны распознаваться (остаются offtopic) ===
        {
            "message": "Оплатил за бензин",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Оплата НЕ связанная со школой"
        },
        {
            "message": "Как оплатить курс?",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Вопрос, а не действие"
        },
        {
            "message": "Вчера ходили в кино",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Действие не связанное со школой"
        },
        {
            "message": "Когда заполнить форму?",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Вопрос с вопросительным словом"
        },
        {
            "message": "Вчера ходили в зоопарк и там видели слона который ел бананы и было очень весело",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Слишком длинное сообщение"
        },
        {
            "message": "Хорошая погода сегодня",
            "expected_status": "offtopic",
            "expected_action": None,
            "description": "Нет паттернов действий"
        },
    ]
    
    # История с контекстом школы для проверки контекстного определения
    school_context_history = [
        {"role": "user", "content": "Сколько стоит курс?"},
        {"role": "assistant", "content": "Курс стоит 5000 грн в месяц. Есть скидки для новых учеников."},
        {"role": "user", "content": "Хорошо, спасибо"},
        {"role": "assistant", "content": "Пожалуйста! Если решите записаться, я помогу с оформлением."},
    ]
    
    handler = CompletedActionsHandler()
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ОБРАБОТЧИКА ЗАВЕРШЁННЫХ ДЕЙСТВИЙ")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for i, case in enumerate(test_cases, 1):
        # Создаём имитацию результата Router'а
        route_result = {"status": "offtopic", "message": "Стандартный offtopic ответ"}
        
        # Используем историю с контекстом школы для некоторых тестов
        history = school_context_history if "курс" in case["message"].lower() or "обучен" in case["message"].lower() else []
        
        # Вызываем обработчик
        result = handler.detect_completed_action(
            case["message"],
            route_result,
            history
        )
        
        # Проверяем результат
        status_match = result["status"] == case["expected_status"]
        action_match = True
        
        if case["expected_action"]:
            action_match = result.get("_action_detected") == case["expected_action"]
        
        test_passed = status_match and action_match
        
        # Выводим результат
        status_emoji = "✅" if test_passed else "❌"
        print(f"\n{status_emoji} Тест #{i}: {case['description']}")
        print(f"   Сообщение: '{case['message']}'")
        print(f"   Ожидалось: status={case['expected_status']}, action={case['expected_action']}")
        print(f"   Получено:  status={result['status']}, action={result.get('_action_detected')}")
        
        if test_passed:
            passed += 1
            if result.get("completed_action_response"):
                print(f"   Ответ: {result['completed_action_response'][:80]}...")
        else:
            failed += 1
            print(f"   ОШИБКА: Неверный результат!")
    
    # Дополнительный тест с историей
    print("\n" + "=" * 60)
    print("ТЕСТ КОНТЕКСТНОГО ОПРЕДЕЛЕНИЯ")
    print("=" * 60)
    
    # Тест где действие определяется только по контексту истории
    context_test = {
        "message": "Оплатил перевод",  # Неявное упоминание
        "with_context": True,
        "without_context": False
    }
    
    # Без контекста
    result_no_context = handler.detect_completed_action(
        context_test["message"],
        {"status": "offtopic"},
        []  # Пустая история
    )
    
    # С контекстом школы
    result_with_context = handler.detect_completed_action(
        context_test["message"],
        {"status": "offtopic"},
        school_context_history
    )
    
    print(f"\nСообщение: '{context_test['message']}'")
    print(f"Без контекста: status={result_no_context['status']} (ожидается offtopic)")
    print(f"С контекстом:  status={result_with_context['status']} (ожидается success)")
    
    if result_no_context['status'] == 'offtopic' and result_with_context['status'] == 'success':
        print("✅ Контекстное определение работает корректно!")
        passed += 1
    else:
        print("❌ Ошибка в контекстном определении!")
        failed += 1
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"📊 Успешность: {passed}/{passed + failed} ({100 * passed / (passed + failed):.1f}%)")
    
    if failed == 0:
        print("\n🎉 Все тесты пройдены успешно!")
    else:
        print(f"\n⚠️ Есть проваленные тесты. Требуется доработка.")
    
    return failed == 0


if __name__ == "__main__":
    success = test_completed_actions()
    exit(0 if success else 1)