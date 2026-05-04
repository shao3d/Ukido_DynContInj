"""Security-focused checks for public API surface."""

import importlib
import os
import sys
import types

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Import main with deterministic, filesystem-isolated settings."""
    os.environ["OPENROUTER_API_KEY"] = "test_key_for_ci"
    os.environ["DETERMINISTIC_MODE"] = "true"
    os.environ["PERSISTENCE_BASE_PATH"] = str(tmp_path_factory.mktemp("states"))
    os.environ.pop("ADMIN_API_TOKEN", None)

    for module_name in (
        "main",
        "config",
        "router",
        "gemini_cached_client",
        "response_generator",
        "translator",
    ):
        sys.modules.pop(module_name, None)

    return TestClient(importlib.import_module("main").app)


def test_clear_history_requires_admin_token(client):
    response = client.post("/clear_history/test_user")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin endpoint is disabled"


def test_metrics_requires_admin_token(client):
    response = client.get("/metrics")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin endpoint is disabled"


def test_admin_token_rejects_wrong_token(client, monkeypatch):
    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "ADMIN_API_TOKEN", "secret-token")

    response = client.get("/metrics", headers={"X-Admin-Token": "wrong-token"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin token"


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


def test_trial_signup_rejects_invalid_phone(client):
    response = client.post(
        "/trial-signup",
        json={
            "firstName": "Anna",
            "lastName": "Ivanova",
            "email": "anna@example.com",
            "phone": "not-a-phone",
        },
    )

    assert response.status_code == 422


def test_trial_signup_does_not_expose_hubspot_contact_id(client, monkeypatch):
    class FakeHubSpotClient:
        async def create_or_update_contact(self, **kwargs):
            return {
                "contact_id": "hubspot-secret-id",
                "action": "created",
                "existing": False,
            }

        async def close(self):
            return None

    main = sys.modules["main"]
    monkeypatch.setattr(main.config, "HUBSPOT_PRIVATE_APP_TOKEN", "test-hubspot-token")
    monkeypatch.setitem(
        sys.modules,
        "hubspot_client",
        types.SimpleNamespace(HubSpotClient=FakeHubSpotClient),
    )

    response = client.post(
        "/trial-signup",
        json={
            "firstName": "Anna",
            "lastName": "Ivanova",
            "email": "anna@example.com",
            "phone": "+380 93 123 45 67",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["success"] is True
    assert body["action"] == "created"
    assert "contact_id" not in body
