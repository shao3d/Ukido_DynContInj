#!/usr/bin/env python3
"""Тест для проверки исправлений ROI и rate limiting."""

import requests
import json
import time

def test_fixes():
    """Тестируем исправления."""
    
    url = "http://localhost:8000/chat"
    user_id = f"test_fixes_{int(time.time())}"
    
    print("=" * 60)
    print("🧪 ТЕСТ ИСПРАВЛЕНИЙ")
    print("=" * 60)
    
    # Тест 1: Проверка фразы про ROI
    print("\n📝 Тест 1: Проверка исправления фразы про ROI")
    print("-" * 40)
    
    data = {
        "user_id": user_id,
        "message": "Это всё развод на деньги! Докажите что это не так!"
    }
    
    response = requests.post(url, json=data, timeout=15)
    if response.status_code == 200:
        result = response.json()
        bot_response = result.get('response', '')
        
        # Проверяем старую и новую фразы
        if "4,3 гривны" in bot_response or "4.3 гривны" in bot_response:
            print("❌ ОШИБКА: Найдена старая фраза про 4.3 гривны!")
        elif "окупаются более чем в 4 раза" in bot_response or "окупаются в 4 раза" in bot_response:
            print("✅ УСПЕХ: Используется новая естественная фраза про окупаемость!")
        else:
            print("⚠️  ROI не упоминается в ответе (может быть нормально)")
        
        print(f"\nОтвет бота (первые 200 символов):")
        print(bot_response[:200] + "...")
    
    # Тест 2: Проверка rate limiting для CTA
    print("\n\n📝 Тест 2: Проверка rate limiting для CTA (price_sensitive)")
    print("-" * 40)
    
    messages = [
        "7000 грн? Это слишком дорого!",
        "За эти деньги я найму репетитора!",
        "У вас есть скидки хоть какие-то?",
        "А если двоих детей записать?"
    ]
    
    cta_count = 0
    for i, msg in enumerate(messages, 1):
        print(f"\n[{i}/4] Отправляю: {msg}")
        
        data = {
            "user_id": user_id,
            "message": msg
        }
        
        response = requests.post(url, json=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            bot_response = result.get('response', '')
            signal = result.get('user_signal', '')
            
            # Проверяем наличие CTA про скидки
            cta_phrases = ["Кстати, у нас действуют скидки", "скидка", "рассрочка", "10% при полной оплате"]
            has_cta = any(phrase in bot_response for phrase in cta_phrases)
            
            if has_cta:
                cta_count += 1
                print(f"  📢 CTA обнаружен! (всего: {cta_count})")
            else:
                print(f"  ✅ CTA не добавлен (правильно)")
            
            print(f"  Signal: {signal}")
        
        time.sleep(0.5)
    
    print("\n" + "=" * 40)
    print(f"📊 РЕЗУЛЬТАТЫ:")
    print(f"  CTA появился {cta_count} раз(а) из 4 сообщений")
    
    if cta_count <= 2:
        print("  ✅ Rate limiting работает! (не более 2 раз)")
    else:
        print(f"  ❌ Rate limiting НЕ работает! ({cta_count} > 2)")
    
    print("=" * 60)

if __name__ == "__main__":
    # Ждём запуска сервера
    time.sleep(2)
    test_fixes()