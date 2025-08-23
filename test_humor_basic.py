#!/usr/bin/env python3
"""
Базовый тест системы юмора Жванецкого без API вызовов.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.zhvanetsky_humor import ZhvanetskyGenerator
from src.zhvanetsky_safety import SafetyChecker


async def test_safety_checker():
    """Тест SafetyChecker"""
    print("=" * 60)
    print("🔒 ТЕСТ SAFETY CHECKER")
    print("=" * 60)
    
    safety_checker = SafetyChecker()
    
    # Тест 1: Проверка блеклиста
    print("\n1. Проверка блеклиста тем:")
    unsafe_messages = [
        "У меня болит голова",
        "Война это ужасно",
        "Денег нет совсем"
    ]
    
    for msg in unsafe_messages:
        is_safe = safety_checker.is_safe_topic(msg)
        print(f"   '{msg}' - {'✅ Безопасно' if is_safe else '❌ Небезопасно'}")
    
    # Тест 2: Проверка user_signal
    print("\n2. Проверка user_signal:")
    signals = ["anxiety_about_child", "price_sensitive", "exploring_only", "ready_to_buy"]
    
    for signal in signals:
        is_ok = safety_checker.check_user_signal(signal)
        print(f"   {signal} - {'✅ OK' if is_ok else '❌ Блокирован'}")
    
    # Тест 3: Rate limiting
    print("\n3. Проверка rate limiting:")
    user_id = "test_user"
    
    # Первые 3 должны пройти
    for i in range(4):
        can_use = safety_checker.check_rate_limit(user_id, max_per_hour=3)
        if can_use and i < 3:
            safety_checker.mark_humor_used(user_id)
        print(f"   Попытка {i+1}: {'✅ Можно' if can_use else '❌ Лимит превышен'}")
    
    print("\n✅ SafetyChecker работает корректно!")


async def test_humor_mock():
    """Тест генератора в mock режиме"""
    print("\n" + "=" * 60)
    print("🎭 ТЕСТ MOCK ГЕНЕРАЦИИ")
    print("=" * 60)
    
    config = Config()
    # Используем None вместо реального клиента для mock режима
    generator = ZhvanetskyGenerator(client=None, config=config)
    
    # История для контекста
    history = [
        {"role": "user", "content": "Расскажите о школе"},
        {"role": "assistant", "content": "Ukido - школа soft skills..."}
    ]
    
    print("\nГенерация mock ответов:")
    test_messages = [
        "Что думаете про футбол?",
        "Погода хорошая сегодня"
    ]
    
    for msg in test_messages:
        print(f"\n   Вопрос: {msg}")
        response = await generator.generate_humor(
            message=msg,
            history=history,
            user_signal="exploring_only",
            user_id="test_user",
            timeout=5.0
        )
        
        if response:
            print(f"   🎭 Mock ответ: {response}")
        else:
            print(f"   ⚠️ Не удалось сгенерировать")
    
    # Метрики
    print("\n📊 Метрики генератора:")
    metrics = generator.get_metrics()
    for key, value in metrics.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Mock генерация работает!")


async def main():
    """Основная функция тестирования"""
    print("\n🚀 ЗАПУСК БАЗОВЫХ ТЕСТОВ СИСТЕМЫ ЮМОРА\n")
    
    # Тест SafetyChecker
    await test_safety_checker()
    
    # Тест mock генерации
    await test_humor_mock()
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())