#!/usr/bin/env python3
"""
Полный прогон цепочки: FastAPI main (/chat) + Router + ResponseGenerator
Берёт мини-диалоги из tests/test_scenarios.json
Сохраняет результаты в tests/reports: JSON и HTML
"""

import asyncio
import json
import sys
import webbrowser
from html import escape
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Добавляем путь к src в sys.path (на уровень выше tests)
sys.path.append(str(Path(__file__).parent.parent / "src"))

# Импортируем FastAPI app
from main import app  # type: ignore
from social_intents import detect_social_intent, SocialIntent
import httpx


class FullChainTester:
    """E2E тестирование через HTTP (ASGI) интерфейс /chat"""

    def __init__(self) -> None:
        self.scenarios = self._load_scenarios()
        self.results: List[Dict] = []

    def _load_scenarios(self) -> List[Dict]:
        try:
            scenarios_path = Path(__file__).parent / "test_scenarios.json"
            with open(scenarios_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print("❌ Файл test_scenarios.json не найден!")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return []

    async def test_scenario(self, client: httpx.AsyncClient, scenario: Dict, scenario_num: int) -> Dict:
        name = scenario.get("scenario_name", f"Сценарий {scenario_num}")
        steps = scenario.get("steps", [])

        print(f"\n🎬 Тестирую сценарий #{scenario_num}: {name}")
        print(f"   Шагов: {len(steps)}")

        # Для истории в main используется user_id, возьмём уникальный на сценарий
        user_id = f"test_user_{scenario_num}"

        scenario_result: Dict = {
            "name": name,
            "steps": [],
            "success": True,
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

                # Дополнительно определяем социальные реплики по правилам (без LLM)
                social_det = detect_social_intent(user_message)
                social_tag = social_det.intent.value if social_det.intent != SocialIntent.UNKNOWN else None

                step_entry = {
                    "step": idx,
                    "user_message": user_message,
                    "intent": intent,
                    "assistant_response": data.get("response", ""),
                    "relevant_documents": data.get("relevant_documents", []),
                    "decomposed_questions": data.get("decomposed_questions", []),
                    "raw_router_status": data.get("raw_router_status"),
                    "social": social_tag,
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
        print("🚀 ЗАПУСК ПОЛНОГО ТЕСТИРОВАНИЯ (main + router + responsegenerator)")
        print("=" * 60)
        print(f"📋 Загружено сценариев: {len(self.scenarios)}")

        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            for i, scenario in enumerate(self.scenarios, 1):
                result = await self.test_scenario(client, scenario, i)
                self.results.append(result)
                if i < len(self.scenarios):
                    await asyncio.sleep(0.5)

        print("\n✅ Тестирование завершено!")
        self._save_json_results()
        html_file = self._generate_html_report()
        print(f"\n🌐 Открываю отчет в браузере: {html_file}")
        webbrowser.open(f"file://{html_file}")

    def _save_json_results(self) -> None:
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            reports_dir = Path(__file__).parent / "reports"
            reports_dir.mkdir(exist_ok=True)
            out = reports_dir / f"test_results_fullchain_{ts}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            print(f"💾 JSON результаты сохранены в {out.relative_to(Path.cwd())}")
        except Exception as e:
            print(f"❌ Ошибка при сохранении JSON отчёта: {e}")

    def _generate_html_report(self) -> str:
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = reports_dir / f"test_report_fullchain_{now.strftime('%Y%m%d_%H%M%S')}.html"

        total_scenarios = len(self.results)
        successful = sum(1 for r in self.results if r.get("success"))
        total_steps = sum(len(r.get("steps", [])) for r in self.results)

    # распределение intent
        status_counts: Dict[str, int] = {}
        for scenario in self.results:
            for step in scenario.get("steps", []):
                st = step.get("intent", "error")
                status_counts[st] = status_counts.get(st, 0) + 1

        # топ документов
        all_docs: Dict[str, int] = {}
        for scenario in self.results:
            for step in scenario.get("steps", []):
                for d in step.get("relevant_documents", []):
                    all_docs[d] = all_docs.get(d, 0) + 1

        # Подсчёт social-реплик
        social_counts: Dict[str, int] = {"greeting": 0, "thanks": 0, "farewell": 0}
        for scenario in self.results:
            for step in scenario.get("steps", []):
                tag = step.get("social")
                if tag in social_counts:
                    social_counts[tag] += 1

        # HTML
        html = f"""<!DOCTYPE html>
<html lang=\"ru\">
<head>
<meta charset=\"UTF-8\">
<title>Отчет полного тестирования Ukido - {ts}</title>
<style>
body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Ubuntu,sans-serif; background:#f5f6fa; color:#222; padding:20px; }}
.container {{ max-width: 1200px; margin:0 auto; background:#fff; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,.08); overflow:hidden; }}
header {{ background:linear-gradient(135deg,#00c6ff,#0072ff); color:#fff; padding:24px; }}
h1 {{ margin:0; font-size:24px; }}
.timestamp {{ opacity:.9 }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; padding:16px; background:#fafbff; border-bottom:1px solid #eee; }}
.card {{ background:#fff; border:1px solid #eee; border-radius:8px; padding:16px; text-align:center; }}
.val {{ font-size:28px; color:#0072ff; font-weight:700; }}
.label {{ color:#666; }}
.content {{ padding:20px; }}
.scenario {{ border:1px solid #eee; border-radius:8px; margin-bottom:16px; }}
.scenario-header {{ background:#fafbff; padding:12px 16px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; }}
.scenario-title {{ font-weight:700; }}
.scenario-body {{ display:none; padding:16px; }}
.scenario.expanded .scenario-body {{ display:block; }}
.step {{ background:#f9fafc; border-left:4px solid #0072ff; padding:12px; margin-bottom:12px; border-radius:6px; }}
.badge {{ padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }}
.badge.success {{ background:#d4edda; color:#155724; }}
.badge.offtopic {{ background:#fff3cd; color:#856404; }}
.badge.need_simplification {{ background:#e2e3ff; color:#383d7c; }}
.badge.error {{ background:#f8d7da; color:#721c24; }}
.msg {{ background:#fff; border:1px solid #eee; border-radius:6px; padding:10px; margin-top:8px; }}
.docs span {{ background:#eef2ff; padding:3px 8px; border-radius:4px; margin-right:6px; font-size:12px; }}
.chart {{ background:#fff; border:1px solid #eee; border-radius:8px; padding:16px; }}
.bar {{ display:flex; align-items:center; margin:6px 0; }}
.bar-label {{ width:160px; font-size:12px; color:#555; }}
.bar-wrap {{ flex:1; background:#f0f2f7; height:22px; border-radius:6px; overflow:hidden; }}
.bar-fill {{ background:linear-gradient(90deg,#00c6ff,#0072ff); height:100%; color:#fff; font-size:12px; display:flex; align-items:center; justify-content:flex-end; padding-right:6px; }}
/* Markdown styling */
.markdown-body h1, .markdown-body h2, .markdown-body h3 {{ margin: 12px 0 8px; }}
.markdown-body p {{ margin: 6px 0; }}
.markdown-body ul, .markdown-body ol {{ padding-left: 1.2em; margin: 6px 0; }}
.markdown-body code, .markdown-body pre {{ background:#f6f8fa; border-radius:6px; }}
.markdown-body pre {{ padding:10px; overflow:auto; white-space:pre; }}
</style>
</head>
<body>
<div class=container>
<header>
<h1>📊 Полный отчёт Ukido</h1>
<div class=timestamp>📅 {ts}</div>
</header>
<div class=summary>
<div class=card><div class=val>{total_scenarios}</div><div class=label>Всего диалогов</div></div>
<div class=card><div class=val>{successful}</div><div class=label>Успешных</div></div>
<div class=card><div class=val>{total_steps}</div><div class=label>Всего шагов</div></div>
<div class=card><div class=val>{(successful/total_scenarios*100 if total_scenarios else 0):.1f}%</div><div class=label>Успешность</div></div>
<div class=card><div class=val>{social_counts['greeting']} / {social_counts['thanks']} / {social_counts['farewell']}</div><div class=label>Social: привет/спасибо/пока</div></div>
</div>
<div class=content>
<h2 style="margin:8px 0 16px 0">📝 Диалоги</h2>
"""
        # Диалоги
        for i, scenario in enumerate(self.results, 1):
            success_icon = "✅" if scenario.get("success") else "❌"
            title = escape(scenario.get("name", f"Диалог {i}"))
            html += f"""
<div class="scenario" id="sc-{i}">
  <div class="scenario-header" onclick="document.getElementById('sc-{i}').classList.toggle('expanded')">
    <div class="scenario-title">{success_icon} Диалог #{i}: {title}</div>
    <div>{len(scenario.get('steps', []))} шагов</div>
  </div>
  <div class="scenario-body">
"""
            for step in scenario.get("steps", []):
                step_no = step.get("step")
                intent = step.get("intent", "error")
                badge_class = {
                    "success": "success",
                    "offtopic": "offtopic",
                    "need_simplification": "need_simplification",
                }.get(intent, "error")
                user_msg = escape(step.get("user_message", ""))
                social_badge = step.get("social")
                # Рендерим Markdown ответа в HTML для удобочитаемости в отчёте
                assistant_md = step.get("assistant_response", "") or ""
                if assistant_md:
                    try:
                        import importlib
                        md_mod = importlib.import_module("markdown")
                        md_func = getattr(md_mod, "markdown", None)
                        assistant_resp = md_func(assistant_md, extensions=["extra", "sane_lists"]) if md_func else escape(assistant_md)
                    except Exception:
                        assistant_resp = escape(assistant_md)
                else:
                    assistant_resp = ""
                docs = step.get("relevant_documents", [])
                decomp = step.get("decomposed_questions", []) or []
                raw_status = step.get("raw_router_status")
                html += f"""
        <div class="step">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <div style="display:flex;gap:8px;align-items:center;">
                    <div><strong>Шаг {step_no}</strong></div>
                    {('<div class="badge" style="background:#e8f5e9;color:#2e7d32;">social: ' + social_badge + '</div>') if social_badge else ''}
                </div>
                <div class="badge {badge_class}">{intent}</div>
            </div>
      <div class="msg"><strong>👤 Вопрос:</strong> {user_msg}</div>
    <div class="msg markdown-body"><strong>🤖 Ответ:</strong><div>{assistant_resp}</div></div>
"""
                if decomp:
                    html += "<div class=msg><strong>🔍 Декомпозиция:</strong><ol style=\"margin:6px 0 0 18px;\">" + "".join(
                        f"<li>{escape(q)}</li>" for q in decomp
                    ) + "</ol></div>"
                if raw_status and raw_status != intent:
                    html += f"<div class=msg><strong>🧪 Router status:</strong> {escape(raw_status)}</div>"
                if docs:
                    html += "<div class=msg><strong>📚 Документы:</strong> <span class=docs>" + " ".join(
                        f"<span>{escape(d)}</span>" for d in docs
                    ) + "</span></div>"
                if step.get("error"):
                    html += f"<div class=msg><strong>❌ Ошибка:</strong> {escape(step['error'])}</div>"
                html += "</div>"
            html += "</div></div>"

        # Статистика
        html += """
<h2 style="margin:24px 0 12px 0">📈 Статистика</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;">
  <div class=chart>
    <div style="font-weight:700;margin-bottom:8px;">Распределение intent</div>
"""
        for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_steps * 100) if total_steps else 0
            html += f"""
    <div class=bar>
      <div class=bar-label>{escape(status)}</div>
      <div class=bar-wrap><div class=bar-fill style="width:{pct:.1f}%">{count} ({pct:.1f}%)</div></div>
    </div>
"""
        html += "</div>\n  <div class=chart>\n    <div style=\"font-weight:700;margin-bottom:8px;\">Топ-10 документов</div>\n"
        top_docs = list(sorted(all_docs.items(), key=lambda x: x[1], reverse=True))[:10]
        maxc = max([c for _, c in top_docs], default=1)
        for doc, c in top_docs:
            pct = (c / maxc * 100) if maxc else 0
            html += f"""
    <div class=bar>
      <div class=bar-label>{escape(doc)}</div>
      <div class=bar-wrap><div class=bar-fill style="width:{pct:.1f}%">{c}</div></div>
    </div>
"""
        html += "</div>\n</div>\n</div>\n<footer style=\"padding:12px;text-align:center;color:#666;border-top:1px solid #eee;\">Сгенерировано системой полного тестирования Ukido</footer>\n</div>\n<script>document.getElementById('sc-1')?.classList.add('expanded');</script>\n</body>\n</html>"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"📄 HTML отчет сохранен в {filename.relative_to(Path.cwd())}")
            return str(filename.absolute())
        except Exception as e:
            print(f"❌ Ошибка при сохранении HTML отчёта: {e}")
            return str(filename)


async def main():
    print("╔" + "═" * 58 + "╗")
    print("║" + " ПОЛНОЕ ТЕСТИРОВАНИЕ (MAIN + ROUTER + RESPONSEGEN) ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")

    tester = FullChainTester()
    if not tester.scenarios:
        print("\n❌ Не удалось загрузить сценарии! Проверьте tests/test_scenarios.json")
        return

    await tester.run_all()
    print("\n✨ Готово! Отчет открыт в браузере.")


if __name__ == "__main__":
    asyncio.run(main())
