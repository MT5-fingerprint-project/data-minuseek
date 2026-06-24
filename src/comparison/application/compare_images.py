"""Cas d'usage : comparer deux images et rapporter le résultat."""

from src.comparison.domain.models import ComparisonResult, ImagePair
from src.comparison.domain.ports import ComparisonReporter


class CompareImagesUseCase:
    """Confronte deux images puis notifie le résultat via le port de sortie.

    Le cas d'usage ne dépend que du port `ComparisonReporter` (inversion de
    dépendance) : l'implémentation concrète est injectée par l'adaptateur.
    """

    def __init__(self, reporter: ComparisonReporter) -> None:
        self._reporter = reporter

    def execute(self, pair: ImagePair) -> ComparisonResult:
        message = (
            f"comparaison effectuée entre {pair.first_image} "
            f"et {pair.second_image}"
        )
        result = ComparisonResult(
            first_image=pair.first_image,
            second_image=pair.second_image,
            message=message,
        )
        self._reporter.report(result)
        return result
