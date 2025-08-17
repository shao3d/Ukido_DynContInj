#!/usr/bin/env python3
"""
Система сохранения и проверки "золотых" (эталонных) ответов
Позволяет отслеживать регрессии в качестве ответов
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import difflib

class GoldenResponseManager:
    def __init__(self, file_path: str = "golden_responses.json"):
        self.file_path = Path(file_path)
        self.responses = self._load()
    
    def _load(self) -> Dict:
        """Загружает сохраненные золотые ответы"""
        if self.file_path.exists():
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_golden(self, question: str, response: str, metadata: Optional[Dict] = None):
        """Сохраняет ответ как эталонный"""
        self.responses[question] = {
            "response": response,
            "saved_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self._persist()
        print(f"✅ Сохранен золотой ответ для: '{question[:50]}...'")
    
    def check_regression(self, question: str, new_response: str, threshold: float = 0.85) -> Dict:
        """Проверяет, не деградировал ли ответ"""
        if question not in self.responses:
            return {"status": "no_golden", "similarity": 0.0}
        
        golden = self.responses[question]["response"]
        
        # Вычисляем схожесть
        similarity = self._calculate_similarity(golden, new_response)
        
        if similarity < threshold:
            # Показываем diff
            diff = self._get_diff(golden, new_response)
            return {
                "status": "regression",
                "similarity": similarity,
                "diff": diff,
                "golden": golden[:200],
                "new": new_response[:200]
            }
        
        return {"status": "ok", "similarity": similarity}
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть двух текстов (0.0 - 1.0)"""
        return difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def _get_diff(self, text1: str, text2: str) -> str:
        """Возвращает diff между текстами"""
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile='golden',
            tofile='new',
            n=1
        )
        return ''.join(diff)
    
    def _persist(self):
        """Сохраняет в файл"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.responses, f, ensure_ascii=False, indent=2)
    
    def list_golden(self):
        """Показывает все сохраненные золотые ответы"""
        print("\n📝 GOLDEN RESPONSES:")
        print("=" * 60)
        for i, (question, data) in enumerate(self.responses.items(), 1):
            saved_at = data.get('saved_at', 'Unknown')
            print(f"{i}. {question[:50]}...")
            print(f"   Сохранено: {saved_at}")
        print("=" * 60)


# Использование в interactive_test.py:
# golden = GoldenResponseManager()
# 
# # Сохранить эталон:
# golden.save_golden("Привет! Сколько стоит?", response)
# 
# # Проверить регрессию:
# result = golden.check_regression("Привет! Сколько стоит?", new_response)
# if result["status"] == "regression":
#     print(f"⚠️ РЕГРЕССИЯ! Схожесть: {result['similarity']:.2%}")
#     print(result["diff"])