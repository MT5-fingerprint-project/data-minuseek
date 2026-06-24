"""Adaptateur de sortie : rapporte la comparaison dans la console (stdout)."""

from src.comparison.domain.models import ComparisonResult
from src.comparison.domain.ports import ComparisonReporter


class ConsoleComparisonReporter(ComparisonReporter):
    """Implémentation du port `ComparisonReporter` qui écrit dans la console.

    Équivalent Python d'un `console.log` : le message apparaît dans la sortie
    standard du serveur uvicorn.
    """

    def report(self, result: ComparisonResult) -> None:
        print(result.message, flush=True)
