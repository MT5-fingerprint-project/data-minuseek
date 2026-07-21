from concurrent.futures import ThreadPoolExecutor

import jpype
import jpype.imports
from fastapi import Request

from src.config import JARS_DIR

# Template extraction dominates the cost of a comparison (tens of seconds per
# high-resolution photo) and is single-threaded inside SourceAFIS, so the
# engine extracts the trace and reference templates concurrently in the JVM
# (JPype releases the GIL during Java calls). Bounded to stay within the
# container CPU and JVM heap budget.
_TEMPLATE_WORKERS = 4


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

    def _make_template(self, image_bytes: bytes, dpi: int) -> object:
        options = self._image_options().dpi(dpi)
        return self._template(self._image(image_bytes, options))

    def search(
        self,
        trace_bytes: bytes,
        reference_prints: list[tuple[str, bytes]],
        top: int,
        dpi: int = 500,
    ) -> list[dict]:
        """Compare a trace against many reference prints, best matches first."""
        with ThreadPoolExecutor(max_workers=_TEMPLATE_WORKERS) as executor:
            trace_future = executor.submit(self._make_template, trace_bytes, dpi)
            reference_futures = [
                (name, executor.submit(self._make_template, data, dpi))
                for name, data in reference_prints
            ]
            matcher = self._matcher(trace_future.result())

            results = []
            for name, reference_future in reference_futures:
                score = float(matcher.match(reference_future.result()))
                results.append({"reference_print": name.split(".")[0], "score": score})

        results.sort(key=lambda result: result["score"], reverse=True)
        return results[:top]


def get_sourceafis_engine(request: Request) -> SourceAfisEngine:
    return request.app.state.sourceafis
