import os
from pathlib import Path

APP_NAME = "data-minuseek"
APP_VERSION = "0.1.0"

JARS_DIR = Path(os.environ.get("SOURCEAFIS_JARS_DIR", "/app/build/jars"))
