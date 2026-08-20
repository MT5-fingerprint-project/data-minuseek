from fastapi.testclient import TestClient

from src.config import ENGINE_VERSION
from src.main import app
from src.services.comparison import get_comparison_service


class StubComparisonService:
    def compare(self, case_id, trace_id, reference_print_ids, top):
        return [{"reference_print": reference_print_ids[0], "score": 88.5}]


def test_compare_returns_the_engine_version_that_produced_the_scores():
    app.dependency_overrides[get_comparison_service] = lambda: StubComparisonService()
    client = TestClient(app)
    try:
        response = client.post(
            "/data/api/compare",
            json={
                "case_id": "case-1",
                "trace_id": "trace-1",
                "reference_print_ids": ["ref-1"],
                "top": 1,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == [{"reference_print": "ref-1", "score": 88.5}]
    assert body["engine_version"] == ENGINE_VERSION
