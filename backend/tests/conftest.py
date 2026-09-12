"""Test fixtures: isolated per-test DB + service graph (no globals leakage)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import Services, build_services


@pytest.fixture()
def services(tmp_path: Path) -> Services:
    db_file = tmp_path / "test.db"
    svc = build_services(database_url=f"sqlite:///{db_file}")
    svc.db.create_all()
    # isolate key storage per test
    from app.services_identity import KeyService
    svc.keys = KeyService(str(tmp_path / "keys"))
    return svc


@pytest.fixture()
def client(services: Services) -> TestClient:
    import app.services as services_module
    from app.main import create_app

    services_module._services = services
    app = create_app()
    with TestClient(app) as c:
        yield c
    services_module._services = None


@pytest.fixture()
def admin_headers() -> dict:
    return {"X-API-Key": "dev-admin-key-change-me"}
