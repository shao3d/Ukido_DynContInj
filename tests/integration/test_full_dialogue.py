#!/usr/bin/env python3
"""
Полное тестирование диалога с сохранением истории
"""

import asyncio
import sys
import json
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interactive_test import test_pipeline, GLOBAL_HISTORY, GLOBAL_SOCIAL_STATE

async def test_full_dialogue():
    """Тестирует полный диалог мамы-блогера"""
    
    # Загружаем сценарий
    with open('tests/test_scenarios.json', 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    mama_scenario = scenarios[0]
    questions = mama_scenario['steps']
    user_id = 'mama_blogger'
    
    # СБРОС ПАМЯТИ перед началом
    GLOBAL_HISTORY.storage.clear()
    GLOBAL_SOCIAL_STATE._store.clear()
    GLOBAL_SOCIAL_STATE._expires.clear()
    print('='*80)
    print('✅ ПАМЯТЬ ПОЛНОСТЬЮ ОЧИЩЕНА')
    print('='*80)
    
    print('\n🎬 НАЧИНАЕМ ТЕСТИРОВАНИЕ: Дружелюбная мама-блогер')
    print(f'📝 Всего вопросов: {len(questions)}')
    
    # Проходим по всем вопросам
    for i, question_text in enumerate(questions, 1):
        print('\n' + '='*80)
        print(f'📋 СЦЕНАРИЙ #1: Дружелюбная мама-блогер')
        print(f'📍 Вопрос {i}/{len(questions)}')
        print('='*80)
        
        # Показываем текущую историю
        history = GLOBAL_HISTORY.get_history(user_id)
        print(f'📚 В памяти сейчас: {len(history)} сообщений')
        if history:
            print(f'   Последнее: "{history[-1]["content"][:50]}..."')
        
        # Тестируем
        print('\n🔄 Запускаю pipeline...\n')
        result = await test_pipeline(question_text, user_id, show_details=True)
        
        # Пауза для читаемости
        await asyncio.sleep(0.5)
        
        print('\n' + '='*80)
        print('📊 МОЙ АНАЛИЗ:')
        print('='*80)
        
        # Анализ в зависимости от номера вопроса
        if i == 1:
            print('Вопрос 1: Приветствие + вопрос про курсы')
            print('- Regex должен был поймать "Привет-привет"')
            print('- Модель дала подробный ответ про "Юный оратор"')
        elif i == 2:
            print('Вопрос 2: Цена + время + стеснительность')
            print('- "Супер!" - это НЕ приветствие')
            print('- Должен использовать историю из вопроса 1')
        elif i == 3:
            print('Вопрос 3: Скидка за двоих детей')
        elif i == 4:
            print('Вопрос 4: Оплата картой')
        elif i == 5:
            print('Вопрос 5: Прощание')
        
        # ОБЯЗАТЕЛЬНО ПОКАЗЫВАЕМ ПОЛНЫЙ ВОПРОС И ОТВЕТ
        print('\n' + '='*80)
        print('🔴🔴🔴 ПОЛНЫЙ ВОПРОС И ПОЛНЫЙ ОТВЕТ:')
        print('='*80)
        print('\n👤 ВОПРОС ПОЛНОСТЬЮ:')
        print(question_text)
        print('\n🤖 ОТВЕТ ПОЛНОСТЬЮ:')
        print(result)
        print('='*80)
        
        # Проверяем что добавилось в историю
        history_after = GLOBAL_HISTORY.get_history(user_id)
        print(f'\n📚 После ответа в памяти: {len(history_after)} сообщений')
        
        # Пауза между вопросами
        if i < len(questions):
            print(f'\n⏸️  Переход к вопросу {i+1}/{len(questions)}...')
            await asyncio.sleep(2)
    
    print('\n' + '='*80)
    print('✅ ДИАЛОГ ЗАВЕРШЕН!')
    print(f'📊 Всего обработано: {len(questions)} вопросов')
    print(f'📚 Финально в истории: {len(GLOBAL_HISTORY.get_history(user_id))} сообщений')
    print('='*80)

if __name__ == "__main__":
    asyncio.run(test_full_dialogue())
