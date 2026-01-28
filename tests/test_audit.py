from datetime import datetime, timezone
from src.repo import write_audit_log, get_audit_logs
from db import get_conn, init_db



def test_audit_log_with_datetime_ts(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    conn = get_conn()
    init_db(conn)

    ts = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
    write_audit_log(conn, event_type="RUN_STARTED", ts=ts, run_id="run-123", day="2026-01-20", details={}) 

    logs = get_audit_logs(conn, limit=1)
    assert len(logs) == 1
    assert logs[0]["event_type"] == "RUN_STARTED"
    assert logs[0]["ts"] == "2026-01-20T12:00:00+00:00"


def test_audit_log_with_string_ts(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    conn = get_conn()
    init_db(conn)
    
    write_audit_log(conn, event_type="DIGEST_GENERATED", ts="2026-01-20T14:00:00Z", run_id="run-456", day="2026-01-20", details={"path": "artifacts/digest.html"})
    
    logs = get_audit_logs(conn, limit=1)
    assert logs[0]["event_type"] == "DIGEST_GENERATED"
    assert logs[0]["details"]["path"] == "artifacts/digest.html"


def test_audit_log_redacts_pii(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    conn = get_conn()
    init_db(conn)

    write_audit_log(conn, event_type="RUN_FINISHED_ERROR", ts="2026-01-20T15:00:00Z", run_id="run-789", day="2026-01-20", details={"error_message": "Failed for user foo@bar.com"})
    
    logs = get_audit_logs(conn, limit=1)
    assert "foo@bar.com" not in logs[0]["details"]["error_message"]
    assert "[REDACTED_EMAIL]" in logs[0]["details"]["error_message"]







