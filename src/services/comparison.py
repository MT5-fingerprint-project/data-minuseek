from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import Depends

from src.repositories.image_repository import GcsImageRepository, get_image_repository
from src.services.sourceafis import (
    SearchTimings,
    SourceAfisEngine,
    get_sourceafis_engine,
)

logger = logging.getLogger(__name__)


class ImageNotFoundError(Exception):
    """Raised when the trace or all requested reference prints are missing from storage."""


class ComparisonFailedError(Exception):
    """Raised when the fingerprint matching engine fails to compare the images."""


def _log_timings(
    trace_id: str,
    reference_count: int,
    downloaded_bytes: int,
    fetch_seconds: float,
    timings: SearchTimings,
    total_seconds: float,
) -> None:
    extraction_cumulative = sum(timings.extraction_seconds)
    parallelism = (
        extraction_cumulative / timings.total_seconds if timings.total_seconds else 0.0
    )

    logger.info(
        "comparison timings trace=%s references=%d downloaded=%.1fMB fetch=%.1fs "
        "engine=%.1fs extraction_cumulative=%.1fs extraction_slowest=%.1fs "
        "extraction_fastest=%.1fs matching=%.3fs parallelism=%.1fx total=%.1fs",
        trace_id,
        reference_count,
        downloaded_bytes / 1_000_000,
        fetch_seconds,
        timings.total_seconds,
        extraction_cumulative,
        max(timings.extraction_seconds),
        min(timings.extraction_seconds),
        timings.matching_seconds,
        parallelism,
        total_seconds,
    )


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
        started = time.perf_counter()

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

        fetch_seconds = time.perf_counter() - started

        _, trace_bytes = trace

        try:
            results, timings = self._engine.search(trace_bytes, references, top)
        except Exception as exc:
            logger.exception("Fingerprint comparison failed")
            raise ComparisonFailedError("Could not compare fingerprints") from exc

        _log_timings(
            trace_id,
            len(references),
            len(trace_bytes) + sum(len(data) for _, data in references),
            fetch_seconds,
            timings,
            time.perf_counter() - started,
        )
        return results


def get_comparison_service(
    image_repository: Annotated[GcsImageRepository, Depends(get_image_repository)],
    engine: Annotated[SourceAfisEngine, Depends(get_sourceafis_engine)],
) -> ComparisonService:
    return ComparisonService(image_repository, engine)
