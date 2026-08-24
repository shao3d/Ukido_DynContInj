#!/usr/bin/env python3
"""
Запуск продвинутых тестовых сценариев для проверки:
- Переходов между состояниями
- Длинных диалогов
- Комбинированных сигналов
- Конфликтных ситуаций
- Групповых записей
"""

import json
import sys
import asyncio
import os
from pathlib import Path
from typing import List, Dict, Any

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Импортируем необходимые компоненты
from src.router import Router
from src.response_generator import ResponseGenerator
from src.history_manager import HistoryManager
from src.social_state import SocialStateManager
from src.standard_responses import get_social_response

# Инициализируем компоненты
router = Router(use_cache=True)
response_generator = ResponseGenerator()
history_manager = HistoryManager()
social_state = SocialStateManager()

async def process_message(message: str, history: List[Dict], user_id: str):
    """Обрабатывает сообщение через полный pipeline"""
    # Вызываем Router
    router_result = await router.route(message, history, user_id)
    
    # Генерируем ответ через настроенную модель, если нужно
    if router_result.status == "success":
        response = await response_generator.generate(
            questions=router_result.decomposed_questions,
            selected_docs=router_result.selected_documents,
            user_signal=router_result.user_signal,
            original_message=message
        )
        final_response = response
    elif router_result.status == "offtopic":
        # Используем заготовленные фразы для offtopic
        final_response = get_social_response(router_result.social_context)
    else:
        # need_simplification
        final_response = "Пожалуйста, задавайте не более трёх вопросов за раз."
    
    return {
        'response': final_response,
        'router_result': router_result
    }

# Цветной вывод
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def load_test_scenarios() -> List[Dict[str, Any]]:
    """Загружает тестовые сценарии из JSON файла"""
    test_file = Path("tests/test_advanced_dialogues.json")
    
    if not test_file.exists():
        print(f"{Colors.RED}❌ Файл {test_file} не найден{Colors.END}")
        return []
    
    with open(test_file, 'r', encoding='utf-8') as f:
        return json.load(f)

async def run_scenario(scenario: Dict[str, Any], scenario_num: int) -> Dict[str, Any]:
    """Запускает один тестовый сценарий"""
    print(f"\n{Colors.HEADER}{'='*80}")
    print(f"СЦЕНАРИЙ #{scenario_num}: {scenario['scenario_name'].upper()}")
    print(f"{'='*80}{Colors.END}")
    print(f"{Colors.DIM}{scenario['description']}{Colors.END}")
    
    # Ожидаемые сигналы
    if 'expected_signal_progression' in scenario:
        print(f"{Colors.DIM}Ожидаемая прогрессия: {' → '.join(scenario['expected_signal_progression'])}{Colors.END}")
    elif 'expected_signal' in scenario:
        print(f"{Colors.DIM}Ожидаемый сигнал: {scenario['expected_signal']}{Colors.END}")
        if 'secondary_signal' in scenario:
            print(f"{Colors.DIM}Вторичный сигнал: {scenario['secondary_signal']}{Colors.END}")
    
    # История диалога
    history = []
    results = []
    detected_signals = []
    
    # Проходим по всем шагам
    for i, step in enumerate(scenario['steps'], 1):
        print(f"\n{Colors.BLUE}━━━ Сообщение {i}/{len(scenario['steps'])} ━━━{Colors.END}")
        print(f"{Colors.BOLD}👤 User:{Colors.END} {step}")
        
        print(f"{Colors.DIM}━━━ Pipeline Start ━━━{Colors.END}")
        
        # Обрабатываем сообщение
        result = await process_message(
            step, 
            history, 
            user_id=f"test_advanced_{scenario_num}"
        )
        
        # Сохраняем сигнал
        if result['router_result'].user_signal:
            detected_signals.append(result['router_result'].user_signal)
        
        # Добавляем в историю
        history.append({"role": "user", "content": step})
        history.append({"role": "assistant", "content": result['response']})
        
        # Показываем ответ (первые 500 символов)
        response_preview = result['response'][:500]
        if len(result['response']) > 500:
            response_preview += "..."
        
        print(f"\n{Colors.GREEN}🤖 Bot:{Colors.END} {response_preview}")
        
        # Анализ результата
        router_result = result['router_result']
        print(f"\n{Colors.CYAN}📊 Анализ:{Colors.END}")
        print(f"  • Router status: {router_result.status}")
        if router_result.user_signal:
            print(f"  • Signal: {router_result.user_signal}")
        if router_result.social_context:
            print(f"  • Social: {router_result.social_context}")
        if router_result.decomposed_questions:
            print(f"  • Вопросы: {router_result.decomposed_questions[:2]}...")
        
        print(f"{Colors.DIM}{'─'*80}{Colors.END}")
        
        results.append({
            'step': i,
            'message': step,
            'signal': router_result.user_signal,
            'status': router_result.status,
            'response_length': len(result['response'])
        })
    
    # Финальный анализ
    print(f"\n{Colors.YELLOW}📈 ИТОГОВЫЙ АНАЛИЗ:{Colors.END}")
    
    # Проверка прогрессии сигналов
    if 'expected_signal_progression' in scenario:
        expected = scenario['expected_signal_progression']
        # Выравниваем длину для сравнения
        detected_aligned = detected_signals[:len(expected)]
        matches = sum(1 for e, d in zip(expected, detected_aligned) if e == d)
        accuracy = (matches / len(expected)) * 100 if expected else 0
        
        print(f"  • Ожидалось: {' → '.join(expected)}")
        print(f"  • Получено:  {' → '.join(detected_signals)}")
        print(f"  • Точность прогрессии: {accuracy:.0f}%")
        
        if accuracy == 100:
            print(f"  {Colors.GREEN}✅ Переходы состояний отработали идеально!{Colors.END}")
        elif accuracy >= 80:
            print(f"  {Colors.YELLOW}⚠️ Переходы в целом корректны, есть отклонения{Colors.END}")
        else:
            print(f"  {Colors.RED}❌ Переходы состояний работают некорректно{Colors.END}")
    
    # Проверка длинных диалогов
    if len(scenario['steps']) >= 12:
        print(f"  • Длина диалога: {len(scenario['steps'])} сообщений")
        signal_changes = sum(1 for i in range(1, len(detected_signals)) 
                           if detected_signals[i] != detected_signals[i-1])
        print(f"  • Изменений сигнала: {signal_changes}")
        
        if signal_changes > 5:
            print(f"  {Colors.YELLOW}⚠️ Слишком частая смена сигналов (нестабильность){Colors.END}")
        else:
            print(f"  {Colors.GREEN}✅ Сигналы стабильны в длинном диалоге{Colors.END}")
    
    # Проверка комбинированных сигналов
    if 'secondary_signal' in scenario:
        primary = scenario['expected_signal']
        secondary = scenario['secondary_signal']
        has_primary = primary in detected_signals
        has_secondary = secondary in detected_signals
        
        if has_primary and has_secondary:
            print(f"  {Colors.GREEN}✅ Оба сигнала детектированы: {primary} + {secondary}{Colors.END}")
        elif has_primary:
            print(f"  {Colors.YELLOW}⚠️ Только основной сигнал: {primary}{Colors.END}")
        else:
            print(f"  {Colors.RED}❌ Сигналы не определены корректно{Colors.END}")
    
    print(f"\n{Colors.GREEN}✅ Сценарий #{scenario_num} завершён{Colors.END}")
    
    return {
        'scenario': scenario['scenario_name'],
        'detected_signals': detected_signals,
        'expected_signals': scenario.get('expected_signal_progression', [scenario.get('expected_signal', 'unknown')]),
        'steps_count': len(scenario['steps']),
        'results': results
    }

