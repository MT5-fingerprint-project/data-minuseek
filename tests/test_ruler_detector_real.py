"""Tests sur photos réelles — opt-in, le jeu vit hors du repo.

    RULER_REAL_SAMPLES_DIR=~/Desktop/dev/data-minuseek-samples/real uv run pytest tests/test_ruler_detector_real.py -v

Attendu : 100 % sur `with/` (règle exploitable) et `without/` (pas de règle).
`hard/` (cas hors domaine, limites connues) est seulement rapporté.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config import RULER_CONFIDENCE_THRESHOLD
from src.services.ruler_detection import RulerDetector

SAMPLES_DIR = os.environ.get("RULER_REAL_SAMPLES_DIR")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

pytestmark = pytest.mark.skipif(
    not SAMPLES_DIR,
    reason="RULER_REAL_SAMPLES_DIR non défini (jeu de photos réelles hors repo)",
)


def _images(subdir: str) -> list[Path]:
    if not SAMPLES_DIR:
        return []
    folder = Path(SAMPLES_DIR) / subdir
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


@pytest.fixture(scope="module")
def detector() -> RulerDetector:
    return RulerDetector(threshold=RULER_CONFIDENCE_THRESHOLD)


@pytest.mark.parametrize("path", _images("with"), ids=lambda p: p.name)
def test_real_photo_with_a_ruler_is_detected(detector, path):
    result = detector.detect(path.read_bytes())

    assert result.present, result
    assert result.ticks_count >= 20


@pytest.mark.parametrize("path", _images("without"), ids=lambda p: p.name)
def test_real_photo_without_a_ruler_is_rejected(detector, path):
    result = detector.detect(path.read_bytes())

    assert not result.present, result


def test_report_hard_cases(detector, capsys):
    """Ne fait jamais échouer : imprime le comportement sur les cas limites connus."""
    for path in _images("hard"):
        result = detector.detect(path.read_bytes())
        with capsys.disabled():
            print(
                f"\n[hard] {path.name[:45]:45s} present={result.present!s:5} "
                f"conf={result.confidence:.2f} period={result.period_px}"
            )
