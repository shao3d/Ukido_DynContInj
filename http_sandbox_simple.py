#!/usr/bin/env python3
"""
Простая HTTP песочница для тестирования диалогов
Делает одну вещь хорошо: прогоняет тестовые диалоги
"""

import json
import time
import sys
import os
from datetime import datetime
import requests

def load_dialogue(dialogue_id):
    """Загружает диалог из test_humor_dialogues.json"""
    try:
        with open('test_humor_dialogues.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            scenarios = data.get('scenarios', [])
            
            for scenario in scenarios:
                if scenario['id'] == dialogue_id:
                    return scenario
            
            print(f"❌ Диалог '{dialogue_id}' не найден")
            print(f"Доступные диалоги: {[s['id'] for s in scenarios]}")
            return None
            
    except FileNotFoundError:
        print("❌ Файл test_humor_dialogues.json не найден")
        return None
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

def run_dialogue(dialogue_id, server_url="http://localhost:8000"):
    """Прогоняет один диалог и сохраняет результаты"""
    
    # Загружаем диалог
    dialogue = load_dialogue(dialogue_id)
    if not dialogue:
        return
    
    print(f"\n{'='*60}")
    print(f"📝 Тест: {dialogue['name']}")
    print(f"📋 Описание: {dialogue['description']}")
    print(f"{'='*60}\n")
    
    # ID пользователя для теста
    user_id = f"test_{dialogue_id}_{int(time.time())}"
    
    # Результаты для сохранения
    results = {
        "dialogue_id": dialogue_id,
        "dialogue_name": dialogue['name'],
        "description": dialogue['description'],
        "timestamp": datetime.now().isoformat(),
        "messages": []
    }
    
    # Очищаем историю перед тестом
    try:
        requests.post(f"{server_url}/clear_history/{user_id}", timeout=2)
        print("✅ История очищена\n")
    except:
        pass  # Если не удалось - продолжаем
    
    # Прогоняем все сообщения
    for i, message in enumerate(dialogue['messages'], 1):
        print(f"[{i}/{len(dialogue['messages'])}] USER: {message}")
        
        # Отправляем на сервер
        try:
            response = requests.post(
                f"{server_url}/chat",
                json={"user_id": user_id, "message": message},
                timeout=15  # Достаточно времени для сложных запросов
            )
            
            if response.status_code == 200:
                data = response.json()
                response_text = data.get('response', 'Нет ответа')
                
                print(f"BOT: {response_text[:200]}..." if len(response_text) > 200 else f"BOT: {response_text}")
                print(f"Intent: {data.get('intent', '?')} | Signal: {data.get('user_signal', '?')}")
                
                # Сохраняем для отчёта
                results['messages'].append({
                    "user": message,
                    "bot": response_text,
                    "intent": data.get('intent'),
                    "signal": data.get('user_signal'),
                    "raw": data
                })
            else:
                print(f"❌ Ошибка сервера: {response.status_code}")
                results['messages'].append({
                    "user": message,
                    "error": f"Status {response.status_code}"
                })
                
        except requests.Timeout:
            print(f"⏱️ Timeout")
            results['messages'].append({
                "user": message,
                "error": "Timeout"
            })
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            results['messages'].append({
                "user": message,
                "error": str(e)
            })
        
        print("-" * 40)
    
    # Сохраняем результаты
    save_results(dialogue_id, results)
    print(f"\n✅ Результаты сохранены в test_results/{dialogue_id}_simple.md")

def save_results(dialogue_id, results):
    """Сохраняет результаты в markdown файл"""
    
    os.makedirs("test_results", exist_ok=True)
    
    filename = f"test_results/{dialogue_id}_simple.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Тест диалога: {results['dialogue_name']}\n\n")
        f.write(f"**ID:** {results['dialogue_id']}\n")
        f.write(f"**Описание:** {results['description']}\n")
        f.write(f"**Дата:** {results['timestamp']}\n\n")
        f.write("## Диалог\n\n")
        
        for i, msg in enumerate(results['messages'], 1):
            f.write(f"### Сообщение {i}\n\n")
            f.write(f"**USER:** {msg['user']}\n\n")
            
            if 'error' in msg:
                f.write(f"**ERROR:** {msg['error']}\n\n")
            else:
                f.write(f"**BOT:** {msg.get('bot', 'Нет ответа')}\n\n")
                f.write(f"**Метрики:**\n")
                f.write(f"- Intent: {msg.get('intent', '?')}\n")
                f.write(f"- Signal: {msg.get('signal', '?')}\n\n")
        
        # Итоговая статистика
        f.write("## Статистика\n\n")
        f.write(f"- Всего сообщений: {len(results['messages'])}\n")
        
        errors = [m for m in results['messages'] if 'error' in m]
        if errors:
            f.write(f"- Ошибок: {len(errors)}\n")
            
        # Отслеживаем изменения сигналов
        signals = [m.get('signal') for m in results['messages'] if 'signal' in m]
        if signals:
            f.write(f"- Сигналы: {' → '.join(filter(None, dict.fromkeys(signals)))}\n")

def main():
    """Точка входа"""
    if len(sys.argv) < 2:
        print("Использование: python http_sandbox_simple.py <dialogue_id>")
        print("Пример: python http_sandbox_simple.py dialog_5")
        sys.exit(1)
    
    dialogue_id = sys.argv[1]
    
    # Проверяем что сервер запущен
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code != 200:
            print("⚠️ Сервер отвечает, но health check failed")
    except:
        print("❌ Сервер не запущен. Запустите: python src/main.py")
        sys.exit(1)
    
    # Запускаем тест
    run_dialogue(dialogue_id)

if __name__ == "__main__":
    main()