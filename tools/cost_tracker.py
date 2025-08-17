#!/usr/bin/env python3
"""
Трекер стоимости API вызовов
Показывает сколько стоит каждый запрос в реальном времени
"""

from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CostTracker:
    """Отслеживает стоимость API вызовов"""
    
    # Цены за 1M токенов
    PRICES = {
        "gemini-2.5-flash": {"input": 0.30, "output": 0.30},
        "claude-3.5-haiku": {"input": 0.25, "output": 1.25},
        "llama-3.1-8b": {"input": 0.05, "output": 0.05}  # Больше не используется
    }
    
    session_costs: List[Dict] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    
    def add_call(self, model: str, input_tokens: int, output_tokens: int):
        """Добавляет информацию о вызове API"""
        
        # Находим правильное имя модели
        model_key = None
        if "gemini" in model.lower():
            model_key = "gemini-2.5-flash"
        elif "claude" in model.lower() or "haiku" in model.lower():
            model_key = "claude-3.5-haiku"
        elif "llama" in model.lower():
            model_key = "llama-3.1-8b"
        
        if not model_key:
            return
        
        # Рассчитываем стоимость
        prices = self.PRICES[model_key]
        input_cost = (input_tokens / 1_000_000) * prices["input"]
        output_cost = (output_tokens / 1_000_000) * prices["output"]
        total_cost = input_cost + output_cost
        
        # Сохраняем
        self.session_costs.append({
            "timestamp": datetime.now().isoformat(),
            "model": model_key,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": total_cost
        })
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
    
    def get_session_summary(self) -> str:
        """Возвращает красивую сводку по сессии"""
        if not self.session_costs:
            return "Нет данных о стоимости"
        
        total_cost = sum(call["cost"] for call in self.session_costs)
        
        # Группируем по моделям
        by_model = {}
        for call in self.session_costs:
            model = call["model"]
            if model not in by_model:
                by_model[model] = {"calls": 0, "cost": 0, "tokens": 0}
            by_model[model]["calls"] += 1
            by_model[model]["cost"] += call["cost"]
            by_model[model]["tokens"] += call["input_tokens"] + call["output_tokens"]
        
        # Форматируем вывод
        lines = []
        lines.append("\n💰 COST SUMMARY")
        lines.append("=" * 50)
        lines.append(f"Total Cost: ${total_cost:.6f}")
        lines.append(f"Total Tokens: {self.total_input_tokens + self.total_output_tokens:,}")
        lines.append("")
        lines.append("By Model:")
        
        for model, stats in by_model.items():
            emoji = "🔮" if "gemini" in model else "🤖" if "claude" in model else "🦙"
            lines.append(f"{emoji} {model}:")
            lines.append(f"   Calls: {stats['calls']}")
            lines.append(f"   Tokens: {stats['tokens']:,}")
            lines.append(f"   Cost: ${stats['cost']:.6f}")
        
        lines.append("=" * 50)
        
        # Средняя стоимость за запрос
        avg_cost = total_cost / len(self.session_costs)
        lines.append(f"Average per request: ${avg_cost:.6f}")
        
        # Проекция на 1000 запросов
        projected = avg_cost * 1000
        lines.append(f"Projected for 1K requests: ${projected:.2f}")
        
        return "\n".join(lines)
    
    def get_last_call_cost(self) -> str:
        """Возвращает стоимость последнего вызова"""
        if not self.session_costs:
            return ""
        
        last = self.session_costs[-1]
        return f"💵 Cost: ${last['cost']:.6f} ({last['model']}, {last['input_tokens'] + last['output_tokens']} tokens)"


# Глобальный трекер
COST_TRACKER = CostTracker()

def estimate_tokens(text: str) -> int:
    """Грубая оценка количества токенов"""
    # Примерно 1 токен = 4 символа для английского
    # Примерно 1 токен = 2 символа для русского/украинского
    return len(text) // 3


# Использование:
# from cost_tracker import COST_TRACKER, estimate_tokens
# 
# # При вызове API:
# input_tokens = estimate_tokens(prompt)
# output_tokens = estimate_tokens(response)
# COST_TRACKER.add_call("gemini-2.5-flash", input_tokens, output_tokens)
# 
# # В конце сессии:
# print(COST_TRACKER.get_session_summary())