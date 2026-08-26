"""Images synthétiques pour tester le détecteur de règle sans données biométriques.

Les photos de traces réelles sont des données personnelles : le jeu de calibration
réel vit hors du repo. Ici on génère des scènes contrôlées, reproductibles (seed),
qui exercent les invariants de l'algorithme : rotation, perspective, bruit, flou,
et surtout les faux positifs connus (crêtes papillaires, rayures).
"""

from __future__ import annotations

import cv2
import numpy as np


def _background(height: int, width: int, rng: np.random.Generator) -> np.ndarray:
    base = int(rng.integers(60, 200))
    noise = rng.normal(0, 12, (height, width)).astype(np.float32)
    texture = cv2.GaussianBlur(noise, (0, 0), 3) * 3 + base
    return np.clip(texture, 0, 255).astype(np.uint8)


def _finish(img: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    img = cv2.GaussianBlur(img, (0, 0), float(rng.uniform(0.5, 1.5)))
    noisy = img.astype(np.float32) + rng.normal(0, 4, img.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def ruler_scene(
    rng: np.random.Generator,
    height: int = 900,
    width: int = 1200,
    px_per_mm: int | None = None,
    center: tuple[float, float] | None = None,
    angle_deg: float | None = None,
    background: np.ndarray | None = None,
) -> tuple[np.ndarray, int]:
    """Scène avec une règle graduée (traits 1/5/10 mm) posée avec rotation et
    perspective aléatoires, sur un fond neutre ou sur `background` (ex. une trace :
    une vraie photo contient la trace ET la règle). Retourne (image, px_par_mm)."""
    img = (
        background.copy() if background is not None else _background(height, width, rng)
    )
    height, width = img.shape
    px_per_mm = px_per_mm or int(rng.integers(8, 18))
    length_mm = int(rng.integers(50, 110))
    ruler_w, ruler_h = px_per_mm * length_mm, int(rng.integers(60, 120))

    ruler = np.full((ruler_h, ruler_w), int(rng.integers(200, 250)), np.uint8)
    thickness = 1 if px_per_mm < 10 else 2
    for mm in range(length_mm):
        x = mm * px_per_mm
        tick = (
            ruler_h // 2
            if mm % 10 == 0
            else ruler_h // 3
            if mm % 5 == 0
            else ruler_h // 5
        )
        cv2.line(ruler, (x, 0), (x, tick), 20, thickness)

    angle = float(rng.uniform(-60, 60)) if angle_deg is None else angle_deg
    cx, cy = center or (
        width / 2 + rng.uniform(-150, 150),
        height / 2 + rng.uniform(-200, 200),
    )
    perspective = float(rng.uniform(0.85, 1.15))
    src = np.float32([[0, 0], [ruler_w, 0], [ruler_w, ruler_h], [0, ruler_h]])
    dst = np.float32(
        [
            [-ruler_w / 2, -ruler_h / 2],
            [ruler_w / 2 * perspective, -ruler_h / 2],
            [ruler_w / 2 * perspective, ruler_h / 2],
            [-ruler_w / 2, ruler_h / 2],
        ]
    )
    rotation = cv2.getRotationMatrix2D((0, 0), angle, 1.0)[:, :2]
    dst = (dst @ rotation.T + [cx, cy]).astype(np.float32)
    homography = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(ruler, homography, (width, height), borderValue=0)
    mask = (
        cv2.warpPerspective(
            np.full((ruler_h, ruler_w), 255, np.uint8), homography, (width, height)
        )
        > 0
    )
    img[mask] = warped[mask]
    return _finish(img, rng), px_per_mm


def fingerprint_scene(
    rng: np.random.Generator,
    height: int = 900,
    width: int = 1200,
    straight_edge: bool = True,
) -> np.ndarray:
    """Négatif difficile : motif de crêtes quasi périodique (spire / arche / boucle)
    + une longue droite (bord de carte ou de table) pour attirer Hough."""
    img = _background(height, width, rng)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx, cy = width / 2 + rng.uniform(-100, 100), height / 2 + rng.uniform(-100, 100)
    period = float(rng.uniform(6, 14))
    kind = int(rng.integers(0, 3))
    radius = np.hypot(xx - cx, yy - cy)
    if kind == 0:
        phase = 2 * np.pi * radius / period
    elif kind == 1:
        phase = (
            2
            * np.pi
            * (yy + 40 * np.sin((xx - cx) / 120) + 0.0004 * (xx - cx) ** 2)
            / period
        )
    else:
        theta = np.arctan2(yy - cy, xx - cx)
        phase = 2 * np.pi * (radius + 30 * np.sin(2 * theta)) / period
    ridges = (np.sin(phase) > 0.2).astype(np.float32)
    blob = (
        np.hypot((xx - cx) / rng.uniform(180, 300), (yy - cy) / rng.uniform(220, 380))
        < 1
    ).astype(np.float32)
    blob = cv2.GaussianBlur(blob, (0, 0), 15)
    contrast = float(rng.uniform(40, 110))
    img = np.clip(img.astype(np.float32) - ridges * blob * contrast, 0, 255).astype(
        np.uint8
    )
    if straight_edge:
        p1 = (int(rng.integers(0, width)), 0)
        p2 = (int(rng.integers(0, width)), height - 1)
        cv2.line(img, p1, p2, int(rng.integers(0, 60)), int(rng.integers(2, 6)))
    return _finish(img, rng)


def stripes_scene(
    rng: np.random.Generator, height: int = 900, width: int = 1200
) -> np.ndarray:
    """Négatif : rayures régulières (chemise, carrelage) — périodique et rectiligne,
    mais sans hiérarchie de graduations."""
    img = _background(height, width, rng)
    period = int(rng.integers(8, 30))
    for x in range(0, width, period):
        cv2.line(
            img,
            (x, 0),
            (x, height),
            int(rng.integers(0, 80)),
            int(rng.integers(1, period // 2 + 1)),
        )
    rotation = cv2.getRotationMatrix2D(
        (width / 2, height / 2), float(rng.uniform(-45, 45)), 1.0
    )
    img = cv2.warpAffine(img, rotation, (width, height), borderMode=cv2.BORDER_REFLECT)
    return img


def encode_png(img: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", img)
    assert ok
    return buffer.tobytes()
