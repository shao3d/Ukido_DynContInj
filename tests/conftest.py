"""Shared pytest setup for repo-local imports."""

import sys
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


@pytest.fixture(autouse=True)
def _reset_sse_shutdown_signal():
    """Изоляция SSE-тестов между event loop'ами.

    sse_starlette хранит глобальный `AppStatus.should_exit_event`, который
    привязывается к первому event loop. Каждый TestClient живёт в своём loop,
    поэтому второй SSE-тест в сьюте падает на Python 3.12 с
    'is bound to a different event loop'. Сбрасываем перед/после каждого
    теста — shutdown в тестах никогда не запрашивается, это безопасно.
    """
    try:
        from sse_starlette.sse import AppStatus
    except ImportError:  # pragma: no cover
        yield
        return
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit = False
    AppStatus.should_exit_event = None
