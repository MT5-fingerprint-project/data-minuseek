"""Détection de la présence d'une règle millimétrée sur une photo de trace.

Approche classique et déterministe : une règle est définie mathématiquement, pas
visuellement. Quelle que soit sa couleur ou sa forme, elle a :

1. des graduations **équidistantes** (motif périodique),
2. **alignées sur une droite** (le bord de la règle),
3. des traits **fins** séparés par des espaces larges (rapport cyclique faible),
4. une **hiérarchie** : un trait plus long tous les 5 mm et tous les 10 mm.

Les critères 3 et 4 sont indispensables : une trace papillaire est elle-même un
motif périodique quasi rectiligne (crêtes/vallées ≈ 50 % / 50 %, sans hiérarchie)
et passe pour une règle si l'on ne regarde que la périodicité.

Pipeline : décodage → (zone d'intérêt à résolution native, puis) image entière
réduite → orientations candidates (Hough) → rotation pour rendre la règle
horizontale → bandes horizontales → profil 1-D de noirceur → période, run de
graduations alignées, cohérence → rapport cyclique, hiérarchie → confiance.

Ce module ne connaît ni FastAPI ni HTTP : le router traduit la requête en appel.
Paramètres et limites connues : ADR-0001.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Optional

from src.config import MAX_IMAGE_PIXELS

# Garde-fou contre les bombes de décompression : OpenCV lit les dimensions dans
# l'en-tête et refuse l'image AVANT d'allouer. À poser avant le premier décodage.
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", str(MAX_IMAGE_PIXELS))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

# --- Paramètres de l'algorithme (calibration `cal.0`, cf. RULER_DETECTOR_VERSION) ---
ANALYSIS_LONG_SIDE = 2600  # l'image entière est réduite à ce grand côté
ROI_LONG_SIDE = 2400  # la zone d'intérêt est analysée (quasi) à résolution native
PERIOD_RANGE = (4, 120)  # période d'une graduation (1 mm), en pixels d'analyse
BAND_HEIGHT = 12  # hauteur des bandes horizontales analysées
MIN_TICKS = 20  # graduations alignées minimales : ≥ 2 cm de règle lisible
MIN_COHERENCE = 0.2  # cohérence de phase minimale du motif
MAX_DUTY_CYCLE = 0.45  # au-delà, les traits sont trop larges pour une règle
PEAK_LEVEL = 0.6  # un pic dépasse la moyenne de PEAK_LEVEL × écart-type


class InvalidImageError(Exception):
    """Levée quand les octets reçus ne sont pas une image décodable (ou déraisonnable)."""


@dataclass(frozen=True)
class Roi:
    """Zone d'intérêt normalisée (0..1) où le client attend la règle.

    Le viseur mobile impose une bande de pose de la règle : la transmettre permet
    de l'analyser en premier, à résolution native. C'est un indice, pas une
    contrainte — l'image entière est analysée si la bande ne contient rien.
    """

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if not (0 <= self.x < 1 and 0 <= self.y < 1):
            raise ValueError("roi: x et y doivent être dans [0, 1[")
        if not (0 < self.width <= 1 - self.x and 0 < self.height <= 1 - self.y):
            raise ValueError(
                "roi: width/height doivent être > 0 et rester dans l'image"
            )

    def crop(self, gray: np.ndarray) -> np.ndarray:
        height, width = gray.shape
        x0, y0 = int(self.x * width), int(self.y * height)
        x1 = min(width, math.ceil((self.x + self.width) * width))
        y1 = min(height, math.ceil((self.y + self.height) * height))
        return gray[y0:y1, x0:x1]


@dataclass(frozen=True)
class RulerDetection:
    """Verdict et mesures qui le justifient (à l'échelle de l'image d'origine)."""

    present: bool
    confidence: float
    period_px: Optional[float]
    angle_deg: Optional[float]
    ticks_count: int
    coherence: float
    duty_cycle: Optional[float]
    hierarchy: float
    found_in_roi: bool


@dataclass(frozen=True)
class _Candidate:
    """Une bande de l'image qui ressemble à une règle."""

    confidence: float
    period_px: float
    angle_deg: float
    ticks_count: int
    coherence: float
    duty_cycle: float
    hierarchy: float


class RulerDetector:
    """Détecteur de règle millimétrée par périodicité des graduations.

    `threshold` : confiance minimale pour déclarer la règle présente (calibrée sur
    photos réelles, versionnée via RULER_DETECTOR_VERSION).
    """

    def __init__(self, threshold: float, max_pixels: int = MAX_IMAGE_PIXELS) -> None:
        self._threshold = threshold
        self._max_pixels = max_pixels

    @property
    def threshold(self) -> float:
        return self._threshold

    def detect(self, image_bytes: bytes, roi: Optional[Roi] = None) -> RulerDetection:
        gray = _decode(image_bytes, self._max_pixels)
        candidates = []

        if roi is not None:
            in_roi = _best_candidate(roi.crop(gray), ROI_LONG_SIDE)
            if in_roi is not None and in_roi.confidence >= self._threshold:
                return self._verdict(in_roi, found_in_roi=True)
            candidates.append(in_roi)

        candidates.append(_best_candidate(gray, ANALYSIS_LONG_SIDE))
        best = max(
            (c for c in candidates if c is not None),
            key=lambda c: c.confidence,
            default=None,
        )
        return self._verdict(best, found_in_roi=False)

    def _verdict(
        self, candidate: Optional[_Candidate], found_in_roi: bool
    ) -> RulerDetection:
        if candidate is None:
            return RulerDetection(
                False, 0.0, None, None, 0, 0.0, None, 0.0, found_in_roi
            )
        return RulerDetection(
            present=candidate.confidence >= self._threshold,
            confidence=round(candidate.confidence, 3),
            period_px=round(candidate.period_px, 2),
            angle_deg=round(candidate.angle_deg, 1),
            ticks_count=candidate.ticks_count,
            coherence=round(candidate.coherence, 3),
            duty_cycle=round(candidate.duty_cycle, 3),
            hierarchy=round(candidate.hierarchy, 3),
            found_in_roi=found_in_roi,
        )


# --------------------------------------------------------------------- image


def _decode(image_bytes: bytes, max_pixels: int) -> np.ndarray:
    """Décode en niveaux de gris 8 bits (orientation EXIF appliquée par OpenCV)."""
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    try:
        gray = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE) if buffer.size else None
    except cv2.error as exc:  # fichier corrompu ou dimensions hors limite
        raise InvalidImageError(f"Image non décodable : {exc}") from None
    if gray is None or gray.size == 0:
        raise InvalidImageError(
            "Image non décodable (formats acceptés : PNG, JPEG, TIFF)"
        )
    if gray.size > max_pixels:
        raise InvalidImageError(f"Image trop grande ({gray.size} pixels)")
    return gray


