from typing import Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    engine_version: str


class SearchCandidate(BaseModel):
    reference_print: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchCandidate]
    engine_version: str


class RulerDetectionDetails(BaseModel):
    """Mesures qui justifient le verdict — lisibles par un expert, réutilisées par la
    calibration DPI (ticket D2) : la période en pixels d'une graduation = 1 mm."""

    period_px: Optional[float]
    angle_deg: Optional[float]
    ticks_count: int
    coherence: float
    duty_cycle: Optional[float]
    hierarchy: float
    found_in_roi: bool


class RulerDetectionResponse(BaseModel):
    present: bool
    confidence: float
    threshold: float
    engine_version: str
    details: RulerDetectionDetails
