from src.services.comparison import ComparisonService
from src.services.sourceafis import DEFAULT_DPI, SearchTimings


class FakeImageRepository:
    """Imite GcsImageRepository : (filename, bytes) ou None si absent."""

    def __init__(self, images):
        self._images = images

    def fetch(self, case_id, folder, image_id):
        return self._images.get((folder, image_id))


class RecordingEngine:
    def __init__(self):
        self.received = None

    def search(self, trace_bytes, reference_prints, top, trace_dpi):
        self.received = {
            "trace_bytes": trace_bytes,
            "reference_prints": reference_prints,
            "top": top,
            "trace_dpi": trace_dpi,
        }
        return (
            [
                {"reference_print": name.split(".")[0], "score": 1.0}
                for name, _, _ in reference_prints
            ],
            SearchTimings(extraction_seconds=[0.0], matching_seconds=0.0, total_seconds=0.0),
        )


def _service(engine):
    images = FakeImageRepository(
        {
            ("traces", "trace-1"): ("trace-1.jpg", b"trace-bytes"),
            ("reference-prints", "ref-1"): ("ref-1.jpg", b"ref1-bytes"),
            ("reference-prints", "ref-2"): ("ref-2.jpg", b"ref2-bytes"),
        }
    )
    return ComparisonService(images, engine)


def test_compare_passes_each_calibrated_dpi_to_the_engine():
    engine = RecordingEngine()
    service = _service(engine)

    service.compare(
        "case-1",
        "trace-1",
        ["ref-1", "ref-2"],
        top=2,
        trace_dpi=1040.0,
        reference_print_dpis={"ref-1": 1067.0, "ref-2": None},
    )

    assert engine.received["trace_dpi"] == 1040.0
    assert engine.received["reference_prints"] == [
        ("ref-1.jpg", b"ref1-bytes", 1067.0),
        ("ref-2.jpg", b"ref2-bytes", DEFAULT_DPI),
    ]


def test_compare_defaults_every_dpi_to_500_when_nothing_is_calibrated():
    engine = RecordingEngine()
    service = _service(engine)

    service.compare("case-1", "trace-1", ["ref-1"], top=1)

    assert engine.received["trace_dpi"] == DEFAULT_DPI
    assert engine.received["reference_prints"] == [("ref-1.jpg", b"ref1-bytes", DEFAULT_DPI)]
