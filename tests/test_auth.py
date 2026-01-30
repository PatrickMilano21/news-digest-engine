"""Tests for authentication and user management (Milestone 4)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.main import app
from src.auth import hash_password, verify_password
from src.repo import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    create_session,
    get_session,
    delete_session,
    get_user_config,
    upsert_user_config,
)


@pytest.fixture
def conn(tmp_path, monkeypatch):
    """Create a temp database for testing."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    conn = get_conn()
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client with isolated DB."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    return TestClient(app)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_bcrypt_hash(self):
        """hash_password should return a bcrypt hash, not plaintext."""
        password = "mysecretpassword123"
        hashed = hash_password(password)

        # Bcrypt hashes start with $2b$ (or $2a$ or $2y$)
        assert hashed.startswith("$2"), f"Expected bcrypt hash, got: {hashed[:20]}"
        assert hashed != password, "Password should not be stored as plaintext"
        assert len(hashed) == 60, "Bcrypt hashes are 60 characters"

    def test_verify_password_correct(self):
        """verify_password returns True for correct password."""
        password = "correctpassword"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """verify_password returns False for wrong password."""
        password = "correctpassword"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_invalid_hash(self):
        """verify_password handles invalid hash gracefully."""
        assert verify_password("password", "not-a-valid-hash") is False
        assert verify_password("password", "") is False

    def test_password_hash_not_plaintext_invariant(self, conn):
        """INVARIANT: users.password_hash must NEVER contain plaintext."""
        password = "testpassword123"
        password_hash = hash_password(password)

        # Create user
        user_id = create_user(conn, email="test@example.com", password_hash=password_hash)

        # Verify stored hash is bcrypt, not plaintext
        user = get_user_by_id(conn, user_id=user_id)
        assert user["password_hash"].startswith("$2"), "Stored password must be bcrypt hash"
        assert user["password_hash"] != password, "Password must NOT be stored as plaintext"


