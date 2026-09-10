"""SEC-01: path traversal при загрузке документов.

Имена документов приходят от LLM (router.py), поэтому _load_doc обязан
отклонять всё, что не входит в allowlist, без чтения с диска.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from response_generator import ResponseGenerator


@pytest.fixture()
def generator(tmp_path):
    """Генератор с изолированным docs_dir: один легитимный md + секрет снаружи."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "pricing.md").write_text("Цены школы Ukido", encoding="utf-8")
    (tmp_path / "secret.env").write_text("HUBSPOT_TOKEN=topsecret", encoding="utf-8")

    gen = ResponseGenerator.__new__(ResponseGenerator)
    gen.docs_dir = docs_dir
    gen._allowed_docs = {"pricing.md"}
    return gen


@pytest.mark.parametrize(
    "evil_name",
    [
        "../../secret.env",
        "../../../etc/passwd",
        "/etc/passwd",
        "..\\secret.env",
        "pricing.md/../../secret.env",
        "secret.env",
        "evil.txt",
        "",
        "PRICING.MD",
        "pricing.md ",
        " pricing.md",
    ],
)
def test_traversal_names_rejected(generator, evil_name):
    assert generator._is_allowed_doc(evil_name) is False
    assert generator._load_doc(evil_name) == ""


def test_legit_doc_loads(generator):
    assert generator._is_allowed_doc("pricing.md") is True
    assert generator._load_doc("pricing.md") == "Цены школы Ukido"


def test_traversal_never_reads_outside_file(generator, tmp_path):
    content = generator._load_docs(["../../secret.env", "pricing.md"])
    assert content == {"pricing.md": "Цены школы Ukido"}
    assert "topsecret" not in str(content)


def test_symlink_escape_rejected(generator, tmp_path):
    (tmp_path / "outside.md").write_text("outside", encoding="utf-8")
    link = generator.docs_dir / "link.md"
    try:
        link.symlink_to(tmp_path / "outside.md")
    except OSError:
        pytest.skip("symlinks not supported here")
    # Имя не в allowlist — отклоняется до resolve-проверки
    assert generator._load_doc("link.md") == ""
    # Даже при подмене allowlist resolve-проверка держит файл внутри docs_dir
    generator._allowed_docs = {"pricing.md", "link.md"}
    assert generator._is_allowed_doc("link.md") is False
    assert generator._load_doc("link.md") == ""


def test_non_string_names_rejected(generator):
    assert generator._is_allowed_doc(None) is False
    assert generator._is_allowed_doc(123) is False
    assert generator._is_allowed_doc(["pricing.md"]) is False
