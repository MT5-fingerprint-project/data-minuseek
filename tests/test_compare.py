from fastapi.testclient import TestClient

from src.config import ENGINE_VERSION
from src.main import app
from src.services.comparison import get_comparison_service


_NOT_PASSED = object()


class StubComparisonService:
    def __init__(self):
        self.received_trace_dpi = _NOT_PASSED
        self.received_reference_print_dpis = _NOT_PASSED

    def compare(
        self,
        case_id,
        trace_id,
        reference_print_ids,
        top,
        trace_dpi=_NOT_PASSED,
        reference_print_dpis=_NOT_PASSED,
    ):
        self.received_trace_dpi = trace_dpi
        self.received_reference_print_dpis = reference_print_dpis
        return [{"reference_print": reference_print_ids[0], "score": 88.5}]


def test_compare_forwards_the_per_image_dpis_to_the_service():
    service = StubComparisonService()
    app.dependency_overrides[get_comparison_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/data/api/compare",
            json={
                "case_id": "case-1",
                "trace_id": "trace-1",
                "reference_print_ids": ["ref-1", "ref-2"],
                "top": 2,
                "trace_dpi": 1040.0,
                "reference_print_dpis": {"ref-1": 1067.0, "ref-2": None},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.received_trace_dpi == 1040.0
    assert service.received_reference_print_dpis == {"ref-1": 1067.0, "ref-2": None}


def test_compare_defaults_the_dpis_when_the_request_does_not_carry_them():
    service = StubComparisonService()
    app.dependency_overrides[get_comparison_service] = lambda: service
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
    assert service.received_trace_dpi is None
    assert service.received_reference_print_dpis == {}


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
