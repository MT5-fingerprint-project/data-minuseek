# AGENTS.md

Guide pour les agents IA **et** les humains qui travaillent sur `data-minuseek`.
Service data du projet Minuseek — **Python + FastAPI**, en **DDD / architecture hexagonale** (mêmes principes que le back NestJS).

> Le code applicatif vit dans `src/`. `Dockerfile`, `compose.yaml` et `Makefile` sont à la racine.

## Directives agents (DO / DON'T)

> **Avant de coder, explore le code avec codegraph** (`codegraph_explore`). Préfère les wrappers **`rtk`** aux commandes brutes pour économiser le contexte : `rtk git`, `rtk grep`, `rtk read`, `rtk find`, `rtk diff`, `rtk err uv run ruff check .`.

✅ **À faire**
- Garder `domain/` **pur** : aucun import `fastapi`/`uvicorn`/`pydantic` ; stdlib uniquement.
- Déclarer les ports (`Protocol`) dans `domain/`, les implémenter dans `adapters/` ; le use case dépend du **port**.
- Valider à la frontière HTTP (Pydantic dans `adapters/inbound/`) ; câbler la DI par `Depends`.
- `ruff` propre + **type hints** partout ; snake_case au cœur, alias camelCase à la frontière.
- Lancer le skill **`data-review` avant chaque PR**.
- **Écrire un ADR** (`docs/adr/`, cf. `docs/adr/README.md`) pour toute décision structurante (algo de comparaison, intégration NIST/NBIS, contrat d'API, format de données).

❌ **À ne pas faire**
- Importer `fastapi`/`uvicorn`/`pydantic` dans `domain/` ou `application/`.
- Appeler un adapter outbound directement depuis le router (passer par le use case).
- Mettre un chemin/une URL en dur ; laisser du code de debug.

## Stack

- **Runtime** : Python ≥ 3.9 (`.python-version` = `3.9`, `requires-python = ">=3.9"`) — **Package manager** : [uv](https://docs.astral.sh/uv/) (`uv.lock` committé).
- **Framework** : FastAPI servi par **uvicorn** (`uvicorn[standard]`). Pydantic (transitif via FastAPI, API v2 : `ConfigDict`, `Field`) sert uniquement aux schémas HTTP — **validation à la frontière HTTP uniquement**.
- **Lint** : ruff (groupe de dépendances `dev`). **Conteneurs** : Docker Compose (`docker compose up --build`) avec hot-reload (`--reload`).
- **Tests** : *aucun pour l'instant* (voir la section Tests).

## Démarrage

```bash
uv sync                                       # installe les dépendances (crée .venv)
make dev                                      # build + up Docker, hot-reload, premier plan
# équivalent hors Docker :
# uv run uvicorn src.main:app --reload
```

L'API écoute sur `http://localhost:8000` (port fixé dans `compose.yaml` et le `Dockerfile`). Endpoint de santé : `GET /health` → `{"status": "ok", "service": "data-minuseek", "version": "0.1.0"}`.

## Commandes (Makefile, à la racine)

| Commande | Rôle |
|---|---|
| `make help` | Liste les targets disponibles |
| `make dev` | `docker compose up --build -V` — build + run, hot-reload, premier plan |
| `make run` | `docker compose up --build -d` — build + run en arrière-plan (détaché) |
| `make down` | `docker compose down` — stoppe le service |
| `make logs` | Suit les logs du service (`logs -f`) |
| `make lint` | `docker compose run --rm data uv run ruff check .` — ruff dans le conteneur |

> Le `Makefile` n'a **pas** de target `sync` ni de target de tests. Pour installer hors Docker, utiliser **`uv sync`** ; pour linter hors Docker, **`uv run ruff check .`**.

## Architecture — où va le code

Comme le back, le service suit une **architecture hexagonale (ports & adapters) / DDD**. Chaque *bounded context* est un dossier sous `src/` (aujourd'hui : `comparison/`), découpé en 3 couches :

```
src/comparison/
├── domain/                         # Cœur métier — Python pur, AUCUNE dépendance framework
│   ├── models.py                   # Entités & value objects (dataclasses frozen : ImagePair, ComparisonResult)
│   └── ports.py                    # Ports (Protocol) — driven ports (ex. ComparisonReporter)
├── application/                    # Cas d'usage (orchestration)
│   └── compare_images.py           # CompareImagesUseCase : ne dépend que des ports du domaine
└── adapters/                       # Adaptateurs (le monde extérieur)
    ├── inbound/                    # Driver adapters : http.py = FastAPI router + schémas Pydantic + DI
    └── outbound/                   # Driven adapters : console_reporter.py (implémente ComparisonReporter)
```

`src/main.py` est le point d'entrée : il crée l'app FastAPI, monte le CORS, inclut les routers des contextes (`comparison.adapters.inbound.http`) et expose `/health`.

### Règle de dépendance (non négociable)

```
adapters  →  application  →  domain
                             (ne dépend de rien)
```

- **`domain/` doit rester framework-free** : zéro import de `fastapi`, `uvicorn`, `pydantic`. Si tu ajoutes un de ces imports dans `domain/` (ou `application/`), c'est une erreur d'architecture. Le domaine n'utilise que la stdlib (`dataclasses`, `typing`).
- **Les ports vivent dans `domain/`** (interfaces `Protocol`), **les adapters les implémentent** dans `adapters/`. Le cas d'usage dépend du port, jamais de l'implémentation concrète (inversion de dépendance).
- **FastAPI vit dans `adapters/inbound/`** (driver) ; les intégrations sortantes (console, intégration NIST, file d'attente, stockage…) vivent dans `adapters/outbound/` (driven).
- Décider où placer du code : règle/invariant métier → `domain/` ; orchestration d'un cas d'usage → `application/` ; tout I/O — HTTP, console, intégration externe (ex. NIST) → `adapters/`.

## Conventions

- **Composition / injection** : le câblage port → adapter se fait dans l'adaptateur inbound via `Depends` (FastAPI), pas dans le domaine — voir `get_reporter` / `get_compare_images_use_case` dans `http.py`. C'est le composition root : le reporter est swappable.
- **Le router appelle le use case**, jamais un adapter outbound directement.
- **Validation à la frontière** : schémas Pydantic dans l'adaptateur HTTP (`ComparisonRequest` / `ComparisonResponse`). Le domaine ne porte que ses propres invariants (dataclasses `frozen=True`, immuables).
- **camelCase à la frontière, snake_case au cœur** : les schémas HTTP exposent des alias camelCase (`firstImage`, `secondImage`) pour coller au front ; le domaine et le code Python restent en **snake_case**.
- **Type hints partout** ; docstrings en français (cf. l'existant).
- **Commits** : Conventional Commits (`feat:`, `fix:`, `chore:`…). **Branching** : trunk-based, branches courtes mergées souvent sur `main` (cf. README).
- **Lint** : ruff (`make lint` ou `uv run ruff check .`) doit passer avant de merger.

## Ajouter un cas d'usage / un bounded context (recette)

1. Modéliser dans `domain/models.py` (entité/VO + invariants), garder la couche pure.
2. Si une sortie externe est nécessaire, déclarer un port (`Protocol`) dans `domain/ports.py`.
3. Créer le cas d'usage dans `application/` : il ne dépend que des ports.
4. Implémenter le(s) port(s) dans `adapters/outbound/`.
5. Exposer via un router dans `adapters/inbound/http.py` (+ schémas Pydantic validés, alias camelCase) et câbler la DI (`Depends`).
6. Inclure le router dans `src/main.py` (`app.include_router(...)`).
7. Pour un nouveau contexte, reproduire l'arborescence `src/<context>/{domain,application,adapters/{inbound,outbound}}` avec ses `__init__.py`.



## Points d'attention

- **CORS `*`** : configuration POC (origins, methods, headers tous ouverts), à restreindre avant tout déploiement réel.
- **`uv.lock` doit rester committé** pour des installs reproductibles (Docker `uv sync --frozen --no-dev` + CI).
- **README désynchronisé** : il mentionne `make sync`, qui **n'existe pas** dans le `Makefile`. Utiliser `uv sync`.
- **Port figé à 8000** dans `compose.yaml` et le `Dockerfile` (`--host 0.0.0.0 --port 8000`), pas via variable d'env.

## Agents IA & skills (multi-outils)

L'équipe travaille avec plusieurs agents (Claude Code, OpenAI Codex, Google Antigravity, Cursor…). Le setup est **partagé, committé**, avec une **source de vérité unique** : le dossier `.agents/`.

- **`AGENTS.md`** (ce fichier) — standard ouvert, lu nativement par Codex, Cursor, GitHub Copilot, Windsurf, Aider, Zed… (désormais sous l'égide de la Linux Foundation).
- **`CLAUDE.md`** — une seule ligne `@AGENTS.md` : Claude Code ne lit pas `AGENTS.md` nativement (feature request `anthropics/claude-code#34235`), on l'importe donc.
- **`.agents/skills/`** — **source de vérité des skills** (format `SKILL.md`). Lue nativement par **Codex** (`$REPO_ROOT/.agents/skills`, en remontant du dossier courant à la racine — et Codex **suit les symlinks**). On édite un skill à un seul endroit.
- **`.claude/skills` → `../.agents/skills`** — **symlink committé** : Claude Code ne lit que `.claude/skills`, or `.claude/` est gitignoré. Le lien lui donne les mêmes skills, sans copie ni dérive.
- **`.agents/rules/conventions.md` → `../../AGENTS.md`** — **symlink committé** pour **Google Antigravity**, qui lit `.agents/rules/` (règles toujours actives). Il voit ainsi tout ce fichier.

```bash
# Liens déjà versionnés ; à ne recréer qu'en cas de besoin :
ln -s ../.agents/skills .claude/skills
ln -s ../../AGENTS.md .agents/rules/conventions.md
```

Le `.gitignore` ne partage que ces liens (`.claude/*` ignoré, `!.claude/skills` ré-inclus) ; `settings.local.json` reste privé à chaque dev.

> **Windows** : si les liens apparaissent comme de simples fichiers texte, lancer une fois `git config core.symlinks true` puis re-checkout. ⚠️ `npx skills` (gestionnaire de skills, lockfile `skills-lock.json`) produit un `computedHash` qui diffère entre Windows et Linux (fins de ligne) — c'est attendu, ne pas s'en alarmer.

@RTK.md
