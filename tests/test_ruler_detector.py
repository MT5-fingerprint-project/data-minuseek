import os

import numpy as np
import pytest

from src.services.ruler_detection import InvalidImageError, Roi, RulerDetector
from tests.synthetic_images import (
    encode_png,
    fingerprint_scene,
    ruler_scene,
    stripes_scene,
)

THRESHOLD = 0.4


@pytest.fixture(scope="module")
def detector() -> RulerDetector:
    return RulerDetector(threshold=THRESHOLD)


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_detects_a_ruler_and_measures_its_graduation_period(detector, seed):
    img, px_per_mm = ruler_scene(np.random.default_rng(seed), px_per_mm=12)

    result = detector.detect(encode_png(img))

    assert result.present, result
    # La période mesurée = 1 mm en pixels, base de la calibration DPI (D2).
    assert result.period_px == pytest.approx(px_per_mm, rel=0.25), result
    assert result.ticks_count >= 15


@pytest.mark.parametrize("seed", [10, 11, 12, 13])
def test_does_not_mistake_fingerprint_ridges_for_a_ruler(detector, seed):
    """Les crêtes papillaires sont périodiques et rectilignes par endroits : seuls le
    rapport cyclique et la hiérarchie des graduations les distinguent d'une règle."""
    img = fingerprint_scene(np.random.default_rng(seed))

    result = detector.detect(encode_png(img))

    assert not result.present, result


@pytest.mark.parametrize("seed", [20, 21])
def test_does_not_mistake_regular_stripes_for_a_ruler(detector, seed):
    result = detector.detect(encode_png(stripes_scene(np.random.default_rng(seed))))

    assert not result.present, result


def test_plain_scene_without_any_periodic_pattern_has_zero_confidence(detector):
    rng = np.random.default_rng(30)
    img = fingerprint_scene(rng, straight_edge=False)
    img[:] = img.mean()  # aplat uniforme

    result = detector.detect(encode_png(img))

    assert result.confidence == 0.0
    assert result.period_px is None and result.angle_deg is None


def test_roi_hint_is_searched_first_at_native_resolution(detector):
    """Le mobile connaît la bande où la règle est posée : on la fouille en premier."""
    rng = np.random.default_rng(40)
    height, width = 1600, 1200
    img, _ = ruler_scene(
        rng, height, width, px_per_mm=14, center=(600, 1230), angle_deg=0
    )
    roi = Roi(x=0.1, y=0.72, width=0.8, height=0.1)

    result = detector.detect(encode_png(img), roi)

    assert result.present
    assert result.found_in_roi


def test_roi_hint_does_not_prevent_a_full_image_search(detector):
    rng = np.random.default_rng(41)
    img, _ = ruler_scene(rng, 1600, 1200, px_per_mm=14, center=(600, 300), angle_deg=0)

    result = detector.detect(encode_png(img), Roi(x=0.1, y=0.72, width=0.8, height=0.1))

    assert result.present
    assert not result.found_in_roi


def test_rejects_bytes_that_are_not_an_image(detector):
    with pytest.raises(InvalidImageError):
        detector.detect(b"definitely not an image")


def test_rejects_empty_payload(detector):
    with pytest.raises(InvalidImageError):
        detector.detect(b"")


def test_rejects_decompression_bombs():
    detector = RulerDetector(threshold=THRESHOLD, max_pixels=1_000)
    with pytest.raises(InvalidImageError):
        detector.detect(encode_png(np.zeros((100, 100), np.uint8)))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(x=1, y=0, width=0.5, height=0.5),
        dict(x=0.5, y=0, width=0.6, height=0.5),
        dict(x=0, y=0, width=0, height=1),
    ],
)
def test_roi_must_stay_inside_the_image(kwargs):
    with pytest.raises(ValueError):
        Roi(**kwargs)


def test_rejects_a_truncated_png_as_invalid_rather_than_crashing(detector):
    truncated = encode_png(np.zeros((64, 64), np.uint8))[:40]

    with pytest.raises(InvalidImageError):
        detector.detect(truncated)


@pytest.mark.skipif(
    not os.environ.get("RULER_FULL_EVAL"),
    reason="RULER_FULL_EVAL non défini (évaluation de population, ~1 min)",
)
def test_synthetic_population_has_no_false_positive_and_high_recall(detector):
    """Population synthétique (règles variées / empreintes / rayures) : 0 faux positif,
    rappel ≥ 0,85. Les seuils sont ceux constatés à la calibration `cal.0`."""
    rng = np.random.default_rng(2026)
    rulers = [detector.detect(encode_png(ruler_scene(rng)[0])) for _ in range(30)]
    negatives = [detector.detect(encode_png(fingerprint_scene(rng))) for _ in range(30)]
    negatives += [detector.detect(encode_png(stripes_scene(rng))) for _ in range(8)]

    assert sum(r.present for r in negatives) == 0, [r for r in negatives if r.present]
    assert sum(r.present for r in rulers) / len(rulers) >= 0.85
