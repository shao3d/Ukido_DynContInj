#!/usr/bin/env python3
"""
Universal Tester - Универсальная песочница для тестирования Ukido AI
Автоматически прогоняет все минидиалоги из JSON и создает полные отчеты
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from html import escape

# Добавляем src в path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from router import Router
from response_generator import ResponseGenerator
from history_manager import HistoryManager
from social_state import SocialStateManager
from config import Config

# ====== ЦВЕТА ДЛЯ КОНСОЛИ ======
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

# ====== РЕЗУЛЬТАТ ШАГА ======
@dataclass
class StepResult:
    """Результат обработки одного шага в диалоге"""
    step_num: int
    user_message: str
    bot_response: str
    router_status: str
    social_context: Optional[str]
    documents: List[str]
    router_time: float
    generator_time: float
    total_time: float
    source: str  # "router_social", "claude", "fallback"
    errors: List[str] = field(default_factory=list)
    # State Machine метрики
    user_signal: str = "exploring_only"
    personalized_offer: str = ""
    tone_adaptation: str = ""
    # Edge case индикаторы
    fuzzy_matched: bool = False
    has_profanity: bool = False
    memory_position: int = 0

# ====== РЕЗУЛЬТАТ ДИАЛОГА ======
@dataclass
class DialogueResult:
    """Результат прогона всего минидиалога"""
    scenario_name: str
    description: str
    expected_signal: Optional[str]
    steps: List[StepResult]
    total_time: float
    avg_response_time: float
    errors_count: int
    success: bool
    
    @property
    def accuracy(self) -> float:
        """Точность определения user_signal"""
        if not self.expected_signal or not self.steps:
            return 0
        correct = sum(1 for s in self.steps if s.user_signal == self.expected_signal)
        return (correct / len(self.steps)) * 100

# ====== ОСНОВНОЙ КЛАСС ======
class UniversalTester:
    """Универсальный тестер для всех типов сценариев"""
    
    def __init__(self, json_file: str):
        """
        Args:
            json_file: Путь к JSON файлу со сценариями
        """
        self.json_file = Path(json_file)
        if not self.json_file.exists():
            raise FileNotFoundError(f"Файл не найден: {json_file}")
        
        # Загружаем сценарии
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Поддержка разных форматов JSON
            if isinstance(data, dict) and "scenarios" in data:
                self.scenarios = data["scenarios"]
            elif isinstance(data, list):
                self.scenarios = data
            else:
                raise ValueError(f"Неподдерживаемый формат JSON в {json_file}")
        
        # Инициализируем компоненты
        self.config = Config()
        self.router = Router(use_cache=True)
        self.response_generator = ResponseGenerator()
        
        # Результаты тестирования
        self.results: List[DialogueResult] = []
        self.start_time = None
        self.end_time = None
    
    async def process_message(
        self,
        message: str,
        user_id: str,
        history_messages: List[Dict]
    ) -> Tuple[str, Dict]:
        """Обрабатывает одно сообщение через pipeline"""
        start_time = time.time()
        
        # Router
        router_start = time.time()
        try:
            route_result = await self.router.route(message, history_messages, user_id)
            router_time = time.time() - router_start
        except Exception as e:
            print(f"{Colors.RED}❌ Router failed: {e}{Colors.ENDC}")
            route_result = {
                "status": "error",
                "message": f"Router error: {str(e)}"
            }
            router_time = time.time() - router_start
        
        # Извлекаем данные
        status = route_result.get("status", "offtopic")
        social_context = route_result.get("social_context")
        documents = route_result.get("documents", [])
        questions = route_result.get("decomposed_questions", [])
        user_signal = route_result.get("user_signal", "exploring_only")
        fuzzy_matched = route_result.get("fuzzy_matched", False)
        
        # Генерация ответа
        generator_time = 0
        source = "fallback"
        
        if status == "success":
            generator_start = time.time()
            try:
                response = await self.response_generator.generate(
                    route_result,
                    history_messages
                )
                generator_time = time.time() - generator_start
                source = "claude"
            except Exception as e:
                print(f"{Colors.RED}❌ Generator failed: {e}{Colors.ENDC}")
                response = f"Извините, произошла ошибка при генерации ответа."
                generator_time = time.time() - generator_start
        else:
            response = route_result.get("message", "К сожалению, я могу помочь только с вопросами о школе.")
            source = "router_social" if social_context else "fallback"
        
        total_time = time.time() - start_time
        
        return response, {
            "status": status,
            "social_context": social_context,
            "documents": documents,
            "questions": questions,
            "router_time": router_time,
            "generator_time": generator_time,
            "total_time": total_time,
            "source": source,
            "user_signal": user_signal,
            "fuzzy_matched": fuzzy_matched
        }
    
    async def run_dialogue(self, scenario: Dict, scenario_num: int) -> DialogueResult:
        """Прогоняет один полный диалог"""
        scenario_name = scenario.get("scenario_name", f"Сценарий {scenario_num}")
        description = scenario.get("description", "")
        expected_signal = scenario.get("expected_signal")
        steps_data = scenario.get("steps", [])
        
        print(f"\n{Colors.CYAN}╔{'═'*60}╗")
        print(f"║ {'Сценарий #{}: {}'.format(scenario_num, scenario_name[:40]):^58} ║")
        print(f"╚{'═'*60}╝{Colors.ENDC}")
        
        if description:
            print(f"{Colors.DIM}📝 {description}{Colors.ENDC}")
        if expected_signal:
            print(f"{Colors.DIM}🎯 Ожидаемый signal: {expected_signal}{Colors.ENDC}")
        print(f"{Colors.DIM}📊 Шагов: {len(steps_data)}{Colors.ENDC}\n")
        
        # Уникальный user_id для изоляции диалога
        user_id = f"universal_test_{scenario_name.replace(' ', '_').lower()}_{datetime.now().timestamp()}"
        
        # Создаем чистые менеджеры для диалога
        history = HistoryManager()
        social_state = SocialStateManager()
        
        step_results = []
        dialogue_start = time.time()
        success = True
        
        for i, step_data in enumerate(steps_data, 1):
            # Поддержка разных форматов шагов
            if isinstance(step_data, str):
                message = step_data
            elif isinstance(step_data, dict):
                message = step_data.get("user_input", step_data.get("message", ""))
            else:
                print(f"{Colors.RED}❌ Неверный формат шага {i}{Colors.ENDC}")
                continue
            
            print(f"{Colors.DIM}Шаг {i}/{len(steps_data)}:{Colors.ENDC} ", end="")
            
            # Получаем историю
            history_messages = history.get_history(user_id)
            
            # Обрабатываем сообщение
            try:
                response, metadata = await self.process_message(message, user_id, history_messages)
                
                # Сохраняем в историю
                history.add_message(user_id, "user", message)
                history.add_message(user_id, "assistant", response)
                
                # Извлекаем персонализацию
                personalized_offer = self._extract_offer(response)
                tone_adaptation = self._detect_tone(response, metadata["user_signal"])
                
                # Проверяем на грубость
                has_profanity = any(marker in message.lower() for marker in ["х**", "о**", "бл*", "суч", "дур"])
                
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
                    source=metadata["source"],
                    user_signal=metadata["user_signal"],
                    personalized_offer=personalized_offer,
                    tone_adaptation=tone_adaptation,
                    fuzzy_matched=metadata["fuzzy_matched"],
                    has_profanity=has_profanity,
                    memory_position=i
                )
                
                # Проверка на ошибки
                if metadata["status"] == "error":
                    step_result.errors.append("Router/Generator error")
                    success = False
                
                step_results.append(step_result)
                
                # Краткий вывод статуса
                status_icon = "✅" if metadata["status"] == "success" else "⚠️"
                print(f"{status_icon} [{metadata['status']}] {metadata['total_time']:.2f}s")
                
            except Exception as e:
                print(f"{Colors.RED}❌ Ошибка: {e}{Colors.ENDC}")
                step_results.append(StepResult(
                    step_num=i,
                    user_message=message,
                    bot_response="[ОШИБКА ОБРАБОТКИ]",
                    router_status="error",
                    social_context=None,
                    documents=[],
                    router_time=0,
                    generator_time=0,
                    total_time=0,
                    source="error",
                    errors=[str(e)]
                ))
                success = False
            
            # Небольшая пауза между сообщениями
            await asyncio.sleep(0.1)
        
        dialogue_time = time.time() - dialogue_start
        avg_time = dialogue_time / len(steps_data) if steps_data else 0
        errors_count = sum(len(s.errors) for s in step_results)
        
        result = DialogueResult(
            scenario_name=scenario_name,
            description=description,
            expected_signal=expected_signal,
            steps=step_results,
            total_time=dialogue_time,
            avg_response_time=avg_time,
            errors_count=errors_count,
            success=success
        )
        
        # Краткая статистика
        print(f"\n{Colors.GREEN}✅ Завершено за {dialogue_time:.1f}s")
        if expected_signal:
            print(f"📊 Точность определения signal: {result.accuracy:.1f}%")
        print(f"⏱️ Среднее время ответа: {avg_time:.2f}s{Colors.ENDC}")
        
        return result
    
    async def run_all(self):
        """Запускает все сценарии и генерирует отчеты"""
        self.start_time = datetime.now()
        
        print(f"\n{Colors.HEADER}{'='*70}")
        print(f"{'UNIVERSAL TESTER - ЗАПУСК ТЕСТИРОВАНИЯ':^70}")
        print(f"{'='*70}{Colors.ENDC}")
        print(f"\n📁 Файл: {self.json_file}")
        print(f"📋 Загружено сценариев: {len(self.scenarios)}")
        print(f"🕐 Начало: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Прогоняем все сценарии
        for i, scenario in enumerate(self.scenarios, 1):
            result = await self.run_dialogue(scenario, i)
            self.results.append(result)
            
            # Пауза между диалогами
            if i < len(self.scenarios):
                await asyncio.sleep(1)
        
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        print(f"\n{Colors.GREEN}{'='*70}")
        print(f"{'ТЕСТИРОВАНИЕ ЗАВЕРШЕНО':^70}")
        print(f"{'='*70}{Colors.ENDC}")
        print(f"⏱️ Общее время: {duration:.1f}s")
        print(f"✅ Успешных диалогов: {sum(1 for r in self.results if r.success)}/{len(self.results)}")
        
        # Генерируем отчеты
        self.generate_reports()
    
    def _extract_offer(self, response: str) -> str:
        """Извлекает персонализированное предложение из ответа"""
        offer_patterns = [
            "скидк", "бесплатн", "пробн", "запис", 
            "попробов", "специальн", "предложени", "акци"
        ]
        for pattern in offer_patterns:
            if pattern in response.lower():
                sentences = response.split(".")
                for sentence in sentences:
                    if pattern in sentence.lower():
                        return sentence.strip()
        return ""
    
    def _detect_tone(self, response: str, user_signal: str) -> str:
        """Определяет тон адаптации ответа"""
        response_lower = response.lower()
        
        # Маркеры разных тонов
        empathy_markers = ["понима", "беспоко", "тревож", "поддерж", "помож", "забот"]
        concrete_markers = ["запис", "начать", "документ", "оплат", "адрес", "график"]
        value_markers = ["ценност", "выгод", "результат", "эффект", "инвестиц", "скидк"]
        
        scores = {
            "эмпатия": sum(1 for m in empathy_markers if m in response_lower),
            "конкретика": sum(1 for m in concrete_markers if m in response_lower),
            "ценность": sum(1 for m in value_markers if m in response_lower)
        }
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "информативность"
    
    def generate_reports(self):
        """Генерирует MD и HTML отчеты"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        reports_dir = Path("tests/reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Генерируем Markdown отчет
        md_file = reports_dir / f"universal_test_{timestamp}.md"
        self._generate_markdown_report(md_file)
        print(f"\n📝 Markdown отчет: {md_file}")
        
        # Генерируем HTML отчет
        html_file = reports_dir / f"universal_test_{timestamp}.html"
        self._generate_html_report(html_file)
        print(f"🌐 HTML отчет: {html_file}")
        
        # Опционально: JSON для программной обработки
        json_file = reports_dir / f"universal_test_{timestamp}.json"
        self._save_json_results(json_file)
        print(f"💾 JSON результаты: {json_file}")
    
    def _generate_markdown_report(self, output_file: Path):
        """Генерирует Markdown отчет"""
        with open(output_file, 'w', encoding='utf-8') as f:
            # Заголовок
            f.write("# Universal Test Report\n\n")
            f.write(f"**Файл сценариев**: `{self.json_file.name}`\n")
            f.write(f"**Дата**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Продолжительность**: {(self.end_time - self.start_time).total_seconds():.1f}s\n\n")
            
            # Сводная таблица
            f.write("## 📊 Сводная таблица результатов\n\n")
            f.write("| # | Сценарий | Шагов | Время | Статус | Точность |\n")
            f.write("|---|----------|-------|-------|--------|----------|\n")
            
            for i, result in enumerate(self.results, 1):
                status = "✅" if result.success else "❌"
                accuracy = f"{result.accuracy:.1f}%" if result.expected_signal else "—"
                f.write(f"| {i} | {result.scenario_name} | {len(result.steps)} | ")
                f.write(f"{result.avg_response_time:.1f}s | {status} | {accuracy} |\n")
            
            # Итоговая статистика
            total_steps = sum(len(r.steps) for r in self.results)
            successful = sum(1 for r in self.results if r.success)
            avg_time = sum(r.avg_response_time for r in self.results) / len(self.results) if self.results else 0
            
            f.write(f"\n**Итого**: {len(self.results)} сценариев, {total_steps} шагов\n")
            f.write(f"**Успешность**: {successful}/{len(self.results)} ({successful/len(self.results)*100:.1f}%)\n")
            f.write(f"**Среднее время ответа**: {avg_time:.2f}s\n\n")
            
            f.write("---\n\n")
            
            # Полные диалоги
            f.write("## 🎭 Полные диалоги\n\n")
            
            for i, result in enumerate(self.results, 1):
                f.write(f"### Сценарий {i}: {result.scenario_name}\n\n")
                
                if result.description:
                    f.write(f"*{result.description}*\n\n")
                
                if result.expected_signal:
                    f.write(f"**Ожидаемый signal**: `{result.expected_signal}`\n")
                    f.write(f"**Точность определения**: {result.accuracy:.1f}%\n\n")
                
                # Шаги диалога
                for step in result.steps:
                    f.write(f"#### Шаг {step.step_num}\n\n")
                    f.write(f"**👤 Пользователь:**\n")
                    f.write(f"> {step.user_message}\n\n")
                    
                    f.write(f"**🤖 Ассистент:**\n")
                    # Полный ответ без обрезки
                    for line in step.bot_response.split('\n'):
                        if line.strip():
                            f.write(f"> {line}\n")
                    f.write("\n")
                    
                    # Метрики шага
                    f.write(f"**📊 Метрики:**\n")
                    f.write(f"- Статус: `{step.router_status}`\n")
                    f.write(f"- Источник: {step.source}\n")
                    f.write(f"- Signal: `{step.user_signal}`\n")
                    
                    if step.tone_adaptation:
                        f.write(f"- Тон: {step.tone_adaptation}\n")
                    if step.personalized_offer:
                        f.write(f"- Персонализация: {step.personalized_offer[:100]}...\n")
                    if step.social_context:
                        f.write(f"- Социальный контекст: {step.social_context}\n")
                    if step.documents:
                        f.write(f"- Документы: {', '.join(step.documents)}\n")
                    if step.fuzzy_matched:
                        f.write(f"- 🔍 Fuzzy matching сработал\n")
                    if step.has_profanity:
                        f.write(f"- 🤬 Обнаружена грубость\n")
                    
                    f.write(f"- Время: {step.total_time:.2f}s ")
                    f.write(f"(Router: {step.router_time:.2f}s, Generator: {step.generator_time:.2f}s)\n")
                    
                    if step.errors:
                        f.write(f"- ❌ Ошибки: {', '.join(step.errors)}\n")
                    
                    f.write("\n---\n\n")
                
                # Анализ диалога
                f.write(f"#### 📈 Анализ диалога\n\n")
                f.write(self._analyze_dialogue(result))
                f.write("\n\n")
            
            # Итоговый анализ
            f.write("## 📈 Итоговый анализ и рекомендации\n\n")
            f.write(self._generate_final_analysis())
    
    def _generate_html_report(self, output_file: Path):
        """Генерирует HTML отчет"""
        # HTML стили
        html_styles = """
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                line-height: 1.6; 
                color: #333; 
                max-width: 1400px; 
                margin: 0 auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            h1 { 
                color: #2c3e50; 
                border-bottom: 3px solid #3498db; 
                padding-bottom: 10px; 
            }
            h2 { 
                color: #34495e; 
                margin-top: 40px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h3 {
                color: #2c3e50;
                margin-top: 30px;
            }
            .stats { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 20px; 
                margin: 30px 0; 
            }
            .stat-card { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; 
                padding: 25px; 
                border-radius: 12px; 
                box-shadow: 0 8px 16px rgba(0,0,0,0.1);
                text-align: center;
            }
            .stat-number { 
                font-size: 2.5em; 
                font-weight: bold;
                margin-bottom: 10px;
            }
            .scenario { 
                background: white; 
                padding: 25px; 
                margin: 25px 0; 
                border-radius: 12px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .scenario.failed { 
                border-left: 5px solid #e74c3c; 
            }
            .scenario.success { 
                border-left: 5px solid #27ae60; 
            }
            .step { 
                background: #f8f9fa; 
                padding: 20px; 
                margin: 15px 0; 
                border-radius: 8px; 
                border: 1px solid #dee2e6; 
            }
            .user-msg { 
                color: #2c3e50; 
                font-weight: 600; 
                margin-bottom: 10px;
                padding: 10px;
                background: #e3f2fd;
                border-radius: 5px;
            }
            .assistant-msg { 
                color: #27ae60; 
                background: #f0f9ff; 
                padding: 15px; 
                border-radius: 8px; 
                margin: 10px 0;
                border-left: 3px solid #27ae60;
            }
            .metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 10px;
            }
            .metric-badge {
                display: inline-block;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 0.85em;
                font-weight: 500;
            }
            .metric-success { background: #d4edda; color: #155724; }
            .metric-warning { background: #fff3cd; color: #856404; }
            .metric-error { background: #f8d7da; color: #721c24; }
            .metric-info { background: #d1ecf1; color: #0c5460; }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            th {
                background: #3498db;
                color: white;
                padding: 12px;
                text-align: left;
            }
            td {
                padding: 10px 12px;
                border-bottom: 1px solid #ecf0f1;
            }
            tr:hover {
                background: #f5f5f5;
            }
            .error {
                color: #e74c3c;
                font-weight: bold;
            }
            .success-icon { color: #27ae60; }
            .error-icon { color: #e74c3c; }
        </style>
        """
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # HTML начало
            f.write(f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Test Report - {self.start_time.strftime('%Y-%m-%d %H:%M')}</title>
    {html_styles}
</head>
<body>
    <h1>🚀 Universal Test Report</h1>
    <p><strong>Файл:</strong> {self.json_file.name}<br>
    <strong>Дата:</strong> {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}<br>
    <strong>Продолжительность:</strong> {(self.end_time - self.start_time).total_seconds():.1f}s</p>
""")
            
            # Статистика в карточках
            total_steps = sum(len(r.steps) for r in self.results)
            successful = sum(1 for r in self.results if r.success)
            avg_time = sum(r.avg_response_time for r in self.results) / len(self.results) if self.results else 0
            
            f.write("""
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{}/{}</div>
            <div>Успешных сценариев</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{}</div>
            <div>Всего шагов</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{:.2f}s</div>
            <div>Среднее время ответа</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{:.1f}%</div>
            <div>Успешность</div>
        </div>
    </div>
""".format(successful, len(self.results), total_steps, avg_time, 
           successful/len(self.results)*100 if self.results else 0))
            
            # Таблица результатов
            f.write("""
    <h2>📊 Сводная таблица</h2>
    <table>
        <tr>
            <th>#</th>
            <th>Сценарий</th>
            <th>Шагов</th>
            <th>Время</th>
            <th>Статус</th>
            <th>Точность</th>
        </tr>
""")
            
            for i, result in enumerate(self.results, 1):
                status_icon = "✅" if result.success else "❌"
                accuracy = f"{result.accuracy:.1f}%" if result.expected_signal else "—"
                f.write(f"""
        <tr>
            <td>{i}</td>
            <td>{escape(result.scenario_name)}</td>
            <td>{len(result.steps)}</td>
            <td>{result.avg_response_time:.1f}s</td>
            <td>{status_icon}</td>
            <td>{accuracy}</td>
        </tr>
""")
            
            f.write("    </table>\n")
            
            # Полные диалоги
            f.write("    <h2>🎭 Полные диалоги</h2>\n")
            
            for i, result in enumerate(self.results, 1):
                scenario_class = "scenario success" if result.success else "scenario failed"
                f.write(f"""
    <div class="{scenario_class}">
        <h3>Сценарий {i}: {escape(result.scenario_name)}</h3>
""")
                
                if result.description:
                    f.write(f"        <p><em>{escape(result.description)}</em></p>\n")
                
                if result.expected_signal:
                    f.write(f"""
        <p>
            <strong>Ожидаемый signal:</strong> <code>{result.expected_signal}</code><br>
            <strong>Точность:</strong> {result.accuracy:.1f}%
        </p>
""")
                
                # Шаги диалога
                for step in result.steps:
                    f.write(f"""
        <div class="step">
            <h4>Шаг {step.step_num}</h4>
            <div class="user-msg">👤 {escape(step.user_message)}</div>
            <div class="assistant-msg">🤖 {escape(step.bot_response)}</div>
            <div class="metrics">
""")
                    
                    # Метрики в виде бейджей
                    status_class = "metric-success" if step.router_status == "success" else "metric-warning"
                    f.write(f'                <span class="metric-badge {status_class}">{step.router_status}</span>\n')
                    f.write(f'                <span class="metric-badge metric-info">{step.source}</span>\n')
                    f.write(f'                <span class="metric-badge metric-info">Signal: {step.user_signal}</span>\n')
                    
                    if step.social_context:
                        f.write(f'                <span class="metric-badge metric-info">👋 {step.social_context}</span>\n')
                    if step.fuzzy_matched:
                        f.write(f'                <span class="metric-badge metric-warning">🔍 Fuzzy</span>\n')
                    if step.has_profanity:
                        f.write(f'                <span class="metric-badge metric-error">🤬 Грубость</span>\n')
                    
                    f.write(f'                <span class="metric-badge metric-info">⏱️ {step.total_time:.2f}s</span>\n')
                    
                    if step.errors:
                        f.write(f'                <span class="metric-badge metric-error">❌ Ошибка</span>\n')
                    
                    f.write("            </div>\n")
                    f.write("        </div>\n")
                
                f.write("    </div>\n")
            
            # Итоговый анализ
            final_analysis = self._generate_final_analysis().replace('\n', '<br>')
            f.write(f"""
    <h2>📈 Итоговый анализ</h2>
    <div class="scenario">
        {final_analysis}
    </div>
</body>
</html>
""")
    
    def _save_json_results(self, output_file: Path):
        """Сохраняет результаты в JSON для программной обработки"""
        data = {
            "timestamp": self.start_time.isoformat(),
            "duration": (self.end_time - self.start_time).total_seconds(),
            "json_file": str(self.json_file),
            "scenarios_count": len(self.scenarios),
            "results": []
        }
        
        for result in self.results:
            scenario_data = {
                "name": result.scenario_name,
                "description": result.description,
                "expected_signal": result.expected_signal,
                "success": result.success,
                "accuracy": result.accuracy,
                "total_time": result.total_time,
                "avg_response_time": result.avg_response_time,
                "errors_count": result.errors_count,
                "steps": []
            }
            
            for step in result.steps:
                scenario_data["steps"].append({
                    "step_num": step.step_num,
                    "user_message": step.user_message,
                    "bot_response": step.bot_response,
                    "router_status": step.router_status,
                    "user_signal": step.user_signal,
                    "source": step.source,
                    "documents": step.documents,
                    "times": {
                        "router": step.router_time,
                        "generator": step.generator_time,
                        "total": step.total_time
                    },
                    "personalized_offer": step.personalized_offer,
                    "tone_adaptation": step.tone_adaptation,
                    "errors": step.errors
                })
            
            data["results"].append(scenario_data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _analyze_dialogue(self, result: DialogueResult) -> str:
        """Анализирует отдельный диалог"""
        analysis = []
        
        # Проверка времени ответа
        slow_steps = [s for s in result.steps if s.total_time > 5]
        if slow_steps:
            analysis.append(f"⚠️ {len(slow_steps)} медленных ответов (>5s)")
        
        # Проверка ошибок
        if result.errors_count > 0:
            analysis.append(f"❌ Обнаружено {result.errors_count} ошибок")
        
        # State Machine анализ
        if result.expected_signal:
            if result.accuracy >= 80:
                analysis.append(f"✅ Хорошая точность определения signal ({result.accuracy:.1f}%)")
            else:
                analysis.append(f"⚠️ Низкая точность определения signal ({result.accuracy:.1f}%)")
            
            # Персонализация
            offers_count = sum(1 for s in result.steps if s.personalized_offer)
            if offers_count > 0:
                analysis.append(f"💰 Персонализированных предложений: {offers_count}")
        
        # Социальные интенты
        social_steps = [s for s in result.steps if s.social_context]
        if social_steps:
            contexts = set(s.social_context for s in social_steps)
            analysis.append(f"👋 Социальные контексты: {', '.join(contexts)}")
        
        # Edge cases
        fuzzy_count = sum(1 for s in result.steps if s.fuzzy_matched)
        if fuzzy_count > 0:
            analysis.append(f"🔍 Fuzzy matching сработал {fuzzy_count} раз")
        
        profanity_count = sum(1 for s in result.steps if s.has_profanity)
        if profanity_count > 0:
            analysis.append(f"🤬 Обработано грубых сообщений: {profanity_count}")
        
        return "\n".join(analysis) if analysis else "✅ Диалог прошел без замечаний"
    
    def _generate_final_analysis(self) -> str:
        """Генерирует итоговый анализ всех результатов"""
        analysis = []
        
        # Общая статистика
        total_dialogues = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        total_steps = sum(len(r.steps) for r in self.results)
        
        analysis.append(f"### 📊 Общая статистика\n")
        analysis.append(f"- Протестировано диалогов: {total_dialogues}")
        analysis.append(f"- Успешных: {successful} ({successful/total_dialogues*100:.1f}%)")
        analysis.append(f"- Всего шагов: {total_steps}")
        
        # Анализ времени
        all_times = [s.total_time for r in self.results for s in r.steps]
        slow_count = 0  # Инициализируем переменную
        if all_times:
            avg_time = sum(all_times) / len(all_times)
            max_time = max(all_times)
            analysis.append(f"\n### ⏱️ Производительность")
            analysis.append(f"- Среднее время ответа: {avg_time:.2f}s")
            analysis.append(f"- Максимальное время: {max_time:.2f}s")
            
            slow_count = sum(1 for t in all_times if t > 5)
            if slow_count > 0:
                analysis.append(f"- ⚠️ Медленных ответов (>5s): {slow_count} ({slow_count/len(all_times)*100:.1f}%)")
        
        # State Machine анализ (если есть)
        state_machine_results = [r for r in self.results if r.expected_signal]
        if state_machine_results:
            analysis.append(f"\n### 🎯 State Machine")
            
            # Точность по типам
            signal_accuracy = {}
            for result in state_machine_results:
                signal = result.expected_signal
                if signal not in signal_accuracy:
                    signal_accuracy[signal] = []
                signal_accuracy[signal].append(result.accuracy)
            
            for signal, accuracies in signal_accuracy.items():
                avg_acc = sum(accuracies) / len(accuracies)
                analysis.append(f"- {signal}: {avg_acc:.1f}% точность")
            
            # Персонализация
            total_offers = sum(
                sum(1 for s in r.steps if s.personalized_offer) 
                for r in state_machine_results
            )
            total_sm_steps = sum(len(r.steps) for r in state_machine_results)
            if total_sm_steps > 0:
                analysis.append(f"- Персонализация: {total_offers}/{total_sm_steps} шагов ({total_offers/total_sm_steps*100:.1f}%)")
        
        # Edge cases
        analysis.append(f"\n### 🔍 Edge Cases")
        
        fuzzy_total = sum(sum(1 for s in r.steps if s.fuzzy_matched) for r in self.results)
        if fuzzy_total > 0:
            analysis.append(f"- Fuzzy matching: {fuzzy_total} срабатываний")
        
        profanity_total = sum(sum(1 for s in r.steps if s.has_profanity) for r in self.results)
        if profanity_total > 0:
            analysis.append(f"- Грубость: {profanity_total} случаев обработано")
        
        # Ошибки
        total_errors = sum(r.errors_count for r in self.results)
        if total_errors > 0:
            analysis.append(f"\n### ❌ Ошибки")
            analysis.append(f"- Всего ошибок: {total_errors}")
            failed_dialogues = [r.scenario_name for r in self.results if not r.success]
            if failed_dialogues:
                analysis.append(f"- Проваленные диалоги: {', '.join(failed_dialogues)}")
        
        # Рекомендации
        analysis.append(f"\n### 💡 Рекомендации")
        
        if successful < total_dialogues:
            analysis.append(f"- Исправить ошибки в {total_dialogues - successful} диалогах")
        
        if all_times and slow_count > len(all_times) * 0.1:
            analysis.append(f"- Оптимизировать производительность (много медленных ответов)")
        
        if state_machine_results:
            low_accuracy_signals = [s for s, accs in signal_accuracy.items() if sum(accs)/len(accs) < 70]
            if low_accuracy_signals:
                analysis.append(f"- Улучшить определение сигналов: {', '.join(low_accuracy_signals)}")
        
        if total_errors == 0 and successful == total_dialogues:
            analysis.append(f"- ✅ Все тесты прошли успешно!")
        
        return "\n".join(analysis)

# ====== MAIN ======
async def main():
    """Точка входа"""
    if len(sys.argv) < 2:
        print(f"{Colors.RED}Использование:{Colors.ENDC}")
        print(f"  python universal_tester.py <json_file>")
        print(f"\n{Colors.BOLD}Примеры:{Colors.ENDC}")
        print(f"  python universal_tester.py tests/test_scenarios_diverse.json")
        print(f"  python universal_tester.py tests/test_scenarios_stress.json")
        print(f"  python universal_tester.py tests/test_scenarios_state_machine.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        tester = UniversalTester(json_file)
        await tester.run_all()
    except FileNotFoundError as e:
        print(f"{Colors.RED}❌ Ошибка: {e}{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}❌ Неожиданная ошибка: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())