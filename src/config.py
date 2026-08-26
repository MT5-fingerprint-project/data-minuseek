import os
from pathlib import Path

APP_NAME = "data-minuseek"
APP_VERSION = "0.1.0"

JARS_DIR = Path(os.environ.get("SOURCEAFIS_JARS_DIR", "/app/build/jars"))

# Version du moteur de comparaison, indépendante d'APP_VERSION : elle change
# quand SourceAFIS ou son paramétrage change, pas quand le service évolue. Un
# rapport probant cite cette valeur pour dire quel algorithme a produit un score.
SOURCEAFIS_VERSION = "3.17.1"
ENGINE_PARAMETERIZATION = "1"
ENGINE_VERSION = f"sourceafis-{SOURCEAFIS_VERSION}+minuseek.{ENGINE_PARAMETERIZATION}"

# Version du détecteur de règle millimétrée, même logique qu'ENGINE_VERSION :
# elle change quand l'algorithme ou sa calibration (seuil, paramètres) change,
# pas quand le service évolue. Le back la trace dans l'audit de chaque upload.
RULER_DETECTOR_ALGORITHM = "periodicity"
RULER_DETECTOR_CALIBRATION = "0"  # 0 = seuil provisoire, non calibré sur photos réelles
RULER_DETECTOR_VERSION = f"ruler-{RULER_DETECTOR_ALGORITHM}-1.0+cal.{RULER_DETECTOR_CALIBRATION}"

# Seuil de confiance au-dessus duquel la règle est déclarée présente. Surchargeable
# par env pour la calibration ; la valeur par défaut est celle du prototype.
RULER_CONFIDENCE_THRESHOLD = float(os.environ.get("RULER_CONFIDENCE_THRESHOLD", "0.4"))

# Taille maximale acceptée pour une image envoyée en multipart (alignée sur le back),
# et nombre de pixels maximal une fois décodée (≈ 4× une photo mobile de 12 MP) :
# borne la mémoire quelle que soit la compression du fichier reçu.
MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000


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
