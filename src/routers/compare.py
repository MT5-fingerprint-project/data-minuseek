import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.config import S3_API_URL
from src.schemas import SearchCandidate, SearchResponse
from src.services.sourceafis import SourceAfisEngine, get_sourceafis_engine

logger = logging.getLogger(__name__)

# Score au-delà duquel deux empreintes sont considérées comme correspondantes
DEFAULT_MATCH_THRESHOLD = 40.0

router = APIRouter()


class CompareRequest(BaseModel):
    case_id: str
    trace_id: str
    reference_print_ids: list[str]
    top: int = 20
    threshold: float = DEFAULT_MATCH_THRESHOLD


def _fetch_image(case_id: str, folder: str, image_id: str) -> tuple[str, bytes]:
    """Fetch an image from the main backend storage via HTTP."""
    # The main backend stores files at: media/investigation-case/{caseId}/{folder}/{id}.*
    # It serves them as static assets under /media/...
    # We list and find the file by its ID prefix (extension unknown at this point)
    base_url = f"{S3_API_URL}/investigation-case/{case_id}/{folder}"

    for ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        url = f"{base_url}/{image_id}{ext}"
        with httpx.Client() as client:
            response = client.get(url)
            if response.status_code == 200:
                return (f"{image_id}{ext}", response.content)

    raise HTTPException(
        status_code=404,
        detail=f"Image {image_id} not found in case {case_id}/{folder}",
    )


@router.post("/compare")
def compare(
    body: CompareRequest,
    engine: Annotated[SourceAfisEngine, Depends(get_sourceafis_engine)],
) -> SearchResponse:
    try:
        trace_name, trace_bytes = _fetch_image(body.case_id, "traces", body.trace_id)
        references = [
            _fetch_image(body.case_id, "reference-prints", ref_id)
            for ref_id in body.reference_print_ids
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch fingerprint images")
        raise HTTPException(status_code=502, detail="Could not fetch fingerprint images") from None

    try:
        results = engine.search(trace_bytes, references, body.top, body.threshold)
    except Exception:
        logger.exception("Fingerprint comparison failed")
        raise HTTPException(status_code=400, detail="Could not compare fingerprints") from None

    return SearchResponse(results=[SearchCandidate(**result) for result in results])
