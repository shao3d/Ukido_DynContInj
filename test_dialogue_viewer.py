#!/usr/bin/env python3
"""
Показывает полные диалоги - вопрос и ответ
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox_v2 import SandboxV2, Colors

async def show_dialogue(scenario_num: int = 1):
    """Показывает полный диалог для сценария"""
    
    # Загружаем тесты
    with open("tests/test_comprehensive_dialogues.json", 'r', encoding='utf-8') as f:
        scenarios = json.load(f)
    
    if scenario_num < 1 or scenario_num > len(scenarios):
        print(f"❌ Сценарий {scenario_num} не найден. Доступно: 1-{len(scenarios)}")
        return
    
    scenario = scenarios[scenario_num - 1]
    sandbox = SandboxV2()
    
    print(f"\n{'='*80}")
    print(f"СЦЕНАРИЙ #{scenario_num}: {scenario['scenario_name']}")
    print(f"Ожидаемый сигнал: {scenario['expected_signal']}")
    print(f"{'='*80}\n")
    
    user_id = f"test_user_{scenario_num}"
    all_messages = []
    
    for i, message in enumerate(scenario['steps'], 1):
        # Обрабатываем сообщение
        result = await sandbox.process_message(message, user_id, show_details=False)
        
        # Сохраняем для вывода
        all_messages.append({
            'num': i,
            'user': message,
            'bot': result.response,
            'intent': result.router_status,
            'signal': result.source  # тут может быть user_signal
        })
    
    # Выводим весь диалог
    for msg in all_messages:
        print(f"\n{Colors.BLUE}──── Сообщение {msg['num']} ────{Colors.ENDC}")
        print(f"{Colors.BOLD}👤 ВОПРОС:{Colors.ENDC}")
        print(f"   {msg['user']}")
        print()
        print(f"{Colors.GREEN}🤖 ОТВЕТ:{Colors.ENDC}")
        # Разбиваем длинный ответ на строки для читаемости
        words = msg['bot'].split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 > 80:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
            else:
                current_line.append(word)
                current_length += len(word) + 1
        
        if current_line:
            lines.append(' '.join(current_line))
        
        for line in lines:
            print(f"   {line}")
        
        print(f"\n   [{msg['intent']}]")
        print(f"   {Colors.DIM}{'─'*76}{Colors.ENDC}")

async def main():
    if len(sys.argv) > 1:
        scenario_num = int(sys.argv[1])
    else:
        scenario_num = 1
    
    await show_dialogue(scenario_num)

if __name__ == "__main__":
    asyncio.run(main())