def _best_candidate(gray: np.ndarray, long_side: int) -> Optional[_Candidate]:
    """Meilleure bande « règle » de l'image, période ramenée aux pixels d'origine."""
    scale = min(1.0, long_side / max(gray.shape))
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    if min(gray.shape) < 4 * BAND_HEIGHT:
        return None
    # Égalisation locale : graduations lisibles même sous éclairage inégal.
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

    best: Optional[_Candidate] = None
    for angle in _candidate_angles(gray):
        darkness = _rotated_darkness(gray, angle)
        for y in range(0, darkness.shape[0] - BAND_HEIGHT, BAND_HEIGHT // 2):
            candidate = _score_band(darkness, y, angle)
            if candidate is not None and (
                best is None or candidate.confidence > best.confidence
            ):
                best = candidate
    if best is None:
        return None
    return _Candidate(**{**best.__dict__, "period_px": best.period_px / scale})


def _candidate_angles(gray: np.ndarray) -> list[float]:
    """Orientations des longues droites de l'image (bord de la règle), via Hough.

    Segments regroupés par pas de 2°, pondérés par leur longueur ; on garde les 4
    groupes dominants et, pour chacun, l'angle **moyen pondéré** (le centre du
    groupe serait trop imprécis : 1° d'erreur décale les graduations de dizaines de
    pixels sur une règle qui traverse l'image). L'horizontale et la verticale sont
    toujours candidates : une règle est presque toujours posée droite.
    """
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 720,
        threshold=80,
        minLineLength=int(0.08 * max(gray.shape)),
        maxLineGap=8,
    )
    angles: list[float] = []
    if lines is not None:
        weight: dict[int, float] = {}
        vector: dict[
            int, complex
        ] = {}  # moyenne d'orientations modulo 180° : angle doublé
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            theta, length = math.atan2(y2 - y1, x2 - x1), math.hypot(x2 - x1, y2 - y1)
            key = round(math.degrees(theta) % 180 / 2) * 2 % 180
            weight[key] = weight.get(key, 0.0) + length
            vector[key] = vector.get(key, 0j) + length * complex(
                math.cos(2 * theta), math.sin(2 * theta)
            )
        for key in sorted(weight, key=lambda k: -weight[k])[:4]:
            angles.append(
                math.degrees(math.atan2(vector[key].imag, vector[key].real)) / 2 % 180
            )
    for axis in (0.0, 90.0):
        if all(min(abs(a - axis), 180 - abs(a - axis)) > 1.0 for a in angles):
            angles.append(axis)
    return angles


