from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.main import app
from src.repo import (
    upsert_run_feedback,
    upsert_item_feedback,
    get_run_feedback,
    get_item_feedback,
    get_idempotency_response,
    store_idempotency_response,
)


# -----------------------------------------------------------------------------
# Step 18.5a: Upsert Run Feedback
# -----------------------------------------------------------------------------

def test_upsert_run_feedback_insert_then_update():
    """First call inserts, second call with same run_id updates."""
    conn = get_conn()
    init_db(conn)

    now = datetime.now(timezone.utc).isoformat()

    # First call: INSERT
    feedback_id_1 = upsert_run_feedback(
        conn,
        run_id="run-123",
        rating=3,
        comment="okay digest",
        created_at=now,
        updated_at=now,
    )

    # Second call: same run_id → UPDATE
    feedback_id_2 = upsert_run_feedback(
        conn,
        run_id="run-123",
        rating=5,
        comment="actually great!",
        created_at=now,
        updated_at=now,
    )

    # Same ID = same row (updated, not duplicated)
    assert feedback_id_1 == feedback_id_2

    # Verify the update took effect
    row = get_run_feedback(conn, run_id="run-123")
    assert row is not None
    assert row["rating"] == 5
    assert row["comment"] == "actually great!"

    conn.close()


# -----------------------------------------------------------------------------
# Step 18.5b: Upsert Item Feedback
# -----------------------------------------------------------------------------

def test_upsert_item_feedback_insert_then_update():
    """First call inserts, second call with same (run_id, item_url) updates."""
    conn = get_conn()
    init_db(conn)

    now = datetime.now(timezone.utc).isoformat()

    # First call: thumbs UP
    feedback_id_1 = upsert_item_feedback(
        conn,
        run_id="run-123",
        item_url="https://example.com/article",
        useful=1,
        created_at=now,
        updated_at=now,
    )

    # Second call: change to thumbs DOWN
    feedback_id_2 = upsert_item_feedback(
        conn,
        run_id="run-123",
        item_url="https://example.com/article",
        useful=0,
        created_at=now,
        updated_at=now,
    )

    # Same ID = same row
    assert feedback_id_1 == feedback_id_2

    # Verify update
    row = get_item_feedback(conn, run_id="run-123", item_url="https://example.com/article")
    assert row is not None
    assert row["useful"] == 0

    conn.close()


# -----------------------------------------------------------------------------
# Step 18.5c: Different Run IDs Create Separate Rows
# -----------------------------------------------------------------------------

def test_run_feedback_different_runs_separate_rows():
    """Different run_ids create separate feedback rows."""
    conn = get_conn()
    init_db(conn)

    now = datetime.now(timezone.utc).isoformat()

    # Feedback for run A
    id_a = upsert_run_feedback(
        conn,
        run_id="run-AAA",
        rating=5,
        comment="loved it",
        created_at=now,
        updated_at=now,
    )

    # Feedback for run B (different run!)
    id_b = upsert_run_feedback(
        conn,
        run_id="run-BBB",
        rating=2,
        comment="not great",
        created_at=now,
        updated_at=now,
    )

    # Different IDs = different rows
    assert id_a != id_b

    # Verify each exists with correct data
    row_a = get_run_feedback(conn, run_id="run-AAA")
    row_b = get_run_feedback(conn, run_id="run-BBB")

    assert row_a["rating"] == 5
    assert row_b["rating"] == 2

    conn.close()


# -----------------------------------------------------------------------------
# Step 18.5d: Idempotency Key Caching
# -----------------------------------------------------------------------------

def test_idempotency_key_returns_cached_response():
    """Stored idempotency key returns cached response."""
    conn = get_conn()
    init_db(conn)

    now = datetime.now(timezone.utc).isoformat()

    # Store a response for a key
    store_idempotency_response(
        conn,
        key="idem-key-123",
        endpoint="/feedback/run",
        response_json='{"feedback_id": 42, "status": "saved"}',
        created_at=now,
    )

    # Retrieve it
    cached = get_idempotency_response(conn, key="idem-key-123")

    # Should get back the stored response
    assert cached is not None
    assert cached["key"] == "idem-key-123"
    assert cached["endpoint"] == "/feedback/run"
    assert cached["response_json"] == '{"feedback_id": 42, "status": "saved"}'

    conn.close()


def test_idempotency_key_not_found_returns_none():
    """Non-existent idempotency key returns None."""
    conn = get_conn()
    init_db(conn)

    # Try to get a key that doesn't exist
    cached = get_idempotency_response(conn, key="does-not-exist")

    assert cached is None

    conn.close()


# -----------------------------------------------------------------------------
# Step 18.5e: Endpoint Integration Tests
# -----------------------------------------------------------------------------

