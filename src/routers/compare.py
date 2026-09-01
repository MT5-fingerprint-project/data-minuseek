from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.config import ENGINE_VERSION
from src.repositories.image_repository import ImageStorageError
from src.schemas import SearchCandidate, SearchResponse
from src.services.comparison import (
    ComparisonFailedError,
    ComparisonService,
    ImageNotFoundError,
    get_comparison_service,
)

# Data rend des scores bruts : l'interprétation match/non-match appartient
# au domaine du back (cf. ADR côté back-minuseek).
router = APIRouter()

# Mêmes bornes que le VO ImageResolution du back, à dessein : une résolution
# refusée à la saisie ne doit pas redevenir acceptable en arrivant ici.
Resolution = Annotated[float, Field(ge=50, le=10_000)]


class ReferencePrintRef(BaseModel):
    id: str
    dpi: Resolution


class CompareRequest(BaseModel):
    case_id: str
    trace_id: str
    trace_dpi: Resolution
    reference_prints: list[ReferencePrintRef]
    top: int = 20


@router.post("/compare")
def compare(
    body: CompareRequest,
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
) -> SearchResponse:
    try:
        results = service.compare(
            body.case_id,
            body.trace_id,
            body.trace_dpi,
            [(reference.id, reference.dpi) for reference in body.reference_prints],
            body.top,
        )
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ImageStorageError:
        raise HTTPException(status_code=502, detail="Could not fetch fingerprint images") from None
    except ComparisonFailedError:
        raise HTTPException(status_code=400, detail="Could not compare fingerprints") from None

    return SearchResponse(
        results=[SearchCandidate(**result) for result in results],
        engine_version=ENGINE_VERSION,
    )
