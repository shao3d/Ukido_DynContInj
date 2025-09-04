#!/usr/bin/env python3
"""Запуск теста burned_mom через песочницу"""

import requests
import json
import time
from datetime import datetime

def run_burned_mom_test():
    """Запуск полного диалога burned_mom"""
    
    # Загружаем сценарий
    with open('test_burned_parent.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    scenario = data['scenarios'][0]  # burned_mom - первый сценарий
    
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    messages = scenario['messages']
    
    print(f"🎭 Запуск теста: {scenario['name']}")
    print(f"📝 Описание: {scenario['description']}")
    print(f"👤 User ID: {user_id}")
    print("=" * 80)
    
    dialog_log = []
    dialog_log.append(f"# Тест диалога: {scenario['name']}")
    dialog_log.append(f"\n**ID:** {scenario['id']}")
    dialog_log.append(f"**Описание:** {scenario['description']}")
    dialog_log.append(f"**Дата:** {datetime.now().isoformat()}")
    dialog_log.append(f"\n## Сводка")
    dialog_log.append(f"\n- **Всего сообщений:** {len(messages)}")
    
    errors = 0
    humor_count = 0
    signal_transitions = []
    last_signal = None
    
    dialog_log.append(f"\n## Диалог")
    
    for i, message in enumerate(messages, 1):
        print(f"\n📝 Сообщение {i}/{len(messages)}")
        print(f"USER: {message}")
        
        try:
            response = requests.post(
                "http://localhost:8000/chat",
                json={"user_id": user_id, "message": message},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}")
                errors += 1
                continue
                
            result = response.json()
            bot_response = result["response"]
            intent = result.get("intent", "unknown")
            user_signal = result.get("user_signal", "unknown")
            humor_generated = result.get("metadata", {}).get("humor_generated", False)
            
            if humor_generated:
                humor_count += 1
            
            # Отслеживание переходов сигналов
            if last_signal and last_signal != user_signal:
                signal_transitions.append(f"{last_signal} → {user_signal}")
            last_signal = user_signal
            
            print(f"BOT: {bot_response}")
            print(f"📊 Intent: {intent} | Signal: {user_signal} | Humor: {'✅' if humor_generated else '❌'}")
            
            # Логирование в markdown
            dialog_log.append(f"\n### Сообщение {i}")
            dialog_log.append(f"\n**USER:** {message}")
            dialog_log.append(f"\n**BOT:** {bot_response}")
            dialog_log.append(f"\n**Метрики:**")
            dialog_log.append(f"- Intent: `{intent}`")
            dialog_log.append(f"- Signal: `{user_signal}`")
            dialog_log.append(f"- Юмор: {'✅' if humor_generated else '❌'}")
            
            # Проверки специфичные для burned_mom
            if i == len(messages) and "ukido.com.ua/trial" in bot_response:
                dialog_log.append(f"- **CTA:** ready_to_buy (органично интегрирован)")
            
            if signal_transitions and i > 1:
                dialog_log.append(f"- 🔄 **Переход сигнала:** {signal_transitions[-1]}")
            
            dialog_log.append(f"\n---")
            
            time.sleep(1)  # Небольшая пауза между запросами
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            errors += 1
    
    # Обновляем сводку
    dialog_log[6] = f"- **Ошибок:** {errors}"
    dialog_log.insert(7, f"- **Юмора сгенерировано:** {humor_count}")
    dialog_log.insert(8, f"- **Переходы сигналов:** {' → '.join(signal_transitions) if signal_transitions else 'Нет'}")
    
    print("\n" + "=" * 80)
    print(f"✨ Тест завершён!")
    print(f"📊 Ошибок: {errors}, Юмора: {humor_count}")
    print(f"🔄 Переходы: {' → '.join(signal_transitions) if signal_transitions else 'Нет'}")
    
    # Сохраняем в файл
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results/{scenario['id']}_{timestamp}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dialog_log))
    
    print(f"💾 Результат сохранён: {filename}")
    
    return filename

if __name__ == "__main__":
    run_burned_mom_test()