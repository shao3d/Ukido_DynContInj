"""BUG-03: блокировка CTA обязана истекать, а не длиться вечно.

Регрессия: current_message_count в main.py ограничен длиной истории
(HISTORY_LIMIT=10 → count максимум 11), поэтому старый порог
count+7 становился недостижим. Новый механизм считает собственные
сообщения пользователя внутренним счётчиком без потолка.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from simple_cta_blocker import SimpleCTABlocker

NEUTRAL = "сколько стоит курс для ребёнка 9 лет"


@pytest.fixture()
def blocker():
    return SimpleCTABlocker()


def pump(blocker, user_id, n, count=11):
    """N нейтральных сообщений (count как в main.py при забитой истории)."""
    for _ in range(n):
        assert blocker.check_refusal(user_id, NEUTRAL, count) is None


def test_hard_block_expires_after_7_messages(blocker):
    assert blocker.check_refusal("u1", "отстаньте уже", 5) == "hard"
    blocked, _ = blocker.should_block_cta("u1", 6)
    assert blocked is True

    pump(blocker, "u1", 6)
    blocked, _ = blocker.should_block_cta("u1", 11)
    assert blocked is True  # прошло 6 из 7

    pump(blocker, "u1", 1)
    blocked, reason = blocker.should_block_cta("u1", 11)
    assert blocked is False
    assert reason == ""


def test_capped_history_counter_does_not_block_forever(blocker):
    """Главный регрессионный кейс BUG-03: история упёрта в потолок (count=11
    всегда), блок всё равно истекает. На старом коде — вечный блок."""
    assert blocker.check_refusal("u2", "не надо", 11) == "hard"
    pump(blocker, "u2", 7, count=11)
    blocked, _ = blocker.should_block_cta("u2", 11)
    assert blocked is False


def test_soft_block_expires_after_3_messages(blocker):
    assert blocker.check_refusal("u3", "я подумаю", 5) == "soft"
    blocked, _ = blocker.should_block_cta("u3", 6)
    assert blocked is True

    pump(blocker, "u3", 3)
    blocked, _ = blocker.should_block_cta("u3", 11)
    assert blocked is False


def test_frequency_modifier_recovers(blocker):
    for _ in range(3):
        blocker.check_refusal("u4", "хватит предлагать", 11)
    assert blocker.get_cta_frequency_modifier("u4") == 0.2

    pump(blocker, "u4", 9)
    assert blocker.get_cta_frequency_modifier("u4") == 0.2  # ещё рано

    pump(blocker, "u4", 1)
    assert blocker.get_cta_frequency_modifier("u4") == 1.0  # восстановилось


def test_no_refusal_no_block(blocker):
    blocker.check_refusal("u5", NEUTRAL, 5)
    blocked, _ = blocker.should_block_cta("u5", 6)
    assert blocked is False
    assert blocker.get_cta_frequency_modifier("u5") == 1.0


def test_clear_resets_seq(blocker):
    blocker.check_refusal("u6", "отстаньте", 5)
    blocker.clear_user_data("u6")
    blocked, _ = blocker.should_block_cta("u6", 6)
    assert blocked is False
    assert blocker.get_cta_frequency_modifier("u6") == 1.0
