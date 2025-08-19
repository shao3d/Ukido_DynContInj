#!/usr/bin/env python3
"""
Скрипт для захвата ПОЛНЫХ диалогов при тестировании State Machine
Сохраняет все вопросы и ответы в детальный отчет
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def run_and_capture(persona_num):
    """Запускает тест и захватывает полный вывод"""
    import subprocess
    
    # Запускаем тест
    cmd = f"python collaborative_test.py --diverse {persona_num}"
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    full_output = stdout.decode('utf-8', errors='replace')
    
    # Парсим диалог из вывода
    dialogue = {"raw_output": full_output}
    
    # Извлекаем вопросы и ответы
    questions = []
    answers = []
    
    lines = full_output.split('\n')
    for i, line in enumerate(lines):
        if '👤 Вопрос' in line:
            # Следующая строка - вопрос
            if i + 1 < len(lines):
                questions.append(lines[i + 1].strip())
        elif '🤖 Ответ' in line:
            # Собираем многострочный ответ до следующего разделителя
            answer_lines = []
            j = i + 1
            while j < len(lines) and '───' not in lines[j] and '👤' not in lines[j]:
                answer_lines.append(lines[j].strip())
                j += 1
            answers.append('\n'.join(answer_lines))
    
    dialogue['questions'] = questions
    dialogue['answers'] = answers
    
    # Извлекаем метрики
    if 'Общая оценка:' in full_output:
        score_line = [l for l in lines if 'Общая оценка:' in l]
        if score_line:
            try:
                score = float(score_line[0].split(':')[1].split('/')[0].strip())
                dialogue['score'] = score
            except:
                dialogue['score'] = 0.0
    
    return dialogue

async def main():
    """Тестирует все 7 персон и создает полный отчет"""
    
    personas = [
        {"num": 1, "name": "Агрессивный отец Виктор", "expected": "price_sensitive"},
        {"num": 2, "name": "Паническая мама Светлана", "expected": "anxiety_about_child"},
        {"num": 3, "name": "Корпоративный заказчик Елена", "expected": "ready_to_buy"},
        {"num": 4, "name": "Бабушка-опекун Раиса", "expected": "anxiety_about_child"},
        {"num": 5, "name": "Молодая мама-блогер Карина", "expected": "exploring_only"},
        {"num": 6, "name": "Дедушка-скептик Борис", "expected": "exploring_only"},
        {"num": 7, "name": "Многодетная мама Оля", "expected": "price_sensitive"}
    ]
    
    results = []
    
    print("="*80)
    print("ПОЛНОЕ ТЕСТИРОВАНИЕ STATE MACHINE V0.9.1")
    print("="*80)
    
    for p in personas:
        print(f"\n▶️ Тестирую персону {p['num']}: {p['name']}...")
        dialogue = await run_and_capture(p['num'])
        
        results.append({
            "persona": p,
            "dialogue": dialogue
        })
        
        print(f"✅ Завершено. Оценка: {dialogue.get('score', 'N/A')}/10")
        print(f"   Вопросов: {len(dialogue.get('questions', []))}")
        print(f"   Ответов: {len(dialogue.get('answers', []))}")
        
        # Небольшая пауза между тестами
        await asyncio.sleep(2)
    
    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"tests/reports/state_machine_FULL_DIALOGUES_{timestamp}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Результаты сохранены в {output_file}")
    
    # Вычисляем средний балл
    scores = [r['dialogue'].get('score', 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА:")
    print(f"   Средний балл: {avg_score:.1f}/10")
    print(f"   Лучший результат: {max(scores):.1f}/10")
    print(f"   Худший результат: {min(scores):.1f}/10")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())