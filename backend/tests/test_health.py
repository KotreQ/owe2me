from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_app_name() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "owe2me"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
