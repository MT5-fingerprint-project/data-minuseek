from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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


class CompareRequest(BaseModel):
    case_id: str
    trace_id: str
    reference_print_ids: list[str]
    top: int = 20


@router.post("/compare")
def compare(
    body: CompareRequest,
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
) -> SearchResponse:
    try:
        results = service.compare(body.case_id, body.trace_id, body.reference_print_ids, body.top)
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ImageStorageError:
        raise HTTPException(status_code=502, detail="Could not fetch fingerprint images") from None
    except ComparisonFailedError:
        raise HTTPException(status_code=400, detail="Could not compare fingerprints") from None

    return SearchResponse(results=[SearchCandidate(**result) for result in results])
