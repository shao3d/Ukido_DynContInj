"""P1: разморозка стиля и устранение фейковой «печати» в стриминге.

Регрессии ревью диалогового качества (этап P1):
1. _final_sanitize больше не ампутирует восклицательные знаки, не
   дедуплицирует предложения регэкспом и не схлопывает абзацы \n\n.
2. Генератор вызывает LLM с температурой из конфига (ANSWER_TEMPERATURE),
   а не с «брошюрными» 0.1.
3. Инструкция завершённого действия не затирается social_context'ом.
4. /chat/stream не добавляет искусственную задержку между словами.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")

from response_generator import ResponseGenerator  # noqa: E402


@pytest.fixture()
def generator():
    return ResponseGenerator()


# --- 1. _final_sanitize сохраняет живой текст ---------------------------------

def test_sanitize_keeps_exclamation_and_paragraphs(generator):
    text = "Привет! Рады видеть вас.\n\nКурс Эмоциональный Компас подойдёт отлично!"
    out = generator._final_sanitize(text)
    assert "!" in out
    assert "\n\n" in out  # абзацные разрывы не схлопываются


def test_sanitize_no_longer_dedups_sentences(generator):
    text = "Мы верим в практику. Практика важна. Мы верим в практику."
    out = generator._final_sanitize(text)
    assert out.count("Мы верим в практику") == 2  # дублей больше не режем


def test_sanitize_still_repairs_truncated_tail(generator):
    out = generator._final_sanitize("Первое предложение. Обрезанное предложение без конца")
    assert out.endswith(".")


# --- 2. Температура из конфига передаётся per-call -----------------------------

def test_generate_passes_answer_temperature(generator):
    seen = {}

    async def fake_chat(messages, **kwargs):
        seen.update(kwargs)
        return "Хороший вопрос."

    generator.client.chat = fake_chat
    generator._load_docs = lambda docs: {"faq.md": "facts"}

    asyncio.run(generator.generate(
        {
            "status": "success",
            "documents": ["faq.md"],
            "decomposed_questions": ["Что такое школа?"],
            "user_signal": "exploring_only",
            "detected_language": "ru",
            "cta_blocked": True,
        },
        history=[],
        current_message="Расскажите о школе",
    ))
    assert seen.get("temperature") == pytest.approx(generator.cfg.ANSWER_TEMPERATURE)
    assert generator.cfg.ANSWER_TEMPERATURE >= 0.5  # дефолт больше не «брошюрный»


# --- 3. Соц-контекст не затирает инструкцию завершённого действия -------------

def test_social_context_does_not_wipe_completed_action_instruction(generator):
    messages = generator._build_messages(
        {"faq.md": "facts"}, ["Как записаться?"], [],
        {
            "status": "success",
            "user_signal": "exploring_only",
            "decomposed_questions": ["Как записаться?"],
            "original_message": "Привет! Я записалась на пробное",
            "social_context": "greeting",
            "user_completed_action": "registered",
            "detected_language": "ru",
        },
        cta_text=None,
    )
    tail = messages[-1]["content"]
    assert "УЖЕ выполнил действие" in tail
    assert "поздоровался" in tail


# --- 4. Стриминг без искусственной задержки ------------------------------------

def test_stream_chunks_have_no_artificial_typing_delay():
    sys.modules.pop("main", None)
    import importlib
    os.environ["PERSISTENCE_BASE_PATH"] = str(Path(os.environ.get("TMPDIR", "/tmp")) / "p1_states")
    os.environ["DETERMINISTIC_MODE"] = "true"
    main = importlib.import_module("main")

    long_text = " ".join(["слово"] * 300)  # со sleep(0.05) это ≥15 секунд

    async def collect():
        return [chunk async for chunk in main.stream_response_chunks(long_text)]

    chunks = asyncio.run(asyncio.wait_for(collect(), timeout=2.0))
    assert "".join(chunks) == long_text


# --- 5. Markdown снимается и после перевода; история не опровергается ----------

def test_markdown_stripped_after_translation(generator):
    seen = {}

    async def fake_chat(messages, **kwargs):
        return "Ответ с **жирным** и заголовком"

    async def fake_translate(text, target_language, source_language="ru", user_context=None):
        seen["in"] = text
        return "Answer with **bold** and a heading"

    generator.client.chat = fake_chat
    generator.translator.translate = fake_translate
    generator._load_docs = lambda docs: {"faq.md": "facts"}

    text, _ = asyncio.run(generator.generate(
        {
            "status": "success",
            "documents": ["faq.md"],
            "decomposed_questions": ["What is this?"],
            "user_signal": "exploring_only",
            "detected_language": "en",
            "cta_blocked": True,
        },
        history=[], current_message="What is this?",
    ))
    assert "**" not in text


def test_prompt_forbids_retracting_earlier_claims(generator):
    messages = generator._build_messages(
        {"faq.md": "facts"}, ["Что такое школа?"], [],
        {
            "status": "success",
            "user_signal": "exploring_only",
            "decomposed_questions": ["Что такое школа?"],
            "original_message": "А это точно работает?",
            "social_context": None,
            "user_completed_action": None,
            "detected_language": "ru",
        },
        cta_text=None,
    )
    system = messages[0]["content"]
    assert "НЕ опровергай факты" in system


# --- 6. Тон под GPT-6 Luna: уверенность вместо юридических оговорок ------------

def test_prompt_guides_confident_tone_without_courtroom_hedging(generator):
    messages = generator._build_messages(
        {"faq.md": "facts"}, ["Что такое школа?"], [],
        {
            "status": "success",
            "user_signal": "exploring_only",
            "decomposed_questions": ["Что такое школа?"],
            "original_message": "Чем лучше других?",
            "social_context": None,
            "user_completed_action": None,
            "detected_language": "ru",
        },
        cta_text=None,
    )
    system = messages[0]["content"]
    assert "Пиши уверенно" in system
    assert "не превращай ответ в юридический документ" in system
    assert "не гадай о чужих ценах" in system
