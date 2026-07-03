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


def _fetch_image(case_id: str, folder: str, image_id: str) -> tuple[str, bytes]:
    """Fetch an image directly from the GCS bucket the back writes to."""
    # The back stores objects at: media/investigation-case/{caseId}/{folder}/{id}.*
    # (same object-key convention as the back's ImageStoragePort, cf. ADR-0002/0003).
    bucket = _storage_client.bucket(GCS_BUCKET)
    base_key = f"media/investigation-case/{case_id}/{folder}/{image_id}"

    for ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        blob = bucket.blob(f"{base_key}{ext}")
        try:
            return (f"{image_id}{ext}", blob.download_as_bytes())
        except NotFound:
            continue

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
