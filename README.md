# data-minuseek

Minuseek data service.

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

## Conventions

- Commits: use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Branching: use trunk-based development with short-lived branches and frequent merges to `main`
