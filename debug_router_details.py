#!/usr/bin/env python3
"""
Детальный анализ обработки сообщения через Router
Показывает внутреннее состояние на каждом этапе
"""

import json
import requests
from typing import Dict, Any
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.router import Router
from src.response_generator import ResponseGenerator
from src.config import Config
import asyncio

async def analyze_message(message: str, user_id: str = "debug_test"):
    """Детальный анализ обработки сообщения"""
    
    print("="*80)
    print(f"📝 АНАЛИЗ СООБЩЕНИЯ: {message}")
    print("="*80)
    
    # Инициализация компонентов
    config = Config()
    router = Router(config)
    generator = ResponseGenerator(config)
    
    # ЭТАП 1: Router обработка
    print("\n🔹 ЭТАП 1: ROUTER (Gemini)")
    print("-"*40)
    
    router_result = await router.process_message(
        message=message,
        user_id=user_id,
        history=[]
    )
    
    print(f"📊 Результат Router:")
    print(f"  Status: {router_result.get('status')}")
    print(f"  User Signal: {router_result.get('user_signal')}")
    print(f"  Social Context: {router_result.get('social_context')}")
    print(f"\n  📝 Decomposed Questions: {json.dumps(router_result.get('decomposed_questions', []), ensure_ascii=False, indent=4)}")
    print(f"\n  📚 Selected Documents: {[doc.get('title', 'Unknown') for doc in router_result.get('documents', [])]}")
    
    # Показать raw промпт для Gemini (частично)
    if hasattr(router, '_build_prompt'):
        prompt = router._build_prompt(message, user_id, [])
        print(f"\n  🔍 Prompt для Gemini (первые 500 символов):")
        print(f"  {prompt[:500]}...")
    
    # ЭТАП 2: Решение Main Orchestrator
    print("\n🔹 ЭТАП 2: MAIN ORCHESTRATOR DECISION")
    print("-"*40)
    
    status = router_result.get('status', 'unknown')
    if status == 'offtopic':
        print("  ➡️ Направление: Standard Responses или Humor")
        print("  ❌ Claude НЕ будет вызван")
        print("  📄 Будет использован стандартный ответ из списка")
        
    elif status == 'success':
        print("  ➡️ Направление: Response Generator (Claude)")
        
        # ЭТАП 3: Generator обработка
        print("\n🔹 ЭТАП 3: RESPONSE GENERATOR (Claude)")
        print("-"*40)
        
        # Что отправляется в Claude
        print(f"  📤 Данные для Claude:")
        print(f"    - Questions: {router_result.get('decomposed_questions', [])}")
        print(f"    - Documents: {len(router_result.get('documents', []))} документов")
        print(f"    - User Signal: {router_result.get('user_signal')}")
        
        # Показать промпт для Claude (частично)
        if router_result.get('documents'):
            # Симуляция построения промпта
            print(f"\n  🔍 System Prompt для Claude включает:")
            print(f"    - Роль: AI помощник школы Ukido")
            print(f"    - Тон: адаптирован под {router_result.get('user_signal')}")
            print(f"    - Документы: {', '.join([d.get('title', '') for d in router_result.get('documents', [])])}")
            print(f"    - Вопросы для ответа: {router_result.get('decomposed_questions', [])}")
            
    elif status == 'need_simplification':
        print("  ➡️ Направление: Упрощение (слишком много вопросов)")
        
    print("\n" + "="*80)

async def test_multiple_variants():
    """Тестирует разные варианты формулировки"""
    test_cases = [
        "Расскажите о вашей школе",
        "Добрый день! Расскажите о вашей школе", 
        "Привет! Что за школа у вас?",
        "Здравствуйте! Хочу узнать о школе Ukido",
        "Чем занимается ваша школа?",
        "Расскажите подробно о школе"
    ]
    
    print("\n🔬 СРАВНИТЕЛЬНЫЙ АНАЛИЗ ВАРИАНТОВ")
    print("="*80)
    
    results = []
    for message in test_cases:
        print(f"\n📌 Тестируем: {message}")
        
        # Быстрый вызов через API
        response = requests.post(
            "http://localhost:8000/chat",
            json={"user_id": f"test_{len(results)}", "message": message},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            meta = data.get('metadata', {})
            results.append({
                'message': message,
                'status': meta.get('intent', 'unknown'),
                'questions': meta.get('decomposed_questions', []),
                'signal': meta.get('user_signal', 'unknown')
            })
            print(f"  ✅ Status: {meta.get('intent')} | Questions: {len(meta.get('decomposed_questions', []))}")
        else:
            print(f"  ❌ Ошибка: {response.status_code}")
    
    # Сводная таблица
    print("\n📊 СВОДНАЯ ТАБЛИЦА:")
    print("-"*80)
    print(f"{'Сообщение':<50} | {'Status':<15} | {'Questions':<10} | {'Signal':<15}")
    print("-"*80)
    for r in results:
        msg = r['message'][:47] + "..." if len(r['message']) > 50 else r['message']
        print(f"{msg:<50} | {r['status']:<15} | {len(r['questions']):<10} | {r['signal']:<15}")

if __name__ == "__main__":
    # Основной анализ
    asyncio.run(analyze_message("Добрый день! Расскажите о вашей школе"))
    
    # Дополнительный сравнительный анализ
    print("\n" + "="*80)
    print("Нажмите Enter для сравнительного анализа вариантов...")
    input()
    asyncio.run(test_multiple_variants())