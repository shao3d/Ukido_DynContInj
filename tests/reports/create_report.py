import re
import os

# Читаем все файлы с результатами
personas = [
    ("1", "Экономная мама Оксана", "price_sensitive"),
    ("2", "Тревожная бабушка Валентина", "anxiety_about_child"),
    ("3", "Решительный папа Андрей", "ready_to_buy"),
    ("4", "Любопытная тётя Наташа", "exploring_only"),
    ("5", "Скептик-переговорщик Игорь", "price_sensitive"),
    ("6", "Заботливая мама первенца Юлия", "anxiety_about_child"),
    ("7", "Занятой бизнесмен Максим", "ready_to_buy")
]

def extract_dialogue(content):
    """Извлекает диалог из содержимого файла"""
    dialogue_start = content.find("СЕКЦИЯ 1: ПОЛНЫЕ ВОПРОСЫ И ОТВЕТЫ")
    dialogue_end = content.find("СЕКЦИЯ 2: МЕТРИКИ")
    if dialogue_start != -1 and dialogue_end != -1:
        dialogue = content[dialogue_start:dialogue_end]
        # Очищаем от ANSI кодов
        dialogue = re.sub(r'\x1b\[[0-9;]*m', '', dialogue)
        return dialogue.strip()
    return ""

def extract_metrics(content):
    """Извлекает метрики из содержимого файла"""
    metrics_start = content.find("СЕКЦИЯ 2: МЕТРИКИ")
    metrics_end = content.find("СЕКЦИЯ 3: АНАЛИЗ")
    if metrics_start != -1 and metrics_end != -1:
        metrics = content[metrics_start:metrics_end]
        # Очищаем от ANSI кодов
        metrics = re.sub(r'\x1b\[[0-9;]*m', '', metrics)
        return metrics.strip()
    return ""

def extract_state_machine_analysis(content):
    """Извлекает анализ State Machine"""
    analysis_start = content.find("🎯 АНАЛИЗ STATE MACHINE")
    if analysis_start != -1:
        analysis = content[analysis_start:]
        # Ищем итоговую оценку
        score_match = re.search(r'Общая оценка: ([\d.]+)/10', analysis)
        score = score_match.group(1) if score_match else "N/A"
        
        # Ищем точность определения
        accuracy_match = re.search(r'Точность: ([\d.]+)%', analysis)
        accuracy = accuracy_match.group(1) if accuracy_match else "N/A"
        
        # Очищаем от ANSI кодов
        analysis = re.sub(r'\x1b\[[0-9;]*m', '', analysis)
        
        return analysis.strip(), score, accuracy
    return "", "N/A", "N/A"

# Создаем итоговый отчет
report = []
summary_data = []

for num, name, expected_type in personas:
    file_path = f"tests/reports/temp_persona_{num}.txt"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        dialogue = extract_dialogue(content)
        metrics = extract_metrics(content)
        analysis, score, accuracy = extract_state_machine_analysis(content)
        
        summary_data.append({
            'num': num,
            'name': name,
            'type': expected_type,
            'score': score,
            'accuracy': accuracy
        })
        
        # Добавляем в отчет
        report.append(f"## Персонаж {num}: {name}")
        report.append(f"**Ожидаемый тип**: {expected_type}")
        report.append(f"**Итоговая оценка**: {score}/10")
        report.append(f"**Точность определения**: {accuracy}%")
        report.append("")
        
        if dialogue:
            report.append("### Полный диалог")
            report.append("```")
            report.append(dialogue)
            report.append("```")
            report.append("")
        
        if metrics:
            report.append("### Метрики")
            report.append("```")
            report.append(metrics)
            report.append("```")
            report.append("")
        
        if analysis:
            report.append("### Анализ State Machine")
            report.append("```")
            report.append(analysis)
            report.append("```")
            report.append("")
        
        report.append("---")
        report.append("")

# Создаем сводную таблицу
summary_table = ["## 📊 Сводная таблица результатов", ""]
summary_table.append("| # | Персонаж | Ожидаемый тип | Точность | Оценка |")
summary_table.append("|---|----------|---------------|----------|--------|")

total_score = 0
valid_scores = 0

for data in summary_data:
    summary_table.append(f"| {data['num']} | {data['name']} | {data['type']} | {data['accuracy']}% | **{data['score']}/10** |")
    try:
        score_float = float(data['score'])
        total_score += score_float
        valid_scores += 1
    except:
        pass

if valid_scores > 0:
    avg_score = total_score / valid_scores
    summary_table.append("")
    summary_table.append(f"**Средняя оценка State Machine: {avg_score:.1f}/10**")

# Собираем финальный отчет
final_report = "\n".join(summary_table) + "\n\n---\n\n" + "\n".join(report)

print(final_report)
