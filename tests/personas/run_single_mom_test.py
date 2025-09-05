#!/usr/bin/env python3
"""
Запуск теста одинокой мамы с СДВГ-ребёнком
"""

import json
import time
import requests
from datetime import datetime
import re

def run_single_mom_test():
    """Запускает тест эмоционально сложного диалога"""
    
    # Загружаем тест
    with open('test_single_mom_adhd.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    scenario = test_data['scenarios'][0]
    dialogue_id = scenario['id']
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    
    print(f"\n{'='*60}")
    print(f"💔 ТЕСТ: {scenario['name']}")
    print(f"📝 ID: {dialogue_id}")
    print(f"👤 User: {user_id}")
    print(f"🎯 Ожидаемые переходы:")
    print(f"   {scenario.get('expected_signal_transition', 'N/A')}")
    print(f"😢 Эмоциональная сложность: ВЫСОКАЯ")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, message in enumerate(scenario['messages'], 1):
        print(f"\n{'─'*50}")
        print(f"💬 Сообщение {i}/{len(scenario['messages'])}")
        print(f"👩 Мама: {message[:70]}{'...' if len(message) > 70 else ''}")
        
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
                
                # Цветовая индикация сигналов
                signal_emoji = {
                    'anxiety_about_child': '😰',
                    'price_sensitive': '💸',
                    'exploring_only': '🔍',
                    'ready_to_buy': '✅'
                }.get(user_signal, '❓')
                
                print(f"🤖 Ukido: {data['response'][:120]}{'...' if len(data['response']) > 120 else ''}")
                print(f"📊 {signal_emoji} Signal: {user_signal} | Intent: {intent}")
                
                results.append({
                    'message': message,
                    'response': data['response'],
                    'intent': intent,
                    'user_signal': user_signal,
                    'humor_generated': humor,
                    'cta_added': cta_added
                })
                
                time.sleep(0.3)
                
            else:
                print(f"❌ Ошибка: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Анализ результатов
    print(f"\n{'='*60}")
    print("📈 АНАЛИЗ РЕЗУЛЬТАТОВ:")
    print(f"{'='*60}")
    
    # Подсчёт сигналов
    signals = [r['user_signal'] for r in results]
    signal_counts = {}
    for s in signals:
        signal_counts[s] = signal_counts.get(s, 0) + 1
    
    print("\n📊 Распределение сигналов:")
    for signal, count in signal_counts.items():
        emoji = {
            'anxiety_about_child': '😰',
            'price_sensitive': '💸',
            'exploring_only': '🔍',
            'ready_to_buy': '✅'
        }.get(signal, '❓')
        print(f"  {emoji} {signal}: {count} раз")
    
    # Проверка эмпатии
    empathy_words = ['понима', 'поддерж', 'помо', 'сочувств', 'сложн', 'труд', 'нелегк', 'опыт']
    empathy_count = 0
    for r in results:
        if any(word in r['response'].lower() for word in empathy_words):
            empathy_count += 1
    
    print(f"\n💙 Эмпатия в ответах: {empathy_count}/{len(results)} ({empathy_count*100//len(results)}%)")
    
    # Проверка упоминаний СДВГ/гиперактивности
    adhd_handled = 0
    for r in results:
        if any(word in r['response'].lower() for word in ['гиперактив', 'сдвг', 'активн', 'энерги', 'подвижн']):
            adhd_handled += 1
    
    print(f"🧠 Обработка СДВГ контекста: {adhd_handled} упоминаний")
    
    # Проверка финансовых решений
    financial_solutions = 0
    for r in results:
        if any(word in r['response'].lower() for word in ['рассрочк', 'скидк', 'пробн', 'бесплатн', 'оплат']):
            financial_solutions += 1
    
    print(f"💰 Финансовые решения предложены: {financial_solutions} раз")
    
    # Переходы сигналов
    unique_signals = []
    for s in signals:
        if not unique_signals or s != unique_signals[-1]:
            unique_signals.append(s)
    
    print(f"\n🔄 Переходы сигналов:")
    print(f"   {' → '.join(unique_signals)}")
    
    # Проверка корректности перехода к ready_to_buy
    if 'ready_to_buy' in signals:
        ready_index = signals.index('ready_to_buy')
        if ready_index == len(signals) - 1 or ready_index == len(signals) - 2:
            print("✅ Переход к ready_to_buy в конце диалога - корректно!")
        else:
            print("⚠️ Преждевременный переход к ready_to_buy")
    
    # Оценка качества диалога
    print(f"\n{'='*60}")
    print("🎯 ОЦЕНКА КАЧЕСТВА:")
    
    quality_score = 0
    max_score = 0
    
    # Критерий 1: Эмпатия (макс 30 баллов)
    empathy_score = min(30, empathy_count * 10)
    quality_score += empathy_score
    max_score += 30
    print(f"💙 Эмпатия: {empathy_score}/30")
    
    # Критерий 2: Обработка СДВГ (макс 20 баллов)
    adhd_score = min(20, adhd_handled * 10)
    quality_score += adhd_score
    max_score += 20
    print(f"🧠 СДВГ контекст: {adhd_score}/20")
    
    # Критерий 3: Финансовые решения (макс 20 баллов)
    finance_score = min(20, financial_solutions * 10)
    quality_score += finance_score
    max_score += 20
    print(f"💰 Финансовая помощь: {finance_score}/20")
    
    # Критерий 4: Правильные сигналы (макс 30 баллов)
    if 'anxiety_about_child' in signal_counts and signal_counts['anxiety_about_child'] >= 2:
        signal_score = 15
    else:
        signal_score = 5
    if 'price_sensitive' in signal_counts:
        signal_score += 10
    if 'ready_to_buy' in signals:
        signal_score += 5
    quality_score += signal_score
    max_score += 30
    print(f"📊 Сигналы: {signal_score}/30")
    
    # Итоговая оценка
    percentage = quality_score * 100 // max_score
    print(f"\n🏆 ИТОГОВАЯ ОЦЕНКА: {quality_score}/{max_score} ({percentage}%)")
    
    if percentage >= 80:
        print("⭐⭐⭐⭐⭐ ОТЛИЧНО! Система проявила высокую эмпатию")
    elif percentage >= 60:
        print("⭐⭐⭐⭐ ХОРОШО! Система адекватно обработала сложную ситуацию")
    elif percentage >= 40:
        print("⭐⭐⭐ УДОВЛЕТВОРИТЕЛЬНО. Есть что улучшить")
    else:
        print("⭐⭐ ТРЕБУЕТ ДОРАБОТКИ. Недостаточно эмпатии")
    
    # Сохранение отчёта
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results/single_mom_adhd_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Отчёт теста: {scenario['name']}\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**User ID:** {user_id}\n\n")
        f.write(f"## Оценка качества: {percentage}%\n\n")
        f.write(f"- **Эмпатия:** {empathy_score}/30\n")
        f.write(f"- **СДВГ контекст:** {adhd_score}/20\n")
        f.write(f"- **Финансовые решения:** {finance_score}/20\n")
        f.write(f"- **Сигналы:** {signal_score}/30\n\n")
        f.write(f"## Переходы сигналов\n\n")
        f.write(f"{' → '.join(unique_signals)}\n\n")
        
        f.write("## Диалог\n\n")
        for i, r in enumerate(results, 1):
            signal_emoji = {
                'anxiety_about_child': '😰',
                'price_sensitive': '💸',
                'exploring_only': '🔍',
                'ready_to_buy': '✅'
            }.get(r['user_signal'], '❓')
            
            f.write(f"### Сообщение {i}\n\n")
            f.write(f"**Мама:** {r['message']}\n\n")
            f.write(f"**Ukido:** {r['response']}\n\n")
            f.write(f"*{signal_emoji} Signal: {r['user_signal']}, Intent: {r['intent']}*\n\n")
            f.write("---\n\n")
    
    print(f"\n📁 Отчёт сохранён: {report_file}")

if __name__ == "__main__":
    run_single_mom_test()