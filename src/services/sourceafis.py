import jpype
import jpype.imports
from fastapi import Request

from src.config import JARS_DIR


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
        threshold: float,
        dpi: int = 500,
    ) -> list[dict]:
        """Compare a trace against many reference prints, best matches first."""
        trace_template = self._make_template(trace_bytes, dpi)
        matcher = self._matcher(trace_template)

        results = []
        for name, data in reference_prints:
            reference_template = self._make_template(data, dpi)
            score = float(matcher.match(reference_template))
            results.append({"reference_print": name.split(".")[0], "score": score, "match": score >= threshold})

        results.sort(key=lambda result: result["score"], reverse=True)
        return results[:top]


def get_sourceafis_engine(request: Request) -> SourceAfisEngine:
    return request.app.state.sourceafis
