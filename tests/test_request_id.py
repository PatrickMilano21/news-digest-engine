from fastapi.testclient import TestClient

from src.main import app


def test_request_id_header_present_on_response():
    client = TestClient(app)
    resp = client.get("/health")

    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 32