def _rotated_darkness(gray: np.ndarray, angle: float) -> np.ndarray:
    """Image de « noirceur » (255 − gris) tournée pour rendre l'orientation horizontale :
    les graduations deviennent des traits verticaux."""
    height, width = gray.shape
    diagonal = int(math.hypot(height, width))
    rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotation[:, 2] += [(diagonal - width) / 2, (diagonal - height) / 2]
    rotated = cv2.warpAffine(gray, rotation, (diagonal, diagonal), borderValue=255)
    return 255.0 - rotated.astype(np.float32)


# ---------------------------------------------------------------------- bande


def _score_band(darkness: np.ndarray, y: int, angle: float) -> Optional[_Candidate]:
    strip = darkness[y : y + BAND_HEIGHT]
    graduations = _graduations(strip.mean(axis=0))
    if graduations is None:
        return None
    period, ticks, coherence = graduations
    if len(ticks) < MIN_TICKS or coherence < MIN_COHERENCE:
        return None

    duty_cycle = _duty_cycle(strip, ticks)
    hierarchy = _hierarchy(_tick_lengths(darkness, ticks, y, period))

    # Confiance : périodicité (cohérence, saturée à MIN_TICKS traits), pondérée par
    # les deux discriminants propres à une règle.
    periodic = coherence * min(1.0, len(ticks) / MIN_TICKS)
    duty_score = float(np.clip((MAX_DUTY_CYCLE - duty_cycle) / 0.25, 0.0, 1.0))
    confidence = periodic * (0.5 * duty_score + 0.5 * math.sqrt(hierarchy))
    return _Candidate(
        confidence, float(period), angle, len(ticks), coherence, duty_cycle, hierarchy
    )


