#!/usr/bin/env python3
"""
Отладка социальных интентов
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from router import Router
from social_intents import detect_social_intent

async def test_social():
    """Тестирует определение социальных интентов"""
    
    router = Router()
    
    test_messages = [
        "Добрый день",
        "Привет",
        "Спасибо",
        "Ок спс",
        "Благодарю",
        "До свидания"
    ]
    
    print("=" * 60)
    print("ТЕСТ ОПРЕДЕЛЕНИЯ СОЦИАЛЬНЫХ ИНТЕНТОВ")
    print("=" * 60)
    
    for msg in test_messages:
        print(f"\n📝 Сообщение: '{msg}'")
        
        # 1. Проверяем detect_social_intent
        social = detect_social_intent(msg)
        print(f"   detect_social_intent: {social.intent.value if social.intent else 'None'}")
        
        # 2. Проверяем что возвращает Router
        result = await router.route(msg, [], "test_user")
        print(f"   Router status: {result.get('status')}")
        print(f"   Router social_context: {result.get('social_context')}")
        print(f"   Router message: {result.get('message', '')[:50]}...")
        
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test_social())