from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import storage
from google.cloud.exceptions import NotFound
from pydantic import BaseModel

from src.config import GCP_PROJECT, GCS_BUCKET
from src.schemas import SearchCandidate, SearchResponse
from src.services.sourceafis import SourceAfisEngine, get_sourceafis_engine

logger = logging.getLogger(__name__)

# Score au-delà duquel deux empreintes sont considérées comme correspondantes
DEFAULT_MATCH_THRESHOLD = 40.0

router = APIRouter()

_storage_client = storage.Client(project=GCP_PROJECT)


class CompareRequest(BaseModel):
    case_id: str
    trace_id: str
    reference_print_ids: list[str]
    top: int = 20
    threshold: float = DEFAULT_MATCH_THRESHOLD


def _fetch_image(case_id: str, folder: str, image_id: str) -> tuple[str, bytes] | None:
    """Fetch an image directly from the GCS bucket"""
    bucket = _storage_client.bucket(GCS_BUCKET)
    base_key = f"media/investigation-case/{case_id}/{folder}/{image_id}"

    for ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        blob = bucket.blob(f"{base_key}{ext}")
        try:
            return (f"{image_id}{ext}", blob.download_as_bytes())
        except NotFound:
            continue

    logger.warning("Image %s not found in case %s/%s, skipping it", image_id, case_id, folder)
    return None


@router.post("/compare")
def compare(
    body: CompareRequest,
    engine: Annotated[SourceAfisEngine, Depends(get_sourceafis_engine)],
) -> SearchResponse:
    try:
        trace = _fetch_image(body.case_id, "traces", body.trace_id)
        references = [
            image
            for ref_id in body.reference_print_ids
            if (image := _fetch_image(body.case_id, "reference-prints", ref_id)) is not None
        ]
    except Exception:
        logger.exception("Failed to fetch fingerprint images")
        raise HTTPException(status_code=502, detail="Could not fetch fingerprint images") from None

    if trace is None or not references:
        return SearchResponse(results=[])

    _, trace_bytes = trace

    try:
        results = engine.search(trace_bytes, references, body.top, body.threshold)
    except Exception:
        logger.exception("Fingerprint comparison failed")
        raise HTTPException(status_code=400, detail="Could not compare fingerprints") from None

    return SearchResponse(results=[SearchCandidate(**result) for result in results])
