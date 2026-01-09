# Import TestClient from FastAPI - this allows us to test our API without running a server
from fastapi.testclient import TestClient
# Import the FastAPI app instance from our main application file
from src.main import app

# Define a test function that will check if the health endpoint works correctly
def test_health():
    # Create a test client that wraps our FastAPI app for testing
    client = TestClient(app)
    # Make a GET request to the "/health" endpoint and store the response
    resp = client.get("/health")
    # Assert that the HTTP status code is 200 (OK/success)
    assert resp.status_code == 200
    # Assert that the JSON response body matches the expected health check format
    assert resp.json() == {"status": "ok"}
