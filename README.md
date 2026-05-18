# dacty data repository

Dacty data service.

## Setup

```bash
uv sync
```

## Run

```bash
uv run uvicorn src.main:app --reload
```

Without auto-reload:

```bash
uv run uvicorn src.main:app
```

## Lint

```bash
uv run ruff check .
```

## Conventions

- Commits: use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Branching: use trunk-based development with short-lived branches and frequent merges to `main`
