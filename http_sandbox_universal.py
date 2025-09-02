#!/usr/bin/env python3
"""
Универсальная HTTP песочница - поддерживает все форматы тестов
Более надёжная версия с улучшенной обработкой ошибок и таймаутов
"""

import json
import sys
import time
import os
from datetime import datetime
import requests
from typing import Dict, List, Any, Optional

# Поддерживаемые файлы с тестами
TEST_FILES = {
    'v1': 'test_humor_dialogues.json',
    'v2': 'test_dialogues_v2.json',
    'scenarios': 'tests/test_scenarios_state_machine.json'
}

def detect_test_file(dialogue_id: str) -> str:
    """Автоматически определяет файл теста по ID диалога"""
    if dialogue_id.startswith('dialog_v2_'):
        return TEST_FILES['v2']
    elif dialogue_id.startswith('dialog_'):
        return TEST_FILES['v1']
    elif dialogue_id.startswith('scenario_'):
        return TEST_FILES['scenarios']
    else:
        # По умолчанию пробуем v1
        return TEST_FILES['v1']

def load_dialogue(dialogue_id: str, filename: Optional[str] = None) -> Optional[Dict]:
    """Загружает диалог из файла"""
    
    # Автоматическое определение файла если не указан
    if not filename:
        filename = detect_test_file(dialogue_id)
    
    # Проверяем существование файла
    if not os.path.exists(filename):
        print(f"❌ Файл {filename} не найден")
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Разные форматы для разных файлов
            if filename == TEST_FILES['scenarios']:
                # Формат test_scenarios_state_machine.json
                for scenario in data:
                    if f"scenario_{scenario.get('scenario_name', '').lower().replace(' ', '_')}" == dialogue_id:
                        # Преобразуем в формат диалога
                        return {
                            'id': dialogue_id,
                            'name': scenario['scenario_name'],
                            'description': scenario['description'],
                            'messages': scenario['steps'],
                            'expected_signal': scenario.get('expected_signal'),
                            'user_id': f"test_{dialogue_id}_{int(time.time())}"
                        }
            else:
                # Стандартный формат с scenarios
                scenarios = data.get('scenarios', [])
                for scenario in scenarios:
                    if scenario.get('id') == dialogue_id:
                        print(f"📂 Загружен из: {filename}")
                        # Добавляем user_id если его нет
                        if 'user_id' not in scenario:
                            scenario['user_id'] = f"test_{dialogue_id}_{int(time.time())}"
                        return scenario
            
            # Не нашли диалог
            available = []
            if filename == TEST_FILES['scenarios']:
                available = [f"scenario_{s.get('scenario_name', '').lower().replace(' ', '_')}" for s in data]
            else:
                available = [s.get('id') for s in data.get('scenarios', [])]
            
            print(f"❌ Диалог '{dialogue_id}' не найден в {filename}")
            print(f"📋 Доступные диалоги: {available}")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON в {filename}: {e}")
        return None
    except Exception as e:
        print(f"❌ Ошибка загрузки {filename}: {e}")
        return None

