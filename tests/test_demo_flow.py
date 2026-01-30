from __future__ import annotations

from datetime import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, upsert_run_failures, insert_run_artifact, update_run_llm_stats
from src.main import app


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    db_path = tmp_path / "test_news.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    return TestClient(app)


def seed_ok_run_for_day(day: str) -> str:
    run_id = uuid.uuid4().hex
    started_at = f"{day}T00:00:00+00:00"
    finished_at = f"{day}T00:01:00+00:00"

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=started_at, received=0)
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at, after_dedupe=0, inserted=0, duplicates=0)
    finally:
        conn.close()

    return run_id

def seed_items_for_day(day: str) -> list[int]:
    """Seed test items and return their database IDs."""
    from src.schemas import NewsItem
    from src.repo import insert_news_items
    from datetime import datetime

    items = [
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-1",

published_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"),
            title="Test Article One",
            evidence="Some evidence text",
        ),
        NewsItem(
            source="test-source",
            url=f"https://example.com/{day}/article-2",
    
published_at=datetime.fromisoformat(f"{day}T11:00:00+00:00"),
            title="Test Article Two",
            evidence="More evidence",
        ),
    ]
    
    conn = get_conn()
    try:
        init_db(conn)
        insert_news_items(conn, items)
        # Get the IDs that were just inserted
        rows = conn.execute(
            "SELECT id FROM news_items WHERE substr(published_at, 1, 10)   = ? ORDER BY id",
            (day,)
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def test_ui_date_invalid_date_returns_400(client: TestClient):
    resp = client.get("/ui/date/not-a-date")
    assert resp.status_code == 400


def test_ui_date_valid_links_present(client: TestClient):
    day = "2026-01-14"
    seed_ok_run_for_day(day)
    seed_items_for_day(day)

    resp = client.get(f"/ui/date/{day}")
    assert resp.status_code == 200

    html = resp.text
    assert f"News Digest — {day}" in html
    assert "Test Article One" in html
    assert "Test Article Two" in html
    # Check that article links are present (links to actual URLs now)
    assert "https://example.com/" in html


def test_debug_run_not_found_404(client: TestClient):
    from tests.conftest import create_admin_session
    client = create_admin_session(client)
    resp = client.get("/debug/run/doesnotexist")
    assert resp.status_code == 404


def test_debug_run_returns_artifact_path(client: TestClient):
    from tests.conftest import create_admin_session
    client = create_admin_session(client)

    day = "2026-01-14"
    run_id = seed_ok_run_for_day(day)

    # Seed artifact
    conn = get_conn()
    try:
        init_db(conn)
        insert_run_artifact(conn, run_id=run_id, kind="digest", path=f"artifacts/digest_{day}.html")
    finally:
        conn.close()

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["artifact_paths"]["digest"] == f"artifacts/digest_{day}.html"


def test_debug_run_returns_breakdown_and_artifacts(client: TestClient):
    from tests.conftest import create_admin_session
    client = create_admin_session(client)

    day = "2026-01-14"

    # Seed run
    run_id = uuid.uuid4().hex
    started_at = f"{day}T00:00:00+00:00"
    finished_at = f"{day}T00:01:00+00:00"

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=started_at, received=10)
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at,
                      after_dedupe=8, inserted=7, duplicates=1)

        # Seed failure breakdown
        breakdown = {"EVAL_MISMATCH_KEYWORD": 2, "EVAL_MISMATCH_RECENCY": 1}
        upsert_run_failures(conn, run_id=run_id, breakdown=breakdown)

        # Seed artifacts
        insert_run_artifact(conn, run_id=run_id, kind="digest", path=f"artifacts/digest_{day}.html")
        insert_run_artifact(conn, run_id=run_id, kind="eval_report", path=f"artifacts/eval_report_{day}.md")
    finally:
        conn.close()

    # Call endpoint
    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Verify structure
    assert data["run_id"] == run_id
    assert data["failures_by_code"] == breakdown
    assert data["artifact_paths"]["digest"] == f"artifacts/digest_{day}.html"
    assert data["artifact_paths"]["eval_report"] == f"artifacts/eval_report_{day}.md"
    assert "request_id" in data
    assert data["counts"]["received"] == 10
    assert data["counts"]["inserted"] == 7
    assert data["run_type"] == "ingest"


def test_debug_run_includes_llm_stats(client: TestClient):
    """Test that /debug/run/{run_id} includes LLM stats section."""
    from tests.conftest import create_admin_session
    client = create_admin_session(client)

    day = "2026-01-20"
    run_id = uuid.uuid4().hex
    started_at = f"{day}T00:00:00+00:00"
    finished_at = f"{day}T00:01:00+00:00"

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=started_at, received=10)
        finish_run_ok(conn, run_id=run_id, finished_at=finished_at,
                      after_dedupe=8, inserted=7, duplicates=1)

        # Set LLM stats
        update_run_llm_stats(
            conn, run_id,
            cache_hits=5,
            cache_misses=3,
            total_cost_usd=0.0025,
            saved_cost_usd=0.0015,
            total_latency_ms=1500,
        )
    finally:
        conn.close()

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Verify llm_stats section exists and has correct values
    assert "llm_stats" in data
    llm = data["llm_stats"]
    assert llm["cache_hits"] == 5
    assert llm["cache_misses"] == 3
    assert llm["total_cost_usd"] == 0.0025
    assert llm["saved_cost_usd"] == 0.0015
    assert llm["total_latency_ms"] == 1500
    # Computed field
    assert llm["cache_hit_rate"] == 62.5  # 5 / 8 * 100