class TestUserCrud:
    """Tests for user CRUD operations."""

    def test_create_user(self, conn):
        """create_user creates a user and returns user_id."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="user@test.com", password_hash=password_hash)

        assert user_id is not None
        assert len(user_id) == 36  # UUID format

    def test_create_user_duplicate_email_fails(self, conn):
        """create_user fails if email already exists."""
        password_hash = hash_password("testpass")
        create_user(conn, email="dupe@test.com", password_hash=password_hash)

        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            create_user(conn, email="dupe@test.com", password_hash=password_hash)

    def test_get_user_by_email(self, conn):
        """get_user_by_email returns user dict."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="lookup@test.com", password_hash=password_hash)

        user = get_user_by_email(conn, email="lookup@test.com")

        assert user is not None
        assert user["user_id"] == user_id
        assert user["email"] == "lookup@test.com"
        assert user["role"] == "user"

    def test_get_user_by_email_not_found(self, conn):
        """get_user_by_email returns None for non-existent email."""
        user = get_user_by_email(conn, email="nonexistent@test.com")
        assert user is None

    def test_get_user_by_id(self, conn):
        """get_user_by_id returns user dict."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="byid@test.com", password_hash=password_hash)

        user = get_user_by_id(conn, user_id=user_id)

        assert user is not None
        assert user["user_id"] == user_id
        assert user["email"] == "byid@test.com"

    def test_create_admin_user(self, conn):
        """create_user with role='admin' creates admin user."""
        password_hash = hash_password("adminpass")
        user_id = create_user(conn, email="admin@test.com", password_hash=password_hash, role="admin")

        user = get_user_by_id(conn, user_id=user_id)
        assert user["role"] == "admin"


class TestSessionManagement:
    """Tests for session management."""

    def test_create_session(self, conn):
        """create_session creates a session and returns session_id."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="session@test.com", password_hash=password_hash)

        session_id = create_session(conn, user_id=user_id)

        assert session_id is not None
        assert len(session_id) == 36  # UUID format

    def test_get_session_valid(self, conn):
        """get_session returns session for valid, non-expired session."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="valid@test.com", password_hash=password_hash)
        session_id = create_session(conn, user_id=user_id, expires_hours=24)

        session = get_session(conn, session_id=session_id)

        assert session is not None
        assert session["session_id"] == session_id
        assert session["user_id"] == user_id

    def test_get_session_not_found(self, conn):
        """get_session returns None for non-existent session."""
        session = get_session(conn, session_id="nonexistent-session-id")
        assert session is None

    def test_expired_session_rejected(self, conn):
        """INVARIANT: Expired sessions are rejected (return None)."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="expired@test.com", password_hash=password_hash)

        # Create session that expires immediately (0 hours)
        session_id = create_session(conn, user_id=user_id, expires_hours=0)

        # Session should be rejected because it's expired
        session = get_session(conn, session_id=session_id)
        assert session is None, "Expired session should return None"

    def test_delete_session(self, conn):
        """delete_session removes session."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="delete@test.com", password_hash=password_hash)
        session_id = create_session(conn, user_id=user_id)

        # Verify session exists
        assert get_session(conn, session_id=session_id) is not None

        # Delete session
        delete_session(conn, session_id=session_id)

        # Verify session is gone
        assert get_session(conn, session_id=session_id) is None


class TestUserConfig:
    """Tests for user config CRUD."""

    def test_get_user_config_none_when_not_set(self, conn):
        """get_user_config returns None if user has no config."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="noconfig@test.com", password_hash=password_hash)

        config = get_user_config(conn, user_id=user_id)
        assert config is None

    def test_upsert_user_config_creates(self, conn):
        """upsert_user_config creates new config."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="newconfig@test.com", password_hash=password_hash)

        upsert_user_config(conn, user_id=user_id, config={"ai_score_alpha": 0.15})

        config = get_user_config(conn, user_id=user_id)
        assert config is not None
        assert config["ai_score_alpha"] == 0.15

    def test_upsert_user_config_updates(self, conn):
        """upsert_user_config updates existing config."""
        password_hash = hash_password("testpass")
        user_id = create_user(conn, email="updateconfig@test.com", password_hash=password_hash)

        # Create initial config
        upsert_user_config(conn, user_id=user_id, config={"ai_score_alpha": 0.1})

        # Update config
        upsert_user_config(conn, user_id=user_id, config={"ai_score_alpha": 0.2, "topics": ["AI"]})

        config = get_user_config(conn, user_id=user_id)
        assert config["ai_score_alpha"] == 0.2
        assert config["topics"] == ["AI"]


class TestAuthEndpoints:
    """Tests for auth API endpoints."""

    def test_login_success(self, client):
        """POST /auth/login succeeds with valid credentials."""
        # Create user directly in DB
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("testpass123")
            create_user(conn, email="login@test.com", password_hash=password_hash)
        finally:
            conn.close()

        resp = client.post("/auth/login", params={"email": "login@test.com", "password": "testpass123"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "logged_in"
        assert data["email"] == "login@test.com"
        assert "session_id" in resp.cookies

    def test_login_wrong_password(self, client):
        """POST /auth/login fails with wrong password."""
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("correctpass")
            create_user(conn, email="wrongpass@test.com", password_hash=password_hash)
        finally:
            conn.close()

        resp = client.post("/auth/login", params={"email": "wrongpass@test.com", "password": "wrongpass"})

        assert resp.status_code == 401

    def test_login_unknown_email(self, client):
        """POST /auth/login fails with unknown email."""
        resp = client.post("/auth/login", params={"email": "unknown@test.com", "password": "anypass"})
        assert resp.status_code == 401

    def test_auth_me_authenticated(self, client):
        """GET /auth/me returns user info when authenticated."""
        # Create and login user
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("testpass")
            create_user(conn, email="me@test.com", password_hash=password_hash)
        finally:
            conn.close()

        client.post("/auth/login", params={"email": "me@test.com", "password": "testpass"})

        resp = client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@test.com"

    def test_auth_me_not_authenticated(self, client):
        """GET /auth/me returns 401 when not authenticated."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_logout_clears_session(self, client):
        """POST /auth/logout clears session cookie."""
        # Create and login user
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("testpass")
            create_user(conn, email="logout@test.com", password_hash=password_hash)
        finally:
            conn.close()

        client.post("/auth/login", params={"email": "logout@test.com", "password": "testpass"})

        # Logout
        resp = client.post("/auth/logout")
        assert resp.status_code == 200

        # Verify session cleared
        resp = client.get("/auth/me")
        assert resp.status_code == 401


