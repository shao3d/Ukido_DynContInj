#!/usr/bin/env python3
"""
Тестирование исправленной системы юмора Жванецкого.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.zhvanetsky_humor import ZhvanetskyGenerator
from src.zhvanetsky_safety import SafetyChecker
from src.openrouter_client import OpenRouterClient


async def test_humor_generation():
    """Тест генерации юмора"""
    print("=" * 60)
    print("🎭 ТЕСТ СИСТЕМЫ ЮМОРА ЖВАНЕЦКОГО")
    print("=" * 60)
    
    # Инициализация
    config = Config()
    
    # Создаём клиент OpenRouter
    client = OpenRouterClient(
        api_key=config.OPENROUTER_API_KEY,
        model="anthropic/claude-3.5-haiku",
        temperature=config.ZHVANETSKY_TEMPERATURE
    )
    
    # Создаём генератор и safety checker
    safety_checker = SafetyChecker()
    generator = ZhvanetskyGenerator(client=client, config=config)
    
    # Тестовые offtopic сообщения
    test_messages = [
        ("Что думаете про футбол?", "sport"),
        ("Погода сегодня хорошая", "weather"),
        ("ChatGPT лучше вас?", "tech"),
        ("Борщ или пицца?", "food"),
        ("В пробках застрял", "transport"),
        ("Как дела?", "general")
    ]
    
    # История для контекста
    history = [
        {"role": "user", "content": "Расскажите о вашей школе"},
        {"role": "assistant", "content": "Ukido - это школа soft skills..."},
        {"role": "user", "content": "Сколько стоит?"},
        {"role": "assistant", "content": "Стоимость курса 30000 грн..."}
    ]
    
    print("\n📝 Тестовые сообщения:\n")
    
    for message, expected_topic in test_messages:
        print(f"\n🔹 Сообщение: '{message}'")
        print(f"   Ожидаемая тема: {expected_topic}")
        
        # Проверяем, можно ли использовать юмор
        can_use, context = safety_checker.should_use_humor(
            message=message,
            user_signal="exploring_only",
            history=history,
            user_id="test_user",
            is_pure_social=False
        )
        
        print(f"   Можно использовать юмор: {'✅ Да' if can_use else '❌ Нет'}")
        
        if can_use:
            # Генерируем юмор
            try:
                response = await generator.generate_humor(
                    message=message,
                    history=history,
                    user_signal="exploring_only",
                    user_id="test_user",
                    timeout=5.0
                )
                
                if response:
                    print(f"   🎭 Ответ: {response}")
                else:
                    print(f"   ⚠️ Не удалось сгенерировать юмор")
            except Exception as e:
                print(f"   ❌ Ошибка: {e}")
    
    # Выводим метрики
    print("\n" + "=" * 60)
    print("📊 МЕТРИКИ ГЕНЕРАТОРА:")
    print("=" * 60)
    metrics = generator.get_metrics()
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    print("\n✅ Тест завершён!")


async def test_rate_limiting():
    """Тест rate limiting"""
    print("\n" + "=" * 60)
    print("🔒 ТЕСТ RATE LIMITING")
    print("=" * 60)
    
    safety_checker = SafetyChecker()
    user_id = "rate_limit_test"
    
    # Пытаемся использовать юмор несколько раз подряд
    for i in range(5):
        can_use, context = safety_checker.should_use_humor(
            message="Тестовое сообщение",
            user_signal="exploring_only",
            history=[],
            user_id=user_id,
            is_pure_social=False
        )
        
        if can_use:
            # Имитируем использование
            safety_checker.mark_humor_used(user_id)
            print(f"  Попытка {i+1}: ✅ Юмор использован")
        else:
            print(f"  Попытка {i+1}: ❌ Rate limit ({context.get('reason', 'unknown')})")
    
    print(f"\n  Активных пользователей в rate limiter: {len(safety_checker.humor_usage)}")


async def main():
    """Главная функция тестирования"""
    print("🚀 Запуск тестов исправленной системы юмора Жванецкого\n")
    
    # Тест генерации
    await test_humor_generation()
    
    # Тест rate limiting
    await test_rate_limiting()
    
    print("\n✨ Все тесты завершены!")


if __name__ == "__main__":
    asyncio.run(main())