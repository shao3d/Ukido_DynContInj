#!/usr/bin/env python3
"""
Анализ внутренней работы Router при обработке сообщения
"Добрый день! Расскажите о вашей школе"
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def analyze_message_processing(message: str, user_id: str = "analyze_test"):
    """Детальный анализ того, что происходит внутри системы"""
    
    print("="*80)
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ОБРАБОТКИ СООБЩЕНИЯ")
    print("="*80)
    print(f"\n📝 Сообщение: {message}")
    print(f"👤 User ID: {user_id}")
    
    # ШАГ 1: Очистка истории для чистого теста
    print("\n" + "="*80)
    print("ШАГ 1: ОЧИСТКА ИСТОРИИ")
    print("-"*40)
    
    clear_response = requests.post(
        f"{BASE_URL}/clear_history/{user_id}"
    )
    
    if clear_response.status_code == 200:
        print("✅ История очищена")
    else:
        print(f"❌ Ошибка очистки: {clear_response.status_code}")
        return
    
    # Небольшая пауза
    time.sleep(1)
    
    # ШАГ 2: Отправка сообщения и получение полного ответа
    print("\n" + "="*80)
    print("ШАГ 2: ОТПРАВКА СООБЩЕНИЯ")
    print("-"*40)
    
    start_time = time.time()
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "user_id": user_id,
            "message": message
        },
        timeout=30
    )
    end_time = time.time()
    
    print(f"⏱️ Время обработки: {end_time - start_time:.2f} сек")
    
    if response.status_code != 200:
        print(f"❌ Ошибка: {response.status_code}")
        print(response.text)
        return
    
    data = response.json()
    
    # Вывод полного JSON для отладки
    print(f"\n📋 Полный ответ сервера:")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
    
    # ШАГ 3: Анализ ответа и метаданных
    print("\n" + "="*80)
    print("ШАГ 3: АНАЛИЗ ВНУТРЕННЕГО СОСТОЯНИЯ")
    print("-"*40)
    
    # Основной ответ
    bot_response = data.get('response', 'No response')
    print(f"\n📤 ФИНАЛЬНЫЙ ОТВЕТ БОТА:")
    print(f"'{bot_response[:200]}{'...' if len(bot_response) > 200 else ''}'")
    
    # Используем прямые поля из data
    print("\n" + "="*80)
    print("🔹 ЭТАП ROUTER (GEMINI)")
    print("-"*40)
    
    # Intent и Status
    intent = data.get('intent', 'unknown')
    user_signal = data.get('user_signal', 'unknown')
    social_context = data.get('social', None)
    confidence = data.get('confidence', 0)
    
    print(f"\n📊 КЛАССИФИКАЦИЯ:")
    print(f"  Intent/Status: {intent}")
    print(f"  User Signal: {user_signal}")
    print(f"  Social Context: {social_context}")
    print(f"  Confidence: {confidence}")
    
    # Декомпозиция вопросов
    decomposed = data.get('decomposed_questions', [])
    print(f"\n📝 ДЕКОМПОЗИЦИЯ ВОПРОСОВ:")
    if decomposed:
        for i, q in enumerate(decomposed, 1):
            print(f"  {i}. {q}")
    else:
        print("  ⚠️ Список вопросов пуст!")
        print("  ❗ Это основная проблема - Router не извлёк вопросы")
    
    # Документы
    documents = data.get('relevant_documents', [])
    print(f"\n📚 ВЫБРАННЫЕ ДОКУМЕНТЫ:")
    if documents:
        for doc in documents:
            if isinstance(doc, dict):
                print(f"  - {doc.get('title', 'Unknown')}")
            else:
                print(f"  - {doc}")
    else:
        print("  ⚠️ Документы не выбраны (следствие пустой декомпозиции)")
    
    # ШАГ 4: Анализ пути обработки
    print("\n" + "="*80)
    print("🔹 ПУТЬ ОБРАБОТКИ")
    print("-"*40)
    
    if intent == 'offtopic':
        print("\n❌ ПУТЬ: OFFTOPIC")
        print("  1. Router определил как нерелевантный вопрос")
        print("  2. Main.py НЕ вызывает Claude")
        print("  3. Используется стандартный ответ или юмор")
        print(f"  4. Результат: '{bot_response[:100]}...'")
        
    elif intent == 'success':
        print("\n✅ ПУТЬ: SUCCESS")
        print("  1. Router определил как релевантный вопрос")
        print(f"  2. Декомпозировал на {len(decomposed)} вопросов")
        print(f"  3. Выбрал {len(documents)} документов")
        print("  4. Main.py отправляет в Claude для генерации")
        print(f"  5. Claude генерирует ответ с тоном '{user_signal}'")
        
    elif intent == 'need_simplification':
        print("\n⚠️ ПУТЬ: NEED_SIMPLIFICATION")
        print("  Слишком много вопросов, требуется упрощение")
    
    # ШАГ 5: Проблемный анализ
    print("\n" + "="*80)
    print("🚨 АНАЛИЗ ПРОБЛЕМЫ")
    print("-"*40)
    
    if intent == 'offtopic' and 'школе' in message.lower():
        print("\n❗ ОБНАРУЖЕНА ПРОБЛЕМА:")
        print("  Вопрос о школе классифицирован как offtopic")
        print("\n  Возможные причины:")
        print("  1. Router не декомпозировал вопрос (пустой список)")
        print("  2. Слишком общая формулировка для Router")
        print("  3. Проблема в промпте Router'а")
        
        print("\n  🔍 Что должно было произойти:")
        print("  - Декомпозиция: ['Расскажите о школе Ukido']")
        print("  - Status: success")
        print("  - Документы: mission_values_history.md, methodology.md")
        print("  - Генерация развёрнутого ответа через Claude")
    
    print("\n" + "="*80)
    
    return {
        'response': bot_response,
        'intent': intent,
        'decomposed': decomposed,
        'documents': documents,
        'user_signal': user_signal
    }

def test_variations():
    """Тестирует разные варианты одного и того же вопроса"""
    
    print("\n" + "="*80)
    print("📊 СРАВНЕНИЕ ВАРИАНТОВ ФОРМУЛИРОВКИ")
    print("="*80)
    
    test_messages = [
        "Расскажите о вашей школе",
        "Добрый день! Расскажите о вашей школе",
        "Что за школа у вас?",
        "Расскажите про школу Ukido",
        "Хочу узнать о вашей школе",
        "Информация о школе"
    ]
    
    results = []
    
    for i, msg in enumerate(test_messages):
        user_id = f"test_variant_{i}"
        
        # Очистка истории
        requests.post(f"{BASE_URL}/clear_history/{user_id}")
        time.sleep(0.5)
        
        # Отправка сообщения
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"user_id": user_id, "message": msg},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results.append({
                'message': msg,
                'intent': data.get('intent', 'unknown'),
                'questions': len(data.get('decomposed_questions', [])),
                'docs': len(data.get('relevant_documents', []))
            })
    
    # Вывод таблицы
    print(f"\n{'Сообщение':<45} | {'Intent':<10} | {'Questions':<10} | {'Docs':<5}")
    print("-"*75)
    for r in results:
        msg = r['message'][:42] + "..." if len(r['message']) > 45 else r['message']
        print(f"{msg:<45} | {r['intent']:<10} | {r['questions']:<10} | {r['docs']:<5}")

if __name__ == "__main__":
    # Основной анализ
    result = analyze_message_processing("Добрый день! Расскажите о вашей школе")
    
    # Дополнительный тест вариантов
    print("\n" + "="*80)
    print("Запуск теста вариантов формулировки...")
    test_variations()