def _graduations(profile: np.ndarray) -> Optional[tuple[int, np.ndarray, float]]:
    """(période, positions du plus long run de traits alignés, cohérence) d'un profil."""
    pmin, pmax = PERIOD_RANGE
    if len(profile) < 2 * pmax:
        return None
    # Détrendage : on retire ombres et dégradés pour ne garder que les oscillations
    # à l'échelle des graduations.
    signal = profile - _box_blur(profile, 3 * pmax)
    if signal.std() < 1e-3:
        return None

    period = _dominant_period(_autocorrelation(signal))
    # Un trait large est un plateau bruité (plusieurs maxima) : lissage au quart de période.
    smooth = _box_blur(signal, max(3, period // 4))
    peaks = _local_maxima(smooth, smooth.mean() + PEAK_LEVEL * smooth.std())
    if len(peaks) < 2:
        return None
    ticks = _longest_regular_run(peaks, period)

    # Cohérence de phase mesurée LOCALEMENT (~30 périodes au cœur du run) : la
    # perspective fait dériver l'espacement le long de la règle (« chirp »), ce qui
    # écrase l'autocorrélation globale sans que la règle soit moins réelle.
    center, window = (ticks[0] + ticks[-1]) // 2, 15 * period
    local = _autocorrelation(signal[max(0, center - window) : center + window])
    lags = [k * period for k in (1, 2) if k * period < len(local)]
    coherence = float(min(local[lag] for lag in lags)) if lags else 0.0
    return period, ticks, coherence


def _dominant_period(autocorr: np.ndarray) -> int:
    """Période fondamentale : plus petit pic de l'autocorrélation atteignant 70 % du
    meilleur pic dans PERIOD_RANGE.

    Pas le maximum global : pour des traits épais le profil est lisse, son
    autocorrélation décroît doucement depuis le lag 1 et le plus petit lag
    l'emporterait. Pas non plus le plus haut pic : les traits de 5 et 10 mm
    s'alignent aussi et l'harmonique peut dépasser le fondamental.
    """
    pmin, pmax = PERIOD_RANGE
    segment = autocorr[pmin:pmax]
    peaks = _local_maxima(segment)
    if len(peaks) == 0 or segment[peaks].max() <= 0:
        return int(np.argmax(segment)) + pmin
    strong = peaks[segment[peaks] >= 0.7 * segment[peaks].max()]
    return int(strong[0]) + pmin


def _longest_regular_run(peaks: np.ndarray, period: int) -> np.ndarray:
    """Plus longue suite de pics espacés de period ± 25 %. Un pic trop proche du
    précédent est un doublon sur le même trait (ignoré) ; un pic trop loin casse la suite."""
    best: list[int] = []
    current: list[int] = []
    for x in peaks.tolist():
        if current:
            gap = x - current[-1]
            if gap < 0.75 * period:
                continue
            if gap > 1.25 * period:
                current = []
        current.append(x)
        if len(current) > len(best):
            best = current
    return np.asarray(best, dtype=np.int64)


def _duty_cycle(strip: np.ndarray, ticks: np.ndarray) -> float:
    """Part des colonnes « sombres » entre le premier et le dernier trait.
    Règle ≈ 0,1-0,4 (traits sur fond clair) ; crêtes papillaires ≈ 0,5."""
    columns = strip[:, ticks[0] : ticks[-1] + 1].mean(axis=0)
    return float((columns > (columns.min() + columns.max()) / 2).mean())


def _tick_lengths(
    darkness: np.ndarray, ticks: np.ndarray, y: int, period: int
) -> np.ndarray:
    """Longueur de chaque trait, mesurée sur ±3 périodes autour de la bande (assez
    pour les traits de 5 et 10 mm).

    Un pixel appartient au trait s'il est nettement plus sombre que la surface de
    la règle à une demi-période de là. Cette référence locale est indispensable :
    au-delà du bord de la règle, les deux colonnes tombent sur le fond et la
    différence s'annule — un fond sombre ne compte pas comme un trait.
    """
    height, width = darkness.shape
    rows = slice(max(0, y - 3 * period), min(height, y + BAND_HEIGHT + 3 * period))

    def columns(xs: np.ndarray) -> np.ndarray:
        return np.stack(
            [darkness[rows, np.clip(xs + dx, 0, width - 1)] for dx in (-1, 0, 1)]
        ).mean(axis=0)

    contrast = columns(ticks) - columns(ticks + period // 2)
    return ((contrast > 0.5 * contrast.max(axis=0)) & (contrast > 8.0)).sum(axis=0)


def _hierarchy(lengths: np.ndarray) -> float:
    """Score [0, 1] : les traits longs reviennent tous les 5 (ou 10) traits.

    Proéminence du pic de l'autocorrélation des longueurs au lag 5 (ou 10) sur ses
    voisins. Des crêtes courbes ont des longueurs qui varient lentement — une
    autocorrélation élevée partout, sans pic.
    """
    if len(lengths) < 15:
        return 0.0
    centered = lengths.astype(np.float32) - lengths.mean()
    energy = float(centered @ centered)
    if energy < 1e-6:
        return 0.0
    autocorr = np.correlate(centered, centered, "full")[len(centered) - 1 :] / energy
    peak_5 = autocorr[5] - max(autocorr[3], autocorr[4])
    peak_10 = (
        autocorr[10] - max(autocorr[8], autocorr[9]) if len(autocorr) > 10 else 0.0
    )
    return float(np.clip(max(peak_5, peak_10), 0.0, 1.0))


# ------------------------------------------------------------------- signal 1-D


def _box_blur(signal: np.ndarray, width: int) -> np.ndarray:
    return cv2.blur(signal.reshape(1, -1), (width, 1)).ravel()


def _local_maxima(signal: np.ndarray, threshold: float = -math.inf) -> np.ndarray:
    """Indices des maxima locaux stricts à gauche, larges à droite, au-dessus du seuil."""
    inner = signal[1:-1]
    is_peak = (inner > threshold) & (inner > signal[:-2]) & (inner >= signal[2:])
    return np.flatnonzero(is_peak) + 1


def _autocorrelation(signal: np.ndarray) -> np.ndarray:
    """Autocorrélation normalisée (FFT avec zero-padding, sans repliement)."""
    centered = signal - signal.mean()
    spectrum = np.fft.rfft(centered, 2 * len(centered))
    autocorr = np.fft.irfft(spectrum * np.conj(spectrum))[: len(centered)]
    return autocorr / (autocorr[0] + 1e-9)
