#!/usr/bin/env python3
"""
Комплексное тестирование роутера с автоматической генерацией HTML отчета
Запускает тесты и сразу создает красивый отчет в браузере
"""

import asyncio
import json
import sys
import webbrowser
import html
from html import escape
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Добавляем путь к src в sys.path (на уровень выше tests)
sys.path.append(str(Path(__file__).parent.parent / "src"))

from router import Router


class DialogScenarioTester:
    """Тестирование роутера на диалоговых сценариях"""
    
    def __init__(self):
        self.router = Router()
        self.scenarios = self._load_scenarios()
        self.results = []
    
    def _load_scenarios(self) -> List[Dict]:
        """Загружает сценарии из test_scenarios.json"""
        try:
            # Файл сценариев в той же папке tests
            scenarios_path = Path(__file__).parent / "test_scenarios.json"
            with open(scenarios_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ Файл test_scenarios.json не найден!")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return []
    
    async def test_scenario(self, scenario: Dict, scenario_num: int) -> Dict:
        """Тестирует один сценарий (мини-диалог)"""
        scenario_name = scenario.get("scenario_name", f"Сценарий {scenario_num}")
        steps = scenario.get("steps", [])
        
        print(f"\n🎬 Тестирую сценарий #{scenario_num}: {scenario_name}")
        print(f"   Шагов: {len(steps)}")
        
        # История диалога (очищается для каждого сценария)
        history = []
        scenario_results = {
            "name": scenario_name,
            "steps": [],
            "success": True
        }
        
        # Проходим по всем шагам диалога
        for step_num, user_message in enumerate(steps, 1):
            print(f"   • Шаг {step_num}/{len(steps)}...", end="")
            
            # Вызываем роутер с текущей историей
            try:
                result = await self.router.route(user_message, history)
                
                # Анализируем результат
                status = result.get("status", "unknown")
                print(f" [{status}]")
                
                if status == "success":
                    documents = result.get("documents", [])
                    assistant_response = f"[Ответ на основе документов: {', '.join(documents)}]"
                elif status in ["offtopic", "need_simplification"]:
                    message = result.get("message", "")
                    assistant_response = message
                else:
                    assistant_response = "Ошибка обработки"
                    scenario_results["success"] = False
                
                # Обновляем историю диалога
                history.append({"role": "user", "content": user_message})
                history.append({"role": "assistant", "content": assistant_response})
                
                # Сохраняем результат шага
                scenario_results["steps"].append({
                    "step": step_num,
                    "user_message": user_message,
                    "router_status": status,
                    "router_response": result
                })
                
            except Exception as e:
                print(f" [ОШИБКА: {e}]")
                scenario_results["success"] = False
                scenario_results["steps"].append({
                    "step": step_num,
                    "user_message": user_message,
                    "error": str(e)
                })
            
            # Небольшая пауза между запросами
            await asyncio.sleep(0.3)
        
        return scenario_results
    
    async def run_all_scenarios(self):
        """Запускает все сценарии из JSON файла"""
        if not self.scenarios:
            print("❌ Нет сценариев для тестирования!")
            return
        
        print("\n" + "="*60)
        print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ")
        print("="*60)
        print(f"📋 Загружено сценариев: {len(self.scenarios)}")
        print(f"📚 Документов в базе: {len(self.router.summaries)}")
        
        # Тестируем каждый сценарий
        for i, scenario in enumerate(self.scenarios, 1):
            result = await self.test_scenario(scenario, i)
            self.results.append(result)
            
            # Пауза между сценариями
            if i < len(self.scenarios):
                await asyncio.sleep(0.5)
        
        print("\n✅ Тестирование завершено!")
        
        # Сохраняем результаты в JSON
        self._save_json_results()
        
        # Генерируем HTML отчет
        html_file = self._generate_html_report()
        
        # Открываем в браузере
        print(f"\n🌐 Открываю отчет в браузере: {html_file}")
        webbrowser.open(f"file://{html_file}")
    
    def _save_json_results(self):
        """Сохраняет результаты тестирования в JSON файл"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Сохраняем в папку reports
            reports_dir = Path(__file__).parent / "reports"
            reports_dir.mkdir(exist_ok=True)
            filename = reports_dir / f"test_results_{timestamp}.json"
            
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            
            print(f"💾 JSON результаты сохранены в {filename.relative_to(Path.cwd())}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении JSON отчёта: {e}")
    
    def _generate_html_report(self) -> str:
        """Генерирует красивый HTML отчет"""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        # Сохраняем в папку reports
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = reports_dir / f"test_report_{now.strftime('%Y%m%d_%H%M%S')}.html"
        
        # Считаем статистику
        total_scenarios = len(self.results)
        successful = sum(1 for r in self.results if r["success"])
        total_steps = sum(len(r["steps"]) for r in self.results)
        
        # Статистика по статусам
        status_counts = {}
        for scenario in self.results:
            for step in scenario["steps"]:
                status = step.get("router_status", "error")
                status_counts[status] = status_counts.get(status, 0) + 1
        
        # Топ документов
        all_docs = {}
        for scenario in self.results:
            for step in scenario["steps"]:
                if step.get("router_status") == "success":
                    for doc in step.get("router_response", {}).get("documents", []):
                        all_docs[doc] = all_docs.get(doc, 0) + 1
        
        # HTML шаблон
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Отчет тестирования роутера - {timestamp}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .timestamp {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }}
        
        .stat-label {{
            color: #6c757d;
            margin-top: 5px;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .scenario {{
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        
        .scenario-header {{
            background: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
            cursor: pointer;
            transition: background 0.3s;
        }}
        
        .scenario-header:hover {{
            background: #e9ecef;
        }}
        
        .scenario-title {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .scenario-meta {{
            color: #6c757d;
        }}
        
        .scenario-body {{
            padding: 20px;
            display: none;
        }}
        
        .scenario.expanded .scenario-body {{
            display: block;
        }}
        
        .step {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
        }}
        
        .step-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .step-number {{
            font-weight: bold;
            color: #495057;
        }}
        
        .status-badge {{
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }}
        
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-offtopic {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .status-need_simplification {{
            background: #e2e3ff;
            color: #383d7c;
        }}
        
        .status-error {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .message {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }}
        
        .user-message {{
            border-left: 3px solid #667eea;
            padding-left: 10px;
        }}
        
        .router-response {{
            border-left: 3px solid #28a745;
            padding-left: 10px;
        }}
        
        .documents {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }}
        
        .document-tag {{
            background: #e9ecef;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        
        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }}
        
        .chart-card {{
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 10px;
            padding: 20px;
        }}
        
        .chart-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #495057;
        }}
        
        .bar {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .bar-label {{
            width: 150px;
            font-size: 0.9em;
        }}
        
        .bar-container {{
            flex: 1;
            background: #e9ecef;
            height: 25px;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }}
        
        .bar-fill {{
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 5px;
            color: white;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #6c757d;
            border-top: 1px solid #e9ecef;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Отчет тестирования роутера Ukido</h1>
            <div class="timestamp">📅 {timestamp}</div>
        </header>
        
        <div class="summary">
            <div class="stat-card">
                <div class="stat-value">{total_scenarios}</div>
                <div class="stat-label">Всего диалогов</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{successful}</div>
                <div class="stat-label">Успешных</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_steps}</div>
                <div class="stat-label">Всего вопросов</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{(successful/total_scenarios*100 if total_scenarios > 0 else 0):.1f}%</div>
                <div class="stat-label">Успешность</div>
            </div>
        </div>
        
        <div class="content">
            <h2 style="margin-bottom: 20px;">📝 Детали по диалогам</h2>
            <p style="color: #6c757d; margin-bottom: 20px;">Нажмите на диалог, чтобы развернуть детали</p>
"""
        
        # Добавляем каждый сценарий
        for i, scenario in enumerate(self.results, 1):
            success_icon = "✅" if scenario["success"] else "❌"
            
            # Считаем статистику для сценария
            scenario_status_counts = {}
            for step in scenario["steps"]:
                status = step.get("router_status", "error")
                scenario_status_counts[status] = scenario_status_counts.get(status, 0) + 1
            
            escaped_scenario_name = escape(scenario['name'])
            html += f"""
            <div class="scenario" id="scenario-{i}">
                <div class="scenario-header" onclick="toggleScenario({i})">
                    <div>
                        <div class="scenario-title">{success_icon} Диалог #{i}: {escaped_scenario_name}</div>
                        <div class="scenario-meta">
                            Шагов: {len(scenario['steps'])} | 
                            Статусы: {', '.join([f"{k}: {v}" for k, v in scenario_status_counts.items()])}
                        </div>
                    </div>
                </div>
                <div class="scenario-body">
"""
            
            # Добавляем шаги
            for step in scenario["steps"]:
                step_num = step["step"]
                user_msg = escape(step["user_message"])
                status = step.get("router_status", "error")
                response = step.get("router_response", {})
                
                status_class = f"status-{status}"
                
                html += f"""
                    <div class="step">
                        <div class="step-header">
                            <span class="step-number">Шаг {step_num}</span>
                            <span class="status-badge {status_class}">{status}</span>
                        </div>
                        <div class="message user-message">
                            <strong>👤 Вопрос:</strong> {user_msg}
                        </div>
"""
                
                # Добавляем decomposed_questions если есть
                decomposed_questions = response.get("decomposed_questions", [])
                if decomposed_questions:
                    html += """
                        <div class="message router-response">
                            <strong>🔍 Декомпозированные вопросы:</strong>
                            <ol style="margin-left: 20px; margin-top: 5px;">
"""
                    for question in decomposed_questions:
                        escaped_question = escape(question)
                        html += f'                            <li style="margin-bottom: 3px;">{escaped_question}</li>\n'
                    html += """                            </ol>
                        </div>
"""
                
                if status == "success":
                    documents = response.get("documents", [])
                    if documents:
                        html += """
                        <div class="message router-response">
                            <strong>🤖 Подобранные документы:</strong>
                            <div class="documents">
"""
                        for doc in documents:
                            html += f'<span class="document-tag">{doc}</span>'
                        html += """
                            </div>
                        </div>
"""
                elif status in ["offtopic", "need_simplification"]:
                    message = response.get("message", "")
                    if message:
                        escaped_message = escape(message)
                        html += f"""
                        <div class="message router-response">
                            <strong>💬 Сообщение роутера:</strong><br>
                            {escaped_message}
                        </div>
"""
                elif "error" in step:
                    escaped_error = escape(step['error'])
                    html += f"""
                        <div class="message router-response">
                            <strong>❌ Ошибка:</strong> {escaped_error}
                        </div>
"""
                
                html += "</div>"
            
            html += """
                </div>
            </div>
"""
        
        # Добавляем графики статистики
        html += """
            <h2 style="margin: 30px 0 20px 0;">📈 Статистика</h2>
            <div class="charts">
                <div class="chart-card">
                    <div class="chart-title">Распределение статусов</div>
"""
        
        # График статусов
        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_steps * 100) if total_steps > 0 else 0
            html += f"""
                    <div class="bar">
                        <div class="bar-label">{status}</div>
                        <div class="bar-container">
                            <div class="bar-fill" style="width: {percentage}%">
                                {count} ({percentage:.1f}%)
                            </div>
                        </div>
                    </div>
"""
        
        html += """
                </div>
                <div class="chart-card">
                    <div class="chart-title">Топ-10 документов</div>
"""
        
        # График документов
        for doc, count in list(sorted(all_docs.items(), key=lambda x: x[1], reverse=True))[:10]:
            max_count = max(all_docs.values()) if all_docs else 1
            percentage = (count / max_count * 100)
            html += f"""
                    <div class="bar">
                        <div class="bar-label">{doc}</div>
                        <div class="bar-container">
                            <div class="bar-fill" style="width: {percentage}%">
                                {count}
                            </div>
                        </div>
                    </div>
"""
        
        html += """
                </div>
            </div>
        </div>
        
        <footer>
            <p>Сгенерировано автоматически системой тестирования роутера Ukido</p>
        </footer>
    </div>
    
    <script>
        function toggleScenario(id) {
            const scenario = document.getElementById('scenario-' + id);
            scenario.classList.toggle('expanded');
        }
        
        // Автоматически разворачиваем первый диалог
        document.getElementById('scenario-1')?.classList.add('expanded');
    </script>
</body>
</html>"""
        
        # Сохраняем HTML
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            
            print(f"📄 HTML отчет сохранен в {filename.relative_to(Path.cwd())}")
            return filename.absolute()
        except Exception as e:
            print(f"❌ Ошибка при сохранении HTML отчёта: {e}")
            return str(filename)


async def main():
    """Главная функция"""
    print("╔" + "═"*58 + "╗")
    print("║" + " ТЕСТИРОВАНИЕ РОУТЕРА С HTML ОТЧЕТОМ ".center(58) + "║")
    print("╚" + "═"*58 + "╝")
    
    tester = DialogScenarioTester()
    
    # Проверяем загрузку данных
    if not tester.scenarios:
        print("\n❌ Не удалось загрузить сценарии!")
        print("Проверьте наличие файла test_scenarios.json")
        return
    
    if not tester.router.summaries:
        print("\n❌ Роутер не смог загрузить summaries.json!")
        print("Проверьте файл data/summaries.json")
        return
    
    # Запускаем тестирование
    await tester.run_all_scenarios()
    
    print("\n✨ Готово! Отчет открыт в браузере.")


if __name__ == "__main__":
    asyncio.run(main())