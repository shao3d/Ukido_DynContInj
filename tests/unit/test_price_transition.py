#!/usr/bin/env python3
"""Тест перехода price_sensitive -> ready_to_buy при позитивных фразах"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox_v2 import SandboxV2, Colors

async def test_transition():
    sandbox = SandboxV2()
    
    print(f"{Colors.HEADER}ТЕСТ: Переход от негатива к принятию цены{Colors.ENDC}\n")
    
    # История диалога для контекста
    history = []
    user_id = "test_transition"
    
    # Шаг 1: Явный негатив
    msg1 = "7000 грн за месяц? Это грабеж!"
    print(f"{Colors.BLUE}Шаг 1:{Colors.ENDC} {msg1}")
    result1 = await sandbox.process_message(msg1, user_id)
    print(f"Signal: {Colors.RED if result1.user_signal == 'price_sensitive' else Colors.GREEN}{result1.user_signal}{Colors.ENDC}")
    history.extend([
        {"role": "user", "content": msg1},
        {"role": "assistant", "content": result1.response[:100]}
    ])
    print()
    
    # Шаг 2: Все еще негатив
    msg2 = "У других дешевле в два раза!"
    print(f"{Colors.BLUE}Шаг 2:{Colors.ENDC} {msg2}")
    result2 = await sandbox.process_message(msg2, user_id)
    print(f"Signal: {Colors.RED if result2.user_signal == 'price_sensitive' else Colors.GREEN}{result2.user_signal}{Colors.ENDC}")
    history.extend([
        {"role": "user", "content": msg2},
        {"role": "assistant", "content": result2.response[:100]}
    ])
    print()
    
    # Шаг 3: Смягчение - должен перейти в exploring_only или ready_to_buy
    msg3 = "Ладно, черт с ними с деньгами. Качество важнее. Записывайте"
    print(f"{Colors.BLUE}Шаг 3:{Colors.ENDC} {msg3}")
    result3 = await sandbox.process_message(msg3, user_id)
    print(f"Signal: {Colors.GREEN if result3.user_signal == 'ready_to_buy' else Colors.YELLOW}{result3.user_signal}{Colors.ENDC}")
    
    # Проверка результата
    print(f"\n{Colors.HEADER}РЕЗУЛЬТАТ:{Colors.ENDC}")
    if result1.user_signal == 'price_sensitive' and result2.user_signal == 'price_sensitive' and result3.user_signal == 'ready_to_buy':
        print(f"{Colors.GREEN}✅ ТЕСТ ПРОЙДЕН! Переход price_sensitive → ready_to_buy работает правильно{Colors.ENDC}")
    else:
        print(f"{Colors.RED}❌ ТЕСТ НЕ ПРОЙДЕН!{Colors.ENDC}")
        print(f"Ожидалось: price_sensitive → price_sensitive → ready_to_buy")
        print(f"Получено: {result1.user_signal} → {result2.user_signal} → {result3.user_signal}")

if __name__ == "__main__":
    asyncio.run(test_transition())