class TestAdminAccess:
    """Tests for admin-only access control."""

    def test_debug_route_requires_auth(self, client):
        """Debug routes return 401 when not authenticated."""
        resp = client.get("/debug/stats")
        assert resp.status_code == 401

    def test_debug_route_requires_admin(self, client):
        """Debug routes return 403 for non-admin users."""
        # Create and login regular user
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("testpass")
            create_user(conn, email="regular@test.com", password_hash=password_hash, role="user")
        finally:
            conn.close()

        client.post("/auth/login", params={"email": "regular@test.com", "password": "testpass"})

        resp = client.get("/debug/stats")
        assert resp.status_code == 403

    def test_debug_route_allowed_for_admin(self, client):
        """Debug routes succeed for admin users."""
        # Create and login admin user
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("adminpass")
            create_user(conn, email="admin@test.com", password_hash=password_hash, role="admin")
        finally:
            conn.close()

        client.post("/auth/login", params={"email": "admin@test.com", "password": "adminpass"})

        resp = client.get("/debug/stats")
        assert resp.status_code == 200

    def test_register_requires_admin(self, client):
        """POST /auth/register requires admin session."""
        # Without auth
        resp = client.post("/auth/register", params={"email": "new@test.com", "password": "newpass"})
        assert resp.status_code == 401

    def test_register_as_admin_creates_user(self, client):
        """POST /auth/register as admin creates new user."""
        # Create and login admin
        conn = get_conn()
        try:
            init_db(conn)
            password_hash = hash_password("adminpass")
            create_user(conn, email="admin@test.com", password_hash=password_hash, role="admin")
        finally:
            conn.close()

        client.post("/auth/login", params={"email": "admin@test.com", "password": "adminpass"})

        # Register new user
        resp = client.post("/auth/register", params={"email": "newuser@test.com", "password": "newpass"})

        assert resp.status_code == 200
        assert resp.json()["status"] == "created"
        assert resp.json()["email"] == "newuser@test.com"


