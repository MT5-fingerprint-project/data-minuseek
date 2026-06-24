"""Entités et objets-valeur du domaine de comparaison.

Pas de FastAPI, pas de Pydantic ici : du Python pur, testable hors framework.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePair:
    """Les deux images à confronter, identifiées par leur nom."""

    first_image: str
    second_image: str


@dataclass(frozen=True)
class ComparisonResult:
    """Résultat d'une comparaison : les images confrontées et le message produit."""

    first_image: str
    second_image: str
    message: str
