import re
from pathlib import Path

from src.config import ENGINE_VERSION, SOURCEAFIS_VERSION

POM = Path(__file__).resolve().parents[1] / "java" / "sourceafis" / "pom.xml"


def test_engine_version_matches_the_sourceafis_dependency():
    """Le jour où le jar SourceAFIS est monté de version sans toucher à
    ENGINE_VERSION, un rapport probant citerait un algorithme qui n'a pas produit
    le score. Ce test rend l'oubli impossible."""
    pom = POM.read_text(encoding="utf-8")
    declared = re.search(
        r"<artifactId>sourceafis</artifactId>\s*<version>([^<]+)</version>", pom
    )

    assert declared is not None, "dépendance sourceafis introuvable dans le pom"
    assert declared.group(1) == SOURCEAFIS_VERSION


def test_engine_version_is_not_the_service_version():
    from src.config import APP_VERSION

    assert ENGINE_VERSION != APP_VERSION
    assert ENGINE_VERSION.startswith(f"sourceafis-{SOURCEAFIS_VERSION}")
