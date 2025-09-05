#!/usr/bin/env python3
"""
HTTP песочница v2 - поддерживает оба набора тестов
Использование:
    python http_sandbox_v2.py dialog_1              # из test_humor_dialogues.json
    python http_sandbox_v2.py dialog_v2_1           # из test_dialogues_v2.json
    python http_sandbox_v2.py --file test_dialogues_v2.json dialog_v2_1  # явное указание файла
"""

import json
import sys
import time
import os
from datetime import datetime
import requests

DEFAULT_FILE = 'test_humor_dialogues.json'
V2_FILE = 'test_dialogues_v2.json'

def load_dialogue(dialogue_id, filename=None):
    """Загружает диалог из указанного файла или автоматически определяет"""
    
    # Если файл не указан, пробуем определить по ID
    if not filename:
        if dialogue_id.startswith('dialog_v2_'):
            filename = V2_FILE
        else:
            filename = DEFAULT_FILE
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            scenarios = data.get('scenarios', [])
            
            for scenario in scenarios:
                if scenario['id'] == dialogue_id:
                    print(f"📂 Загружен из: {filename}")
                    return scenario
            
            print(f"❌ Диалог '{dialogue_id}' не найден в {filename}")
            print(f"Доступные диалоги: {[s['id'] for s in scenarios]}")
            return None
            
    except FileNotFoundError:
        print(f"❌ Файл {filename} не найден")
        return None
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return None

def test_dialogue(dialogue_id, server_url="http://localhost:8000", filename=None):
    """Тестирует один диалог"""
    
    dialogue = load_dialogue(dialogue_id, filename)
    if not dialogue:
        return
    
    print(f"\n{'='*60}")
    print(f"📝 Тест: {dialogue['name']}")
    print(f"📋 Описание: {dialogue['description']}")
    if 'expected_signal_transition' in dialogue:
        print(f"🎯 Ожидаемый переход: {dialogue['expected_signal_transition']}")
    if 'expected_humor' in dialogue:
        print(f"😄 Ожидаемый юмор: {dialogue['expected_humor']}")
    print(f"{'='*60}\n")
    
    # ID пользователя для теста
    user_id = dialogue.get('user_id', f"test_{dialogue_id}_{int(time.time())}")
    
    # Результаты для сохранения
    results = {
        "dialogue_id": dialogue_id,
        "dialogue_name": dialogue['name'],
        "description": dialogue['description'],
        "timestamp": datetime.now().isoformat(),
        "messages": [],
        "signal_transitions": []
    }
    
    # Очищаем историю перед тестом
    try:
        requests.post(f"{server_url}/clear_history/{user_id}", timeout=2)
        print("✅ История очищена\n")
    except:
        pass
    
    # Для отслеживания переходов сигналов
    last_signal = None
    
    # Прогоняем все сообщения
    for i, message in enumerate(dialogue['messages'], 1):
        print(f"[{i}/{len(dialogue['messages'])}] USER: {message}")
        
        # Отправляем сообщение
        try:
            response = requests.post(
                f"{server_url}/chat",
                json={"user_id": user_id, "message": message},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                bot_response = data.get('response', 'No response')
                
                # Сокращаем для консоли если слишком длинный
                display_response = bot_response[:150] + "..." if len(bot_response) > 150 else bot_response
                print(f"BOT: {display_response}")
                
                # Метрики
                intent = data.get('intent', 'unknown')
                signal = data.get('user_signal', 'unknown')
                
                print(f"Intent: {intent} | Signal: {signal}")
                
                # Отслеживаем переходы сигналов
                if last_signal and last_signal != signal:
                    transition = f"{last_signal} → {signal}"
                    results["signal_transitions"].append({
                        "message_num": i,
                        "transition": transition
                    })
                    print(f"🔄 Переход сигнала: {transition}")
                last_signal = signal
                
                # Сохраняем результат
                results["messages"].append({
                    "num": i,
                    "user": message,
                    "bot": bot_response,
                    "intent": intent,
                    "signal": signal
                })
                
            else:
                print(f"❌ Ошибка сервера: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("❌ Timeout - сервер не ответил за 30 секунд")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        print("-"*40)
        time.sleep(1)  # Пауза между сообщениями
    
    # Сохраняем результаты
    save_results(results)
    
    # Выводим итоговую статистику
    print(f"\n{'='*60}")
    print("📊 ИТОГИ:")
    if results["signal_transitions"]:
        print(f"Переходы сигналов: {' → '.join([t['transition'] for t in results['signal_transitions']])}")
    else:
        print(f"Сигнал стабилен: {last_signal}")
    print(f"{'='*60}")

def save_results(results):
    """Сохраняет результаты в markdown файл"""
    
    # Создаём папку если нет
    os.makedirs("test_results", exist_ok=True)
    
    # Имя файла
    filename = f"test_results/{results['dialogue_id']}_v2.md"
    
    # Формируем markdown
    md_content = f"""# Тест диалога: {results['dialogue_name']}

**ID:** {results['dialogue_id']}
**Описание:** {results['description']}
**Дата:** {results['timestamp']}

## Диалог

"""
    
    for msg in results['messages']:
        md_content += f"""### Сообщение {msg['num']}

**USER:** {msg['user']}

**BOT:** {msg['bot']}

**Метрики:**
- Intent: {msg['intent']}
- Signal: {msg['signal']}

"""
    
    # Статистика
    md_content += f"""## Статистика

- Всего сообщений: {len(results['messages'])}
"""
    
    if results["signal_transitions"]:
        transitions = [t['transition'] for t in results['signal_transitions']]
        md_content += f"- Переходы сигналов: {' → '.join(transitions)}\n"
    else:
        if results['messages']:
            md_content += f"- Сигнал стабилен: {results['messages'][-1]['signal']}\n"
    
    # Сохраняем
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"\n✅ Результаты сохранены в {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python http_sandbox_v2.py dialog_1")
        print("  python http_sandbox_v2.py dialog_v2_1")
        print("  python http_sandbox_v2.py --file test_dialogues_v2.json dialog_v2_1")
        sys.exit(1)
    
    # Парсим аргументы
    if sys.argv[1] == "--file" and len(sys.argv) >= 4:
        filename = sys.argv[2]
        dialogue_id = sys.argv[3]
    else:
        filename = None
        dialogue_id = sys.argv[1]
    
    # Запускаем тест
    test_dialogue(dialogue_id, filename=filename)