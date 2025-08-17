#!/usr/bin/env python3
"""
Тест памяти v2 - проверяем, помнит ли система свои предыдущие ответы
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent / "src"))

from main import app
import httpx


async def test_memory():
    """Тестируем память через специфичные вопросы"""
    
    # Сценарий с уникальными деталями в ответах
    scenario = {
        "scenario_name": "Тест памяти с уникальными деталями",
        "description": "Проверяем, помнит ли система свои конкретные ответы",
        "steps": [
            "Привет! У меня есть необычный вопрос - можно ли записать на курс ребенка из другой страны?",
            "А какая у вас самая популярная программа?",  
            "Сколько детей в группе на курсе Юный Оратор?",
            "Какие документы выдаете после окончания?",
            "Есть ли у вас летние интенсивы?",
            "А пробное занятие платное или бесплатное?",
            "Вы в самом начале говорили про запись ребенка из другой страны. Что именно вы отвечали?",
            "И напомните, сколько детей в группе вы называли для Юного Оратора?"
        ]
    }
    
    print("\n" + "=" * 80)
    print("🧠 ТЕСТ ПАМЯТИ v2 - Проверка памяти конкретных ответов")
    print("=" * 80)
    print("\n📊 Математика:")
    print("  • Лимит истории: 10 сообщений")
    print("  • После шага 5: в истории 10 сообщений (5 пар)")
    print("  • После шага 6: история обрезается, шаг 1 забыт")
    print("  • Шаг 7: спрашиваем про ответ из шага 1")
    print("  • Шаг 8: спрашиваем про ответ из шага 3")
    print("\n" + "-" * 80)
    
    user_id = f"memory_v2_{datetime.now().timestamp()}"
    results = []
    
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        for idx, user_message in enumerate(scenario['steps'], 1):
            print(f"\n🔹 Шаг {idx}/8:")
            print(f"👤 User: {user_message}")
            
            try:
                payload = {"user_id": user_id, "message": user_message}
                resp = await client.post("/chat", json=payload, timeout=60.0)
                
                if resp.status_code != 200:
                    print(f"❌ HTTP {resp.status_code}")
                    continue
                
                data = resp.json()
                response_text = data.get("response", "")
                
                print(f"🤖 Bot: {response_text[:150]}...")
                
                results.append({
                    "step": idx,
                    "user_message": user_message,
                    "bot_response": response_text,
                    "intent": data.get("intent"),
                    "documents": data.get("relevant_documents", [])
                })
                
                # Анализ критических моментов
                if idx == 1:
                    print("   💡 Запоминаем ответ про другую страну")
                
                if idx == 3:
                    print("   💡 Запоминаем количество детей в группе")
                    
                if idx == 7:
                    print("\n⚠️ КРИТИЧЕСКИЙ ТЕСТ - Шаг 7:")
                    print("   Спрашиваем про ответ из шага 1 (должен быть забыт)")
                    # Проверяем, есть ли конкретика из первого ответа
                    first_response = results[0]["bot_response"] if results else ""
                    if any(phrase in response_text.lower() for phrase in ["польш", "онлайн", "zoom"]):
                        print("   ✅ СИСТЕМА ПОМНИТ детали из шага 1")
                    else:
                        print("   🔴 СИСТЕМА НЕ ПОМНИТ детали из шага 1")
                        print("   📄 Использует документы:", data.get("relevant_documents", []))
                
                if idx == 8:
                    print("\n⚠️ КРИТИЧЕСКИЙ ТЕСТ - Шаг 8:")
                    print("   Спрашиваем про ответ из шага 3 (может помнить)")
                    if "8" in response_text or "восем" in response_text.lower():
                        print("   ✅ СИСТЕМА ПОМНИТ или заново отвечает правильно")
                    else:
                        print("   🔴 СИСТЕМА НЕ ПОМНИТ количество из шага 3")
                        print("   📄 Использует документы:", data.get("relevant_documents", []))
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
            
            await asyncio.sleep(0.3)
    
    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    output_file = reports_dir / f"test_memory_v2_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "scenario": scenario,
            "results": results,
            "analysis": {
                "history_limit": 10,
                "expected_forgotten_after": "step 6",
                "step_7_asks_about": "step 1 response",
                "step_8_asks_about": "step 3 response"
            }
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты: {output_file.relative_to(Path.cwd())}")
    
    # Финальный анализ
    print("\n" + "=" * 80)
    print("📊 ВЫВОДЫ:")
    print("=" * 80)
    print("\n🔍 Важное наблюдение:")
    print("  Если система отвечает правильно на шагах 7-8, это может быть:")
    print("  1) Она ПОМНИТ из истории (неожиданно)")
    print("  2) Она ЗАНОВО отвечает, используя документы (ожидаемо)")
    print("\n  Смотрите на использованные документы!")
    print("  Если documents=[] - значит помнит из истории")
    print("  Если documents=['...'] - значит отвечает заново")


if __name__ == "__main__":
    asyncio.run(test_memory())