"""SEC-03: сырой HTML, обрезка ссылок, отсутствие allowlist доменов."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from response_generator import ResponseGenerator

gen = ResponseGenerator.__new__(ResponseGenerator)


def test_full_path_preserved():
    out = gen._make_urls_clickable("Запишитесь: https://ukido.com.ua/trial")
    assert '<a href="https://ukido.com.ua/trial"' in out
    assert "/trial</a>" in out
    # Хвост пути не болтается голым текстом
    assert out.count("/trial") == 2  # href + текст ссылки


def test_trailing_punctuation_excluded():
    out = gen._make_urls_clickable("Вот ссылка https://ukido.com.ua/trial.")
    assert 'href="https://ukido.com.ua/trial"' in out
    assert out.endswith("</a>.")


def test_evil_domain_not_linkified():
    out = gen._make_urls_clickable("Жми https://evil.example/phish скорее")
    assert "<a " not in out
    assert "https://evil.example/phish" in out


def test_quote_injection_escaped():
    # Кавычка останавливает матч: в href она попасть не может.
    # Остаток идёт plain text вне тега — без `<` новый тег не образуется.
    out = gen._make_urls_clickable('Ссылка https://ukido.com.ua/"onmouseover="alert(1)')
    assert 'href="https://ukido.com.ua/"' in out
    assert "<img" not in out and "<script" not in out

    out2 = gen._make_urls_clickable("Жми https://evil.example/a тут")
    assert "<a " not in out2  # чужой домен ссылкой не становится


def test_bare_domain_linkified():
    out = gen._make_urls_clickable("Страница ukido.com.ua/trial тут")
    assert '<a href="https://ukido.com.ua/trial"' in out


def test_github_trial_linkified():
    out = gen._make_urls_clickable("Форма https://shao3d.github.io/trial/ здесь")
    assert '<a href="https://shao3d.github.io/trial/"' in out


def test_foreign_github_pages_not_linkified():
    out = gen._make_urls_clickable("Сайт https://other.github.io/evil тут")
    assert "<a " not in out


def test_subdomains_and_case():
    assert "<a " in gen._make_urls_clickable("Зайди https://WWW.UKIDO.COM.UA/trial")
    assert "<a " in gen._make_urls_clickable("Чат https://ukido.beyondhorizon.dev/x")
    assert "<a " not in gen._make_urls_clickable("Чат https://ukido.evilbeyondhorizon.dev/x")


def test_rel_noopener_present():
    out = gen._make_urls_clickable("Ссылка https://ukido.com.ua/trial")
    assert 'rel="noopener"' in out
