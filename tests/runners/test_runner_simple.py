#!/usr/bin/env python3
"""
Простой запуск тестов через песочницу - по одному сценарию за раз
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Импортируем песочницу
from sandbox_v2 import SandboxV2, Colors

async def run_one_scenario(scenario_num: int = 1, use_advanced: bool = False):
    """Запускает один сценарий из выбранного JSON файла"""
    
    # Выбираем файл с тестами
    test_file = "tests/test_advanced_dialogues.json" if use_advanced else "tests/test_comprehensive_dialogues.json"
    
    # Загружаем тесты
    with open(test_file, 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    if scenario_num < 1 or scenario_num > len(scenarios):
        print(f"❌ Сценарий {scenario_num} не найден. Доступно: 1-{len(scenarios)}")
        return
    
    scenario = scenarios[scenario_num - 1]
    sandbox = SandboxV2()
    
    print(f"{Colors.HEADER}{'='*80}")
    print(f"СЦЕНАРИЙ #{scenario_num}: {scenario['scenario_name']}")
    print(f"{'='*80}{Colors.ENDC}")
    print(f"{Colors.DIM}Описание: {scenario['description']}{Colors.ENDC}")
    
    # Показываем ожидаемые сигналы
    if 'expected_signal_progression' in scenario:
        print(f"{Colors.DIM}Ожидаемая прогрессия: {' → '.join(scenario['expected_signal_progression'])}{Colors.ENDC}")
    elif 'expected_signal' in scenario:
        print(f"{Colors.DIM}Ожидаемый сигнал: {scenario['expected_signal']}{Colors.ENDC}")
    if 'secondary_signal' in scenario:
        print(f"{Colors.DIM}Вторичный сигнал: {scenario['secondary_signal']}{Colors.ENDC}")
    
    print()
    
    user_id = f"test_user_{scenario_num}"
    
    for i, message in enumerate(scenario['steps'], 1):
        print(f"\n{Colors.BLUE}━━━ Сообщение {i}/{len(scenario['steps'])} ━━━{Colors.ENDC}")
        print(f"{Colors.BOLD}👤 User:{Colors.ENDC} {message}")
        
        # Обрабатываем сообщение через песочницу
        result = await sandbox.process_message(message, user_id, show_details=True)
        
        # Показываем ответ
        print(f"\n{Colors.GREEN}🤖 Bot:{Colors.ENDC} {result.response}")
        
        # Показываем анализ
        print(f"\n{Colors.CYAN}📊 Анализ:{Colors.ENDC}")
        print(f"  • Router status: {result.router_status}")
        if result.social_context:
            print(f"  • Social context: {result.social_context}")
        if result.questions:
            print(f"  • Вопросы: {result.questions}")
        if result.documents:
            print(f"  • Документы: {', '.join([d.split('/')[-1].replace('.md', '') for d in result.documents])}")
        print(f"  • Время: Router {result.router_time:.2f}s, Generator {result.generator_time:.2f}s")
        
        # Валидация (если нужно)
        validation = sandbox.validate_result(result)
        if hasattr(validation, 'warnings') and validation.warnings:
            print(f"\n{Colors.YELLOW}⚠️ Предупреждения:{Colors.ENDC}")
            for warning in validation.warnings:
                print(f"  • {warning}")
        elif hasattr(validation, 'checks'):
            # Показываем проверки если есть проблемы
            problems = [c for c in validation.checks if "❌" in c or "⚠️" in c]
            if problems:
                print(f"\n{Colors.YELLOW}⚠️ Проверки:{Colors.ENDC}")
                for check in problems:
                    print(f"  {check}")
        
        print(f"\n{Colors.DIM}{'─'*80}{Colors.ENDC}")
        
        # Небольшая пауза для читаемости
        await asyncio.sleep(0.1)
    
    print(f"\n{Colors.GREEN}✅ Сценарий #{scenario_num} завершён{Colors.ENDC}\n")

async def main():
    # Проверяем флаг --advanced
    use_advanced = '--advanced' in sys.argv
    if use_advanced:
        sys.argv.remove('--advanced')
    
    if len(sys.argv) > 1:
        try:
            scenario_num = int(sys.argv[1])
            await run_one_scenario(scenario_num, use_advanced)
        except ValueError:
            print("Использование: python test_runner_simple.py [номер_сценария] [--advanced]")
            print("Например: python test_runner_simple.py 1")
            print("         python test_runner_simple.py 1 --advanced")
    else:
        # По умолчанию запускаем первый
        await run_one_scenario(1, use_advanced)

if __name__ == "__main__":
    asyncio.run(main())