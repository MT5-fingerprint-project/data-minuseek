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
    case_id: str,
    trace_id: str,
    trace_bytes: bytes,
    reference_images: list[tuple[str, bytes]],
    fetch_seconds: float,
    timings: SearchTimings,
    total_seconds: float,
) -> None:
    # Le poids accompagne chaque durée : sans lui on ne peut pas dire si une
    # extraction lente l'est parce que l'image est grosse ou parce qu'elle est
    # chargée en texture, et les deux n'appellent pas le même remède.
    weights = {name.split(".")[0]: len(data) for name, data in reference_images}
    durations = timings.reference_extraction_seconds

    slowest_reference, slowest_seconds = max(durations, key=lambda entry: entry[1])
    fastest_reference, fastest_seconds = min(durations, key=lambda entry: entry[1])
    extraction_cumulative = timings.trace_extraction_seconds + sum(
        seconds for _, seconds in durations
    )
    downloaded_bytes = len(trace_bytes) + sum(weights.values())
    parallelism = (
        extraction_cumulative / timings.total_seconds if timings.total_seconds else 0.0
    )

    logger.info(
        "comparison timings case=%s trace=%s references=%d downloaded=%.1fMB fetch=%.1fs "
        "engine=%.1fs trace_extraction=%.1fs/%.1fMB reference_slowest=%s:%.1fs/%.1fMB "
        "reference_fastest=%s:%.1fs/%.1fMB extraction_cumulative=%.1fs matching=%.3fs "
        "parallelism=%.1fx total=%.1fs",
        case_id,
        trace_id,
        len(durations),
        downloaded_bytes / 1_000_000,
        fetch_seconds,
        timings.total_seconds,
        timings.trace_extraction_seconds,
        len(trace_bytes) / 1_000_000,
        slowest_reference,
        slowest_seconds,
        weights[slowest_reference] / 1_000_000,
        fastest_reference,
        fastest_seconds,
        weights[fastest_reference] / 1_000_000,
        extraction_cumulative,
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
            case_id,
            trace_id,
            trace_bytes,
            references,
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
