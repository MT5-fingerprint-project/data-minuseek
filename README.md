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
