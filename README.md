# dacty data repository

Dacty data service.

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
curl -X POST "http://localhost:8000/compare?top=10&threshold=40" \
  -F "trace=@trace.png" \
  -F "reference_prints=@reference1.png" \
  -F "reference_prints=@reference2.png"
# -> {"results": [{"reference_print": "reference1.png", "score": 84.32, "match": true}, ...]}
```

`threshold` (query param, default `40`) controls the score above which `match` is `true`. `top` (query param, default `20`) caps how many candidates are returned.

SourceAFIS is a Java library; this service embeds the JVM in-process via [JPype](https://github.com/jpype-project/jpype) and loads the SourceAFIS jars built from `java/sourceafis/pom.xml`. **This is wired up to run via Docker only**: the image's build stage compiles/fetches the jars with Maven, and the runtime stage installs a JDK for JPype. Running `/compare` outside Docker requires a JDK installed locally (e.g. `brew install openjdk` on macOS, matching your CPU architecture) and the jars built manually with `mvn -f java/sourceafis dependency:copy-dependencies`.

## Conventions

- Commits: use Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Branching: use trunk-based development with short-lived branches and frequent merges to `main`
