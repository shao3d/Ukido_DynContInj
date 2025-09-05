#!/usr/bin/env python3
"""
Запуск теста Tech Twins Parent через API
"""

import json
import time
import requests
from datetime import datetime

def run_dialogue_test():
    """Запускает тест диалога с техническим папой близнецов"""
    
    # Загружаем тест
    with open('test_tech_twins_parent.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    scenario = test_data['scenarios'][0]
    dialogue_id = scenario['id']
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    
    print(f"\n{'='*60}")
    print(f"🧪 Тест: {scenario['name']}")
    print(f"📝 ID: {dialogue_id}")
    print(f"👤 User: {user_id}")
    print(f"🎯 Ожидаемый переход: {scenario.get('expected_signal_transition', 'N/A')}")
    print(f"😄 Ожидаемый юмор: {scenario.get('expected_humor', 'N/A')}")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, message in enumerate(scenario['messages'], 1):
        print(f"\n{'─'*50}")
        print(f"📤 Сообщение {i}/{len(scenario['messages'])}")
        print(f"👤 User: {message[:100]}{'...' if len(message) > 100 else ''}")
        
        try:
            # Отправляем запрос
            response = requests.post(
                'http://localhost:8000/chat',
                json={'user_id': user_id, 'message': message},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Извлекаем метаданные
                metadata = data.get('metadata', {})
                intent = metadata.get('intent', data.get('intent', 'unknown'))
                user_signal = metadata.get('user_signal', data.get('user_signal', 'unknown'))
                humor = metadata.get('humor_generated', False)
                cta_added = metadata.get('cta_added', False)
                
                print(f"🤖 Bot: {data['response'][:200]}{'...' if len(data['response']) > 200 else ''}")
                print(f"📊 Intent: {intent} | Signal: {user_signal} | Humor: {humor} | CTA: {cta_added}")
                
                results.append({
                    'message': message,
                    'response': data['response'],
                    'intent': intent,
                    'user_signal': user_signal,
                    'humor_generated': humor,
                    'cta_added': cta_added
                })
                
                # Небольшая пауза между сообщениями
                time.sleep(0.5)
                
            else:
                print(f"❌ Ошибка: {response.status_code}")
                print(f"   {response.text[:200]}")
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout после 30 секунд")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Анализ результатов
    print(f"\n{'='*60}")
    print("📈 АНАЛИЗ РЕЗУЛЬТАТОВ:")
    print(f"{'='*60}")
    
    # Подсчёт юмора
    humor_count = sum(1 for r in results if r['humor_generated'])
    print(f"😄 Юмор сгенерирован: {humor_count} раз")
    
    # Подсчёт CTA
    cta_count = sum(1 for r in results if r['cta_added'])
    print(f"📢 CTA добавлен: {cta_count} раз")
    
    # Переходы сигналов
    signals = [r['user_signal'] for r in results]
    unique_signals = []
    for s in signals:
        if not unique_signals or s != unique_signals[-1]:
            unique_signals.append(s)
    
    print(f"🔄 Переходы сигналов: {' → '.join(unique_signals)}")
    
    # Проверка обработки множественных детей
    twin_mentions = 0
    for r in results:
        if any(word in r['response'].lower() for word in ['артём', 'софия', 'близнец', 'оба', 'двоих']):
            twin_mentions += 1
    
    print(f"👥 Упоминания близнецов в ответах: {twin_mentions}")
    
    # Сохранение отчёта
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results/tech_twins_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Отчёт теста: {scenario['name']}\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**User ID:** {user_id}\n\n")
        f.write(f"## Результаты\n\n")
        f.write(f"- **Юмор:** {humor_count} раз\n")
        f.write(f"- **CTA:** {cta_count} раз\n")
        f.write(f"- **Переходы:** {' → '.join(unique_signals)}\n")
        f.write(f"- **Упоминания близнецов:** {twin_mentions}\n\n")
        
        f.write("## Диалог\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"### Сообщение {i}\n\n")
            f.write(f"**User:** {r['message']}\n\n")
            f.write(f"**Bot:** {r['response']}\n\n")
            f.write(f"*Метаданные: intent={r['intent']}, signal={r['user_signal']}, "
                   f"humor={r['humor_generated']}, cta={r['cta_added']}*\n\n")
            f.write("---\n\n")
    
    print(f"\n✅ Отчёт сохранён: {report_file}")

if __name__ == "__main__":
    run_dialogue_test()