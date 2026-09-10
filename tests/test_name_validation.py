"""SEC-09: валидация имён не должна резать легитимные имена и портить регистр.

Регрессия: O'Brien / St. John отклонялись (потеря заявок), а McDonald
коверкался в Mcdonald через .title().
"""

import importlib
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("OPENROUTER_API_KEY", "test_key_for_ci")

main = importlib.import_module("main")
TrialSignupRequest = main.TrialSignupRequest


def make_request(first_name="Anna", last_name="Ivanova"):
    return TrialSignupRequest(
        firstName=first_name,
        lastName=last_name,
        email="anna@example.com",
        phone="+380 93 123 45 67",
    )


@pytest.mark.parametrize(
    "first_name,last_name",
    [
        ("Anna", "Ivanova"),
        ("Ольга", "Шевченко"),
        ("Sean", "O'Brien"),
        ("Anna", "St. John"),
        ("Ronald", "McDonald"),
        ("Mary-Kate", "O'Neill"),
        ("  Anna  ", "Ivanova"),  # крайние пробелы подрезаются
    ],
)
def test_legit_names_accepted(first_name, last_name):
    req = make_request(first_name, last_name)
    assert req.firstName == first_name.strip()
    assert req.lastName == last_name.strip()


def test_case_preserved_not_titled():
    req = make_request("Ronald", "McDonald")
    assert req.lastName == "McDonald"  # было бы Mcdonald через .title()


@pytest.mark.parametrize(
    "bad_name",
    ["John3", "Anna!", "Ivan@ov", "", "   "],
)
def test_garbage_names_rejected(bad_name):
    with pytest.raises(ValidationError):
        make_request(bad_name, "Ivanova")
    with pytest.raises(ValidationError):
        make_request("Anna", bad_name)
