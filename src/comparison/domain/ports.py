"""Ports du domaine : contrats que les adaptateurs doivent implémenter."""

from typing import Protocol

from src.comparison.domain.models import ComparisonResult


class ComparisonReporter(Protocol):
    """Port de sortie (driven).

    Le domaine sait qu'une comparaison doit être « rapportée » au monde
    extérieur, sans connaître le canal concret (console, logs, file d'attente…).
    """

    def report(self, result: ComparisonResult) -> None: ...
