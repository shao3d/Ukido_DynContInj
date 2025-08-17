#!/usr/bin/env python3
"""
Быстрый тест для проверки обработки вопросов о лицензии
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from main import app
from fastapi.testclient import TestClient
import httpx

async def test_license_question():
    """Тестируем вопрос о лицензии"""
    print("\n" + "="*60)
    print("🧪 ТЕСТ: Вопрос о лицензии")
    print("="*60)
    
    # Создаем async client
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # Тестовые вопросы о лицензии
        test_cases = [
            "Покажите лицензию на образовательную деятельность!",
            "Есть ли у вас лицензия?",
            "Какие документы подтверждают право на обучение?"
        ]
        
        for i, question in enumerate(test_cases, 1):
            print(f"\n📝 Тест {i}: {question}")
            
            response = await client.post(
                "/chat",
                json={"user_id": "test_user", "message": question}
            )
            
            data = response.json()
            
            # Проверяем статус
            intent = data.get("intent", "unknown")
            print(f"   Статус: {intent}")
            
            # Проверяем ответ
            response_text = data.get("response", "")
            print(f"   Ответ: {response_text[:200]}...")
            
            # Проверяем документы
            documents = data.get("relevant_documents", [])
            print(f"   Документы: {documents}")
            
            # Оценка результата
            if intent == "success" and "safety_and_trust.md" in documents:
                print("   ✅ УСПЕХ: Правильная обработка")
            elif intent == "offtopic":
                print("   ❌ ОШИБКА: Классифицировано как offtopic")
            else:
                print(f"   ⚠️ ПРЕДУПРЕЖДЕНИЕ: Неожиданный результат")
            
            print("-" * 40)

if __name__ == "__main__":
    print("\n🚀 Запуск теста обработки вопросов о лицензии...")
    asyncio.run(test_license_question())
    print("\n✅ Тест завершен!")