class TestUserIsolation:
    """Tests verifying user data isolation."""

    def test_user_runs_isolated(self, conn):
        """User A cannot see User B's runs."""
        from src.repo import start_run, get_recent_runs_summary

        # Create users
        password_hash = hash_password("testpass")
        user_a = create_user(conn, email="user_a@test.com", password_hash=password_hash)
        user_b = create_user(conn, email="user_b@test.com", password_hash=password_hash)

        # Create runs for each user
        started_a = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        started_b = datetime(2026, 1, 28, 11, 0, 0, tzinfo=timezone.utc)
        started_g = datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)

        start_run(conn, "run_a", started_a, received=10, run_type="ingest", user_id=user_a)
        start_run(conn, "run_b", started_b, received=10, run_type="ingest", user_id=user_b)
        start_run(conn, "run_global", started_g, received=10, run_type="ingest", user_id=None)

        # User A only sees their own runs
        runs_a = get_recent_runs_summary(conn, user_id=user_a)
        run_ids_a = [r["run_id"] for r in runs_a]
        assert "run_a" in run_ids_a
        assert "run_b" not in run_ids_a
        assert "run_global" not in run_ids_a

        # User B only sees their own runs
        runs_b = get_recent_runs_summary(conn, user_id=user_b)
        run_ids_b = [r["run_id"] for r in runs_b]
        assert "run_b" in run_ids_b
        assert "run_a" not in run_ids_b

        # Global/legacy sees global runs only
        runs_global = get_recent_runs_summary(conn, user_id=None)
        run_ids_global = [r["run_id"] for r in runs_global]
        assert "run_global" in run_ids_global
        assert "run_a" not in run_ids_global
        assert "run_b" not in run_ids_global

    def test_user_feedback_isolated(self, conn):
        """User A cannot see User B's item feedback in positive items."""
        from src.repo import (
            insert_news_items,
            start_run,
            upsert_item_feedback,
            get_positive_feedback_items,
        )
        from src.schemas import NewsItem
        from pydantic import HttpUrl

        # Create users
        password_hash = hash_password("testpass")
        user_a = create_user(conn, email="alice@test.com", password_hash=password_hash)
        user_b = create_user(conn, email="bob@test.com", password_hash=password_hash)

        # Create runs for each user
        started_a = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        started_b = datetime(2026, 1, 28, 11, 0, 0, tzinfo=timezone.utc)
        start_run(conn, "run_a", started_a, received=10, run_type="ingest", user_id=user_a)
        start_run(conn, "run_b", started_b, received=10, run_type="ingest", user_id=user_b)

        # Insert test news item
        now = datetime.now(timezone.utc)
        item = NewsItem(
            url=HttpUrl("https://example.com/article1"),
            title="Test Article",
            source="test",
            evidence="Test evidence for isolation",
            published_at=now,
            collected_at=now,
        )
        insert_news_items(conn, [item])

        # User A gives positive feedback
        upsert_item_feedback(
            conn,
            run_id="run_a",
            item_url="https://example.com/article1",
            useful=1,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            user_id=user_a,
        )

        # User B gives negative feedback on same item
        upsert_item_feedback(
            conn,
            run_id="run_b",
            item_url="https://example.com/article1",
            useful=0,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            user_id=user_b,
        )

        # User A sees their positive feedback
        positives_a = get_positive_feedback_items(conn, as_of_date="2026-01-28", user_id=user_a)
        urls_a = [p["url"] for p in positives_a]
        assert "https://example.com/article1" in urls_a

        # User B does NOT see the item as positive (they gave negative feedback)
        positives_b = get_positive_feedback_items(conn, as_of_date="2026-01-28", user_id=user_b)
        urls_b = [p["url"] for p in positives_b]
        assert "https://example.com/article1" not in urls_b

        # Global query sees neither (no global feedback given)
        positives_global = get_positive_feedback_items(conn, as_of_date="2026-01-28", user_id=None)
        urls_global = [p["url"] for p in positives_global]
        assert "https://example.com/article1" not in urls_global

    def test_user_weights_isolated(self, conn):
        """User A's source weights don't affect User B's ranking config."""
        from src.repo import upsert_weight_snapshot, get_active_source_weights

        # Create users
        password_hash = hash_password("testpass")
        user_a = create_user(conn, email="weights_a@test.com", password_hash=password_hash)
        user_b = create_user(conn, email="weights_b@test.com", password_hash=password_hash)

        # User A has custom weights
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.0},
            weights_after={"techcrunch": 2.0},  # User A doubled techcrunch
            feedback_summary={},
            eval_before=1.0,
            eval_after=1.0,
            applied=True,
            user_id=user_a,
        )

        # User B has different weights
        upsert_weight_snapshot(
            conn,
            cycle_date="2026-01-28",
            weights_before={"techcrunch": 1.0},
            weights_after={"techcrunch": 0.5},  # User B halved techcrunch
            feedback_summary={},
            eval_before=1.0,
            eval_after=1.0,
            applied=True,
            user_id=user_b,
        )

        # User A sees their own weights
        weights_a = get_active_source_weights(conn, user_id=user_a)
        assert weights_a.get("techcrunch") == 2.0

        # User B sees their own weights
        weights_b = get_active_source_weights(conn, user_id=user_b)
        assert weights_b.get("techcrunch") == 0.5

        # Global sees default weights (no global snapshot applied)
        weights_global = get_active_source_weights(conn, user_id=None)
        # Should be default from RankConfig, not 2.0 or 0.5
        assert weights_global.get("techcrunch") != 2.0
        assert weights_global.get("techcrunch") != 0.5

    def test_user_homepage_latest_isolated(self, conn):
        """User A's homepage shows their latest run, not User B's."""
        from src.repo import start_run, get_latest_run

        # Create users
        password_hash = hash_password("testpass")
        user_a = create_user(conn, email="home_a@test.com", password_hash=password_hash)
        user_b = create_user(conn, email="home_b@test.com", password_hash=password_hash)

        # User A has a run on Jan 26
        started_a = datetime(2026, 1, 26, 10, 0, 0, tzinfo=timezone.utc)
        start_run(conn, "run_a_jan26", started_a, received=10, run_type="ingest", user_id=user_a)

        # User B has a more recent run on Jan 28
        started_b = datetime(2026, 1, 28, 10, 0, 0, tzinfo=timezone.utc)
        start_run(conn, "run_b_jan28", started_b, received=10, run_type="ingest", user_id=user_b)

        # User A's latest run is Jan 26, NOT Jan 28
        latest_a = get_latest_run(conn, user_id=user_a)
        assert latest_a is not None
        assert latest_a["run_id"] == "run_a_jan26"
        assert latest_a["started_at"][:10] == "2026-01-26"

        # User B's latest run is Jan 28
        latest_b = get_latest_run(conn, user_id=user_b)
        assert latest_b is not None
        assert latest_b["run_id"] == "run_b_jan28"
        assert latest_b["started_at"][:10] == "2026-01-28"

        # Global (no user) sees nothing (no NULL user_id runs created)
        latest_global = get_latest_run(conn, user_id=None)
        assert latest_global is None