def test_dialogue(dialogue_id: str, server_url: str = "http://localhost:8000", filename: Optional[str] = None) -> None:
    """Тестирует один диалог с улучшенной обработкой ошибок"""
    
    # Загружаем диалог
    dialogue = load_dialogue(dialogue_id, filename)
    if not dialogue:
        return
    
    print(f"\n{'='*60}")
    print(f"📝 Тест: {dialogue['name']}")
    print(f"📋 Описание: {dialogue['description']}")
    
    # Показываем ожидания если есть
    if 'expected_signal_transition' in dialogue:
        print(f"🎯 Ожидаемый переход: {dialogue['expected_signal_transition']}")
    elif 'expected_signal' in dialogue:
        print(f"🎯 Ожидаемый сигнал: {dialogue['expected_signal']}")
    
    if 'expected_humor' in dialogue:
        print(f"😄 Ожидаемый юмор: {dialogue['expected_humor']}")
    
    print(f"{'='*60}\n")
    
    # ВСЕГДА генерируем уникальный ID пользователя с timestamp
    # Это обеспечивает чистое состояние для каждого теста
    user_id = f"test_{dialogue_id}_{int(time.time())}"
    print(f"🔑 Используем уникальный user_id: {user_id}\n")
    
    # Результаты для сохранения
    results = {
        "dialogue_id": dialogue_id,
        "dialogue_name": dialogue['name'],
        "description": dialogue['description'],
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,  # Сохраняем для отладки
        "messages": [],
        "signal_transitions": [],
        "humor_count": 0,
        "errors": []
    }
    
    # Проверяем доступность сервера
    try:
        health_response = requests.get(f"{server_url}/health", timeout=2)
        if health_response.status_code != 200:
            print("⚠️ Сервер отвечает, но health check failed")
    except:
        print("❌ Сервер не доступен на {server_url}")
        print("💡 Запустите сервер: python src/main.py")
        return
    
    # Очищаем историю (хотя с уникальным user_id это не обязательно)
    try:
        clear_response = requests.post(f"{server_url}/clear_history/{user_id}", timeout=5)
        if clear_response.status_code == 200:
            print("✅ История очищена\n")
    except Exception as e:
        print(f"⚠️ Не удалось очистить историю: {e}\n")
    
    # Переменные для отслеживания
    last_signal = None
    last_response_has_humor = False
    
    # Обрабатываем сообщения
    messages = dialogue.get('messages', [])
    total_messages = len(messages)
    
    for i, message in enumerate(messages, 1):
        print(f"[{i}/{total_messages}] USER: {message}")
        
        # Готовим запрос
        request_data = {
            "user_id": user_id,
            "message": message
        }
        
        try:
            # Отправляем с увеличенным таймаутом
            start_time = time.time()
            response = requests.post(
                f"{server_url}/chat",
                json=request_data,
                timeout=30  # 30 секунд таймаут
            )
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                bot_response = data.get('response', 'Нет ответа')
                
                # Показываем ответ (сокращаем если длинный)
                if len(bot_response) > 150:
                    display_response = bot_response[:150] + "..."
                else:
                    display_response = bot_response
                print(f"BOT: {display_response}")
                
                # Метаданные
                intent = data.get('intent', 'unknown')
                signal = data.get('user_signal', 'unknown')
                metadata = data.get('metadata', {})
                
                # Проверяем наличие юмора (простая эвристика)
                humor_indicators = [
                    'а вот', 'как говорится', 'видимо', 'похоже',
                    'знаете', '!', 'может быть', 'наверное'
                ]
                has_humor = any(ind in bot_response.lower() for ind in humor_indicators)
                
                # Жванецкий-специфичные фразы
                zhvanetsky_phrases = [
                    'сидит в телефоне как программист',
                    'стучит по клавишам',
                    'эконом-класс для эконом-родителей',
                    'чемпион мира по переговорам'
                ]
                if any(phrase in bot_response.lower() for phrase in zhvanetsky_phrases):
                    has_humor = True
                    
                if has_humor and intent == 'offtopic':
                    results["humor_count"] += 1
                    print(f"😄 Юмор обнаружен! (всего: {results['humor_count']})")
                
                print(f"📊 Intent: {intent} | Signal: {signal} | Time: {elapsed_time:.2f}s")
                
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
                    "signal": signal,
                    "has_humor": has_humor,
                    "response_time": elapsed_time,
                    "metadata": metadata
                })
                
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:100]}"
                print(f"❌ Ошибка сервера: {error_msg}")
                results["errors"].append({
                    "message_num": i,
                    "error": error_msg
                })
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout после 30 секунд")
            results["errors"].append({
                "message_num": i,
                "error": "Timeout 30s"
            })
            
        except Exception as e:
            print(f"❌ Ошибка: {str(e)[:100]}")
            results["errors"].append({
                "message_num": i,
                "error": str(e)[:100]
            })
        
        print("-" * 40)
        
        # Небольшая пауза между сообщениями
        if i < total_messages:
            time.sleep(0.5)
    
    # Сохраняем результаты
    save_results(results)
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"├─ Сообщений обработано: {len(results['messages'])}")
    print(f"├─ Ошибок: {len(results['errors'])}")
    print(f"├─ Юмора сгенерировано: {results['humor_count']}")
    
    if results["signal_transitions"]:
        transitions = ' → '.join([t['transition'] for t in results['signal_transitions']])
        print(f"├─ Переходы сигналов: {transitions}")
    elif last_signal:
        print(f"├─ Сигнал стабилен: {last_signal}")
    
    # Проверяем соответствие ожиданиям
    if 'expected_signal' in dialogue:
        if last_signal == dialogue['expected_signal']:
            print(f"✅ Сигнал соответствует ожидаемому: {dialogue['expected_signal']}")
        else:
            print(f"⚠️ Сигнал не соответствует! Ожидался: {dialogue['expected_signal']}, получен: {last_signal}")
    
    print(f"{'='*60}")

