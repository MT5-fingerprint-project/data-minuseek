"""Adaptateur d'entrée HTTP : expose le cas d'usage de comparaison via FastAPI.

Schémas Pydantic en camelCase (alias) pour coller aux conventions du front,
tandis que le domaine reste en snake_case.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from src.comparison.adapters.outbound.console_reporter import (
    ConsoleComparisonReporter,
)
from src.comparison.application.compare_images import CompareImagesUseCase
from src.comparison.domain.models import ImagePair
from src.comparison.domain.ports import ComparisonReporter

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


class ComparisonRequest(BaseModel):
    """Corps de requête : les noms des deux images à comparer."""

    model_config = ConfigDict(populate_by_name=True)

    first_image: str = Field(alias="firstImage", min_length=1)
    second_image: str = Field(alias="secondImage", min_length=1)


class ComparisonResponse(BaseModel):
    """Réponse : les images confrontées et le message de comparaison."""

    model_config = ConfigDict(populate_by_name=True)

    first_image: str = Field(serialization_alias="firstImage")
    second_image: str = Field(serialization_alias="secondImage")
    message: str


# --- Composition / injection de dépendances ---------------------------------


def get_reporter() -> ComparisonReporter:
    return ConsoleComparisonReporter()


def get_compare_images_use_case(
    reporter: ComparisonReporter = Depends(get_reporter),
) -> CompareImagesUseCase:
    return CompareImagesUseCase(reporter)


# --- Route -------------------------------------------------------------------


@router.post("", response_model=ComparisonResponse)
def compare_images(
    payload: ComparisonRequest,
    use_case: CompareImagesUseCase = Depends(get_compare_images_use_case),
) -> ComparisonResponse:
    result = use_case.execute(
        ImagePair(
            first_image=payload.first_image,
            second_image=payload.second_image,
        )
    )
    return ComparisonResponse(
        first_image=result.first_image,
        second_image=result.second_image,
        message=result.message,
    )
