import json

import numpy as np
from fastapi.testclient import TestClient

from src.config import MAX_IMAGE_SIZE_BYTES, RULER_DETECTOR_VERSION
from src.main import app
from src.routers.detect_ruler import get_ruler_detector
from src.services.ruler_detection import RulerDetection, RulerDetector
from tests.synthetic_images import encode_png


class StubDetector:
    threshold = 0.3

    def __init__(self):
        self.calls = []

    def detect(self, image_bytes, roi=None):
        self.calls.append((image_bytes, roi))
        return RulerDetection(
            present=True,
            confidence=0.71,
            period_px=18.2,
            angle_deg=3.0,
            ticks_count=47,
            coherence=0.8,
            duty_cycle=0.2,
            hierarchy=0.6,
            found_in_roi=roi is not None,
        )


def _post(client, files, data=None):
    return client.post("/data/api/detect-ruler", files=files, data=data or {})


def test_returns_the_verdict_the_measures_and_the_engine_version():
    stub = StubDetector()
    app.dependency_overrides[get_ruler_detector] = lambda: stub
    try:
        response = _post(
            TestClient(app), {"image": ("trace.png", b"png-bytes", "image/png")}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["present"] is True
    assert body["confidence"] == 0.71
    assert body["threshold"] == 0.3
    assert body["engine_version"] == RULER_DETECTOR_VERSION
    assert body["details"] == {
        "period_px": 18.2,
        "angle_deg": 3.0,
        "ticks_count": 47,
        "coherence": 0.8,
        "duty_cycle": 0.2,
        "hierarchy": 0.6,
        "found_in_roi": False,
    }
    assert stub.calls == [(b"png-bytes", None)]


def test_forwards_the_roi_hint_to_the_detector():
    stub = StubDetector()
    app.dependency_overrides[get_ruler_detector] = lambda: stub
    try:
        response = _post(
            TestClient(app),
            {"image": ("trace.png", b"png-bytes", "image/png")},
            {"roi": json.dumps({"x": 0.1, "y": 0.72, "width": 0.8, "height": 0.1})},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["details"]["found_in_roi"] is True
    _, roi = stub.calls[0]
    assert (roi.x, roi.y, roi.width, roi.height) == (0.1, 0.72, 0.8, 0.1)


def test_rejects_a_roi_outside_the_image():
    stub = StubDetector()
    app.dependency_overrides[get_ruler_detector] = lambda: stub
    try:
        response = _post(
            TestClient(app),
            {"image": ("trace.png", b"png-bytes", "image/png")},
            {"roi": json.dumps({"x": 0.5, "y": 0.5, "width": 0.6, "height": 0.1})},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert stub.calls == []


def test_rejects_an_undecodable_image_with_400():
    app.dependency_overrides[get_ruler_detector] = lambda: RulerDetector(threshold=0.3)
    try:
        response = _post(
            TestClient(app), {"image": ("trace.png", b"not an image", "image/png")}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_rejects_an_oversized_image_with_413():
    stub = StubDetector()
    app.dependency_overrides[get_ruler_detector] = lambda: stub
    try:
        too_big = b"\0" * (MAX_IMAGE_SIZE_BYTES + 1)
        response = _post(
            TestClient(app), {"image": ("trace.png", too_big, "image/png")}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert stub.calls == []


def test_requires_an_image():
    response = TestClient(app).post("/data/api/detect-ruler")

    assert response.status_code == 422


def test_end_to_end_with_the_real_detector_on_a_synthetic_ruler():
    from tests.synthetic_images import ruler_scene

    img, _ = ruler_scene(np.random.default_rng(7), px_per_mm=12)

    response = _post(
        TestClient(app), {"image": ("trace.png", encode_png(img), "image/png")}
    )

    assert response.status_code == 200
    assert response.json()["present"] is True
