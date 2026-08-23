#!/usr/bin/env python3
"""Живая репетиция демо для англоязычной аудитории.

Прогоняет ровно те реплики, которые произнесёт коллега в первые минуты
общения с ботом, и проверяет главный инвариант P0: в ответах EN-диалога
нет ни одной кириллической буквы. Также проверяет, что русский диалог
не сломался.

Запуск (нужен поднятый сервер и реальный OPENROUTER_API_KEY):
    python tests/scripts/test_english_demo_rehearsal.py [--base http://localhost:8000]
"""

import argparse
import asyncio
import re
import sys
import time

import httpx

CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

# (user_id, message, ожидаемый язык, ожидаемая доля кириллицы в ответе)
EN_SCENARIOS = [
    ("demo_en_hello", "Hello! Tell me about your school", "en", False),
    ("demo_en_price", "How much do the courses cost?", "en", False),
    ("demo_en_thanks", "Thanks!", "en", False),
    ("demo_en_ack", "ok", "en", False),
    ("demo_en_offtopic", "What's the weather like today?", "en", False),
    ("demo_en_many", "What courses do you have, who teaches, what's the schedule, how do I sign up?", "en", False),
    ("demo_en_bye", "Goodbye!", "en", False),
]

STICKY_SCENARIOS = [
    ("demo_sticky", "Hi there, I'm looking for courses for my kid", "en", False),
    ("demo_sticky", "👍", "en", False),
]

RU_SCENARIOS = [
    ("demo_ru_main", "Привет! Расскажите о ваших курсах", "ru", True),
    ("demo_ru_short", "спасибо", "ru", True),
]


async def send(client: httpx.AsyncClient, base: str, user_id: str, message: str):
    start = time.time()
    response = await client.post(
        f"{base}/chat",
        json={"user_id": user_id, "message": message},
        timeout=60.0,
    )
    latency = time.time() - start
    if response.status_code != 200:
        return None, latency, f"HTTP {response.status_code}: {response.text[:120]}"
    body = response.json()
    return body, latency, None


async def main(base: str) -> int:
    failures = []
    print(f"\n🎭 Репетиция демо: {base}\n" + "=" * 78)

    async with httpx.AsyncClient() as client:
        health = await client.get(f"{base}/health", timeout=10.0)
        if health.status_code != 200:
            print(f"❌ Сервер не отвечает: {health.status_code}")
            return 1
        print(f"✅ Сервер жив: {health.json()}\n")

        for user_id, message, want_lang, want_cyrillic in EN_SCENARIOS + STICKY_SCENARIOS + RU_SCENARIOS:
            body, latency, error = await send(client, base, user_id, message)
            label = f"[{want_lang}] {message[:48]}"

            if error:
                print(f"❌ {label}\n   {error}")
                failures.append((label, error))
                continue

            text = body.get("response", "")
            got_lang = body.get("detected_language", "?")
            has_cyr = bool(CYRILLIC_RE.search(text))

            problems = []
            if got_lang != want_lang:
                problems.append(f"язык определён как {got_lang}, ожидали {want_lang}")
            if has_cyr != want_cyrillic:
                kind = "кириллица в EN-ответе" if has_cyr else "нет кириллицы в RU-ответе"
                problems.append(kind)

            status = "❌ " + "; ".join(problems) if problems else "✅"
            print(f"{status} {label}")
            print(f"    lang={got_lang}  {latency:.1f}s  → {text[:96]!r}")
            if problems:
                failures.append((label, "; ".join(problems)))

    print("=" * 78)
    total = len(EN_SCENARIOS) + len(STICKY_SCENARIOS) + len(RU_SCENARIOS)
    if failures:
        print(f"❌ ПРОВАЛЕНО {len(failures)}/{total} сценариев — демо показывать рано:")
        for label, problem in failures:
            print(f"   - {label}: {problem}")
        return 1
    print(f"✅ Все {total} сценариев чисто — демо готово.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    sys.exit(asyncio.run(main(parser.parse_args().base)))
