#!/usr/bin/env python3
"""
Collaborative Testing Framework
Прогоняет мини-диалоги из test_scenarios_stress.json
с сохранением истории и детальным анализом
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, field

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from router import Router
from response_generator import ResponseGenerator
from history_manager import HistoryManager
from social_state import SocialStateManager
from config import Config

# ====== ЦВЕТА ======
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

# ====== РЕЗУЛЬТАТ ОДНОГО ШАГА ======
@dataclass
class StepResult:
    """Результат обработки одного сообщения в диалоге"""
    step_num: int
    user_message: str
    bot_response: str
    router_status: str
    social_context: str
    documents: List[str]
    router_time: float
    generator_time: float
    total_time: float
    source: str  # "router_social", "claude", "fallback"
    errors: List[str] = field(default_factory=list)

# ====== РЕЗУЛЬТАТ ДИАЛОГА ======
@dataclass
class DialogueResult:
    """Результат прогона всего мини-диалога"""
    scenario_name: str
    description: str
    steps: List[StepResult]
    total_time: float
    avg_response_time: float
    errors_count: int
    
    @property
    def success_rate(self) -> float:
        """Процент успешных ответов"""
        if not self.steps:
            return 0
        successful = sum(1 for s in self.steps if not s.errors)
        return (successful / len(self.steps)) * 100

# ====== ОСНОВНОЙ КЛАСС ======
class CollaborativeTester:
    """Класс для collaborative тестирования диалогов"""
    
    def __init__(self):
        self.config = Config()
        self.router = Router(use_cache=True)
        self.response_generator = ResponseGenerator()
        self.history = HistoryManager()
        self.social_state = SocialStateManager()
        
        # Загружаем сценарии
        self.scenarios = self._load_scenarios()
    
    def _load_scenarios(self) -> List[Dict]:
        """Загружает тестовые сценарии"""
        path = Path(__file__).parent / "tests" / "test_scenarios_stress.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    async def process_message(
        self, 
        message: str, 
        user_id: str
    ) -> Tuple[str, Dict]:
        """Обрабатывает одно сообщение через pipeline"""
        start_time = time.time()
        
        # Получаем историю
        history_messages = self.history.get_history(user_id)
        
        # Router
        router_start = time.time()
        try:
            route_result = await self.router.route(message, history_messages, user_id)
            router_time = time.time() - router_start
        except Exception as e:
            print(f"{Colors.RED}❌ Router failed: {e}{Colors.ENDC}")
            route_result = {
                "status": "error",
                "message": str(e)
            }
            router_time = time.time() - router_start
        
        # Извлекаем данные
        status = route_result.get("status", "offtopic")
        social_context = route_result.get("social_context", "")
        documents = route_result.get("documents", [])
        
        # Генерация ответа
        generator_time = 0
        source = "fallback"
        
        if status == "success":
            generator_start = time.time()
            try:
                response = await self.response_generator.generate(
                    {
                        "status": status,
                        "documents": documents,
                        "decomposed_questions": route_result.get("decomposed_questions", []),
                        "social_context": social_context,
                    },
                    history_messages
                )
                generator_time = time.time() - generator_start
                source = "claude"
            except Exception as e:
                print(f"{Colors.RED}❌ Generator failed: {e}{Colors.ENDC}")
                response = f"Ошибка генерации: {e}"
                generator_time = time.time() - generator_start
        else:
            response = route_result.get("message", "К сожалению, я могу помочь только с вопросами о школе.")
            source = "router_social" if social_context else "fallback"
        
        # Сохраняем в историю
        self.history.add_message(user_id, "user", message)
        self.history.add_message(user_id, "assistant", response)
        
        total_time = time.time() - start_time
        
        return response, {
            "status": status,
            "social_context": social_context,
            "documents": documents,
            "router_time": router_time,
            "generator_time": generator_time,
            "total_time": total_time,
            "source": source
        }
    
    async def run_dialogue(self, scenario: Dict) -> DialogueResult:
        """Прогоняет один полный диалог"""
        scenario_name = scenario["scenario_name"]
        description = scenario["description"]
        steps = scenario["steps"]
        
        print(f"\n{Colors.HEADER}{'='*70}")
        print(f"📋 СЦЕНАРИЙ: {scenario_name}")
        print(f"📝 Описание: {description}")
        print(f"📊 Шагов: {len(steps)}")
        print(f"{'='*70}{Colors.ENDC}\n")
        
        # Сбрасываем состояние перед новым диалогом
        user_id = f"test_{scenario_name.replace(' ', '_').lower()}"
        self.history = HistoryManager()
        self.social_state = SocialStateManager()
        
        step_results = []
        dialogue_start = time.time()
        
        for i, message in enumerate(steps, 1):
            print(f"{Colors.DIM}━━━ Шаг {i}/{len(steps)} ━━━{Colors.ENDC}")
            
            # Обрабатываем сообщение
            response, metadata = await self.process_message(message, user_id)
            
            # Создаем результат шага
            step_result = StepResult(
                step_num=i,
                user_message=message,
                bot_response=response,
                router_status=metadata["status"],
                social_context=metadata["social_context"],
                documents=metadata["documents"],
                router_time=metadata["router_time"],
                generator_time=metadata["generator_time"],
                total_time=metadata["total_time"],
                source=metadata["source"]
            )
            
            # Базовая валидация
            if "ошибка" in response.lower() or "error" in response.lower():
                step_result.errors.append("Ответ содержит ошибку")
            
            step_results.append(step_result)
            
            # Небольшая пауза между сообщениями
            await asyncio.sleep(0.1)
        
        dialogue_time = time.time() - dialogue_start
        avg_time = dialogue_time / len(steps) if steps else 0
        errors_count = sum(len(s.errors) for s in step_results)
        
        return DialogueResult(
            scenario_name=scenario_name,
            description=description,
            steps=step_results,
            total_time=dialogue_time,
            avg_response_time=avg_time,
            errors_count=errors_count
        )
    
    def show_dialogue_results(self, result: DialogueResult):
        """Красиво отображает результаты диалога"""
        # СЕКЦИЯ 1: ПОЛНЫЙ ДИАЛОГ БЕЗ ОБРЕЗКИ
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"              СЕКЦИЯ 1: ПОЛНЫЕ ВОПРОСЫ И ОТВЕТЫ")
        print(f"{'='*80}{Colors.ENDC}\n")
        
        for step in result.steps:
            print(f"{Colors.YELLOW}👤 Вопрос {step.step_num}:{Colors.ENDC}")
            print(f"   {step.user_message}")
            print(f"\n{Colors.GREEN}🤖 Ответ {step.step_num}:{Colors.ENDC}")
            # Выводим ПОЛНЫЙ ответ без обрезки
            print(f"   {step.bot_response}")
            print(f"\n{Colors.DIM}{'─'*80}{Colors.ENDC}\n")
        
        # СЕКЦИЯ 2: МЕТРИКИ
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"                    СЕКЦИЯ 2: МЕТРИКИ")
        print(f"{'='*80}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}📊 МЕТРИКИ ПО ШАГАМ:{Colors.ENDC}\n")
        for step in result.steps:
            status_color = Colors.GREEN if step.router_status == "success" else Colors.YELLOW
            print(f"Шаг {step.step_num}: {status_color}{step.router_status}{Colors.ENDC} | "
                  f"Источник: {step.source} | "
                  f"Время: {step.total_time:.2f}s | "
                  f"Router: {step.router_time:.2f}s | "
                  f"Gen: {step.generator_time:.2f}s")
            if step.social_context:
                print(f"       Социальный контекст: {step.social_context}")
            if step.documents:
                print(f"       Документы: {', '.join(step.documents)}")
            if step.errors:
                print(f"       {Colors.RED}Ошибки: {', '.join(step.errors)}{Colors.ENDC}")
        
        # Итоговые метрики
        print(f"\n{Colors.BOLD}📈 ИТОГОВЫЕ МЕТРИКИ:{Colors.ENDC}\n")
        print(f"  • Общее время: {result.total_time:.2f}s")
        print(f"  • Среднее время ответа: {result.avg_response_time:.2f}s")
        print(f"  • Успешность: {result.success_rate:.1f}%")
        print(f"  • Ошибок: {result.errors_count}")
        
        # Распределение источников
        sources = {}
        for step in result.steps:
            sources[step.source] = sources.get(step.source, 0) + 1
        print(f"\n  • Источники ответов:")
        for source, count in sources.items():
            print(f"    - {source}: {count} ({count/len(result.steps)*100:.1f}%)")
    
    def analyze_dialogue(self, result: DialogueResult) -> str:
        """Анализирует результаты диалога"""
        # СЕКЦИЯ 3: АНАЛИЗ И РЕКОМЕНДАЦИИ
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"            СЕКЦИЯ 3: АНАЛИЗ И РЕКОМЕНДАЦИИ")
        print(f"{'='*80}{Colors.ENDC}\n")
        
        analysis = []
        
        # Анализ времени ответа
        slow_steps = [s for s in result.steps if s.total_time > 5]
        if slow_steps:
            analysis.append(f"⚠️ {len(slow_steps)} медленных ответов (>5s)")
        
        # Анализ социальных интентов
        social_steps = [s for s in result.steps if s.social_context]
        if social_steps:
            contexts = [s.social_context for s in social_steps]
            analysis.append(f"👋 Социальные контексты: {', '.join(set(contexts))}")
        
        # Анализ ошибок
        if result.errors_count > 0:
            analysis.append(f"❌ Обнаружено {result.errors_count} ошибок")
        
        # Анализ документов
        all_docs = []
        for step in result.steps:
            all_docs.extend(step.documents)
        if all_docs:
            unique_docs = set(all_docs)
            analysis.append(f"📄 Использовано документов: {len(unique_docs)} уникальных")
        
        return "\n".join(analysis) if analysis else "✅ Диалог прошел без замечаний"

# ====== ГЛАВНАЯ ФУНКЦИЯ ======
async def main():
    """Основная функция для collaborative тестирования"""
    tester = CollaborativeTester()
    
    print(f"{Colors.HEADER}{'='*70}")
    print("     COLLABORATIVE TESTING FRAMEWORK")
    print("     Тестирование диалогов с анализом")
    print(f"{'='*70}{Colors.ENDC}\n")
    
    # Показываем доступные сценарии
    print(f"{Colors.BOLD}Доступные сценарии:{Colors.ENDC}")
    for i, scenario in enumerate(tester.scenarios):
        print(f"{i+1}. {scenario['scenario_name']}")
    
    # Интерактивный выбор или автозапуск
    if len(sys.argv) > 1:
        try:
            scenario_num = int(sys.argv[1]) - 1
            if 0 <= scenario_num < len(tester.scenarios):
                scenario = tester.scenarios[scenario_num]
            else:
                print(f"Неверный номер сценария: {sys.argv[1]}")
                return
        except:
            # Ищем по имени
            scenario_name = " ".join(sys.argv[1:])
            scenario = next((s for s in tester.scenarios if s["scenario_name"].lower() == scenario_name.lower()), None)
            if not scenario:
                print(f"Сценарий не найден: {scenario_name}")
                return
    else:
        print("\nИспользование:")
        print("  python collaborative_test.py <номер>")
        print("  python collaborative_test.py <название>")
        print("\nПример:")
        print("  python collaborative_test.py 1")
        print('  python collaborative_test.py "Забывчивая бабушка"')
        return
    
    # Запускаем выбранный сценарий
    result = await tester.run_dialogue(scenario)
    
    # Показываем результаты
    tester.show_dialogue_results(result)
    
    # Анализ
    print(f"\n{Colors.BOLD}🔍 АНАЛИЗ:{Colors.ENDC}\n")
    analysis = tester.analyze_dialogue(result)
    print(analysis)
    
    print(f"\n{Colors.CYAN}{'='*70}")
    print("Готово! Теперь мы можем обсудить что нужно исправить.")
    print(f"{'='*70}{Colors.ENDC}\n")

if __name__ == "__main__":
    asyncio.run(main())