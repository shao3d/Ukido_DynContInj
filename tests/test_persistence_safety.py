"""OPS-03: персистентность не теряет данные молча.

Атомарная запись (tmp + fsync + replace), битые файлы — в карантин (.bak),
а не в unlink; clear_history удаляет и файл; metadata переживает рестарт.
"""

import importlib
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from history_manager import HistoryManager
from persistence_manager import (
    PersistenceManager,
    create_state_snapshot,
    restore_state_snapshot,
)


@pytest.fixture()
def pm(tmp_path):
    return PersistenceManager(base_path=str(tmp_path / "states"))


def sample_state():
    return {
        "history": [
            {"role": "user", "content": "Сколько стоит курс?"},
            {"role": "assistant", "content": "Курс стоит 6000.",
             "metadata": {"cta_added": True, "cta_type": "price_sensitive",
                          "user_signal": "price_sensitive"}},
        ],
        "user_signal": "price_sensitive",
    }


def test_roundtrip_preserves_metadata(pm):
    assert pm.save_state("u1", sample_state()) is True
    loaded = pm.load_state("u1")
    assert loaded["history"][1]["metadata"]["cta_added"] is True
    assert loaded["user_signal"] == "price_sensitive"


def test_no_tmp_residue_and_valid_json(pm, tmp_path):
    pm.save_state("u1", sample_state())
    leftovers = list((tmp_path / "states").glob("*.tmp"))
    assert leftovers == []
    raw = (tmp_path / "states" / "u1.json").read_text(encoding="utf-8")
    assert json.loads(raw)["user_signal"] == "price_sensitive"


def test_corrupt_file_quarantined_not_deleted(pm, tmp_path):
    pm.save_state("u1", sample_state())
    (tmp_path / "states" / "u1.json").write_text("{broken json", encoding="utf-8")

    assert pm.load_state("u1") is None
    states = tmp_path / "states"
    assert not (states / "u1.json").exists()
    backups = list(states.glob("u1.corrupt-*.bak"))
    assert len(backups) == 1
    assert "{broken json" in backups[0].read_text(encoding="utf-8")


def test_load_all_quarantines_corrupt(pm, tmp_path):
    pm.save_state("good", sample_state())
    (tmp_path / "states" / "bad.json").write_text("nope{", encoding="utf-8")

    states = pm.load_all_states()
    assert "good" in states
    assert not (tmp_path / "states" / "bad.json").exists()
    assert len(list((tmp_path / "states").glob("bad.corrupt-*.bak"))) == 1


def test_expired_file_still_deleted(pm, tmp_path):
    from datetime import datetime, timedelta
    state = sample_state()
    state["last_updated"] = (datetime.now() - timedelta(days=30)).isoformat()
    (tmp_path / "states").mkdir(exist_ok=True)
    (tmp_path / "states" / "old.json").write_text(
        json.dumps(state), encoding="utf-8")

    assert pm.load_state("old") is None
    assert not (tmp_path / "states" / "old.json").exists()


def test_restore_keeps_message_metadata():
    history = HistoryManager()
    signals = {}
    restore_state_snapshot(sample_state(), history, signals, None, "u1")

    assistant_msgs = [m for m in history.get_history("u1")
                      if m["role"] == "assistant"]
    assert assistant_msgs[0]["metadata"]["cta_type"] == "price_sensitive"
    assert signals["u1"] == "price_sensitive"


def test_snapshot_captures_metadata():
    history = HistoryManager()
    history.add_message("u1", "user", "Hi")
    history.add_message("u1", "assistant", "Hello", {"cta_added": True})
    snapshot = create_state_snapshot(history, {}, None, "u1")
    assert snapshot["history"][1]["metadata"] == {"cta_added": True}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("persist_states"))

    for module_name in (
        "main", "config", "router", "gemini_cached_client",
        "response_generator", "translator", "standard_responses",
        "localization", "social_state", "persistence_manager",
    ):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


def test_clear_history_deletes_state_file(client, monkeypatch):
    """clear_history чистит и память, и файл — данные не воскресают."""
    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "ADMIN_API_TOKEN", "secret-token")

    main.history.add_message("persist_u1", "user", "Сколько стоит?")
    main.persistence_manager.save_state(
        "persist_u1", {"history": main.history.get_history("persist_u1")})
    assert main.persistence_manager._get_file_path("persist_u1").exists()

    response = client.post(
        "/clear_history/persist_u1", headers={"X-Admin-Token": "secret-token"})
    assert response.status_code == 200
    assert main.history.get_history("persist_u1") == []
    assert not main.persistence_manager._get_file_path("persist_u1").exists()