async def main():
    """Основная функция запуска тестов"""
    print(f"{Colors.BOLD}🚀 Запуск продвинутых тестовых сценариев{Colors.END}")
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        # Запуск конкретного сценария
        scenario_num = int(sys.argv[1])
        scenarios = load_test_scenarios()
        
        if 1 <= scenario_num <= len(scenarios):
            scenario = scenarios[scenario_num - 1]
            await run_scenario(scenario, scenario_num)
        else:
            print(f"{Colors.RED}❌ Сценарий #{scenario_num} не найден. Доступно: 1-{len(scenarios)}{Colors.END}")
    else:
        # Запуск всех сценариев
        scenarios = load_test_scenarios()
        print(f"Загружено {len(scenarios)} тестовых сценариев\n")
        
        all_results = []
        for i, scenario in enumerate(scenarios, 1):
            result = await run_scenario(scenario, i)
            all_results.append(result)
            
            # Пауза между сценариями
            if i < len(scenarios):
                print(f"\n{Colors.DIM}Пауза перед следующим сценарием...{Colors.END}")
                await asyncio.sleep(2)
        
        # Финальная статистика
        print(f"\n{Colors.HEADER}{'='*80}")
        print(f"ФИНАЛЬНАЯ СТАТИСТИКА")
        print(f"{'='*80}{Colors.END}")
        
        # Подсчёт успешных переходов
        transition_scenarios = [r for r in all_results if len(r['expected_signals']) > 1]
        if transition_scenarios:
            print(f"\n{Colors.CYAN}Переходы состояний:{Colors.END}")
            for result in transition_scenarios:
                expected = result['expected_signals']
                detected = result['detected_signals'][:len(expected)]
                matches = sum(1 for e, d in zip(expected, detected) if e == d)
                accuracy = (matches / len(expected)) * 100
                
                status = "✅" if accuracy >= 80 else "⚠️" if accuracy >= 60 else "❌"
                print(f"  {status} {result['scenario']}: {accuracy:.0f}%")
        
        # Статистика по длинным диалогам
        long_dialogues = [r for r in all_results if r['steps_count'] >= 12]
        if long_dialogues:
            print(f"\n{Colors.CYAN}Длинные диалоги (12+ сообщений):{Colors.END}")
            for result in long_dialogues:
                print(f"  • {result['scenario']}: {result['steps_count']} сообщений")
        
        print(f"\n{Colors.GREEN}✅ Все тесты завершены!{Colors.END}")

if __name__ == "__main__":
    asyncio.run(main())
