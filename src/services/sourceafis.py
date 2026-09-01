import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import jpype
import jpype.imports
from fastapi import Request

from src.config import JARS_DIR

logger = logging.getLogger(__name__)

# Template extraction dominates the cost of a comparison (tens of seconds per
# high-resolution photo) and is single-threaded inside SourceAFIS, so the
# engine extracts the trace and reference templates concurrently in the JVM
# (JPype releases the GIL during Java calls).
#
# The pool is shared by ALL requests: extraction of a 12MP photo transiently
# allocates hundreds of MB of JVM heap, so the number of concurrent
# extractions service-wide must stay bounded or the JVM OOMs (observed with
# Xmx3g). Size the heap for _TEMPLATE_WORKERS concurrent extractions.
_TEMPLATE_WORKERS = 4
_template_pool = ThreadPoolExecutor(max_workers=_TEMPLATE_WORKERS)


@dataclass(frozen=True)
class SearchTimings:
    """Durées d'une recherche, pour savoir où porter l'effort d'optimisation.

    Trace et empreintes sont séparées parce qu'elles n'appellent pas le même
    remède : une trace lente se traite au dpi et au cadrage, une empreinte lente
    se pré-extrait une fois pour toutes au dépôt.

    Les durées sont mesurées à l'intérieur des threads du pool : leur somme
    dépasse `total_seconds` quand les extractions se recouvrent, et le rapport
    entre les deux donne le parallélisme réellement obtenu. La plus longue est
    le plancher qu'aucun ajout de vCPU ne fera descendre, une extraction seule
    étant mono-thread dans SourceAFIS.
    """

    trace_extraction_seconds: float
    reference_extraction_seconds: list[tuple[str, float]]
    matching_seconds: float
    total_seconds: float


class SourceAfisEngine:
    """Wraps the embedded SourceAFIS JVM and exposes fingerprint matching.

    Framework-agnostic on purpose: routers translate HTTP requests into calls
    here, but this class has no knowledge of FastAPI or HTTP.
    """

    def __init__(self) -> None:
        if not jpype.isJVMStarted():
            jars = [str(jar) for jar in JARS_DIR.glob("*.jar")]
            if not jars:
                raise RuntimeError(f"No SourceAFIS jars found in {JARS_DIR}")
            jpype.startJVM(classpath=jars)

        from com.machinezoo.sourceafis import (
            FingerprintImage,
            FingerprintImageOptions,
            FingerprintMatcher,
            FingerprintTemplate,
        )

        self._image = FingerprintImage
        self._image_options = FingerprintImageOptions
        self._matcher = FingerprintMatcher
        self._template = FingerprintTemplate

        # La JVM lit les vCPU et le heap dans les limites du conteneur : ce que
        # Cloud Run alloue et ce que SourceAFIS peut réellement utiliser ne se
        # déduisent pas du Terraform. JClass plutôt qu'un `import java.lang` :
        # le système d'import de JPype n'expose pas les modules du JDK.
        runtime = jpype.JClass("java.lang.Runtime").getRuntime()
        logger.info(
            "sourceafis engine ready processors=%d max_heap=%.1fGB extraction_workers=%d",
            runtime.availableProcessors(),
            runtime.maxMemory() / 1_000_000_000,
            _TEMPLATE_WORKERS,
        )

    def _make_template(self, image_bytes: bytes, dpi: int) -> tuple[object, float]:
        started = time.perf_counter()
        options = self._image_options().dpi(dpi)
        template = self._template(self._image(image_bytes, options))
        return template, time.perf_counter() - started

    def search(
        self,
        trace_bytes: bytes,
        reference_prints: list[tuple[str, bytes]],
        top: int,
        dpi: int = 500,
    ) -> tuple[list[dict], SearchTimings]:
        """Compare a trace against many reference prints, best matches first."""
        started = time.perf_counter()

        trace_future = _template_pool.submit(self._make_template, trace_bytes, dpi)
        reference_futures = [
            (name, _template_pool.submit(self._make_template, data, dpi))
            for name, data in reference_prints
        ]

        trace_template, trace_extraction_seconds = trace_future.result()
        matcher = self._matcher(trace_template)

        reference_extraction_seconds = []
        matching_seconds = 0.0
        results = []
        for name, reference_future in reference_futures:
            reference_template, extraction_seconds = reference_future.result()
            reference_id = name.split(".")[0]
            reference_extraction_seconds.append((reference_id, extraction_seconds))

            matching_started = time.perf_counter()
            score = float(matcher.match(reference_template))
            matching_seconds += time.perf_counter() - matching_started

            results.append({"reference_print": reference_id, "score": score})

        results.sort(key=lambda result: result["score"], reverse=True)

        timings = SearchTimings(
            trace_extraction_seconds=trace_extraction_seconds,
            reference_extraction_seconds=reference_extraction_seconds,
            matching_seconds=matching_seconds,
            total_seconds=time.perf_counter() - started,
        )
        return results[:top], timings


def get_sourceafis_engine(request: Request) -> SourceAfisEngine:
    return request.app.state.sourceafis
