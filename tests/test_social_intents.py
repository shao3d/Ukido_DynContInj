#!/usr/bin/env python3
"""
Unit-тесты для социального модуля:
- detect_social_intent (regex/эвристики)
- SocialResponder (шаблонные ответы + антидублирование)
- (опционально) LLM-классификатор, если установлен OPENROUTER_API_KEY и RUN_SOCIAL_LLM_TESTS=1

Запуск:
1) Быстрый скриптовый (без pytest):
   python tests/test_social_intents.py

2) Через pytest (рекомендуется):
   pip install pytest  # один раз
   pytest -q tests/test_social_intents.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавляем src в sys.path
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.append(str(SRC))

from social_intents import detect_social_intent, SocialIntent
from social_state import SocialStateManager
from social_responder import SocialResponder

# LLM fallback (опционально)
try:
    from social_llm_classifier import classify_social_with_llm
    from openrouter_client import OpenRouterClient
except Exception:  # pragma: no cover
    classify_social_with_llm = None
    OpenRouterClient = None


# === ТЕСТЫ ДЛЯ INTENTS ===
BASIC_CASES = [
    ("Привет!", SocialIntent.GREETING),
    ("Здравствуйте", SocialIntent.GREETING),
    ("Добрый вечер", SocialIntent.GREETING),
    ("Спасибо большое", SocialIntent.THANKS),
    ("Пока!", SocialIntent.FAREWELL),
    ("Сколько стоит курс?", SocialIntent.UNKNOWN),
]

MIXED_CASES = [
    ("Привет, сколько стоит курс?", SocialIntent.UNKNOWN),
    ("Спасибо, а как записаться на пробный?", SocialIntent.UNKNOWN),
]


def run_basic_intent_tests():
    ok = True
    for text, expected in BASIC_CASES:
        det = detect_social_intent(text)
        if det.intent != expected:
            print(f"[FAIL] Intent for '{text}' => {det.intent}, expected {expected}")
            ok = False
        else:
            print(f"[PASS] Intent for '{text}' => {det.intent}")
    for text, expected in MIXED_CASES:
        det = detect_social_intent(text)
        if det.intent != expected:
            print(f"[FAIL] Mixed '{text}' => {det.intent}, expected {expected}")
            ok = False
        else:
            print(f"[PASS] Mixed '{text}' => {det.intent}")
    return ok


# === ТЕСТЫ ДЛЯ RESPONDER ===

def run_responder_tests():
    ok = True
    state = SocialStateManager()
    r = SocialResponder(state)
    sid = "test-session"

    # Первое приветствие — полноценное
    ans1 = r.respond(sid, SocialIntent.GREETING)
    if "Чем помочь" not in ans1:
        print(f"[FAIL] GREETING first response: {ans1}")
        ok = False
    else:
        print("[PASS] GREETING first response")

    # Второе приветствие — короткое подтверждение
    ans2 = r.respond(sid, SocialIntent.GREETING)
    if "на связи" not in ans2:
        print(f"[FAIL] GREETING repeated response: {ans2}")
        ok = False
    else:
        print("[PASS] GREETING repeated response")

    # THANKS
    ans3 = r.respond(sid, SocialIntent.THANKS)
    if "Пожалуйста" not in ans3:
        print(f"[FAIL] THANKS response: {ans3}")
        ok = False
    else:
        print("[PASS] THANKS response")

    # FAREWELL
    ans4 = r.respond(sid, SocialIntent.FAREWELL)
    if "Хорошего дня" not in ans4:
        print(f"[FAIL] FAREWELL response: {ans4}")
        ok = False
    else:
        print("[PASS] FAREWELL response")

    return ok


# === ОПЦИОНАЛЬНО: LLM-КЛАССИФИКАТОР ===
async def run_llm_classifier_smoke() -> bool:
    if not (classify_social_with_llm and OpenRouterClient):
        print("[SKIP] LLM classifier module not available")
        return True
    if os.environ.get("RUN_SOCIAL_LLM_TESTS") != "1":
        print("[SKIP] Set RUN_SOCIAL_LLM_TESTS=1 to run LLM smoke test")
        return True
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("[SKIP] OPENROUTER_API_KEY is not set")
        return True

    client = OpenRouterClient(api_key, temperature=0.0, max_tokens=32)
    res = await classify_social_with_llm(client, "Привет")
    if not res:
        print("[FAIL] LLM returned no result")
        return False
    if res.cls not in ("greeting", "thanks", "farewell", "other"):
        print(f"[FAIL] LLM cls invalid: {res.cls}")
        return False
    print(f"[PASS] LLM smoke: {res.cls} ({res.confidence:.2f})")
    return True


def _script_main():
    print("=== Social intents tests ===")
    ok1 = run_basic_intent_tests()
    print("\n=== Social responder tests ===")
    ok2 = run_responder_tests()
    print("\n=== Social LLM classifier (optional) ===")
    ok3 = asyncio.run(run_llm_classifier_smoke())

    ok = ok1 and ok2 and ok3
    print(f"\nRESULT: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _script_main()
