import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from src.schemas import SearchCandidate, SearchResponse
from src.services.sourceafis import SourceAfisEngine, get_sourceafis_engine

logger = logging.getLogger(__name__)

# Score au-delà duquel deux empreintes sont considérées comme correspondantes
# (valeur "industry standard" de haute confiance pour SourceAFIS).
DEFAULT_MATCH_THRESHOLD = 40.0

router = APIRouter()


@router.post("/compare")
def compare(
    trace: UploadFile,
    reference_prints: list[UploadFile],
    top: int = 20,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    engine: SourceAfisEngine = Depends(get_sourceafis_engine),
) -> SearchResponse:
    references = [(ref.filename or "unknown", ref.file.read()) for ref in reference_prints]

    try:
        results = engine.search(trace.file.read(), references, top, threshold)
    except Exception:
        logger.exception("Fingerprint comparison failed")
        raise HTTPException(status_code=400, detail="Could not compare fingerprints") from None

    return SearchResponse(results=[SearchCandidate(**result) for result in results])
