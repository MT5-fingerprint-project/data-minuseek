"""Évalue le détecteur de règle et aide à calibrer son seuil.

Usage :
    uv run python scripts/evaluate_ruler_detector.py                   # jeu synthétique
    uv run python scripts/evaluate_ruler_detector.py --with DIR --without DIR   # photos réelles

Le jeu de photos réelles (avec / sans règle) vit HORS du repo : les photos de
traces sont des données biométriques. Le script imprime la distribution des
confiances et TPR/FPR pour plusieurs seuils ; le seuil retenu se reporte dans
RULER_CONFIDENCE_THRESHOLD et incrémente RULER_DETECTOR_CALIBRATION (config.py).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.ruler_detection import RulerDetection, RulerDetector  # noqa: E402

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
THRESHOLDS = (0.2, 0.3, 0.4, 0.5, 0.6)


def _load_dir(directory: Path) -> list[bytes]:
    files = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    return [p.read_bytes() for p in files]


def _synthetic(count: int, seed: int) -> tuple[list[bytes], list[bytes]]:
    from tests.synthetic_images import (
        encode_png,
        fingerprint_scene,
        ruler_scene,
        stripes_scene,
    )

    rng = np.random.default_rng(seed)
    positives = [encode_png(ruler_scene(rng)[0]) for _ in range(count)]
    negatives = [encode_png(fingerprint_scene(rng)) for _ in range(count)]
    negatives += [encode_png(stripes_scene(rng)) for _ in range(count // 4)]
    return positives, negatives


def _run(detector: RulerDetector, images: list[bytes]) -> list[RulerDetection]:
    return [detector.detect(data) for data in images]


def _describe(name: str, results: list[RulerDetection]) -> None:
    conf = np.array([r.confidence for r in results])
    print(
        f"{name:10s} n={len(conf):3d}  confiance min/p10/med/p90/max = "
        f"{conf.min():.2f} / {np.percentile(conf, 10):.2f} / {np.median(conf):.2f} / "
        f"{np.percentile(conf, 90):.2f} / {conf.max():.2f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--with", dest="with_dir", type=Path, help="photos AVEC règle")
    parser.add_argument(
        "--without", dest="without_dir", type=Path, help="photos SANS règle"
    )
    parser.add_argument(
        "--count", type=int, default=40, help="taille du jeu synthétique par classe"
    )
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    if args.with_dir and args.without_dir:
        positives, negatives = _load_dir(args.with_dir), _load_dir(args.without_dir)
    else:
        positives, negatives = _synthetic(args.count, args.seed)

    detector = RulerDetector(threshold=0.0)
    start = time.time()
    pos, neg = _run(detector, positives), _run(detector, negatives)
    print(f"{(time.time() - start) / (len(pos) + len(neg)):.2f} s / image\n")

    _describe("avec", pos)
    _describe("sans", neg)
    print()
    for threshold in THRESHOLDS:
        tpr = float(np.mean([r.confidence >= threshold for r in pos]))
        fpr = float(np.mean([r.confidence >= threshold for r in neg]))
        print(f"seuil {threshold:.2f} : TPR = {tpr:.2f}   FPR = {fpr:.2f}")

    print("\nRègles les moins sûres :")
    for r in sorted(pos, key=lambda r: r.confidence)[:5]:
        print(f"  {r}")
    print("Faux positifs les plus sûrs :")
    for r in sorted(neg, key=lambda r: -r.confidence)[:5]:
        print(f"  {r}")


if __name__ == "__main__":
    main()
