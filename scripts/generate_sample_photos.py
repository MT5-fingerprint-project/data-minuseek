"""Génère un jeu de démo pour tester `POST /data/api/detect-ruler` à la main.

    uv run python scripts/generate_sample_photos.py OUT_DIR

Produit OUT_DIR/with/*.jpg (trace + règle, variées) et OUT_DIR/without/*.jpg (trace
seule, bord de carte, texture rayée). Images synthétiques : aucune donnée réelle.
Le jeu de calibration réel, lui, reste hors du repo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.synthetic_images import fingerprint_scene, ruler_scene, stripes_scene  # noqa: E402

MOBILE = (4000, 3000)  # portrait 3:4, 12 MP, comme la capture guidée
GALLERY = (1600, 1200)  # import galerie basse résolution


def _save(path: Path, img: np.ndarray, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img, [cv2.IMWRITE_JPEG_QUALITY, quality])


def main(out_dir: Path) -> None:
    rng = np.random.default_rng(2026)

    # --- avec règle : (taille, px/mm, angle, centre normalisé, qualité JPEG)
    with_ruler = [
        ("01_mobile_regle_bande_viseur", MOBILE, 20, 0, (0.5, 0.77), 92),
        ("02_mobile_regle_inclinee_15deg", MOBILE, 18, 15, (0.5, 0.75), 90),
        ("03_mobile_regle_verticale_a_gauche", MOBILE, 22, 90, (0.15, 0.5), 88),
        ("04_mobile_regle_loin_petite_echelle", MOBILE, 13, -30, (0.55, 0.8), 85),
        ("05_galerie_basse_resolution", GALLERY, 9, 5, (0.5, 0.78), 80),
    ]
    for name, (height, width), px_per_mm, angle, (cx, cy), quality in with_ruler:
        trace = fingerprint_scene(rng, height, width, straight_edge=False)
        img, _ = ruler_scene(
            rng,
            px_per_mm=px_per_mm,
            angle_deg=angle,
            center=(cx * width, cy * height),
            background=trace,
        )
        _save(out_dir / "with" / f"{name}.jpg", img, quality)

    # --- sans règle
    without = [
        (
            "01_mobile_trace_seule",
            lambda: fingerprint_scene(rng, *MOBILE, straight_edge=False),
            92,
        ),
        (
            "02_mobile_trace_et_bord_de_carte",
            lambda: fingerprint_scene(rng, *MOBILE, straight_edge=True),
            90,
        ),
        (
            "03_mobile_trace_contraste_fort",
            lambda: _high_contrast(fingerprint_scene(rng, *MOBILE, False)),
            88,
        ),
        (
            "04_galerie_trace_seule",
            lambda: fingerprint_scene(rng, *GALLERY, straight_edge=False),
            80,
        ),
        ("05_mobile_texture_rayee", lambda: stripes_scene(rng, *MOBILE), 85),
    ]
    for name, build, quality in without:
        _save(out_dir / "without" / f"{name}.jpg", build(), quality)

    print(f"10 images écrites dans {out_dir}/with et {out_dir}/without")


def _high_contrast(img: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(img)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
