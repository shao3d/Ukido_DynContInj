#!/usr/bin/env python3
"""Тест исправлений mixed greeting detection"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sandbox_v2 import SandboxV2, Colors

async def test_mixed_greetings():
    sandbox = SandboxV2()
    
    print(f"{Colors.HEADER}ТЕСТ: Mixed Greeting Detection{Colors.ENDC}\n")
    
    test_cases = [
        {
            "message": "Добрый день! У меня трое детей: 7, 10 и 13 лет",
            "expected_status": "success",
            "expected_social": "greeting",
            "description": "Приветствие + информация о детях"
        },
        {
            "message": "Привет! Мой ребенок очень стеснительный",
            "expected_status": "success",
            "expected_social": "greeting",
            "description": "Приветствие + проблема ребенка"
        },
        {
            "message": "Здравствуйте! Интересует курс для 10-летнего",
            "expected_status": "success",
            "expected_social": "greeting",
            "description": "Приветствие + интерес к курсу"
        },
        {
            "message": "Добрый день!",
            "expected_status": "offtopic",
            "expected_social": "greeting",
            "description": "Чистое приветствие"
        },
        {
            "message": "Спасибо! Запишите нас на пробное",
            "expected_status": "success",
            "expected_social": "thanks",
            "description": "Благодарность + готовность"
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"{Colors.BLUE}Тест {i}: {test['description']}{Colors.ENDC}")
        print(f"Сообщение: {test['message']}")
        
        result = await sandbox.process_message(test['message'], f"test_user_{i}")
        
        status_ok = result.router_status == test['expected_status']
        social_ok = result.social_context == test['expected_social']
        
        # Проверяем наличие вопросов для success случаев
        questions_ok = True
        if test['expected_status'] == 'success':
            questions_ok = len(result.questions) > 0
        
        if status_ok and social_ok and questions_ok:
            print(f"{Colors.GREEN}✅ PASSED{Colors.ENDC}")
            print(f"  Status: {result.router_status}")
            print(f"  Social: {result.social_context}")
            if result.questions:
                print(f"  Questions: {result.questions}")
            passed += 1
        else:
            print(f"{Colors.RED}❌ FAILED{Colors.ENDC}")
            print(f"  Expected: status={test['expected_status']}, social={test['expected_social']}")
            print(f"  Got: status={result.router_status}, social={result.social_context}")
            if test['expected_status'] == 'success' and not result.questions:
                print(f"  {Colors.YELLOW}⚠️ No questions generated!{Colors.ENDC}")
            failed += 1
        
        print(f"{Colors.DIM}{'─'*60}{Colors.ENDC}\n")
    
    # Итоги
    print(f"{Colors.HEADER}РЕЗУЛЬТАТЫ:{Colors.ENDC}")
    print(f"{Colors.GREEN}✅ Passed: {passed}/{len(test_cases)}{Colors.ENDC}")
    if failed > 0:
        print(f"{Colors.RED}❌ Failed: {failed}/{len(test_cases)}{Colors.ENDC}")
    
    if passed == len(test_cases):
        print(f"\n{Colors.GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Mixed greeting detection работает правильно!{Colors.ENDC}")
    else:
        print(f"\n{Colors.YELLOW}⚠️ Есть проблемы с mixed greeting detection{Colors.ENDC}")

if __name__ == "__main__":
    asyncio.run(test_mixed_greetings())
