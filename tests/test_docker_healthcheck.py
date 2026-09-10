"""OPS-01: HEALTHCHECK обязан проверять HTTP-статус.

Регрессия: без raise_for_status() 5xx-ответ считался здоровым контейнером —
битый релиз не перезапускался и не откатывался.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"


def _healthcheck_cmd():
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "HEALTHCHECK" in text
    # Склеиваем продолжение строки через backslash
    lines = text.splitlines()
    cmd = ""
    capture = False
    for line in lines:
        if "HEALTHCHECK" in line:
            capture = True
        if capture:
            cmd += line.rstrip("\\") + " "
            if not line.rstrip().endswith("\\"):
                break
    return cmd


def test_healthcheck_checks_http_status():
    cmd = _healthcheck_cmd()
    assert "raise_for_status" in cmd


def test_healthcheck_fails_closed():
    cmd = _healthcheck_cmd()
    assert "exit 1" in cmd
