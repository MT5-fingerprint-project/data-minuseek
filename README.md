# data-minuseek

Service data du projet **Minuseek** — Python + [FastAPI](https://fastapi.tiangolo.com/), organisé en **architecture hexagonale (ports & adapters)** par feature (vertical slicing).

## Architecture

Chaque bounded context est un dossier sous `src/` (ex. `comparison/`), découpé en 3 couches :

```
src/<context>/
├── domain/          # Cœur métier — Python pur, aucune dépendance framework
├── application/     # Cas d'usage (orchestration), ne dépend que des ports
└── adapters/
    ├── inbound/     # Driver adapters (FastAPI router, schémas Pydantic, DI)
    └── outbound/    # Driven adapters (implémentations concrètes des ports)
```

**Règle de dépendance** : `adapters → application → domain` (le domaine ne dépend de rien).

A `Makefile` wraps the most common commands. Run `make help` to list them.

A `Makefile` wraps the most common commands. Run `make help` to list them.

## Setup

```bash
make sync   # or: uv sync
```

## Run

```bash
make dev    # or: uv run uvicorn src.main:app --reload
```

Without auto-reload:

```bash
make run    # or: uv run uvicorn src.main:app
```

## Lint

```bash
make lint   # or: uv run ruff check .
```

## Fingerprint comparison (`POST /compare`)

Compares a trace fingerprint against one or more reference fingerprints using [SourceAFIS](https://github.com/robertvazan/sourceafis-java) (1:N search) and returns the best-scoring candidates, sorted descending.

```bash
curl -X POST "http://localhost:8000/api/compare?top=10&threshold=40" \
  -F "trace=@trace.png" \
  -F "reference_prints=@reference1.png" \
  -F "reference_prints=@reference2.png"
# -> {"results": [{"reference_print": "reference1.png", "score": 84.32, "match": true}, ...]}
```

`threshold` (query param, default `40`) controls the score above which `match` is `true`. `top` (query param, default `20`) caps how many candidates are returned.

SourceAFIS is a Java library; this service embeds the JVM in-process via [JPype](https://github.com/jpype-project/jpype) and loads the SourceAFIS jars built from `java/sourceafis/pom.xml`. **This is wired up to run via Docker only**: the image's build stage compiles/fetches the jars with Maven, and the runtime stage installs a JDK for JPype. Running `/compare` outside Docker requires a JDK installed locally (e.g. `brew install openjdk` on macOS, matching your CPU architecture) and the jars built manually with `mvn -f java/sourceafis dependency:copy-dependencies`.

## Ruler detection (`POST /data/api/detect-ruler`)

Detects whether a **millimetric ruler** is present on a trace photo (spec BIO-38). The back calls it at upload time, on the raw bytes, *before* writing anything; refusing the trace (`422 RULER_NOT_DETECTED`) is the back's decision — data only returns a verdict with the measures that justify it. See [ADR-0001](docs/adr/0001-detect-ruler-contrat-octets-algo-periodicite.md).

```bash
curl -X POST "http://localhost:8000/data/api/detect-ruler" \
  -F "image=@trace.jpg" \
  -F 'roi={"x":0.1,"y":0.72,"width":0.8,"height":0.1}'   # optional: band where the mobile viewfinder asks for the ruler
# -> {"present": true, "confidence": 0.74, "threshold": 0.4,
#     "engine_version": "ruler-periodicity-1.0+cal.0",
#     "details": {"period_px": 18.5, "angle_deg": 3.0, "ticks_count": 98, "coherence": 0.8,
#                 "duty_cycle": 0.23, "hierarchy": 1.0, "found_in_roi": true}}
```

`period_px` is the size of 1 mm in pixels — the input of the DPI calibration (ticket D2). Errors: `400` undecodable image, `413` over 20 MB, `422` invalid `roi`.

The algorithm is classical and deterministic (OpenCV): graduations are equidistant, aligned on a line, thin (low duty cycle) and hierarchical (longer ticks every 5/10 mm) — the last two criteria are what tells a ruler apart from fingerprint ridges. `RULER_CONFIDENCE_THRESHOLD` (default `0.4`, **not yet calibrated on real photos**) can be overridden by env; calibrate with:

```bash
uv run python scripts/evaluate_ruler_detector.py                        # synthetic scenes
uv run python scripts/evaluate_ruler_detector.py --with DIR --without DIR   # real photos, kept out of git
uv run python scripts/generate_sample_photos.py OUT_DIR              # 5+5 synthetic demo photos to try the route by hand
```

## Tests

```bash
make test                                   # pytest inside the container
STORAGE_EMULATOR_HOST=http://localhost:9 uv run pytest   # locally without GCP credentials
```

`src/repositories/image_repository.py` creates a GCS client at import time; `STORAGE_EMULATOR_HOST` makes it use anonymous credentials so the suite runs offline.

Two opt-in suites, off by default (slow, or data kept out of git):

```bash
RULER_FULL_EVAL=1 uv run pytest tests/test_ruler_detector.py -k population        # synthetic population, ~1 min
RULER_REAL_SAMPLES_DIR=~/Desktop/dev/data-minuseek-samples/real uv run pytest tests/test_ruler_detector_real.py -v   # real photos: 100 % expected on with/ and without/
```

## AI agents

### Ce que ça apporte

- **`AGENTS.md`** — conventions du repo (+ section « Directives agents » DO/DON'T) ; **`CLAUDE.md`** = `@AGENTS.md`.
- **`.agents/skills/`** — skills maison versionnés (review pré-PR, etc.), exposés à Claude via le lien symbolique `.claude/skills` et lus nativement par Codex/antigravity.
- **`.agents/rules/`** — règles pour Antigravity (lien symbolique vers `AGENTS.md`).
- **`.mcp.json`** — serveur MCP **codegraph** pour le repo, n'hésitez pas à mettre d'autres mcp utiles.
- **`RTK.md`** — règle d'usage de **rtk** (proxy CLI qui économise les tokens).
- **`docs/adr/`** — gabarit d'ADR : on consigne les décisions structurantes.

### À faire par chaque dev (une fois par poste)

```bash
brew install codegraph rtk        # les 2 binaires requis
rtk init -g                       # hook d'auto-réécriture (économie de tokens) — recommandé mais pas obligatoire
```

- **Claude Code** : approuver le serveur MCP `codegraph` au 1er lancement (prompt automatique sur `.mcp.json`).
- **Codex** : ajouter une fois `[mcp_servers.codegraph]\ncommand = "codegraph"\nargs = ["serve","--mcp"]` dans `~/.codex/config.toml`.
- **Windows uniquement** : si les liens symboliques apparaissent comme des fichiers texte → `git config core.symlinks true` puis re-checkout.

> Au clone, les symlinks et les skills sont restaurés automatiquement : à part les 2 binaires ci-dessus, rien à faire.

### Skills IA (`.agents/skills/`)

Les **skills** sont des instructions spécialisées que l'agent IA charge automatiquement selon le contexte de votre demande. Vous n'avez **rien à activer manuellement** : l'agent détecte les mots-clés dans votre prompt et charge le skill adapté. Vous pouvez aussi les invoquer explicitement en mentionnant leur nom.

| Skill                   | Quand ça se déclenche                                                                             | Exemple de prompt                               |
| ----------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `data-review`           | Review de code / PR / diff data, audit archi hexagonale Python/FastAPI, avant un merge sur `main` | _« Réalise une review complète de ma branche »_ |
| `product-brainstorming` | Brainstorming produit, exploration de problème                                                    | _« brainstorm avec moi sur cette feature »_     |

## Conventions

- Commits: use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Branching: use trunk-based development with short-lived branches and frequent merges to `main`
