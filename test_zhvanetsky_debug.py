#!/usr/bin/env python3
"""
Детальная отладка системы юмора Жванецкого.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import Config
from src.zhvanetsky_humor import ZhvanetskyGenerator
from src.zhvanetsky_safety import SafetyChecker
from src.openrouter_client import OpenRouterClient


async def test_single_generation():
    """Тест одной генерации с детальной отладкой"""
    print("=" * 60)
    print("🎭 ДЕТАЛЬНАЯ ОТЛАДКА ГЕНЕРАЦИИ ЮМОРА")
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
    
    # Тестовое сообщение
    message = "Что думаете про футбол?"
    
    # История для контекста
    history = [
        {"role": "user", "content": "Расскажите о вашей школе"},
        {"role": "assistant", "content": "Ukido - это школа soft skills..."}
    ]
    
    print(f"\n📝 Тестовое сообщение: '{message}'")
    
    # Пробуем сгенерировать без проверок
    try:
        from src.zhvanetsky_safety import TopicClassifier
        from src.zhvanetsky_golden import get_mixed_examples, format_examples_for_prompt
        
        # Классифицируем тему
        topic = TopicClassifier.classify(message)
        print(f"📌 Классифицированная тема: {topic}")
        
        # Получаем примеры
        examples = get_mixed_examples(topic)
        print(f"📚 Получено примеров: {len(examples)}")
        for i, ex in enumerate(examples, 1):
            if isinstance(ex, dict):
                print(f"   {i}. {ex.get('example', 'No example')[:50]}...")
            else:
                print(f"   {i}. {str(ex)[:50]}...")
        
        # Формируем промпт
        formatted_examples = format_examples_for_prompt(examples)
        dialogue_context = generator._extract_dialogue_context(history)
        
        prompt = generator.HUMOR_PROMPT_TEMPLATE.format(
            dialogue_context=dialogue_context,
            message=message,
            examples=formatted_examples
        )
        
        print(f"\n📋 Промпт (первые 500 символов):")
        print(prompt[:500] + "...")
        
        # Вызываем Haiku напрямую
        print(f"\n🚀 Отправляем запрос к Claude Haiku...")
        response = await generator._call_claude_haiku(prompt)
        
        if response:
            print(f"\n✅ Получен ответ от Haiku:")
            print(f"   '{response}'")
            print(f"   Длина: {len(response)} символов")
            
            # Проверяем валидацию
            is_valid, error_reason = safety_checker.validate_humor_response(response)
            print(f"\n🔍 Валидация:")
            print(f"   Валидный: {'✅ Да' if is_valid else '❌ Нет'}")
            if not is_valid:
                print(f"   Причина: {error_reason}")
        else:
            print(f"\n❌ Ответ не получен от Haiku")
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Главная функция"""
    await test_single_generation()
    print("\n✨ Отладка завершена!")


if __name__ == "__main__":
    asyncio.run(main())