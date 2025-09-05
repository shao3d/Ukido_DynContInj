#!/usr/bin/env python3
"""Тест унификации доменов и удаления артефактов"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_domain_unification():
    """Тест унификации доменов ukido.ua → ukido.com.ua"""
    print("\n🔍 Тест унификации доменов")
    print("-" * 50)
    
    # Тест 1: Запрос на пробное занятие
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": f"test_domain_{int(time.time())}",
            "message": "Давайте попробуем пробное занятие для моей дочки 10 лет"
        }
    )
    
    result = response.json()
    text = result["response"]
    
    # Проверка домена
    if "ukido.ua/" in text and "ukido.com.ua/" not in text:
        print("❌ ОШИБКА: Найден ukido.ua без .com")
        print(f"   Текст: {text[:200]}...")
    elif "ukido.com.ua/" in text:
        print("✅ Домен унифицирован: ukido.com.ua")
        print(f"   Найдено в: ...{text[text.index('ukido.com.ua')-20:text.index('ukido.com.ua')+40]}...")
    else:
        print("⚠️ Домен не найден в ответе")
    
    # Тест 2: Проверка отсутствия дублирования
    contact_count = text.count("📞")
    if contact_count > 1:
        print(f"⚠️ Контакты дублируются {contact_count} раз")
    elif contact_count == 1:
        print("✅ Контакты добавлены один раз")
    
    return result

def test_artifact_removal():
    """Тест удаления числовых артефактов"""
    print("\n🔍 Тест удаления артефактов")
    print("-" * 50)
    
    # Запрос, который может вызвать артефакты
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": f"test_artifact_{int(time.time())}",
            "message": "Расскажите про домашние задания, сколько времени они занимают?"
        }
    )
    
    result = response.json()
    text = result["response"]
    
    # Проверка артефактов
    import re
    artifacts = re.findall(r'\d+-[а-я]+\d{2,}', text)
    
    if artifacts:
        print(f"❌ ОШИБКА: Найдены артефакты: {artifacts}")
    else:
        print("✅ Артефакты не найдены")
        
    # Проверка корректных числовых выражений
    if "30-секундное" in text or "20-минутные" in text or "15-20 минут" in text:
        print("✅ Корректные временные выражения сохранены")
    
    return result

def test_full_scenario():
    """Полный сценарий burned_mom"""
    print("\n🔍 Полный тест burned_mom")
    print("-" * 50)
    
    user_id = f"test_burned_{int(time.time())}"
    
    messages = [
        "Здравствуйте. Я уже пробовала две онлайн-школы для дочки, обе оказались пустышками. Чем вы отличаетесь?",
        "Знаете что, давайте попробуем одно пробное занятие. Но я буду присутствовать и смотреть"
    ]
    
    for i, msg in enumerate(messages, 1):
        print(f"\n📝 Сообщение {i}: {msg[:50]}...")
        
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"user_id": user_id, "message": msg}
        )
        
        result = response.json()
        text = result["response"]
        
        # Анализ ответа
        print(f"   Signal: {result.get('user_signal', 'N/A')}")
        print(f"   Intent: {result.get('intent', 'N/A')}")
        
        if "ukido.com.ua" in text:
            print("   ✅ Домен корректный")
        
        if i == 2:  # Второе сообщение должно содержать ссылку
            if "ukido.com.ua/trial" in text or "+380" in text:
                print("   ✅ Контакты для записи добавлены")
            else:
                print("   ❌ Контакты отсутствуют")
        
        print(f"   Ответ: {text[:150]}...")
        time.sleep(0.5)

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 ТЕСТИРОВАНИЕ УНИФИКАЦИИ ДОМЕНОВ И АРТЕФАКТОВ")
    print("=" * 60)
    
    try:
        # Проверка доступности сервера
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ Сервер недоступен!")
            exit(1)
        
        print("✅ Сервер работает")
        
        # Запуск тестов
        test_domain_unification()
        test_artifact_removal()
        test_full_scenario()
        
        print("\n" + "=" * 60)
        print("✨ Тестирование завершено!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")