#!/usr/bin/env python3
"""
Запуск теста подростка-бунтаря через API
"""

import json
import time
import requests
from datetime import datetime

def run_teenager_test():
    """Запускает тест диалога с подростком"""
    
    # Загружаем тест
    with open('test_teenager_rebel.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    scenario = test_data['scenarios'][0]
    dialogue_id = scenario['id']
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    
    print(f"\n{'='*60}")
    print(f"🛹 ТЕСТ: {scenario['name']}")
    print(f"📝 ID: {dialogue_id}")
    print(f"👤 User: {user_id}")
    print(f"🎯 Ожидаемый переход: {scenario.get('expected_signal_transition', 'N/A')}")
    print(f"😎 Ожидаемый юмор: {scenario.get('expected_humor', 'N/A')}")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, message in enumerate(scenario['messages'], 1):
        print(f"\n{'─'*50}")
        print(f"💬 Сообщение {i}/{len(scenario['messages'])}")
        print(f"🛹 Подросток: {message[:80]}{'...' if len(message) > 80 else ''}")
        
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
                
                print(f"🤖 Ukido: {data['response'][:150]}{'...' if len(data['response']) > 150 else ''}")
                print(f"📊 Intent: {intent} | Signal: {user_signal} | Humor: {'✅' if humor else '❌'} | CTA: {'✅' if cta_added else '❌'}")
                
                results.append({
                    'message': message,
                    'response': data['response'],
                    'intent': intent,
                    'user_signal': user_signal,
                    'humor_generated': humor,
                    'cta_added': cta_added
                })
                
                time.sleep(0.3)  # Небольшая пауза
                
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
    print(f"😎 Юмор сгенерирован: {humor_count} раз (ожидалось 2-3)")
    
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
    
    # Проверка адаптации под подростка
    teen_words = ['круто', 'прикольн', 'клёв', 'топ', 'крут', 'блогер', 'скилл', 'лидер']
    teen_adaptation = 0
    for r in results:
        if any(word in r['response'].lower() for word in teen_words):
            teen_adaptation += 1
    
    print(f"🛹 Адаптация под подростка: {teen_adaptation}/{len(results)} ответов")
    
    # Проверка обработки конфликта с родителями
    parent_conflict_handled = False
    for r in results:
        if 'родител' in r['message'].lower():
            if any(word in r['response'].lower() for word in ['понима', 'поддерж', 'помож', 'родител']):
                parent_conflict_handled = True
                break
    
    print(f"👨‍👩‍👧 Конфликт с родителями обработан: {'✅' if parent_conflict_handled else '❌'}")
    
    # Проверка на детские формулировки
    childish_words = ['детки', 'малыши', 'ребятки', 'деточки']
    childish_count = 0
    for r in results:
        if any(word in r['response'].lower() for word in childish_words):
            childish_count += 1
    
    print(f"👶 Детские формулировки (нежелательно): {childish_count} раз")
    
    # Оценка успешности
    print(f"\n{'='*60}")
    print("🎯 ОЦЕНКА ТЕСТА:")
    
    success_criteria = [
        ('Юмор в норме', 1 <= humor_count <= 4),
        ('CTA добавлен', cta_count >= 1),
        ('Правильные переходы', 'ready_to_buy' in signals),
        ('Адаптация под подростка', teen_adaptation >= 3),
        ('Конфликт обработан', parent_conflict_handled),
        ('Без детских формулировок', childish_count <= 1)
    ]
    
    passed = 0
    for name, result in success_criteria:
        status = '✅' if result else '❌'
        print(f"{status} {name}")
        if result:
            passed += 1
    
    print(f"\n🏆 Результат: {passed}/{len(success_criteria)} критериев пройдено")
    
    # Сохранение отчёта
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results/teenager_rebel_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Отчёт теста: {scenario['name']}\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**User ID:** {user_id}\n\n")
        f.write(f"## Результаты\n\n")
        f.write(f"- **Юмор:** {humor_count} раз (ожидалось 2-3)\n")
        f.write(f"- **CTA:** {cta_count} раз\n")
        f.write(f"- **Переходы:** {' → '.join(unique_signals)}\n")
        f.write(f"- **Адаптация под подростка:** {teen_adaptation}/{len(results)}\n")
        f.write(f"- **Конфликт с родителями:** {'Обработан' if parent_conflict_handled else 'Не обработан'}\n")
        f.write(f"- **Детские формулировки:** {childish_count}\n\n")
        
        f.write("## Диалог\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"### Сообщение {i}\n\n")
            f.write(f"**🛹 Подросток:** {r['message']}\n\n")
            f.write(f"**🤖 Ukido:** {r['response']}\n\n")
            f.write(f"*Метаданные: intent={r['intent']}, signal={r['user_signal']}, "
                   f"humor={r['humor_generated']}, cta={r['cta_added']}*\n\n")
            f.write("---\n\n")
    
    print(f"\n📁 Отчёт сохранён: {report_file}")

if __name__ == "__main__":
    run_teenager_test()