from fastapi.testclient import TestClient

from src.config import APP_VERSION, ENGINE_VERSION
from src.main import app

client = TestClient(app)


def test_health_exposes_engine_version_next_to_service_version():
    response = client.get("/data/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == APP_VERSION
    assert body["engine_version"] == ENGINE_VERSION
