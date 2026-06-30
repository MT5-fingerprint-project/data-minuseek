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

## Codegraph (AI agents)

Le projet utilise [codegraph](https://github.com/anthropics/codegraph) comme serveur MCP pour permettre aux agents IA (Claude Code, Antigravity, Cursor…) d'explorer le graphe de dépendances du code (callers, callees, impact analysis…).

La configuration est déjà en place dans [`.mcp.json`](.mcp.json). Pour que ça fonctionne, `codegraph` doit être installé  :

```bash
npm install -g @anthropics/codegraph   # installation globale
```

## Conventions

- Commits: use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Branching: use trunk-based development with short-lived branches and frequent merges to `main`
