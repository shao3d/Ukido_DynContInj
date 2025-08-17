#!/usr/bin/env python3
"""
Тестирование сценария "Дружелюбная мама-блогер"
С сохранением контекста между вопросами
"""

import asyncio
import sys
import json
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interactive_test import test_pipeline, GLOBAL_HISTORY, GLOBAL_SOCIAL_STATE

async def test_mama_blogger_scenario():
    """Тестируем полный диалог мамы-блогера"""
    
    # Загружаем сценарий
    with open('tests/test_scenarios.json', 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    mama_scenario = scenarios[0]  # Первый сценарий - мама-блогер
    questions = mama_scenario['steps']
    
    user_id = 'mama_blogger'
    
    print("\n" + "="*80)
    print("🎬 НАЧИНАЕМ ТЕСТИРОВАНИЕ СЦЕНАРИЯ: Дружелюбная мама-блогер")
    print(f"📝 Всего вопросов: {len(questions)}")
    print("="*80)
    
    # Очищаем историю перед началом
    GLOBAL_HISTORY.storage.clear()
    GLOBAL_SOCIAL_STATE._store.clear()
    GLOBAL_SOCIAL_STATE._expires.clear()
    print("✅ Память очищена\n")
    
    # Проходим по всем вопросам
    for i, question in enumerate(questions, 1):
        print("\n" + "="*80)
        print(f"📍 ВОПРОС {i}/{len(questions)}")
        print("="*80)
        
        # Показываем текущую историю
        history = GLOBAL_HISTORY.get_history(user_id)
        print(f"📚 В истории {len(history)} сообщений")
        if history:
            print("Последнее сообщение:", history[-1]['content'][:100] + "...")
        
        print("\n" + "-"*80)
        print(f"👤 ВОПРОС: {question}")
        print("-"*80)
        
        # Тестируем
        response = await test_pipeline(question, user_id, show_details=True)
        
        print("\n" + "="*80)
        print(f"🔍 АНАЛИЗ ВОПРОСА {i}/{len(questions)}")
        print("="*80)
        print(f"👤 ВОПРОС: {question}")
        print(f"🤖 ОТВЕТ: {response}")
        print("="*80)
        
        # Небольшая пауза между вопросами
        if i < len(questions):
            await asyncio.sleep(1)
    
    print("\n" + "="*80)
    print("✅ СЦЕНАРИЙ ЗАВЕРШЕН!")
    print(f"📊 Итого обработано: {len(questions)} вопросов")
    print(f"📚 В истории: {len(GLOBAL_HISTORY.get_history(user_id))} сообщений")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_mama_blogger_scenario())