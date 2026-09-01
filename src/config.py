import os
from pathlib import Path

APP_NAME = "data-minuseek"
APP_VERSION = "0.1.0"

JARS_DIR = Path(os.environ.get("SOURCEAFIS_JARS_DIR", "/app/build/jars"))

# Version du moteur de comparaison, indépendante d'APP_VERSION : elle change
# quand SourceAFIS ou son paramétrage change, pas quand le service évolue. Le
# back l'inscrit dans l'acte COMPARISON_EXECUTED de son journal ; le rapport,
# lui, ne la cite pas. La paramétrisation passe à 2 parce que les images sont
# désormais extraites à leur propre résolution : les mêmes deux images ne
# rendent plus le même score qu'avant, et rien d'autre ne distingue les deux.
SOURCEAFIS_VERSION = "3.17.1"
ENGINE_PARAMETERIZATION = "2"
ENGINE_VERSION = f"sourceafis-{SOURCEAFIS_VERSION}+minuseek.{ENGINE_PARAMETERIZATION}"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


# Bucket GCS privé où le back stocke les images (traces, empreintes de
# référence) ; accès en lecture directe, keyless (ADC / impersonation), même
# bucket que celui signé par le back (cf. ADR-0002/0003 du back).
GCS_BUCKET = _require_env("GCS_BUCKET")

# Projet GCP du bucket (le client Python google-cloud-storage, contrairement
# au client Node du back, ne le déduit pas des credentials impersonées).
GCP_PROJECT = _require_env("GCP_PROJECT")
