#!/usr/bin/env python3
"""
Тест только проверки памяти - один сценарий с 8 шагами
Проверяет забывчивость системы после 10 сообщений (5 пар вопрос-ответ)
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем путь к src
sys.path.append(str(Path(__file__).parent.parent / "src"))

from main import app
import httpx


async def test_memory():
    """Тестируем только сценарий с проверкой памяти"""
    
    # Сценарий для теста
    scenario = {
        "scenario_name": "Длинный диалог с проверкой памяти",
        "description": "8 шагов для явной проверки забывчивости после 10 сообщений",
        "steps": [
            "Привет! У меня сын Максим, 9 лет. Какой курс ему подойдет лучше всего?",
            "Отлично! А сколько стоит месяц обучения на курсе Юный Оратор?",
            "Понятно. А какие конкретно навыки развивает этот курс?",
            "Какое расписание занятий? В какое время проводятся?",
            "А домашние задания много задают на курсе?",
            "Можно ли заниматься онлайн или только офлайн?",
            "Напомните пожалуйста - как зовут моего сына и сколько ему лет? Вы же помните из начала разговора?",
            "И еще раз - какую цену за месяц курса Юный Оратор вы называли в самом начале?"
        ]
    }
    
    print("\n" + "=" * 80)
    print("🧠 ТЕСТ ПАМЯТИ СИСТЕМЫ (обрезка после 10 сообщений)")
    print("=" * 80)
    print(f"📋 Сценарий: {scenario['scenario_name']}")
    print(f"📝 {scenario['description']}")
    print(f"📊 Шагов: {len(scenario['steps'])}")
    print("\n" + "-" * 80)
    
    # Уникальный user_id для теста
    user_id = f"memory_test_{datetime.now().timestamp()}"
    results = []
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        for idx, user_message in enumerate(scenario['steps'], 1):
            print(f"\n🔹 Шаг {idx}/8:")
            print(f"👤 User: {user_message[:60]}...")
            
            try:
                payload = {"user_id": user_id, "message": user_message}
                resp = await client.post("/chat", json=payload, timeout=60.0)
                
                if resp.status_code != 200:
                    print(f"❌ HTTP {resp.status_code}")
                    continue
                
                data = resp.json()
                response_text = data.get("response", "")
                
                print(f"🤖 Bot: {response_text[:100]}...")
                
                # Сохраняем результат
                results.append({
                    "step": idx,
                    "user_message": user_message,
                    "bot_response": response_text,
                    "intent": data.get("intent"),
                    "documents": data.get("relevant_documents", [])
                })
                
                # Анализ ключевых моментов
                if idx == 7:
                    print("\n⚠️ КРИТИЧЕСКИЙ МОМЕНТ - Шаг 7:")
                    print("   Спрашиваем имя и возраст из шага 1")
                    print("   После 12 сообщений (6 пар) история должна быть обрезана")
                    if "Максим" in response_text or "9 лет" in response_text:
                        print("   ✅ СИСТЕМА ПОМНИТ (история еще не обрезана)")
                    else:
                        print("   🔴 СИСТЕМА ЗАБЫЛА (история обрезана после 10 сообщений)")
                
                if idx == 8:
                    print("\n⚠️ КРИТИЧЕСКИЙ МОМЕНТ - Шаг 8:")
                    print("   Спрашиваем цену из шага 2")
                    print("   После 14 сообщений (7 пар) шаг 2 точно должен быть забыт")
                    if "6,000" in response_text or "6000" in response_text:
                        print("   ✅ СИСТЕМА ПОМНИТ (неожиданно!)")
                    else:
                        print("   🔴 СИСТЕМА ЗАБЫЛА (ожидаемое поведение)")
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            
            await asyncio.sleep(0.3)
    
    # Итоговый анализ
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ:")
    print("=" * 80)
    
    print("\n📝 История сообщений (для анализа):")
    for i, r in enumerate(results, 1):
        print(f"  Шаг {i}: {r['user_message'][:50]}...")
        
    print("\n🧮 Математика памяти:")
    print("  • Лимит истории: 10 сообщений (5 пар вопрос-ответ)")
    print("  • После шага 5: в истории 10 сообщений")
    print("  • После шага 6: в истории 12 сообщений → обрезка до 10")
    print("  • На шаге 7: шаг 1 должен быть забыт")
    print("  • На шаге 8: шаги 1-2 должны быть забыты")
    
    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    output_file = reports_dir / f"test_memory_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "scenario": scenario,
            "results": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в: {output_file.relative_to(Path.cwd())}")


if __name__ == "__main__":
    asyncio.run(test_memory())