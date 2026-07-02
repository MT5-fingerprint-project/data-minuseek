import os
from pathlib import Path

APP_NAME = "data-minuseek"
APP_VERSION = "0.1.0"

JARS_DIR = Path(os.environ.get("SOURCEAFIS_JARS_DIR", "/app/build/jars"))

# URL du main backend pour récupérer les fichiers d'empreintes
S3_API_URL = os.environ.get("S3_API_URL", "http://app:3000/media")
