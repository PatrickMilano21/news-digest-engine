"""Tests for suggestion API endpoints (Milestone 4.5 Step 3)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.main import app
from src.auth import hash_password
from src.repo import (
    create_user,
    create_session,
    insert_suggestion,
    insert_outcome,
    get_suggestion_by_id,
    get_user_config,
    upsert_user_config,
    get_user_profile,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create test client with isolated DB."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))
    return TestClient(app)


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    """Create test client with authenticated user."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    # Initialize DB and create user
    conn = get_conn()
    init_db(conn)
    create_user(conn, email="test@example.com", password_hash=hash_password("password"))
    conn.close()

    # Use /auth/login to get proper session cookie
    client = TestClient(app)
    resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return client


@pytest.fixture
def user_with_suggestion(tmp_path, monkeypatch):
    """Create user with a pending suggestion."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    init_db(conn)
    user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

    # Create a suggestion
    suggestion_id = insert_suggestion(
        conn,
        user_id=user_id,
        suggestion_type="boost_source",
        field="source_weights",
        target_key="techcrunch",
        current_value="1.0",
        suggested_value="1.3",
        evidence_items=[{"url": "a", "title": "a"}] * 3,
        reason="You liked TechCrunch",
    )
    conn.close()

    # Use /auth/login to get proper session cookie
    client = TestClient(app)
    resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"client": client, "suggestion_id": suggestion_id, "user_id": user_id}


class TestAuthRequired:
    """Test that all endpoints require authentication."""

    def test_get_suggestions_requires_auth(self, client):
        """GET /api/suggestions requires auth."""
        resp = client.get("/api/suggestions")
        assert resp.status_code == 401

    def test_generate_requires_auth(self, client):
        """POST /api/suggestions/generate requires auth."""
        resp = client.post("/api/suggestions/generate")
        assert resp.status_code == 401

    def test_accept_requires_auth(self, client):
        """POST /api/suggestions/{id}/accept requires auth."""
        resp = client.post("/api/suggestions/1/accept")
        assert resp.status_code == 401

    def test_reject_requires_auth(self, client):
        """POST /api/suggestions/{id}/reject requires auth."""
        resp = client.post("/api/suggestions/1/reject")
        assert resp.status_code == 401

    def test_accept_all_requires_auth(self, client):
        """POST /api/suggestions/accept-all requires auth."""
        resp = client.post("/api/suggestions/accept-all")
        assert resp.status_code == 401


class TestGetSuggestions:
    """Tests for GET /api/suggestions."""

    def test_returns_empty_list_when_no_suggestions(self, auth_client):
        """Returns empty list when no pending suggestions."""
        resp = auth_client.get("/api/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["suggestions"] == []
        assert data["count"] == 0

    def test_returns_pending_suggestions(self, user_with_suggestion):
        """Returns pending suggestions with all fields."""
        client = user_with_suggestion["client"]
        resp = client.get("/api/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        s = data["suggestions"][0]
        assert s["suggestion_type"] == "boost_source"
        assert s["target_key"] == "techcrunch"
        assert s["suggested_value"] == "1.3"
        assert s["status"] == "pending"


class TestGenerateSuggestions:
    """Tests for POST /api/suggestions/generate."""

    def test_blocked_pending_when_suggestions_exist(self, user_with_suggestion):
        """Returns blocked_pending if pending suggestions exist."""
        client = user_with_suggestion["client"]
        resp = client.post("/api/suggestions/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "blocked_pending"
        assert data["pending_count"] == 1

    def test_skipped_when_insufficient_data(self, auth_client):
        """Returns skipped when no feedback data."""
        resp = auth_client.post("/api/suggestions/generate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert "reason" in data


class TestAcceptSuggestion:
    """Tests for POST /api/suggestions/{id}/accept."""

    def test_accept_updates_config(self, user_with_suggestion):
        """Accepting a suggestion updates user config."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["config_updated"] is True
        assert "outcome_id" in data

        # Verify config was updated
        conn = get_conn()
        config = get_user_config(conn, user_id=user_with_suggestion["user_id"])
        conn.close()
        assert config["source_weights"]["techcrunch"] == 1.3

    def test_accept_updates_suggestion_status(self, user_with_suggestion):
        """Accepting changes suggestion status to accepted."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        client.post(f"/api/suggestions/{suggestion_id}/accept")

        conn = get_conn()
        suggestion = get_suggestion_by_id(conn, suggestion_id=suggestion_id)
        conn.close()
        assert suggestion["status"] == "accepted"

    def test_accept_updates_profile_stats(self, user_with_suggestion):
        """Accepting increments profile acceptance stats."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        client.post(f"/api/suggestions/{suggestion_id}/accept")

        conn = get_conn()
        profile = get_user_profile(conn, user_id=user_with_suggestion["user_id"])
        conn.close()
        assert profile is not None
        assert profile["acceptance_stats"]["boost_source"]["accepted"] == 1

    def test_double_accept_returns_409(self, user_with_suggestion):
        """Accepting already accepted suggestion returns 409."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        # First accept
        resp1 = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp1.status_code == 200

        # Second accept returns 409
        resp2 = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp2.status_code == 409
        data = resp2.json()
        assert data["error"] == "already_resolved"
        assert data["current_status"] == "accepted"

    def test_accept_nonexistent_returns_404(self, auth_client):
        """Accepting nonexistent suggestion returns 404."""
        resp = auth_client.post("/api/suggestions/9999/accept")
        assert resp.status_code == 404


class TestRejectSuggestion:
    """Tests for POST /api/suggestions/{id}/reject."""

    def test_reject_does_not_update_config(self, user_with_suggestion):
        """Rejecting a suggestion does not update config."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        resp = client.post(f"/api/suggestions/{suggestion_id}/reject")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "outcome_id" in data

        # Config should not be updated
        conn = get_conn()
        config = get_user_config(conn, user_id=user_with_suggestion["user_id"])
        conn.close()
        # No config should exist or should not have the source weight
        if config:
            assert "source_weights" not in config or \
                   "techcrunch" not in config.get("source_weights", {})

    def test_reject_updates_suggestion_status(self, user_with_suggestion):
        """Rejecting changes suggestion status to rejected."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        client.post(f"/api/suggestions/{suggestion_id}/reject")

        conn = get_conn()
        suggestion = get_suggestion_by_id(conn, suggestion_id=suggestion_id)
        conn.close()
        assert suggestion["status"] == "rejected"

    def test_reject_updates_profile_stats(self, user_with_suggestion):
        """Rejecting increments profile rejection stats."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        client.post(f"/api/suggestions/{suggestion_id}/reject")

        conn = get_conn()
        profile = get_user_profile(conn, user_id=user_with_suggestion["user_id"])
        conn.close()
        assert profile is not None
        assert profile["acceptance_stats"]["boost_source"]["rejected"] == 1

    def test_double_reject_returns_409(self, user_with_suggestion):
        """Rejecting already rejected suggestion returns 409."""
        client = user_with_suggestion["client"]
        suggestion_id = user_with_suggestion["suggestion_id"]

        # First reject
        resp1 = client.post(f"/api/suggestions/{suggestion_id}/reject")
        assert resp1.status_code == 200

        # Second reject returns 409
        resp2 = client.post(f"/api/suggestions/{suggestion_id}/reject")
        assert resp2.status_code == 409
        data = resp2.json()
        assert data["error"] == "already_resolved"
        assert data["current_status"] == "rejected"


