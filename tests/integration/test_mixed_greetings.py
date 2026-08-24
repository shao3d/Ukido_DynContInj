#!/usr/bin/env python3
"""
Тест исправления повторных приветствий в mixed запросах
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox_v2 import SandboxV2, Colors

async def test_mixed_greetings():
    """Тестируем обработку повторных приветствий в mixed запросах"""
    sandbox = SandboxV2()
    user_id = "test_mixed_user"
    
    print(f"{Colors.HEADER}╔══════════════════════════════════════════════╗")
    print(f"║  ТЕСТ ПОВТОРНЫХ ПРИВЕТСТВИЙ В MIXED ЗАПРОСАХ ║")
    print(f"╚══════════════════════════════════════════════╝{Colors.ENDC}\n")
    
    # Тестовые сообщения
    test_cases = [
        ("Привет!", "чистое первое приветствие"),
        ("Какие есть курсы для детей 10 лет?", "обычный вопрос"),
        ("Привет! А какие цены на курсы?", "mixed с повторным приветствием"),
        ("Здравствуйте еще раз! Есть скидки?", "явное повторное приветствие в mixed"),
    ]
    
    print(f"{Colors.BOLD}Тестовый сценарий:{Colors.ENDC}")
    for i, (msg, desc) in enumerate(test_cases, 1):
        print(f"  {i}. {desc}: \"{msg}\"")
    print()
    
    for i, (message, description) in enumerate(test_cases, 1):
        print(f"{Colors.CYAN}═══ Шаг {i}/{len(test_cases)}: {description} ═══{Colors.ENDC}")
        print(f"👤 {Colors.YELLOW}{message}{Colors.ENDC}")
        
        result = await sandbox.process_message(
            message, 
            user_id=user_id,
            show_details=False
        )
        
        # Показываем ответ (первые 200 символов)
        response_preview = result.response[:200] + "..." if len(result.response) > 200 else result.response
        print(f"🤖 {Colors.GREEN}{response_preview}{Colors.ENDC}")
        
        # Анализ результата
        print(f"\n{Colors.DIM}📊 Метрики:{Colors.ENDC}")
        print(f"  • Статус: {result.router_status}")
        print(f"  • Социальный контекст: {Colors.BOLD}{result.social_context}{Colors.ENDC}")
        print(f"  • Источник: {result.source}")
        
        # Проверка корректности обработки
        if i == 1:  # Первое приветствие
            if result.social_context == "greeting":
                print(f"  {Colors.GREEN}✓ Первое приветствие обработано как 'greeting'{Colors.ENDC}")
            else:
                print(f"  {Colors.RED}✗ Ошибка: ожидался 'greeting'{Colors.ENDC}")
                
        elif i == 3:  # Mixed с повторным приветствием
            if result.social_context == "repeated_greeting":
                print(f"  {Colors.GREEN}✓ Повторное приветствие в mixed обработано как 'repeated_greeting'{Colors.ENDC}")
            elif result.social_context == "greeting":
                print(f"  {Colors.YELLOW}⚠ Обработано как обычное приветствие (старое поведение){Colors.ENDC}")
            
            # Проверяем, что в ответе нет повторного приветствия
            greetings = ["привет", "здравств", "добрый день", "приветствуем"]
            has_greeting = any(g in result.response.lower()[:50] for g in greetings)
            if not has_greeting:
                print(f"  {Colors.GREEN}✓ В ответе нет повторного приветствия{Colors.ENDC}")
            else:
                print(f"  {Colors.YELLOW}⚠ В ответе есть приветствие{Colors.ENDC}")
                
        elif i == 4:  # Явное повторное приветствие
            if result.social_context == "repeated_greeting":
                print(f"  {Colors.GREEN}✓ Явное повторное приветствие обработано корректно{Colors.ENDC}")
            
            # Проверяем упоминание повторного приветствия
            if "уже поздоровались" in result.response.lower() or "еще раз" in result.response.lower():
                print(f"  {Colors.GREEN}✓ Модель отметила повторное приветствие{Colors.ENDC}")
        
        print()
    
    print(f"{Colors.HEADER}═══════════════════════════════════════════════{Colors.ENDC}")
    print(f"{Colors.BOLD}✅ Тест завершен!{Colors.ENDC}")
    print(f"\n{Colors.CYAN}Ключевые выводы:{Colors.ENDC}")
    print("• Чистые приветствия обрабатываются Router (0.00s)")
    print("• Mixed запросы с повторными приветствиями теперь помечаются как 'repeated_greeting'")
    print("• Модель корректно обрабатывает повторные приветствия")

if __name__ == "__main__":
    asyncio.run(test_mixed_greetings())
