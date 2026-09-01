from fastapi.testclient import TestClient

from src.config import ENGINE_VERSION
from src.main import app
from src.services.comparison import get_comparison_service


class StubComparisonService:
    def __init__(self):
        self.received = None

    def compare(self, case_id, trace_id, trace_dpi, reference_prints, top):
        self.received = (case_id, trace_id, trace_dpi, reference_prints, top)
        return [
            {"reference_print": reference_id, "score": 88.5}
            for reference_id, _ in reference_prints
        ]


def post_compare(body, service=None):
    app.dependency_overrides[get_comparison_service] = lambda: service or StubComparisonService()
    try:
        return TestClient(app).post("/data/api/compare", json=body)
    finally:
        app.dependency_overrides.clear()


def test_compare_returns_the_engine_version_that_produced_the_scores():
    response = post_compare(
        {
            "case_id": "case-1",
            "trace_id": "trace-1",
            "trace_dpi": 2775,
            "reference_prints": [{"id": "ref-1", "dpi": 1054}],
            "top": 1,
        }
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == [{"reference_print": "ref-1", "score": 88.5}]
    assert body["engine_version"] == ENGINE_VERSION == "sourceafis-3.17.1+minuseek.2"


def test_compare_refuses_a_trace_without_a_resolution():
    response = post_compare(
        {
            "case_id": "case-1",
            "trace_id": "trace-1",
            "reference_prints": [{"id": "ref-1", "dpi": 1054}],
        }
    )

    assert response.status_code == 422
    assert "trace_dpi" in str(response.json()["detail"])


def test_compare_refuses_a_reference_print_resolution_outside_the_bounds():
    below = post_compare(
        {
            "case_id": "case-1",
            "trace_id": "trace-1",
            "trace_dpi": 2775,
            "reference_prints": [{"id": "ref-1", "dpi": 10}],
        }
    )
    above = post_compare(
        {
            "case_id": "case-1",
            "trace_id": "trace-1",
            "trace_dpi": 2775,
            "reference_prints": [{"id": "ref-1", "dpi": 10_001}],
        }
    )

    assert below.status_code == 422
    assert above.status_code == 422


def test_compare_hands_each_reference_print_its_own_resolution():
    """Deux empreintes de résolutions différentes : les extraire toutes les deux
    à celle de la première produirait des scores plausibles et faux."""
    service = StubComparisonService()

    response = post_compare(
        {
            "case_id": "case-1",
            "trace_id": "trace-1",
            "trace_dpi": 2775,
            "reference_prints": [{"id": "ref-1", "dpi": 1054}, {"id": "ref-2", "dpi": 500}],
            "top": 2,
        },
        service,
    )

    assert response.status_code == 200
    assert service.received == (
        "case-1",
        "trace-1",
        2775,
        [("ref-1", 1054), ("ref-2", 500)],
        2,
    )
