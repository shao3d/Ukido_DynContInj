#!/usr/bin/env python3
"""
Тест для проверки 4-го сообщения из диалога 7
После исправления имени методиста в документах
"""

import requests
import json
import time

def test_single_message():
    """Тестируем вопрос про супервизии"""
    
    server_url = "http://localhost:8000"
    user_id = f"test_message4_{int(time.time())}"
    
    # Сначала создаём контекст диалога (первые 3 сообщения)
    messages = [
        "Здравствуйте, коллеги! Я сама педагог, ищу дополнительное развитие для сына",
        "Какие конкретно методики используете? Монтессори, Вальдорф, или своя разработка?",
        "Как вы работаете с разными типами темперамента? Холерики vs меланхолики?"
    ]
    
    print("🔄 Создаём контекст диалога (первые 3 сообщения)...")
    for i, msg in enumerate(messages, 1):
        print(f"\n[{i}/3] Отправляем: {msg[:50]}...")
        response = requests.post(
            f"{server_url}/chat",
            json={"user_id": user_id, "message": msg},
            timeout=30
        )
        if response.status_code == 200:
            print(f"✅ Ответ получен")
        else:
            print(f"❌ Ошибка: {response.status_code}")
        time.sleep(1)  # Небольшая пауза между сообщениями
    
    # Теперь отправляем тестовое 4-е сообщение
    test_message = "Интересно! А есть ли у вас супервизии для преподавателей? Обмен опытом?"
    
    print("\n" + "="*60)
    print("📝 ТЕСТОВОЕ СООБЩЕНИЕ №4")
    print("="*60)
    print(f"USER: {test_message}")
    print("-"*60)
    
    # Отправляем запрос
    start_time = time.time()
    response = requests.post(
        f"{server_url}/chat",
        json={
            "user_id": user_id,
            "message": test_message
        },
        timeout=30
    )
    elapsed_time = time.time() - start_time
    
    if response.status_code == 200:
        data = response.json()
        bot_response = data.get('response', 'Нет ответа')
        
        print(f"BOT: {bot_response}")
        print("-"*60)
        print(f"⏱️ Время ответа: {elapsed_time:.2f}с")
        print(f"📊 Intent: {data.get('intent', 'unknown')}")
        print(f"📊 Signal: {data.get('user_signal', 'unknown')}")
        
        # Проверки
        print("\n" + "="*60)
        print("🔍 АНАЛИЗ ОТВЕТА:")
        print("="*60)
        
        # 1. Проверка имени методиста
        if "Ольга Мирная" in bot_response:
            print("❌ ПРОБЛЕМА: Всё ещё упоминается 'Ольга Мирная'")
        elif "Елена Мирошникова" in bot_response:
            print("✅ ИСПРАВЛЕНО: Используется правильное имя 'Елена Мирошникова'")
        elif "методист" in bot_response.lower():
            print("⚠️ Методист упоминается без имени")
        else:
            print("ℹ️ Методист не упоминается в ответе")
        
        # 2. Проверка лишнего приветствия
        if bot_response.startswith("Привет!"):
            print("⚠️ ПРОБЛЕМА: Ответ начинается с 'Привет!' в середине диалога")
        else:
            print("✅ Ответ НЕ начинается с приветствия")
        
        # 3. Проверка других потенциальных галлюцинаций
        if "трёхмесячн" in bot_response or "3 месяца" in bot_response or "три месяца" in bot_response:
            print("ℹ️ Упоминается трёхмесячное менторство (это есть в документах)")
        
        if "воркшоп" in bot_response.lower():
            print("ℹ️ Упоминаются воркшопы (это есть в документах)")
            
        if "сертификац" in bot_response.lower():
            print("ℹ️ Упоминается сертификация (это есть в документах)")
        
    else:
        print(f"❌ Ошибка сервера: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("🚀 Запуск теста 4-го сообщения из диалога №7")
    print("📋 Тема: Супервизии для преподавателей")
    print()
    
    # Проверяем доступность сервера
    try:
        health = requests.get("http://localhost:8000/health", timeout=2)
        if health.status_code == 200:
            print("✅ Сервер доступен\n")
            test_single_message()
        else:
            print("⚠️ Сервер отвечает, но health check failed")
    except:
        print("❌ Сервер не доступен на http://localhost:8000")
        print("💡 Запустите сервер: python src/main.py")