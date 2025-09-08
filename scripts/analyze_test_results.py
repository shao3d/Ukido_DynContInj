#!/usr/bin/env python3
"""
Анализатор результатов тестирования роутера
Показывает детальную статистику по каждому диалогу и каждому вопросу
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
import glob

def load_latest_results() -> Dict:
    """Загружает последний файл с результатами тестирования"""
    base_dir = Path(__file__).parent
    reports_dir = base_dir / "tests" / "reports"
    result_files = list(reports_dir.glob("test_results_*.json"))
    if not result_files:
        print("❌ Не найдено файлов с результатами тестирования!")
    print("   Сначала запустите tests/test_router_with_report.py")
    return None
    # Берем самый свежий по времени модификации
    latest_file = max(result_files, key=lambda p: p.stat().st_mtime)
    print(f"📄 Загружаю результаты из: {latest_file}")
    
    with open(latest_file, "r", encoding="utf-8") as f:
        return json.load(f)

def print_detailed_analysis(results: List[Dict]):
    """Выводит детальный анализ каждого диалога"""
    
    print("\n" + "="*80)
    print("📊 ДЕТАЛЬНАЯ СТАТИСТИКА ПО КАЖДОМУ ДИАЛОГУ")
    print("="*80)
    
    for scenario_num, scenario in enumerate(results, 1):
        print(f"\n{'='*80}")
        print(f"🎬 ДИАЛОГ #{scenario_num}: {scenario['name']}")
        print(f"{'='*80}")
        
        success_emoji = "✅" if scenario['success'] else "❌"
        print(f"\nСтатус диалога: {success_emoji} {'Успешно' if scenario['success'] else 'С ошибками'}")
        print(f"Количество шагов: {len(scenario['steps'])}")
        
        # Статистика по статусам в диалоге
        status_counts = {}
        for step in scenario['steps']:
            status = step.get('router_status', 'error')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"\n📈 Распределение ответов роутера:")
        for status, count in status_counts.items():
            percentage = (count / len(scenario['steps']) * 100)
            print(f"   • {status}: {count} ({percentage:.0f}%)")
        
        # Детали по каждому шагу
        print(f"\n📝 ДЕТАЛИ ПО КАЖДОМУ ВОПРОСУ:")
        print("-" * 80)
        
        for step in scenario['steps']:
            step_num = step['step']
            user_msg = step['user_message']
            router_response = step.get('router_response', {})
            router_status = step.get('router_status', 'error')
            
            # Эмодзи для статуса
            status_emoji = {
                'success': '✅',
                'offtopic': '❓',
                'need_simplification': '🔄',
                'error': '❌'
            }.get(router_status, '⚠️')
            
            print(f"\n🔹 ШАГ {step_num}:")
            print(f"   👤 Вопрос: {user_msg[:100]}{'...' if len(user_msg) > 100 else ''}")
            print(f"   {status_emoji} Статус роутера: {router_status}")
            
            # Детали ответа в зависимости от статуса
            if router_status == 'success':
                documents = router_response.get('documents', [])
                if documents:
                    print(f"   📚 Подобранные документы:")
                    for doc in documents:
                        print(f"      • {doc}")
                else:
                    print(f"   ⚠️ Документы не указаны")
                    
            elif router_status in ['offtopic', 'need_simplification']:
                message = router_response.get('message', '')
                if message:
                    print(f"   💬 Сообщение роутера:")
                    # Разбиваем длинное сообщение на строки
                    words = message.split()
                    line = "      "
                    for word in words:
                        if len(line) + len(word) > 75:
                            print(line)
                            line = "      " + word
                        else:
                            line += " " + word if line != "      " else word
                    if line.strip():
                        print(line)
            
            # Печать декомпозиции вопросов (если есть)
            decomposed = router_response.get('decomposed_questions') or []
            if isinstance(decomposed, list) and decomposed:
                print(f"   🔍 Декомпозиция вопросов:")
                for i, q in enumerate(decomposed, 1):
                    # Ограничиваем длину строки для читабельности
                    q_str = str(q)
                    q_str_short = (q_str[:100] + '...') if len(q_str) > 100 else q_str
                    print(f"      {i}. {q_str_short}")

            elif 'error' in step:
                print(f"   ❌ Ошибка: {step['error']}")
        
        print("-" * 80)
        
        # Сводка по использованным документам в диалоге
        docs_usage = {}
        for step in scenario['steps']:
            if step.get('router_status') == 'success':
                for doc in step.get('router_response', {}).get('documents', []):
                    docs_usage[doc] = docs_usage.get(doc, 0) + 1
        
        if docs_usage:
            print(f"\n📚 ИСПОЛЬЗОВАНИЕ ДОКУМЕНТОВ В ДИАЛОГЕ:")
            for doc, count in sorted(docs_usage.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {doc}: {count} раз(а)")

def print_overall_statistics(results: List[Dict]):
    """Выводит общую статистику по всем диалогам"""
    
    print(f"\n{'='*80}")
    print("📊 ОБЩАЯ СТАТИСТИКА ПО ВСЕМ ДИАЛОГАМ")
    print("="*80)
    
    total_scenarios = len(results)
    successful = sum(1 for r in results if r["success"])
    total_steps = sum(len(r["steps"]) for r in results)
    
    print(f"\n📋 Основные показатели:")
    print(f"   • Всего диалогов: {total_scenarios}")
    print(f"   • Успешных диалогов: {successful} ({successful/total_scenarios*100:.0f}%)")
    print(f"   • Всего вопросов: {total_steps}")
    
    # Общая статистика по статусам
    all_statuses = {}
    for scenario in results:
        for step in scenario["steps"]:
            status = step.get("router_status", "error")
            all_statuses[status] = all_statuses.get(status, 0) + 1
    
    print(f"\n📈 Распределение ответов роутера (всего {total_steps} вопросов):")
    for status, count in sorted(all_statuses.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_steps * 100)
        emoji = {
            'success': '✅',
            'offtopic': '❓',
            'need_simplification': '🔄',
            'error': '❌'
        }.get(status, '⚠️')
        print(f"   {emoji} {status}: {count} ({percentage:.1f}%)")
    
    # Топ документов
    all_docs = {}
    for scenario in results:
        for step in scenario["steps"]:
            if step.get("router_status") == "success":
                for doc in step.get("router_response", {}).get("documents", []):
                    all_docs[doc] = all_docs.get(doc, 0) + 1
    
    if all_docs:
        print(f"\n📚 ТОП-10 наиболее используемых документов:")
        for i, (doc, count) in enumerate(sorted(all_docs.items(), key=lambda x: x[1], reverse=True)[:10], 1):
            print(f"   {i:2}. {doc}: {count} раз(а)")
    
    # Статистика по диалогам с ошибками
    failed_scenarios = [s for s in results if not s["success"]]
    if failed_scenarios:
        print(f"\n⚠️ Диалоги с ошибками:")
        for scenario in failed_scenarios:
            print(f"   • {scenario['name']}")

def main():
    """Главная функция"""
    print("╔" + "═"*78 + "╗")
    print("║" + " АНАЛИЗАТОР РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ РОУТЕРА ".center(78) + "║")
    print("╚" + "═"*78 + "╝")
    print("Подготовьте результаты, запустив tests/test_router_with_report.py (создаёт tests/reports/test_results_*.json)")
    
    # Загружаем результаты
    results = load_latest_results()
    if not results:
        return
    
    print(f"✅ Загружено {len(results)} диалогов")
    
    # Выводим детальный анализ
    print_detailed_analysis(results)
    
    # Выводим общую статистику
    print_overall_statistics(results)
    
    print(f"\n{'='*80}")
    print("✨ Анализ завершен!")
    print("="*80)

if __name__ == "__main__":
    main()