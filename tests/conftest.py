# tests/conftest.py
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_DB_PATH", str(tmp_path / "test.db"))


def create_admin_session(client):
    """
    Helper to create an admin user and set up authenticated client.

    Creates admin user directly in DB and logs in via /auth/login.
    Returns the client with session cookie set.
    """
    from src.db import get_conn, init_db
    from src.repo import create_user
    from src.auth import hash_password

    # Create admin user directly in DB
    conn = get_conn()
    try:
        init_db(conn)
        password_hash = hash_password("admin123")
        create_user(conn, email="admin@test.com", password_hash=password_hash, role="admin")
    finally:
        conn.close()

    # Log in to get session cookie
    resp = client.post("/auth/login", params={"email": "admin@test.com", "password": "admin123"})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"

    return client


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    """Fixture that returns an authenticated admin TestClient."""
    from fastapi.testclient import TestClient
    from src.main import app

    db_path = tmp_path / "test_admin.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))

    client = TestClient(app)
    return create_admin_session(client)