def test_debug_run_llm_stats_defaults_to_zero(client: TestClient):
    """Test that runs without LLM stats show zeros in the response."""
    from tests.conftest import create_admin_session
    client = create_admin_session(client)

    day = "2026-01-20"
    run_id = uuid.uuid4().hex

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=f"{day}T00:00:00+00:00", received=5)
        finish_run_ok(conn, run_id=run_id, finished_at=f"{day}T00:01:00+00:00",
                      after_dedupe=5, inserted=5, duplicates=0)
        # No update_run_llm_stats called
    finally:
        conn.close()

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    llm = data["llm_stats"]
    assert llm["cache_hits"] == 0
    assert llm["cache_misses"] == 0
    assert llm["total_cost_usd"] == 0.0
    assert llm["saved_cost_usd"] == 0.0
    assert llm["total_latency_ms"] == 0
    assert llm["cache_hit_rate"] == 0.0


def test_debug_run_includes_failed_sources(client: TestClient):
    """GET /debug/run/{run_id} includes failed_sources in response."""
    from tests.conftest import create_admin_session
    client = create_admin_session(client)

    day = "2026-01-25"
    run_id = uuid.uuid4().hex

    conn = get_conn()
    try:
        init_db(conn)
        start_run(conn, run_id=run_id, started_at=f"{day}T00:00:00+00:00", received=5)
        finish_run_ok(conn, run_id=run_id, finished_at=f"{day}T00:01:00+00:00", after_dedupe=5, inserted=5, duplicates=0)

        #Add failures WITH sources
        upsert_run_failures(conn, run_id=run_id, breakdown={"PARSE_ERROR": 1},
        sources={"PARSE_ERROR": ["fixtures/feeds/broken.xml"]}
        )

    finally:
        conn.close()

    resp = client.get(f"/debug/run/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    #Verify failed_sources in response
    assert "failed_sources" in data
    assert data["failed_sources"] == {"PARSE_ERROR": ["fixtures/feeds/broken.xml"]}
    assert data["failures_by_code"] == {"PARSE_ERROR": 1}


def test_debug_stats_scoped_to_last_10_dates(client: TestClient):
    """GET /debug/stats returns counts for last 10 dates only."""
    from tests.conftest import create_admin_session
    from src.schemas import NewsItem
    from src.repo import insert_news_items

    client = create_admin_session(client)

    conn = get_conn()
    try:
        init_db(conn)

        # Seed items for 15 different dates
        items = []
        for i in range(15):
            day = f"2026-01-{10 + i:02d}"
            items.append(NewsItem(
                source="test",
                url=f"https://example.com/{day}/article",
                published_at=datetime.fromisoformat(f"{day}T12:00:00+00:00"),
                title=f"Article for {day}",
                evidence="test",
            ))
        insert_news_items(conn, items)
    finally:
        conn.close()

    resp = client.get("/debug/stats")
    assert resp.status_code == 200
    data = resp.json()

    # Should have max 10 dates
    assert len(data["items_by_date"]) <= 10

    # Oldest dates (2026-01-10 through 2026-01-14) should NOT be in response
    dates_in_response = [d["date"] for d in data["items_by_date"]]
    assert "2026-01-10" not in dates_in_response
    assert "2026-01-24" in dates_in_response  # Most recent should be there


def test_debug_stats_items_by_date_breakdown(client: TestClient):
    """GET /debug/stats returns items_by_date with correct counts."""
    from tests.conftest import create_admin_session
    from src.schemas import NewsItem
    from src.repo import insert_news_items

    client = create_admin_session(client)

    conn = get_conn()
    try:
        init_db(conn)

        # Seed 3 items for one date, 2 for another
        items = [
            NewsItem(source="test", url="https://example.com/a1",
                     published_at=datetime.fromisoformat("2026-01-20T12:00:00+00:00"),
                     title="Article A1", evidence="test"),
            NewsItem(source="test", url="https://example.com/a2",
                     published_at=datetime.fromisoformat("2026-01-20T13:00:00+00:00"),
                     title="Article A2", evidence="test"),
            NewsItem(source="test", url="https://example.com/a3",
                     published_at=datetime.fromisoformat("2026-01-20T14:00:00+00:00"),
                     title="Article A3", evidence="test"),
            NewsItem(source="test", url="https://example.com/b1",
                     published_at=datetime.fromisoformat("2026-01-21T12:00:00+00:00"),
                     title="Article B1", evidence="test"),
            NewsItem(source="test", url="https://example.com/b2",
                     published_at=datetime.fromisoformat("2026-01-21T13:00:00+00:00"),
                     title="Article B2", evidence="test"),
        ]
        insert_news_items(conn, items)
    finally:
        conn.close()

    resp = client.get("/debug/stats")
    assert resp.status_code == 200
    data = resp.json()

    # Find counts for each date
    by_date = {d["date"]: d["items"] for d in data["items_by_date"]}
    assert by_date.get("2026-01-20") == 3
    assert by_date.get("2026-01-21") == 2