class TestAcceptAll:
    """Tests for POST /api/suggestions/accept-all."""

    def test_accept_all_with_no_suggestions(self, auth_client):
        """Accept all with no pending suggestions returns empty results."""
        resp = auth_client.post("/api/suggestions/accept-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["accepted_count"] == 0
        assert data["results"] == []

    def test_accept_all_accepts_all_pending(self, user_with_suggestion):
        """Accept all accepts all pending suggestions."""
        client = user_with_suggestion["client"]

        resp = client.post("/api/suggestions/accept-all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["accepted_count"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "accepted"


class TestUserIsolation:
    """Tests for user isolation - users can only access their own suggestions."""

    def test_cannot_accept_other_users_suggestion(self, tmp_path, monkeypatch):
        """User A cannot accept User B's suggestion."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)

        # Create two users (store UUIDs)
        user_a_id = create_user(conn, email="user_a@example.com", password_hash=hash_password("password"))
        user_b_id = create_user(conn, email="user_b@example.com", password_hash=hash_password("password"))

        # User B's suggestion (using UUID)
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_b_id,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # User A logs in
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "user_a@example.com", "password": "password"})
        assert resp.status_code == 200

        # User A tries to accept User B's suggestion
        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 403

    def test_cannot_see_other_users_suggestions(self, tmp_path, monkeypatch):
        """User A cannot see User B's suggestions."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)

        # Create two users (store UUIDs)
        user_a_id = create_user(conn, email="user_a@example.com", password_hash=hash_password("password"))
        user_b_id = create_user(conn, email="user_b@example.com", password_hash=hash_password("password"))

        # User B's suggestion (using UUID)
        insert_suggestion(
            conn,
            user_id=user_b_id,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # User A logs in
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "user_a@example.com", "password": "password"})
        assert resp.status_code == 200

        # User A should see empty list
        resp = client.get("/api/suggestions")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestConfigMutations:
    """Tests for config mutation edge cases."""

    def test_add_topic_skips_duplicate(self, tmp_path, monkeypatch):
        """Adding a topic that already exists is a no-op."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Pre-set config with topics
        upsert_user_config(conn, user_id=user_id, config={"topics": ["kubernetes"]})

        # Create suggestion to add same topic
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 200

        # Topic should still appear only once
        conn = get_conn()
        config = get_user_config(conn, user_id=user_id)
        conn.close()
        assert config["topics"].count("kubernetes") == 1

    def test_remove_topic_handles_missing(self, tmp_path, monkeypatch):
        """Removing a topic that doesn't exist is a no-op."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Pre-set config without the topic
        upsert_user_config(conn, user_id=user_id, config={"topics": ["other"]})

        # Create suggestion to remove non-existent topic
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="remove_topic",
            field="topics",
            current_value=None,
            suggested_value="kubernetes",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 200  # Should succeed silently

    def test_invalid_weight_returns_400(self, tmp_path, monkeypatch):
        """Invalid weight value returns 400."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Create suggestion with invalid weight
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="boost_source",
            field="source_weights",
            target_key="techcrunch",
            current_value="1.0",
            suggested_value="not_a_number",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "invalid_weight"

    def test_accept_preserves_existing_config(self, tmp_path, monkeypatch):
        """Accepting a suggestion preserves existing config keys."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Pre-set config with multiple keys
        initial_config = {
            "topics": ["kubernetes", "security"],
            "source_weights": {"bbc": 1.2, "cnn": 0.8},
            "custom_setting": "value",  # Some other config key
        }
        upsert_user_config(conn, user_id=user_id, config=initial_config)

        # Create suggestion to add a topic (should not affect source_weights or custom_setting)
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="add_topic",
            field="topics",
            current_value=None,
            suggested_value="docker",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 200

        # Verify ALL existing config was preserved
        conn = get_conn()
        config = get_user_config(conn, user_id=user_id)
        conn.close()

        # New topic added
        assert "docker" in config["topics"]
        # Existing topics preserved
        assert "kubernetes" in config["topics"]
        assert "security" in config["topics"]
        # Existing source_weights preserved
        assert config["source_weights"]["bbc"] == 1.2
        assert config["source_weights"]["cnn"] == 0.8
        # Custom setting preserved
        assert config["custom_setting"] == "value"

    def test_accept_source_preserves_existing_config(self, tmp_path, monkeypatch):
        """Accepting a source weight suggestion preserves other config keys."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Pre-set config with multiple keys
        initial_config = {
            "topics": ["kubernetes", "security"],
            "source_weights": {"bbc": 1.2},
        }
        upsert_user_config(conn, user_id=user_id, config=initial_config)

        # Create suggestion to boost a source (should not affect topics)
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="boost_source",
            field="source_weights",
            target_key="techcrunch",
            current_value="1.0",
            suggested_value="1.5",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 200

        # Verify ALL existing config was preserved
        conn = get_conn()
        config = get_user_config(conn, user_id=user_id)
        conn.close()

        # New source weight added
        assert config["source_weights"]["techcrunch"] == 1.5
        # Existing source weight preserved
        assert config["source_weights"]["bbc"] == 1.2
        # Existing topics preserved
        assert config["topics"] == ["kubernetes", "security"]

    def test_missing_target_key_returns_400(self, tmp_path, monkeypatch):
        """Source suggestion with missing target_key returns 400."""
        db_file = tmp_path / "test.db"
        monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

        conn = get_conn()
        init_db(conn)
        user_id = create_user(conn, email="test@example.com", password_hash=hash_password("password"))

        # Create suggestion with no target_key (legacy/bad data scenario)
        suggestion_id = insert_suggestion(
            conn,
            user_id=user_id,
            suggestion_type="boost_source",
            field="source_weights",
            target_key=None,  # Missing!
            current_value="1.0",
            suggested_value="1.5",
            evidence_items=[{"url": "a"}] * 3,
            reason="Test",
        )
        conn.close()

        # Login to get session
        client = TestClient(app)
        resp = client.post("/auth/login", params={"email": "test@example.com", "password": "password"})
        assert resp.status_code == 200

        resp = client.post(f"/api/suggestions/{suggestion_id}/accept")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "missing_target_key"
