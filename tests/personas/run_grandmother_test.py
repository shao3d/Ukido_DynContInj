#!/usr/bin/env python3
"""
Запуск теста бабушки-опекуна с традиционными взглядами
"""

import json
import time
import requests
from datetime import datetime

def run_grandmother_test():
    """Запускает тест диалога с бабушкой-скептиком"""
    
    # Загружаем тест
    with open('test_grandmother_skeptic.json', 'r', encoding='utf-8') as f:
        test_data = json.load(f)
    
    scenario = test_data['scenarios'][0]
    dialogue_id = scenario['id']
    user_id = f"{scenario['user_id']}_{int(time.time())}"
    
    print(f"\n{'='*60}")
    print(f"👵 ТЕСТ: {scenario['name']}")
    print(f"📝 ID: {dialogue_id}")
    print(f"👤 User: {user_id}")
    print(f"🎯 Ожидаемые переходы:")
    print(f"   {scenario.get('expected_signal_transition', 'N/A')}")
    print(f"💭 Поколенческий разрыв: ВЫСОКИЙ")
    print(f"{'='*60}\n")
    
    results = []
    
    for i, message in enumerate(scenario['messages'], 1):
        print(f"\n{'─'*50}")
        print(f"💬 Сообщение {i}/{len(scenario['messages'])}")
        print(f"👵 Бабушка: {message[:70]}{'...' if len(message) > 70 else ''}")
        
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
    
    # Проверка простоты языка (избегание англицизмов и техножаргона)
    tech_words = ['онлайн', 'zoom', 'интернет', 'компьютер', 'технолог', 'цифров', 'платформ']
    simple_words = ['понятн', 'прост', 'легк', 'удобн', 'помо', 'покаж', 'объясн']
    
    tech_count = 0
    simple_count = 0
    for r in results:
        response_lower = r['response'].lower()
        tech_count += sum(1 for word in tech_words if word in response_lower)
        simple_count += sum(1 for word in simple_words if word in response_lower)
    
    print(f"\n🗣️ Адаптация языка:")
    print(f"  Технические термины: {tech_count} упоминаний")
    print(f"  Простые объяснения: {simple_count} раз")
    
    # Проверка развеивания мифов
    myth_busting = 0
    myth_phrases = ['на самом деле', 'многие думают', 'это миф', 'важно понимать', 
                    'исследования показ', 'опыт показывает', 'практика показ']
    for r in results:
        if any(phrase in r['response'].lower() for phrase in myth_phrases):
            myth_busting += 1
    
    print(f"\n🎓 Развеивание мифов: {myth_busting} раз")
    
    # Проверка упоминаний социализации
    social_addressed = 0
    social_words = ['общен', 'друз', 'команд', 'группов', 'социализ', 'сверстник']
    for r in results:
        if any(word in r['response'].lower() for word in social_words):
            social_addressed += 1
    
    print(f"👥 Обработка вопросов социализации: {social_addressed} раз")
    
    # Проверка технической поддержки
    tech_support = 0
    support_words = ['помож', 'поддерж', 'научим', 'покажем', 'объясним', 'проведём']
    for r in results:
        if any(word in r['response'].lower() for word in support_words):
            tech_support += 1
    
    print(f"💻 Предложение техподдержки: {tech_support} раз")
    
    # Проверка упоминания традиционных ценностей
    traditional = 0
    trad_words = ['воспитан', 'ценност', 'традиц', 'важно', 'семь', 'забот', 'внимани']
    for r in results:
        if any(word in r['response'].lower() for word in trad_words):
            traditional += 1
    
    print(f"🏛️ Упоминание традиционных ценностей: {traditional} раз")
    
    # Проверка цен
    price_ok = True
    for r in results:
        # Проверяем, что цены корректно отображаются
        if '70 грн' in r['response'] or '28 0 грн' in r['response']:
            price_ok = False
            print("⚠️ ОБНАРУЖЕНА ПРОБЛЕМА С ЦЕНАМИ!")
            break
        if '7000' in r['response'] or '8000' in r['response']:
            print("✅ Цены отображаются корректно")
            break
    
    # Переходы сигналов
    unique_signals = []
    for s in signals:
        if not unique_signals or s != unique_signals[-1]:
            unique_signals.append(s)
    
    print(f"\n🔄 Переходы сигналов:")
    print(f"   {' → '.join(unique_signals)}")
    
    # Оценка качества диалога
    print(f"\n{'='*60}")
    print("🎯 ОЦЕНКА КАЧЕСТВА:")
    
    quality_score = 0
    max_score = 0
    
    # Критерий 1: Простота языка (макс 25 баллов)
    simplicity_score = min(25, simple_count * 5 - tech_count)
    simplicity_score = max(0, simplicity_score)
    quality_score += simplicity_score
    max_score += 25
    print(f"🗣️ Простота языка: {simplicity_score}/25")
    
    # Критерий 2: Развеивание мифов (макс 20 баллов)
    myth_score = min(20, myth_busting * 7)
    quality_score += myth_score
    max_score += 20
    print(f"🎓 Развеивание мифов: {myth_score}/20")
    
    # Критерий 3: Социализация (макс 15 баллов)
    social_score = min(15, social_addressed * 5)
    quality_score += social_score
    max_score += 15
    print(f"👥 Социализация: {social_score}/15")
    
    # Критерий 4: Техподдержка (макс 20 баллов)
    support_score = min(20, tech_support * 4)
    quality_score += support_score
    max_score += 20
    print(f"💻 Техподдержка: {support_score}/20")
    
    # Критерий 5: Традиционные ценности (макс 20 баллов)
    trad_score = min(20, traditional * 4)
    quality_score += trad_score
    max_score += 20
    print(f"🏛️ Традиционные ценности: {trad_score}/20")
    
    # Итоговая оценка
    percentage = quality_score * 100 // max_score
    print(f"\n🏆 ИТОГОВАЯ ОЦЕНКА: {quality_score}/{max_score} ({percentage}%)")
    
    if percentage >= 80:
        print("⭐⭐⭐⭐⭐ ОТЛИЧНО! Система отлично адаптировалась под бабушку")
    elif percentage >= 60:
        print("⭐⭐⭐⭐ ХОРОШО! Система учла возрастные особенности")
    elif percentage >= 40:
        print("⭐⭐⭐ УДОВЛЕТВОРИТЕЛЬНО. Есть проблемы с адаптацией")
    else:
        print("⭐⭐ ТРЕБУЕТ ДОРАБОТКИ. Язык слишком сложный")
    
    # Особые замечания
    print(f"\n📝 ОСОБЫЕ ЗАМЕЧАНИЯ:")
    if 'anxiety_about_child' in signal_counts and signal_counts['anxiety_about_child'] >= 2:
        print("✅ Система правильно распознала тревогу о внучке")
    if 'price_sensitive' in signal_counts:
        print("✅ Система учла финансовые ограничения пенсионерки")
    if not price_ok:
        print("❌ КРИТИЧНО: Проблема с отображением цен!")
    
    # Сохранение отчёта
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"test_results/grandmother_skeptic_{timestamp}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# Отчёт теста: {scenario['name']}\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**User ID:** {user_id}\n\n")
        f.write(f"## Оценка качества: {percentage}%\n\n")
        f.write(f"- **Простота языка:** {simplicity_score}/25\n")
        f.write(f"- **Развеивание мифов:** {myth_score}/20\n")
        f.write(f"- **Социализация:** {social_score}/15\n")
        f.write(f"- **Техподдержка:** {support_score}/20\n")
        f.write(f"- **Традиционные ценности:** {trad_score}/20\n\n")
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
            f.write(f"**Бабушка:** {r['message']}\n\n")
            f.write(f"**Ukido:** {r['response']}\n\n")
            f.write(f"*{signal_emoji} Signal: {r['user_signal']}, Intent: {r['intent']}*\n\n")
            f.write("---\n\n")
    
    print(f"\n📁 Отчёт сохранён: {report_file}")

if __name__ == "__main__":
    run_grandmother_test()