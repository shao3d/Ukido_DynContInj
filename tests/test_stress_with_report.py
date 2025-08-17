#!/usr/bin/env python3
"""
Стресс-тест с edge cases: проверка памяти, fuzzy matching, социальных интентов, грубости
Берёт мини-диалоги из tests/test_scenarios_stress.json
Сохраняет результаты в tests/reports с расширенной аналитикой
"""

import asyncio
import json
import sys
import webbrowser
from html import escape
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Добавляем путь к src в sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Импортируем FastAPI app и вспомогательные модули
from main import app  # type: ignore
from social_intents import detect_social_intent, SocialIntent
import httpx


class StressChainTester:
    """Стресс-тестирование с edge cases и проверкой памяти"""

    def __init__(self, scenarios_file: str = "test_scenarios_stress.json") -> None:
        self.scenarios = self._load_scenarios(scenarios_file)
        self.results: List[Dict] = []
        self.llm_calls: Dict[str, int] = {"llama": 0, "gemini": 0, "claude": 0}

    def _load_scenarios(self, filename: str) -> List[Dict]:
        try:
            scenarios_path = Path(__file__).parent / filename
            with open(scenarios_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Файл {filename} не найден!")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return []

    async def test_scenario(self, client: httpx.AsyncClient, scenario: Dict, scenario_num: int) -> Dict:
        name = scenario.get("scenario_name", f"Сценарий {scenario_num}")
        description = scenario.get("description", "")
        steps = scenario.get("steps", [])

        print(f"\n🎬 Тестирую сценарий #{scenario_num}: {name}")
        if description:
            print(f"   📝 {description}")
        print(f"   Шагов: {len(steps)}")

        # Уникальный user_id для каждого сценария (сброс памяти между сценариями)
        user_id = f"stress_user_{scenario_num}_{datetime.now().timestamp()}"

        scenario_result: Dict = {
            "name": name,
            "description": description,
            "steps": [],
            "success": True,
            "memory_test": len(steps) > 5,  # Помечаем диалоги для проверки памяти
        }

        for idx, user_message in enumerate(steps, 1):
            print(f"   • Шаг {idx}/{len(steps)}...", end="")
            try:
                payload = {"user_id": user_id, "message": user_message}
                resp = await client.post("/chat", json=payload, timeout=60.0)
                if resp.status_code != 200:
                    print(f" [HTTP {resp.status_code}]")
                    scenario_result["success"] = False
                    scenario_result["steps"].append({
                        "step": idx,
                        "user_message": user_message,
                        "error": f"HTTP {resp.status_code}: {resp.text[:200]}"
                    })
                    continue

                data = resp.json()
                intent = data.get("intent", "unknown")
                print(f" [{intent}]")

                # Определяем социальные интенты
                social_det = detect_social_intent(user_message)
                social_tag = social_det.intent.value if social_det.intent != SocialIntent.UNKNOWN else None
                
                # Проверяем, была ли вызвана LLM для социалки
                llm_social_used = data.get("llm_social_used", False)
                if llm_social_used:
                    self.llm_calls["llama"] += 1

                # Определяем, сработал ли fuzzy matching
                fuzzy_matched = data.get("fuzzy_matched", False)
                
                # Проверяем содержание мата/грубости
                has_profanity = any(marker in user_message.lower() for marker in ["х**", "о**", "бл*", "суч", "дур"])

                step_entry = {
                    "step": idx,
                    "user_message": user_message,
                    "intent": intent,
                    "assistant_response": data.get("response", ""),
                    "relevant_documents": data.get("relevant_documents", []),
                    "decomposed_questions": data.get("decomposed_questions", []),
                    "raw_router_status": data.get("raw_router_status"),
                    "social": social_tag,
                    "llm_social_used": llm_social_used,
                    "fuzzy_matched": fuzzy_matched,
                    "has_profanity": has_profanity,
                    "memory_position": idx,  # Позиция в диалоге для анализа памяти
                }
                scenario_result["steps"].append(step_entry)

            except Exception as e:
                print(f" [ОШИБКА: {e}]")
                scenario_result["success"] = False
                scenario_result["steps"].append({
                    "step": idx,
                    "user_message": user_message,
                    "error": str(e),
                })

            await asyncio.sleep(0.2)

        return scenario_result

    async def run_all(self) -> None:
        if not self.scenarios:
            print("❌ Нет сценариев для тестирования!")
            return

        print("\n" + "=" * 60)
        print("🚀 ЗАПУСК СТРЕСС-ТЕСТИРОВАНИЯ С EDGE CASES")
        print("=" * 60)
        print(f"📋 Загружено сценариев: {len(self.scenarios)}")

        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            for i, scenario in enumerate(self.scenarios, 1):
                result = await self.test_scenario(client, scenario, i)
                self.results.append(result)
                if i < len(self.scenarios):
                    await asyncio.sleep(0.5)

        print("\n✅ Тестирование завершено!")
        self._print_summary()
        self._save_json_results()
        html_file = self._generate_html_report()
        print(f"\n🌐 Открываю отчет в браузере: {html_file}")
        webbrowser.open(f"file://{html_file}")

    def _print_summary(self) -> None:
        print("\n" + "=" * 60)
        print("📊 СВОДКА РЕЗУЛЬТАТОВ")
        print("=" * 60)
        
        total_scenarios = len(self.results)
        successful = sum(1 for r in self.results if r.get("success"))
        
        print(f"✅ Успешных сценариев: {successful}/{total_scenarios}")
        print(f"📞 Вызовов LLM для социалки: {self.llm_calls['llama']}")
        
        # Анализ fuzzy matching
        fuzzy_count = sum(
            1 for scenario in self.results 
            for step in scenario.get("steps", []) 
            if step.get("fuzzy_matched")
        )
        print(f"🔍 Сработал fuzzy matching: {fuzzy_count} раз")
        
        # Анализ обработки грубости
        profanity_count = sum(
            1 for scenario in self.results 
            for step in scenario.get("steps", []) 
            if step.get("has_profanity")
        )
        print(f"🤬 Обработано грубостей: {profanity_count}")
        
        # Анализ памяти
        memory_scenarios = [s for s in self.results if s.get("memory_test")]
        print(f"🧠 Сценариев с проверкой памяти (>5 шагов): {len(memory_scenarios)}")

    def _save_json_results(self) -> None:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            reports_dir = Path(__file__).parent / "reports"
            reports_dir.mkdir(exist_ok=True)
            out = reports_dir / f"test_results_stress_{ts}.json"
            
            # Добавляем метаданные
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "total_scenarios": len(self.results),
                "llm_calls": self.llm_calls,
                "scenarios": self.results
            }
            
            with open(out, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"💾 JSON результаты сохранены в {out.relative_to(Path.cwd())}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении JSON отчёта: {e}")

    def _generate_html_report(self) -> str:
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = reports_dir / f"test_report_stress_{now.strftime('%Y%m%d_%H%M%S')}.html"

        total_scenarios = len(self.results)
        successful = sum(1 for r in self.results if r.get("success"))
        total_steps = sum(len(r.get("steps", [])) for r in self.results)

        # Статистика по intent
        status_counts: Dict[str, int] = {}
        for scenario in self.results:
            for step in scenario.get("steps", []):
                st = step.get("intent", "error")
                status_counts[st] = status_counts.get(st, 0) + 1

        # Анализ edge cases
        edge_stats = {
            "fuzzy_matches": sum(1 for s in self.results for st in s.get("steps", []) if st.get("fuzzy_matched")),
            "llm_social": sum(1 for s in self.results for st in s.get("steps", []) if st.get("llm_social_used")),
            "profanity": sum(1 for s in self.results for st in s.get("steps", []) if st.get("has_profanity")),
            "memory_tests": sum(1 for s in self.results if s.get("memory_test")),
        }

        html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Стресс-тест Ukido - {ts}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                line-height: 1.6; color: #333; max-width: 1400px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                  gap: 20px; margin: 20px 0; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .stat-number {{ font-size: 2em; font-weight: bold; }}
        .scenario {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 10px; 
                     border-left: 5px solid #3498db; }}
        .scenario.failed {{ border-left-color: #e74c3c; }}
        .scenario-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .steps {{ margin-top: 15px; }}
        .step {{ background: white; padding: 15px; margin: 10px 0; border-radius: 5px; 
                 border: 1px solid #dee2e6; }}
        .user-msg {{ color: #2c3e50; font-weight: 600; margin-bottom: 8px; }}
        .assistant-msg {{ color: #27ae60; background: #f0f9ff; padding: 10px; 
                          border-radius: 5px; margin: 10px 0; }}
        .error {{ color: #e74c3c; background: #fee; padding: 10px; border-radius: 5px; }}
        .intent {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 0.85em; 
                   font-weight: 600; margin-left: 10px; }}
        .intent-success {{ background: #d4edda; color: #155724; }}
        .intent-offtopic {{ background: #fff3cd; color: #856404; }}
        .intent-error {{ background: #f8d7da; color: #721c24; }}
        .docs {{ color: #6c757d; font-size: 0.9em; margin-top: 5px; }}
        .edge-indicator {{ display: inline-block; margin-left: 5px; padding: 2px 6px; 
                          border-radius: 3px; font-size: 0.8em; font-weight: bold; }}
        .fuzzy {{ background: #e3f2fd; color: #1565c0; }}
        .llm {{ background: #f3e5f5; color: #6a1b9a; }}
        .profanity {{ background: #ffebee; color: #c62828; }}
        .memory {{ background: #e8f5e9; color: #2e7d32; }}
        .description {{ color: #666; font-style: italic; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>🚀 Стресс-тест Ukido AI Chatbot - {ts}</h1>
    
    <div class="stats">
        <div class="stat-card">
            <div class="stat-number">{successful}/{total_scenarios}</div>
            <div>Успешных сценариев</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{total_steps}</div>
            <div>Всего шагов</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{edge_stats['fuzzy_matches']}</div>
            <div>Fuzzy matches</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{edge_stats['llm_social']}</div>
            <div>LLM social calls</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{edge_stats['profanity']}</div>
            <div>Грубость обработана</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{edge_stats['memory_tests']}</div>
            <div>Тесты памяти</div>
        </div>
    </div>

    <h2>📊 Распределение по статусам</h2>
    <ul>
        {"".join(f'<li><strong>{st}:</strong> {cnt} шагов</li>' for st, cnt in sorted(status_counts.items()))}
    </ul>

    <h2>🎬 Детали сценариев</h2>
"""

        for scenario in self.results:
            name = escape(scenario.get("name", "Без названия"))
            description = escape(scenario.get("description", ""))
            success = scenario.get("success", False)
            memory_test = scenario.get("memory_test", False)
            class_name = "scenario" if success else "scenario failed"
            
            html_content += f"""
    <div class="{class_name}">
        <div class="scenario-header">
            <h3>{name}</h3>
            <span>{"✅ Успешно" if success else "❌ Провалено"}</span>
        </div>
        {f'<div class="description">{description}</div>' if description else ''}
        {f'<div class="edge-indicator memory">🧠 Тест памяти (>5 шагов)</div>' if memory_test else ''}
        <div class="steps">
"""

            for step in scenario.get("steps", []):
                step_num = step.get("step", "?")
                user_msg = escape(step.get("user_message", ""))
                assistant_msg = escape(step.get("assistant_response", ""))
                intent = step.get("intent", "unknown")
                error = step.get("error")
                docs = step.get("relevant_documents", [])
                
                # Edge indicators
                indicators = []
                if step.get("fuzzy_matched"):
                    indicators.append('<span class="edge-indicator fuzzy">🔍 Fuzzy</span>')
                if step.get("llm_social_used"):
                    indicators.append('<span class="edge-indicator llm">🤖 LLM</span>')
                if step.get("has_profanity"):
                    indicators.append('<span class="edge-indicator profanity">🤬 Грубость</span>')
                if step.get("memory_position", 0) > 5:
                    indicators.append('<span class="edge-indicator memory">🧠 После 5 шагов</span>')
                
                intent_class = f"intent-{intent}" if intent in ["success", "offtopic"] else "intent-error"
                
                html_content += f"""
            <div class="step">
                <div class="user-msg">
                    👤 Шаг {step_num}: {user_msg}
                    <span class="intent {intent_class}">{intent}</span>
                    {"".join(indicators)}
                </div>
"""
                
                if error:
                    html_content += f'                <div class="error">⚠️ Ошибка: {escape(error)}</div>\n'
                else:
                    html_content += f'                <div class="assistant-msg">🤖 {assistant_msg}</div>\n'
                    if docs:
                        html_content += f'                <div class="docs">📄 Документы: {", ".join(escape(d) for d in docs)}</div>\n'
                
                html_content += "            </div>\n"
            
            html_content += "        </div>\n    </div>\n"

        html_content += """
</body>
</html>"""

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return str(filename)


async def main():
    """Основная функция запуска"""
    tester = StressChainTester()
    await tester.run_all()


if __name__ == "__main__":
    asyncio.run(main())