def save_results(results: Dict) -> None:
    """Сохраняет результаты теста в markdown файл"""
    
    # Создаём папку если нет
    os.makedirs("test_results", exist_ok=True)
    
    # Имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results/{results['dialogue_id']}_{timestamp}.md"
    
    # Формируем markdown
    md_content = f"""# Тест диалога: {results['dialogue_name']}

**ID:** {results['dialogue_id']}
**Описание:** {results['description']}
**Дата:** {results['timestamp']}

## Сводка

- **Всего сообщений:** {len(results['messages'])}
- **Ошибок:** {len(results['errors'])}
- **Юмора сгенерировано:** {results['humor_count']}
"""
    
    if results["signal_transitions"]:
        transitions = ' → '.join([t['transition'] for t in results['signal_transitions']])
        md_content += f"- **Переходы сигналов:** {transitions}\n"
    elif results['messages']:
        last_signal = results['messages'][-1].get('signal', 'unknown')
        md_content += f"- **Финальный сигнал:** {last_signal}\n"
    
    # Диалог
    md_content += "\n## Диалог\n\n"
    
    for msg in results['messages']:
        md_content += f"""### Сообщение {msg['num']}

**USER:** {msg['user']}

**BOT:** {msg['bot']}

**Метрики:**
- Intent: `{msg['intent']}`
- Signal: `{msg['signal']}`
- Юмор: {'✅' if msg.get('has_humor') else '❌'}
- Время ответа: {msg.get('response_time', 0):.2f}с
"""
        
        # Добавляем переход если был
        for transition in results['signal_transitions']:
            if transition['message_num'] == msg['num']:
                md_content += f"- 🔄 **Переход сигнала:** {transition['transition']}\n"
        
        md_content += "\n---\n\n"
    
    # Ошибки если были
    if results['errors']:
        md_content += "## Ошибки\n\n"
        for error in results['errors']:
            md_content += f"- Сообщение {error['message_num']}: {error['error']}\n"
    
    # Сохраняем
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"\n✅ Результаты сохранены в {filename}")

def list_available_tests() -> None:
    """Показывает все доступные тесты"""
    print("\n📋 Доступные тесты:\n")
    
    for key, filename in TEST_FILES.items():
        if not os.path.exists(filename):
            print(f"  ❌ {filename} - не найден")
            continue
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                if key == 'scenarios':
                    # Особый формат
                    scenarios = data
                    print(f"\n  📂 {filename}:")
                    for s in scenarios[:5]:  # Показываем первые 5
                        scenario_id = f"scenario_{s.get('scenario_name', '').lower().replace(' ', '_')}"
                        print(f"    - {scenario_id}: {s.get('description', 'Нет описания')}")
                    if len(scenarios) > 5:
                        print(f"    ... и ещё {len(scenarios) - 5} сценариев")
                else:
                    # Стандартный формат
                    scenarios = data.get('scenarios', [])
                    print(f"\n  📂 {filename}:")
                    for s in scenarios[:5]:  # Показываем первые 5
                        print(f"    - {s.get('id')}: {s.get('name', 'Без названия')}")
                    if len(scenarios) > 5:
                        print(f"    ... и ещё {len(scenarios) - 5} диалогов")
                        
        except Exception as e:
            print(f"  ⚠️ {filename} - ошибка чтения: {e}")

def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("📖 Универсальная HTTP песочница для тестирования диалогов")
        print("\nИспользование:")
        print("  python http_sandbox_universal.py <dialogue_id>")
        print("  python http_sandbox_universal.py --file <filename> <dialogue_id>")
        print("  python http_sandbox_universal.py --list")
        print("\nПримеры:")
        print("  python http_sandbox_universal.py dialog_1          # из test_humor_dialogues.json")
        print("  python http_sandbox_universal.py dialog_v2_1       # из test_dialogues_v2.json")
        print("  python http_sandbox_universal.py --list            # показать все доступные тесты")
        sys.exit(1)
    
    # Обработка аргументов
    if sys.argv[1] == "--list":
        list_available_tests()
        sys.exit(0)
    elif sys.argv[1] == "--file" and len(sys.argv) >= 4:
        filename = sys.argv[2]
        dialogue_id = sys.argv[3]
        test_dialogue(dialogue_id, filename=filename)
    else:
        dialogue_id = sys.argv[1]
        test_dialogue(dialogue_id)

if __name__ == "__main__":
    main()