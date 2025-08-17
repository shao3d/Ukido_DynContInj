#!/usr/bin/env python3
"""
Тестирование новой архитектуры без Quick Regex
Проверяем все критические сценарии из документации
"""

import asyncio
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interactive_test import test_pipeline, Colors
from history_manager import HistoryManager
from social_state import SocialStateManager
from config import Config

# Глобальные экземпляры для сохранения состояния
GLOBAL_HISTORY = HistoryManager()
GLOBAL_SOCIAL_STATE = SocialStateManager()

async def test_scenario(name: str, user_id: str, messages: list, expected: str):
    """Тестирует один сценарий с последовательностью сообщений"""
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}📋 СЦЕНАРИЙ: {name}{Colors.ENDC}")
    print(f"🎯 Ожидается: {expected}")
    print(f"👤 User ID: {user_id}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
    
    for i, message in enumerate(messages, 1):
        print(f"\n{Colors.CYAN}━━━ Сообщение {i}/{len(messages)} ━━━{Colors.ENDC}")
        print(f"👤 ВОПРОС: {message}")
        
        # Запускаем через pipeline
        response = await test_pipeline(message, user_id, show_details=False)
        
        print(f"🤖 ОТВЕТ: {response[:200]}{'...' if len(response) > 200 else ''}")
        
        # Небольшая пауза между сообщениями
        await asyncio.sleep(0.5)
    
    print(f"\n{Colors.GREEN}✅ Сценарий завершен{Colors.ENDC}")
    return True

async def main():
    """Основная функция тестирования"""
    config = Config()
    
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("🚀 ТЕСТИРОВАНИЕ НОВОЙ АРХИТЕКТУРЫ БЕЗ QUICK REGEX")
    print("="*70)
    print(f"Конфигурация:")
    print(f"  Quick Regex: {'✅ ВКЛЮЧЕН ⚠️' if config.USE_QUICK_REGEX else '❌ ОТКЛЮЧЕН (правильно!)'}")
    print(f"  Логирование: {config.LOG_LEVEL}")
    print("="*70)
    print(f"{Colors.ENDC}")
    
    if config.USE_QUICK_REGEX:
        print(f"{Colors.YELLOW}⚠️ ВНИМАНИЕ: Quick Regex все еще включен!{Colors.ENDC}")
        print(f"{Colors.YELLOW}Установите USE_QUICK_REGEX = False в config.py{Colors.ENDC}")
        print(f"{Colors.YELLOW}для тестирования новой архитектуры{Colors.ENDC}\n")
    
    # Тестовые сценарии из документации
    test_scenarios = [
        {
            "name": "1. Чистое приветствие",
            "user_id": "test_clean_greeting",
            "messages": ["Привет!"],
            "expected": "Router обрабатывает социалку"
        },
        {
            "name": "2. Mixed: приветствие + вопрос",
            "user_id": "test_mixed_greeting",
            "messages": ["Привет! Есть курсы для детей 10 лет?"],
            "expected": "Полный ответ с приветствием и информацией о курсах"
        },
        {
            "name": "3. Повторное приветствие",
            "user_id": "test_repeated_greeting",
            "messages": [
                "Привет!",
                "Сколько стоит обучение?",
                "Привет!"
            ],
            "expected": "Распознавание повторного приветствия"
        },
        {
            "name": "4. Контекстуальный вопрос 'А?'",
            "user_id": "test_contextual",
            "messages": [
                "Расскажите про цены",
                "А?"
            ],
            "expected": "Продолжение темы про цены из контекста"
        },
        {
            "name": "5. Mixed: благодарность + вопрос",
            "user_id": "test_mixed_thanks",
            "messages": ["Спасибо! А есть скидки?"],
            "expected": "Ответ про скидки с благодарностью"
        },
        {
            "name": "6. Прощание после диалога",
            "user_id": "test_farewell",
            "messages": [
                "Какие есть курсы?",
                "До свидания!"
            ],
            "expected": "Корректное прощание без offtopic message"
        }
    ]
    
    # Запускаем тесты
    for scenario in test_scenarios:
        success = await test_scenario(
            scenario["name"],
            scenario["user_id"],
            scenario["messages"],
            scenario["expected"]
        )
        
        # Пауза между сценариями
        await asyncio.sleep(1)
    
    # Итоговый отчет
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}📊 ИТОГОВЫЙ ОТЧЕТ{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")
    
    print(f"\n{Colors.GREEN}✅ Что должно работать без Quick Regex:{Colors.ENDC}")
    print("1. Mixed запросы (приветствие + вопрос) - полная обработка")
    print("2. Повторные приветствия - правильное определение через Router")
    print("3. Контекстуальные вопросы - использование истории")
    print("4. Прощания - корректная обработка без лишних сообщений")
    print("5. История - сохраняется для ВСЕХ типов запросов")
    
    print(f"\n{Colors.YELLOW}⚠️ На что обратить внимание:{Colors.ENDC}")
    print("1. Скорость ответа на приветствия (2с вместо 0с)")
    print("2. Стоимость увеличилась на ~20% ($0.00003 за приветствие)")
    print("3. Router должен правильно передавать social_context")
    
    print(f"\n{Colors.CYAN}💡 Рекомендации:{Colors.ENDC}")
    print("1. Проверьте логи Router на предмет social_context")
    print("2. Убедитесь что user_id передается корректно")
    print("3. Проверьте SocialStateManager на отслеживание приветствий")
    
    print(f"\n{Colors.BOLD}Тестирование завершено!{Colors.ENDC}")

if __name__ == "__main__":
    asyncio.run(main())