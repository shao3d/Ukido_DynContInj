#!/usr/bin/env python3
"""
Запуск и анализ comprehensive тестов с полным выводом
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List
from datetime import datetime

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from router import Router
from response_generator import ResponseGenerator
from history_manager import HistoryManager
from social_state import SocialStateManager
from social_intents import detect_social_intent
from config import Config

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

class ComprehensiveTestRunner:
    def __init__(self):
        self.config = Config()
        self.router = Router()
        self.response_generator = ResponseGenerator()
        self.results = []
        
    async def run_scenario(self, scenario: dict, scenario_num: int) -> dict:
        """Запускает один сценарий и возвращает результаты"""
        history = HistoryManager()
        social_state = SocialStateManager()
        
        print(f"\n{Colors.HEADER}{'='*80}")
        print(f"СЦЕНАРИЙ #{scenario_num}: {scenario['scenario_name']}")
        print(f"{'='*80}{Colors.ENDC}")
        print(f"{Colors.DIM}Описание: {scenario['description']}{Colors.ENDC}")
        print(f"{Colors.DIM}Ожидаемый сигнал: {scenario['expected_signal']}{Colors.ENDC}")
        print()
        
        scenario_results = {
            "scenario_name": scenario["scenario_name"],
            "description": scenario["description"],
            "expected_signal": scenario["expected_signal"],
            "messages": []
        }
        
        for i, message in enumerate(scenario["steps"], 1):
            print(f"{Colors.BLUE}─── Сообщение {i}/{len(scenario['steps'])} ───{Colors.ENDC}")
            print(f"{Colors.BOLD}👤 User:{Colors.ENDC} {message}")
            
            # Добавляем в историю
            history.add_message("user", message, "test_user")
            
            # Проверяем социальный контекст
            social_detection = detect_social_intent(message)
            social_context = social_detection.intent.value if social_detection.intent else None
            
            # Роутер
            router_result = await self.router.route(
                user_message=message,
                history=history.get_history("test_user"),
                user_id="test_user"
            )
            
            # Генерация ответа
            intent = router_result.get("intent") or router_result.get("status")
            
            if intent == "success":
                response = await self.response_generator.generate(
                    questions=router_result.get("questions", []),
                    documents=router_result.get("documents", []),
                    history=history.get_history("test_user"),
                    social_context=social_context,
                    user_signal=router_result.get("user_signal")
                )
            elif intent == "offtopic":
                # Используем стандартный ответ для offtopic
                response = router_result.get("standard_response", "Привет! Я помощник школы Ukido. Чем могу помочь?")
            else:
                # Другие случаи
                response = "Извините, я могу помочь только с вопросами о школе Ukido и наших курсах."
            
            # Выводим ответ
            print(f"{Colors.GREEN}🤖 Bot:{Colors.ENDC} {response}")
            
            # Выводим детали анализа
            print(f"\n{Colors.CYAN}📊 Анализ:{Colors.ENDC}")
            print(f"  • Intent: {intent}")
            print(f"  • User signal: {router_result.get('user_signal', 'none')}")
            print(f"  • Social context: {social_context if social_context else 'none'}")
            if router_result.get("questions"):
                print(f"  • Вопросы: {router_result['questions']}")
            if router_result.get("documents"):
                print(f"  • Документы: {len(router_result['documents'])} шт")
            
            print()
            
            # Сохраняем результат
            scenario_results["messages"].append({
                "user": message,
                "response": response,
                "intent": intent,
                "user_signal": router_result.get("user_signal"),
                "social_context": social_context
            })
            
            # Добавляем ответ в историю
            history.add_message("assistant", response, "test_user")
            
            # Небольшая пауза для читаемости
            await asyncio.sleep(0.1)
        
        return scenario_results
    
    async def run_all(self, test_file: str, start_from: int = 1, count: int = None):
        """Запускает все или указанное количество сценариев"""
        # Загружаем тесты
        with open(test_file, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)
        
        # Определяем какие сценарии запускать
        end_at = start_from + count - 1 if count else len(scenarios)
        end_at = min(end_at, len(scenarios))
        
        print(f"{Colors.HEADER}{'='*80}")
        print(f"ЗАПУСК ТЕСТОВ: {test_file}")
        print(f"Сценарии: {start_from} - {end_at} из {len(scenarios)}")
        print(f"{'='*80}{Colors.ENDC}")
        
        # Запускаем сценарии
        for i in range(start_from - 1, end_at):
            scenario_result = await self.run_scenario(scenarios[i], i + 1)
            self.results.append(scenario_result)
        
        # Сохраняем результаты
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_comprehensive_{timestamp}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"\n{Colors.GREEN}✅ Результаты сохранены в {results_file}{Colors.ENDC}")
        
        # Итоговая статистика
        print(f"\n{Colors.HEADER}{'='*80}")
        print("ИТОГОВАЯ СТАТИСТИКА")
        print(f"{'='*80}{Colors.ENDC}")
        
        signal_stats = {}
        intent_stats = {}
        
        for result in self.results:
            for msg in result["messages"]:
                signal = msg.get("user_signal", "none")
                intent = msg.get("intent", "unknown")
                signal_stats[signal] = signal_stats.get(signal, 0) + 1
                intent_stats[intent] = intent_stats.get(intent, 0) + 1
        
        print(f"\n{Colors.CYAN}User Signals:{Colors.ENDC}")
        for signal, count in signal_stats.items():
            print(f"  • {signal}: {count}")
        
        print(f"\n{Colors.CYAN}Intents:{Colors.ENDC}")
        for intent, count in intent_stats.items():
            print(f"  • {intent}: {count}")

async def main():
    runner = ComprehensiveTestRunner()
    
    # Парсим аргументы
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            # Запускаем все тесты
            await runner.run_all("tests/test_comprehensive_dialogues.json")
        else:
            # Запускаем конкретный номер сценария
            try:
                scenario_num = int(sys.argv[1])
                await runner.run_all("tests/test_comprehensive_dialogues.json", 
                                   start_from=scenario_num, count=1)
            except ValueError:
                print("Использование:")
                print("  python test_comprehensive_runner.py 1  # Запустить сценарий 1")
                print("  python test_comprehensive_runner.py --all  # Запустить все")
    else:
        # По умолчанию запускаем первый сценарий
        await runner.run_all("tests/test_comprehensive_dialogues.json", 
                           start_from=1, count=1)

if __name__ == "__main__":
    asyncio.run(main())