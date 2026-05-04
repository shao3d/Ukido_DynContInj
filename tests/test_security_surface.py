"""Security-focused checks for public API surface."""

import importlib
import os
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Import main with deterministic, filesystem-isolated settings."""
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("states"))
    os.environ.pop("ADMIN_API_TOKEN", None)

    for module_name in ("main", "config"):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


def test_clear_history_requires_admin_token(client):
    response = client.post("/clear_history/test_user")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin endpoint is disabled"


def test_stream_rejects_invalid_user_id(client):
    response = client.get("/chat/stream", params={"user_id": "../bad", "message": "hello"})

    assert response.status_code == 422


def test_cors_rejects_unknown_origin(client):
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://shao3d.github.io",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://shao3d.github.io"
