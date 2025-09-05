#!/usr/bin/env python3
"""
Запуск теста весёлого папы-айтишника для активации юмора Жванецкого
"""

import json
import time
import requests
from datetime import datetime

def run_funny_dad_test():
    """Запускает тест для максимальной активации юмора"""
    
    # Загружаем тест
    with open('test_funny_it_dad.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    scenario = test_data['scenarios'][0]
    dialogue_id = scenario['id']
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    
    print(f"\n{'='*60}")
    print(f"😂 ТЕСТ: {scenario['name']}")
    print(f"📝 ID: {dialogue_id}")
    print(f"👤 User: {user_id}")
    print(f"🎯 Цель: АКТИВИРОВАТЬ ЮМОР ЖВАНЕЦКОГО")
    print(f"🎪 Ожидаемый юмор: {scenario.get('expected_humor', 'N/A')}")
    print(f"{'='*60}\n")
    
    results = []
    humor_count = 0
    
    for i, message in enumerate(scenario['messages'], 1):
        print(f"\n{'─'*50}")
        print(f"💬 Сообщение {i}/{len(scenario['messages'])}")
        print(f"🤪 Папа: {message[:70]}{'...' if len(message) > 70 else ''}")
        
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
                
                # Увеличиваем счётчик юмора
                if humor:
                    humor_count += 1
                
                # Эмодзи для юмора
                humor_emoji = "🎭 ЮМОР!" if humor else ""
                
                # Цветовая индикация intent
                intent_emoji = {
                    'success': '✅',
                    'offtopic': '🎪',
                    'need_simplification': '🤔'
                }.get(intent, '❓')
                
                print(f"🤖 Ukido: {data['response'][:120]}{'...' if len(data['response']) > 120 else ''}")
                print(f"📊 {intent_emoji} Intent: {intent} | Signal: {user_signal} {humor_emoji}")
                
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
    print("🎭 АНАЛИЗ ЮМОРА:")
    print(f"{'='*60}")
    
    # Общая статистика юмора
    print(f"\n📊 СТАТИСТИКА ЮМОРА:")
    print(f"  🎭 Всего шуток: {humor_count} из {len(results)}")
    print(f"  📈 Процент юмора: {humor_count * 100 // len(results)}%")
    
    # Детальный анализ каждой шутки
    humor_messages = []
    standard_responses = []
    for i, r in enumerate(results, 1):
        if r['humor_generated']:
            humor_messages.append((i, r['message'][:50], r['response'][:100]))
        elif r['intent'] == 'offtopic' and not r['humor_generated']:
            standard_responses.append((i, r['response'][:100]))
    
    if humor_messages:
        print(f"\n🎪 СГЕНЕРИРОВАННЫЙ ЮМОР:")
        for num, trigger, joke in humor_messages:
            print(f"  #{num}: Триггер: {trigger}...")
            print(f"        Шутка: {joke}...")
    
    if standard_responses:
        print(f"\n📝 СТАНДАРТНЫЕ ОТВЕТЫ НА OFFTOPIC (без юмора):")
        for num, response in standard_responses:
            print(f"  #{num}: {response}...")
    
    # Анализ intent'ов
    intents = {}
    for r in results:
        intent = r['intent']
        intents[intent] = intents.get(intent, 0) + 1
    
    print(f"\n📈 РАСПРЕДЕЛЕНИЕ INTENT'ов:")
    for intent, count in intents.items():
        print(f"  {intent}: {count} раз")
    
    # Анализ сигналов
    signals = {}
    for r in results:
        signal = r['user_signal']
        signals[signal] = signals.get(signal, 0) + 1
    
    print(f"\n🚦 РАСПРЕДЕЛЕНИЕ СИГНАЛОВ:")
    for signal, count in signals.items():
        print(f"  {signal}: {count} раз")
    
    # Проверка блокировок юмора
    print(f"\n🚫 АНАЛИЗ БЛОКИРОВОК:")
    blocked_signals = ['anxiety_about_child', 'price_sensitive']
    blocks_found = False
    for signal in blocked_signals:
        if signal in signals:
            print(f"  ⚠️ Обнаружен блокирующий сигнал: {signal} ({signals[signal]} раз)")
            blocks_found = True
    if not blocks_found:
        print(f"  ✅ Блокирующие сигналы НЕ обнаружены - юмор должен работать!")
    
    # Проверка Rate Limiting
    print(f"\n⏱️ RATE LIMITING:")
    if humor_count <= 3:
        print(f"  ✅ Rate limiting соблюдён (max 3 шутки в час)")
    else:
        print(f"  ⚠️ Превышен лимит! {humor_count} > 3 шуток")
    
    # Итоговая оценка
    print(f"\n{'='*60}")
    print("🏆 ИТОГОВАЯ ОЦЕНКА ЮМОРА:")
    print(f"{'='*60}")
    
    if humor_count >= 3:
        print("⭐⭐⭐⭐⭐ ОТЛИЧНО! Жванецкий в деле! 🎭")
        print("Система активно генерирует юмор на абсурдные вопросы")
    elif humor_count >= 2:
        print("⭐⭐⭐⭐ ХОРОШО! Юмор работает")
        print("Система периодически шутит")
    elif humor_count >= 1:
        print("⭐⭐⭐ УДОВЛЕТВОРИТЕЛЬНО. Юмор еле жив")
        print("Система редко активирует юмор")
    else:
        print("⭐⭐ ПРОВАЛ! Юмор не активировался 😢")
        print("Проверьте блокировки и вероятности")
    
    # Дополнительная диагностика
    print(f"\n📋 ДИАГНОСТИКА:")
    offtopic_count = intents.get('offtopic', 0)
    print(f"  Offtopic сообщений: {offtopic_count}")
    print(f"  Вероятность юмора: 33%")
    print(f"  Ожидаемый юмор: ~{offtopic_count * 33 // 100} шуток")
    print(f"  Фактический юмор: {humor_count} шуток")
    
    if humor_count < offtopic_count * 0.2:  # Меньше 20% от ожидаемого
        print(f"\n  ⚠️ ПРОБЛЕМА: Юмор срабатывает реже ожидаемого!")
        print(f"  Возможные причины:")
        print(f"  1. Сработали блокировки (anxiety/price_sensitive)")
        print(f"  2. Pure social states блокируют юмор")
        print(f"  3. Rate limiting (max 3 в час)")
        print(f"  4. Random не в нашу пользу")
    
    # Сохранение отчёта
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results/funny_dad_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Отчёт теста: {scenario['name']}\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**User ID:** {user_id}\n\n")
        f.write(f"## Статистика юмора\n\n")
        f.write(f"- **Всего шуток:** {humor_count}/{len(results)}\n")
        f.write(f"- **Процент юмора:** {humor_count * 100 // len(results)}%\n")
        f.write(f"- **Offtopic сообщений:** {offtopic_count}\n")
        f.write(f"- **Блокировки:** {'Да' if blocks_found else 'Нет'}\n\n")
        
        f.write("## Диалог\n\n")
        for i, r in enumerate(results, 1):
            humor_mark = " 🎭 **[ЮМОР АКТИВИРОВАН]**" if r['humor_generated'] else ""
            
            f.write(f"### Сообщение {i}{humor_mark}\n\n")
            f.write(f"**Папа:** {r['message']}\n\n")
            f.write(f"**Ukido:** {r['response']}\n\n")
            f.write(f"*Intent: {r['intent']}, Signal: {r['user_signal']}*\n\n")
            f.write("---\n\n")
    
    print(f"\n📁 Отчёт сохранён: {report_file}")

if __name__ == "__main__":
    run_funny_dad_test()