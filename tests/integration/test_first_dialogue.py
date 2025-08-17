#!/usr/bin/env python3
"""
Тестирование первого диалога - Забывчивая бабушка с повторами
"""

import asyncio
import json
import time
import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from main import router, response_generator, history, social_state
from src.main import ChatRequest

async def run_dialogue():
    """Запуск первого диалога из test_scenarios_stress.json"""
    
    # Загружаем сценарии
    with open('tests/test_scenarios_stress.json', 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    # Берем первый сценарий
    scenario = scenarios[0]
    print(f"📋 СЦЕНАРИЙ: {scenario['scenario_name']}")
    print(f"📝 Описание: {scenario['description']}")
    print(f"📊 Шагов: {len(scenario['steps'])}")
    print("\n" + "="*60 + "\n")
    
    user_id = "babushka_test"
    results = []
    
    # Очищаем историю и состояние
    if user_id in history.storage:
        history.storage[user_id] = []
    if user_id in social_state._store:
        del social_state._store[user_id]
    
    print("📝 ПОЛНЫЙ ДИАЛОГ:")
    print("-" * 60)
    
    for i, message in enumerate(scenario['steps'], 1):
        print(f"\n👤 Вопрос {i}: {message}")
        
        start_time = time.time()
        
        # Получаем историю
        history_messages = history.get_history(user_id)
        
        # Router
        try:
            route_result = await router.route(message, history_messages, user_id)
        except Exception as e:
            print(f"❌ Ошибка Router: {e}")
            route_result = {"status": "error", "message": str(e)}
        
        status = route_result.get("status", "offtopic")
        response_text = ""
        source = "unknown"
        
        # Обработка результата
        if status == "offtopic":
            # Проверяем социальный контекст
            if route_result.get("social_context"):
                response_text = route_result.get("message", "Не понял вопрос")
                source = "router_social"
            else:
                response_text = route_result.get("message", "Это выходит за рамки наших услуг")
                source = "router_offtopic"
        
        elif status == "need_simplification":
            response_text = route_result.get("message", "Пожалуйста, задайте вопросы по отдельности")
            source = "router_simplification"
        
        elif status == "success":
            # Генерация через Claude
            try:
                response_text = await response_generator.generate(
                    router_result=route_result,
                    history=history_messages
                )
                source = "claude"
            except Exception as e:
                print(f"❌ Ошибка Generator: {e}")
                response_text = "Извините, возникла ошибка при генерации ответа"
                source = "error"
        
        # Сохраняем в историю
        history.add_message(user_id, "user", message)
        history.add_message(user_id, "assistant", response_text)
        
        elapsed = time.time() - start_time
        
        # Выводим ответ
        print(f"🤖 Ответ: {response_text}")
        print(f"⏱️  Время: {elapsed:.2f}s | Источник: {source} | Статус: {status}")
        
        # Сохраняем результат
        results.append({
            "step": i,
            "question": message,
            "answer": response_text,
            "status": status,
            "source": source,
            "time": elapsed,
            "documents": route_result.get("documents", []),
            "decomposed_questions": route_result.get("decomposed_questions", []),
            "social_context": route_result.get("social_context"),
            "repeated_question": route_result.get("repeated_question", False)
        })
    
    # Итоговые метрики
    print("\n" + "="*60)
    print("📊 ИТОГОВЫЕ МЕТРИКИ:")
    print("-" * 60)
    
    total_time = sum(r["time"] for r in results)
    avg_time = total_time / len(results)
    success_count = sum(1 for r in results if r["status"] == "success")
    
    print(f"• Общее время: {total_time:.2f}s")
    print(f"• Среднее время ответа: {avg_time:.2f}s")
    print(f"• Успешность: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    # Источники ответов
    sources = {}
    for r in results:
        sources[r["source"]] = sources.get(r["source"], 0) + 1
    
    print("\n• Источники ответов:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {source}: {count} ({count/len(results)*100:.1f}%)")
    
    # Детальные метрики по шагам
    print("\n📊 ДЕТАЛЬНЫЕ МЕТРИКИ ПО ШАГАМ:")
    print("-" * 60)
    for r in results:
        print(f"Шаг {r['step']}: {r['status']} | Источник: {r['source']} | Время: {r['time']:.2f}s")
        if r['documents']:
            print(f"  Документы: {', '.join(r['documents'])}")
        if r['social_context']:
            print(f"  Социальный контекст: {r['social_context']}")
        if r['repeated_question']:
            print(f"  🔄 ПОВТОРНЫЙ ВОПРОС")
    
    return results

if __name__ == "__main__":
    results = asyncio.run(run_dialogue())