def test_endpoint_run_feedback_creates_feedback():
    """POST /feedback/run creates feedback and returns 200."""
    client = TestClient(app)

    response = client.post(
        "/feedback/run",
        json={
            "run_id": "run-endpoint-test",
            "rating": 4,
            "comment": "good digest"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["feedback_id"] is not None
    assert data["run_id"] == "run-endpoint-test"
    assert data["rating"] == 4


def test_endpoint_run_feedback_idempotency():
    """Same idempotency key returns cached response."""
    client = TestClient(app)

    # First request
    response1 = client.post(
        "/feedback/run",
        json={"run_id": "run-idem-test", "rating": 5},
        headers={"X-Idempotency-Key": "unique-key-abc"}
    )

    # Second request with SAME key
    response2 = client.post(
        "/feedback/run",
        json={"run_id": "run-idem-test", "rating": 5},
        headers={"X-Idempotency-Key": "unique-key-abc"}
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Same feedback_id = cached response (not processed twice)
    assert response1.json()["feedback_id"] == response2.json()["feedback_id"]


def test_endpoint_item_feedback_creates_feedback():
    """POST /feedback/item creates item feedback and returns 200."""
    client = TestClient(app)

    response = client.post(
        "/feedback/item",
        json={
            "run_id": "run-item-test",
            "item_url": "https://example.com/article",
            "useful": True
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["feedback_id"] is not None
    assert data["useful"]

def test_endpoint_validation_error_returns_problem_details():
    """Invalid request body returns ProblemDetails format."""
    client = TestClient(app)

    # Send invalid rating (must be 1-5)
    response = client.post(
        "/feedback/run",
        json={
            "run_id": "test-run",
            "rating": 10  # Invalid! Max is 5
        }
    )

    assert response.status_code == 422
    data = response.json()

    assert data["status"] == 422
    assert data["code"] == "validation_error"
    assert "rating" in data["message"]   # Error mentions the field
    assert "request_id" in data

def test_all_responses_have_request_id_header():
    """All responses include X-Request-ID header."""
    client = TestClient(app)

    # Test success repsonse
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers

    #Test error response
    response = client.get("/runs/latest")  #Will 404 if no runs
    assert "X-Request-ID" in response.headers


# -----------------------------------------------------------------------------
# Step 18.8: Error Shape Tests
# -----------------------------------------------------------------------------

def test_404_error_returns_problem_details():
    """404 errors return ProblemDetails format."""
    from tests.conftest import create_admin_session
    client = TestClient(app)
    client = create_admin_session(client)

    # Hit an endpoint that will 404
    response = client.get("/debug/run/nonexistent-run-id")

    assert response.status_code == 404
    data = response.json()

    # Should be ProblemDetails format
    assert data["status"] == 404
    assert data["code"] == "http_error"
    assert "request_id" in data
    assert "X-Request-ID" in response.headers


def test_500_error_returns_problem_details_no_leak():
    """500 errors return ProblemDetails without leaking stack trace."""
    from tests.conftest import create_admin_session
    client = TestClient(app, raise_server_exceptions=False)
    client = create_admin_session(client)

    # Hit debug endpoint that crashes
    response = client.get("/debug/crash")

    assert response.status_code == 500
    data = response.json()

    # Should be ProblemDetails format
    assert data["status"] == 500
    assert data["code"] == "internal_error"
    assert data["message"] == "Internal server error"  # Generic, not "boom"
    assert "request_id" in data

    # Should NOT contain stack trace or actual error
    assert "boom" not in str(data)
    assert "RuntimeError" not in str(data)


def test_different_idempotency_keys_processed_separately():
    """Different idempotency keys are processed independently."""
    client = TestClient(app)

    # Request 1 with key A
    response1 = client.post(
        "/feedback/run",
        json={"run_id": "run-A", "rating": 5},
        headers={"X-Idempotency-Key": "key-AAA"}
    )

    # Request 2 with key B (different key, different run)
    response2 = client.post(
        "/feedback/run",
        json={"run_id": "run-B", "rating": 3},
        headers={"X-Idempotency-Key": "key-BBB"}
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Different feedback_ids (separate rows)
    assert response1.json()["feedback_id"] != response2.json()["feedback_id"]

    # Correct data returned for each
    assert response1.json()["run_id"] == "run-A"
    assert response1.json()["rating"] == 5
    assert response2.json()["run_id"] == "run-B"
    assert response2.json()["rating"] == 3

def test_idempotency_skips_processing_on_second_request(monkeypatch):
    """Second request with same idempotency key should NOT call upsert."""    

    # Track how many times upsert is called
    call_count = {"value": 0}
    original_upsert = upsert_run_feedback

    def counting_upsert(*args, **kwargs):
        call_count["value"] += 1
        return original_upsert(*args, **kwargs)

    monkeypatch.setattr("src.main.upsert_run_feedback", counting_upsert)      

    client = TestClient(app)

    # Request 1: should process (call upsert)
    response1 = client.post(
        "/feedback/run",
        json={"run_id": "run-count-test", "rating": 5},
        headers={"X-Idempotency-Key": "count-key-123"}
    )
    assert response1.status_code == 200
    assert call_count["value"] == 1  # Called once

    # Request 2: should skip processing (NOT call upsert)
    response2 = client.post(
        "/feedback/run",
        json={"run_id": "run-count-test", "rating": 5},
        headers={"X-Idempotency-Key": "count-key-123"}  # Same key!
    )
    assert response2.status_code == 200
    assert call_count["value"] == 1  # Still 1! Should NOT have called again 
