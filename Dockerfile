# Image uv officielle avec Python 3.9 (cf. .python-version)
FROM ghcr.io/astral-sh/uv:python3.9-bookworm-slim

WORKDIR /app

# Copie en mode "copy" pour éviter les soucis de hardlink entre volumes
ENV UV_LINK_MODE=copy

# Installe les dépendances d'abord pour profiter du cache de couche Docker
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev

# Copie le code source
COPY . .

EXPOSE 8000

# Démarre l'API (hot-reload) ; la commande est aussi surchargée dans compose.yaml
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
