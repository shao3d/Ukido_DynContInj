#!/usr/bin/env python3
"""Простой тест блокировки CTA"""

import httpx
import asyncio
import time

async def test():
    user_id = f"test_{int(time.time())}"
    url = "http://localhost:8000/chat"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Тест 1: Спрашиваем про цены (должен быть CTA)
        print("\n1. Спрашиваем про цены:")
        resp = await client.post(url, json={"user_id": user_id, "message": "Сколько стоит обучение?"})
        result = resp.json()
        has_cta = "скидк" in result["response"].lower() or "рассрочк" in result["response"].lower()
        print(f"   CTA найден: {'✅ ДА' if has_cta else '❌ НЕТ'}")
        print(f"   Ответ: {result['response'][:150]}...")
        
        # Тест 2: Сообщаем об оплате
        print("\n2. Сообщаем об оплате:")
        resp = await client.post(url, json={"user_id": user_id, "message": "Я только что оплатил курс"})
        result = resp.json()
        print(f"   Ответ: {result['response'][:150]}...")
        
        # Тест 3: Снова спрашиваем (НЕ должно быть CTA)
        print("\n3. Спрашиваем про курсы после оплаты:")
        resp = await client.post(url, json={"user_id": user_id, "message": "Какие есть курсы?"})
        result = resp.json()
        has_cta = "скидк" in result["response"].lower() or "ukido.ua" in result["response"].lower()
        print(f"   CTA найден: {'❌ ОШИБКА' if has_cta else '✅ НЕТ (правильно)'}")
        print(f"   Ответ: {result['response'][:150]}...")
        
        print("\n" + "="*50)
        print("ТЕСТ БЛОКИРОВКИ ПОСЛЕ ОПЛАТЫ:", "❌ ПРОВАЛЕН" if has_cta else "✅ ПРОЙДЕН")

if __name__ == "__main__":
    asyncio.run(test())