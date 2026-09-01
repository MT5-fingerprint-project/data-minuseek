import pytest

from src.services.comparison import ComparisonService, ImageNotFoundError
from src.services.sourceafis import SearchTimings


class FakeImageRepository:
    """Rend une image par identifiant connu, et None pour les autres — comme GCS
    quand un objet manque."""

    def __init__(self, known_ids):
        self._known_ids = known_ids

    def fetch(self, case_id, folder, image_id):
        if image_id not in self._known_ids:
            return None
        return (f"{image_id}.jpg", f"{image_id} bytes".encode())


class RecordingEngine:
    def __init__(self):
        self.received = None

    def search(self, trace_bytes, trace_dpi, reference_prints, top):
        self.received = (trace_bytes, trace_dpi, reference_prints, top)
        results = [
            {"reference_print": name.split(".")[0], "score": 1.0} for name, _, _ in reference_prints
        ]
        timings = SearchTimings(
            trace_extraction_seconds=0.0,
            reference_extraction_seconds=[(result["reference_print"], 0.0) for result in results],
            matching_seconds=0.0,
            total_seconds=0.0,
        )
        return results, timings


def test_a_missing_reference_print_does_not_shift_the_others_resolutions():
    """L'empreinte absente est retirée en silence : si la résolution voyageait
    dans une liste parallèle, les suivantes seraient extraites à l'échelle de
    leur voisine."""
    engine = RecordingEngine()
    service = ComparisonService(FakeImageRepository({"trace-1", "ref-1", "ref-3"}), engine)

    service.compare(
        "case-1",
        "trace-1",
        2775,
        [("ref-1", 1054), ("ref-2", 600), ("ref-3", 500)],
        3,
    )

    _, trace_dpi, reference_prints, _ = engine.received
    assert trace_dpi == 2775
    assert [(name, dpi) for name, _, dpi in reference_prints] == [
        ("ref-1.jpg", 1054),
        ("ref-3.jpg", 500),
    ]


def test_comparing_without_a_single_reachable_reference_print_fails():
    service = ComparisonService(FakeImageRepository({"trace-1"}), RecordingEngine())

    with pytest.raises(ImageNotFoundError):
        service.compare("case-1", "trace-1", 2775, [("ref-1", 1054)], 1)
