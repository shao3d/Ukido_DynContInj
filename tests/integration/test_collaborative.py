#!/usr/bin/env python3
"""
Collaborative тестирование с полным выводом Q&A
"""

import asyncio
import sys
import json
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interactive_test import test_pipeline, GLOBAL_HISTORY, GLOBAL_SOCIAL_STATE

async def test_question(question_text, question_num, total_questions, user_id='mama_blogger'):
    """Тестирует один вопрос с полным выводом"""
    
    print('\n' + '='*80)
    print(f'📋 СЦЕНАРИЙ #1: Дружелюбная мама-блогер')
    print(f'📍 Вопрос {question_num}/{total_questions}')
    print('='*80)
    
    # Показываем текущую историю
    history = GLOBAL_HISTORY.get_history(user_id)
    print(f'📚 В памяти {len(history)} сообщений')
    
    # Тестируем
    result = await test_pipeline(question_text, user_id, show_details=True)
    
    # СНАЧАЛА показываем ПОЛНЫЙ вопрос и ответ
    print('\n' + '='*80)
    print('🔴 ПОЛНЫЙ ВОПРОС И ОТВЕТ:')
    print('='*80)
    print('\n👤 ВОПРОС:')
    print(question_text)
    print('\n🤖 ОТВЕТ:')
    print(result)
    print('='*80)
    
    return result

# Для запуска отдельных вопросов
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        question_num = int(sys.argv[1])
        
        # Загружаем сценарий
        with open('tests/test_scenarios.json', 'r', encoding='utf-8') as f:
            scenarios = json.load(f)
        
        mama_scenario = scenarios[0]
        questions = mama_scenario['steps']
        
        if question_num == 1:
            # Сброс памяти перед первым вопросом
            GLOBAL_HISTORY.storage.clear()
            GLOBAL_SOCIAL_STATE._store.clear()
            GLOBAL_SOCIAL_STATE._expires.clear()
            print('✅ ПАМЯТЬ ОЧИЩЕНА')
        
        asyncio.run(test_question(questions[question_num-1], question_num, len(questions)))
    else:
        print("Usage: python test_collaborative.py <question_number>")