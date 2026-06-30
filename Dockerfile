# Stage 1 : récupère le jar SourceAFIS + ses dépendances transitives via Maven
FROM maven:3.9-eclipse-temurin-17 AS java-builder

WORKDIR /build

COPY java/sourceafis/pom.xml ./
RUN mvn -B dependency:copy-dependencies -DoutputDirectory=jars

# Stage 2 : image runtime Python (cf. .python-version)
FROM ghcr.io/astral-sh/uv:python3.9-bookworm-slim

WORKDIR /app

# Copie en mode "copy" pour éviter les soucis de hardlink entre volumes
ENV UV_LINK_MODE=copy

# JDK headless requis par JPype (libjvm.so) pour embarquer la JVM de SourceAFIS ;
# build-essential + ant requis pour compiler jpype1 (pas de wheel précompilée disponible ici)
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless build-essential ant \
    && rm -rf /var/lib/apt/lists/*

# Installe les dépendances d'abord pour profiter du cache de couche Docker
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev

# Jars SourceAFIS construits dans le stage Maven (cf. exclusion /app/build dans compose.yaml)
COPY --from=java-builder /build/jars /app/build/jars

# Copie le code source
COPY . .

EXPOSE 8000

# Démarre l'API (hot-reload) ; la commande est aussi surchargée dans compose.yaml
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
