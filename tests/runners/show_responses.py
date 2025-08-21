#!/usr/bin/env python3
"""
Скрипт для просмотра полных ответов системы на тестовые запросы
"""

import asyncio
import httpx
import json
from datetime import datetime

TEST_QUERIES = [
    {
        "category": "Ready to buy (неявные)",
        "queries": [
            "Спасибо. Мы согласны.",
            "Спасибо. Действуем.",
            "Благодарю! Регистрируйте меня"
        ]
    },
    {
        "category": "State Machine сигналы",
        "queries": [
            "Сколько стоит? Дорого наверное?",
            "Мой ребенок очень стеснительный",
            "Хочу записать ребенка на курс"
        ]
    },
    {
        "category": "Социальные",
        "queries": [
            "Спасибо!",
            "Привет! Сколько стоит курс?"
        ]
    }
]

async def get_response(message: str, user_id: str = "test_user") -> dict:
    """Получает ответ от системы"""
    url = "http://localhost:8000/chat"
    payload = {"message": message, "user_id": user_id}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

async def main():
    print("=" * 80)
    print("📋 ПОЛНЫЕ ВОПРОСЫ И ОТВЕТЫ СИСТЕМЫ")
    print("=" * 80)
    
    results = []
    
    for category_data in TEST_QUERIES:
        category = category_data["category"]
        print(f"\n{'='*60}")
        print(f"📂 {category}")
        print("="*60)
        
        for i, query in enumerate(category_data["queries"], 1):
            print(f"\n{i}. 💬 Вопрос: '{query}'")
            print("-" * 40)
            
            response = await get_response(query, f"user_{category}_{i}")
            
            if "error" in response:
                print(f"❌ Ошибка: {response['error']}")
                continue
            
            # Показываем все поля ответа
            print(f"📊 Статус: {response.get('intent', 'unknown')}")
            print(f"🎯 User Signal: {response.get('user_signal', 'unknown')}")
            print(f"👋 Social Context: {response.get('social', 'None')}")
            
            # Декомпозированные вопросы
            decomposed = response.get('decomposed_questions', [])
            if decomposed:
                print(f"🔍 Декомпозированные вопросы:")
                for q in decomposed:
                    print(f"   - {q}")
            
            # Полный ответ
            print(f"\n💡 ПОЛНЫЙ ОТВЕТ:")
            print("-" * 40)
            full_response = response.get('response', '')
            print(full_response)
            print("-" * 40)
            
            # Сохраняем для анализа
            results.append({
                "category": category,
                "query": query,
                "status": response.get('intent'),
                "signal": response.get('user_signal'),
                "social": response.get('social'),
                "decomposed": decomposed,
                "response": full_response
            })
    
    # Сохраняем в файл
    filename = f"full_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Полные результаты сохранены в {filename}")

if __name__ == "__main__":
    print("🚀 Запрос полных ответов от системы...")
    print("⚠️ Убедитесь, что сервер запущен: python src/main.py")
    asyncio.run(main())