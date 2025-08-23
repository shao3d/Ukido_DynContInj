#!/usr/bin/env python3
"""
Запуск тестовых сценариев для проверки системы юмора Жванецкого
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Добавляем пути для импортов
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox_v2 import SandboxV2

async def run_humor_test(scenario_num: int):
    """Запускает один сценарий из test_zhvanetsky_humor.json"""
    
    # Загружаем тесты
    test_file = "tests/test_zhvanetsky_humor.json"
    with open(test_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scenarios = data['scenarios']
    
    if scenario_num < 1 or scenario_num > len(scenarios):
        print(f"❌ Сценарий {scenario_num} не найден. Доступно: 1-{len(scenarios)}")
        return
    
    scenario = scenarios[scenario_num - 1]
    sandbox = SandboxV2()
    
    print("=" * 80)
    print(f"🎭 ТЕСТ ЮМОРА #{scenario_num}: {scenario['persona']}")
    print("=" * 80)
    print(f"📝 {scenario['description']}")
    print()
    
    user_id = f"humor_test_{scenario_num}"
    
    # Прогоняем все сообщения
    for i, msg_data in enumerate(scenario['messages'], 1):
        message = msg_data['user']
        print(f"👤 Сообщение {i}: {message}")
        
        result = await sandbox.process_message(user_id, message)
        
        # Показываем результат
        print(f"📊 Status: {result.router_status}")
        print(f"📊 Signal: {result.user_signal if result.user_signal else 'N/A'}")
        
        # Проверяем, был ли использован юмор
        response = result.response
        
        # Простая эвристика для определения юмора
        humor_markers = [
            "развивает тело", "развиваем личность",  # спорт
            "дождь", "танцевать под ним",  # погода
            "ИИ", "хаотичность в интеллект",  # технологии
            "смешали и вкусно", "детский коллектив",  # еда
            "пробках", "движется вперёд",  # транспорт
            "инструкция", "вырастить"  # общее
        ]
        
        has_humor = any(marker in response for marker in humor_markers)
        
        if result.router_status == 'offtopic':
            if has_humor:
                print(f"🎭 Юмор: ✅ ИСПОЛЬЗОВАН")
            else:
                print(f"🎭 Юмор: ❌ НЕ использован (стандартный offtopic)")
        
        print(f"🤖 Ответ: {response[:200]}{'...' if len(response) > 200 else ''}")
        print("-" * 40)
    
    print()

async def main():
    """Запускает все тесты юмора"""
    print("\n🚀 ЗАПУСК ТЕСТОВ СИСТЕМЫ ЮМОРА ЖВАНЕЦКОГО\n")
    
    # Определяем какие тесты запускать
    if len(sys.argv) > 1:
        # Запускаем конкретный сценарий
        scenario_num = int(sys.argv[1])
        await run_humor_test(scenario_num)
    else:
        # Запускаем несколько ключевых тестов
        key_tests = [
            1,  # Спорт - должен сработать юмор
            2,  # Погода - должен сработать юмор
            5,  # Здоровье - НЕ должен сработать (блеклист)
            7,  # Anxiety - НЕ должен сработать (блокировка по сигналу)
            8,  # Price sensitive - НЕ должен сработать (блокировка по сигналу)
        ]
        
        for num in key_tests:
            await run_humor_test(num)
            print("\n" + "="*80 + "\n")
    
    print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")

if __name__ == "__main__":
    asyncio.run(main())