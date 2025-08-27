#!/usr/bin/env python3
"""
Интеграционный тест системы юмора без запуска сервера.
"""

import asyncio
import sys
import os

# Добавляем пути для импортов
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'src'))

from config import Config
from router import Router
from history_manager import HistoryManager
from zhvanetsky_humor import ZhvanetskyGenerator
from zhvanetsky_safety import SafetyChecker
from openrouter_client import OpenRouterClient


async def test_integration():
    """Тест интеграции системы юмора"""
    print("=" * 60)
    print("🎭 ИНТЕГРАЦИОННЫЙ ТЕСТ СИСТЕМЫ ЮМОРА")
    print("=" * 60)
    
    # Инициализация компонентов
    config = Config()
    router = Router(use_cache=True)
    history = HistoryManager()
    
    # Инициализация системы юмора
    print("\n📦 Инициализация системы юмора...")
    
    # Создаём глобальный safety checker
    safety_checker = SafetyChecker()
    
    # Создаём клиент (None для mock режима)
    zhvanetsky_client = None  # Для тестирования без API
    
    # Создаём генератор
    generator = ZhvanetskyGenerator(
        client=zhvanetsky_client,
        config=config
    )
    
    print("✅ Система инициализирована в mock режиме")
    
    # Тестовые сценарии
    test_cases = [
        {
            "user_id": "test_user_1",
            "message": "Привет, расскажите о школе",
            "expected": "business"
        },
        {
            "user_id": "test_user_2",
            "message": "Что думаете про футбол?",
            "expected": "offtopic"
        },
        {
            "user_id": "test_user_3",
            "message": "У меня болит голова",
            "expected": "offtopic (unsafe)"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Тест {i}: {test['expected']} ---")
        print(f"👤 User: {test['message']}")
        
        # Получаем историю
        history_messages = history.get_history(test['user_id'])
        
        # Роутинг
        try:
            route_result = await router.route(
                user_message=test['message'],
                history=history_messages,
                user_id=test['user_id']
            )
            
            status = route_result.get('status', 'unknown')
            user_signal = route_result.get('user_signal', 'exploring_only')
            
            print(f"📊 Status: {status}")
            print(f"📊 Signal: {user_signal}")
            
            # Если offtopic, проверяем юмор
            if status == 'offtopic':
                # Проверяем, можно ли использовать юмор
                can_use, context = safety_checker.should_use_humor(
                    message=test['message'],
                    user_signal=user_signal,
                    history=history_messages,
                    user_id=test['user_id'],
                    is_pure_social=False
                )
                
                print(f"🎭 Юмор разрешён: {'✅ Да' if can_use else '❌ Нет'}")
                if not can_use:
                    print(f"   Причина: {context.get('reason', 'unknown')}")
                
                if can_use:
                    # Генерируем юмор
                    humor = await generator.generate_humor(
                        message=test['message'],
                        history=history_messages,
                        user_signal=user_signal,
                        user_id=test['user_id'],
                        timeout=3.0
                    )
                    
                    if humor:
                        # Отмечаем использование
                        safety_checker.mark_humor_used(test['user_id'])
                        print(f"🎭 Ответ: {humor}")
                    else:
                        print("⚠️ Не удалось сгенерировать юмор")
                        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Финальные метрики
    print("\n" + "=" * 60)
    print("📊 МЕТРИКИ СИСТЕМЫ:")
    print("=" * 60)
    
    metrics = generator.get_metrics()
    print(f"Всего попыток: {metrics['total_generated']}")
    print(f"Успешных: {metrics['successful_generated']}")
    print(f"Success rate: {metrics['success_rate']:.1%}")
    print(f"Среднее время: {metrics['average_generation_time']:.3f}s")
    
    print("\n✅ Интеграционный тест завершён!")


if __name__ == "__main__":
    asyncio.run(test_integration())