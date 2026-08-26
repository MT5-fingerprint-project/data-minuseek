from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError, model_validator

from src.config import (
    MAX_IMAGE_SIZE_BYTES,
    RULER_CONFIDENCE_THRESHOLD,
    RULER_DETECTOR_VERSION,
)
from src.schemas import RulerDetectionDetails, RulerDetectionResponse
from src.services.ruler_detection import InvalidImageError, Roi, RulerDetector

# Data rend un verdict brut (présence + confiance + mesures) : décider de refuser
# la trace (422 RULER_NOT_DETECTED) ou d'accepter un override appartient au back.
# La route prend les octets et non des IDs, car elle est appelée AVANT toute
# écriture de la trace (cf. ADR-0001 de ce repo, ADR-0010 §7 du back).
router = APIRouter()


class RoiForm(BaseModel):
    """Zone d'intérêt normalisée, transmise en JSON dans le champ multipart `roi`."""

    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_image(self) -> "RoiForm":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("roi must stay inside the image")
        return self


@lru_cache(maxsize=1)
def get_ruler_detector() -> RulerDetector:
    return RulerDetector(threshold=RULER_CONFIDENCE_THRESHOLD)


def _parse_roi(raw: Optional[str]) -> Optional[Roi]:
    if raw is None or raw == "":
        return None
    try:
        form = RoiForm.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid roi: {exc}") from None
    return Roi(x=form.x, y=form.y, width=form.width, height=form.height)


@router.post("/detect-ruler")
def detect_ruler(
    detector: Annotated[RulerDetector, Depends(get_ruler_detector)],
    image: UploadFile = File(...),
    roi: Optional[str] = Form(None),
) -> RulerDetectionResponse:
    # Lecture bornée : on ne charge jamais plus que la limite + 1 octet en mémoire.
    data = image.file.read(MAX_IMAGE_SIZE_BYTES + 1)
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the size limit")

    try:
        result = detector.detect(data, _parse_roi(roi))
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return RulerDetectionResponse(
        present=result.present,
        confidence=result.confidence,
        threshold=detector.threshold,
        engine_version=RULER_DETECTOR_VERSION,
        details=RulerDetectionDetails(
            period_px=result.period_px,
            angle_deg=result.angle_deg,
            ticks_count=result.ticks_count,
            coherence=result.coherence,
            duty_cycle=result.duty_cycle,
            hierarchy=result.hierarchy,
            found_in_roi=result.found_in_roi,
        ),
    )
