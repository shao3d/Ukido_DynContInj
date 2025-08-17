#!/usr/bin/env python3
"""
Тест системы с сохранением истории между вопросами
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from interactive_test import test_pipeline

async def test_history_flow():
    """Тестирует последовательность вопросов с одним user_id"""
    
    user_id = "history_test_user"
    
    # Последовательность вопросов для проверки контекста
    questions = [
        "Привет! Расскажите про курсы",
        "Привет! А цены какие?",  # Второе приветствие - должно быть проигнорировано
        "А?",  # Ультра-краткий контекстуальный вопрос
        "Это дорого...",  # Реакция на цену
        "До свидания"
    ]
    
    print("\n🔬 ТЕСТИРОВАНИЕ С СОХРАНЕНИЕМ ИСТОРИИ")
    print("=" * 50)
    print(f"User ID: {user_id}")
    print("=" * 50)
    
    for i, question in enumerate(questions, 1):
        print(f"\n📝 Вопрос {i}/{len(questions)}: {question}")
        print("-" * 40)
        
        # Используем один и тот же user_id для всех вопросов
        await test_pipeline(question, user_id, show_details=False)
        
        # Небольшая пауза между вопросами
        await asyncio.sleep(1)
    
    print("\n✅ Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_history_flow())