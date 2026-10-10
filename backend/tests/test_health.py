"""Health endpoint."""

import pytest
from fastapi.testclient import TestClient

import app.database


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_database_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_session() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(app.database, "SessionLocal", broken_session)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "error"}
