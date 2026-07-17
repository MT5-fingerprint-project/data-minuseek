from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends

from src.repositories.image_repository import GcsImageRepository, get_image_repository
from src.services.sourceafis import SourceAfisEngine, get_sourceafis_engine

logger = logging.getLogger(__name__)


class ImageNotFoundError(Exception):
    """Raised when the trace or all requested reference prints are missing from storage."""


class ComparisonFailedError(Exception):
    """Raised when the fingerprint matching engine fails to compare the images."""


class ComparisonService:
    """Orchestrates fetching fingerprint images and matching them via SourceAFIS."""

    def __init__(self, image_repository: GcsImageRepository, engine: SourceAfisEngine) -> None:
        self._images = image_repository
        self._engine = engine

    def compare(
        self,
        case_id: str,
        trace_id: str,
        reference_print_ids: list[str],
        top: int,
    ) -> list[dict]:
        trace = self._images.fetch(case_id, "traces", trace_id)
        if trace is None:
            raise ImageNotFoundError(f"Trace {trace_id} not found in case {case_id}")

        references = [
            image
            for ref_id in reference_print_ids
            if (image := self._images.fetch(case_id, "reference-prints", ref_id)) is not None
        ]
        if not references:
            raise ImageNotFoundError(f"No reference prints found in case {case_id}")

        _, trace_bytes = trace

        try:
            return self._engine.search(trace_bytes, references, top)
        except Exception as exc:
            logger.exception("Fingerprint comparison failed")
            raise ComparisonFailedError("Could not compare fingerprints") from exc


def get_comparison_service(
    image_repository: Annotated[GcsImageRepository, Depends(get_image_repository)],
    engine: Annotated[SourceAfisEngine, Depends(get_sourceafis_engine)],
) -> ComparisonService:
    return ComparisonService(image_repository, engine)
