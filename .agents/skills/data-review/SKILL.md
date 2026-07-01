---
name: data-review
description: "Review du service data Minuseek (paquet pyproject `data-dacty`, Python 3.9, FastAPI + uvicorn, géré par uv, conteneurisé via Docker Compose, architecture hexagonale domain/application/adapters). À lancer avant chaque PR. Déclencher aussi pour toute review de code ou de PR/diff du service data, audit de l'archi hexagonale Python/FastAPI, vérif de la séparation domain/application/adapters et de la pureté du domaine, contrôle des ports/adapters (typing.Protocol) et de l'injection via FastAPI Depends, reproductibilité des comparaisons d'empreintes, validation Pydantic à la frontière HTTP, sécurité des endpoints et des images uploadées, CORS, propreté ruff et type hints. Vérifie le diff contre AGENTS.md et applique un process de review par sévérité (Critical/Warning/Info) avec format de rapport."
---

# Data Review

Skill de **process de review** pour le service data de Minuseek (paquet `data-dacty`, Python ≥ 3.9, FastAPI + uvicorn, packagé/lancé par **uv**, conteneurisé via **Docker Compose**, en **architecture hexagonale** : `domain/` → `application/` → `adapters/`).

> **Source de vérité des conventions = `AGENTS.md`** (attendu à la racine de `data-minuseek`). Ce skill ne ré-énonce PAS les conventions (stack, règle de dépendance, nommage, commandes `make`/`uv`) : il y **pointe** et n'ajoute que ce qui manque : un **process de review**, un **modèle de sévérité**, un **format de rapport**, et les **pièges réels propres au service data**. **Lis `AGENTS.md` d'abord s'il existe.** ⚠️ Au moment d'écrire ce skill, **`AGENTS.md` n'existe pas encore** à la racine de `data-minuseek` — signale-le (💡) : les conventions doivent y vivre, pas être dupliquées ici. En attendant, appuie-toi sur le `README.md` et sur le code réel.

## Quand utiliser

- Demande de review de code, review de PR / diff du service data.
- Audit de l'architecture hexagonale Python/FastAPI, ou après l'ajout d'un nouveau module/contexte sous `src/`.
- Audit de sécurité des endpoints (validation des entrées, images uploadées, CORS).
- Avant un merge sur `main` (le repo suit du trunk-based + Conventional Commits — cf. `README.md`).

## Runbook — à lancer avant chaque PR

Ce skill est le **gate de review maison** du service data (il prime sur toute review générique téléchargée). À exécuter sur le **diff de la PR** (`rtk git diff origin/main...HEAD`) avant d'ouvrir la PR.

1. **Portes CI locales** (bloquantes) :
   - `rtk err uv run ruff check .` (ruff propre) — ou `make lint`
   - _Tests : aucun à ce jour (cf. `AGENTS.md`) — ne pas inventer de commande ; recommander pytest si on en ajoute._
   Si ruff échoue → corriger d'abord.
2. **Passes de review** sur le diff (sections ci-dessous).
3. **Checklist auteur** (ci-dessous) : tout coché ?
4. **Verdict** : conclure par **✅ READY** ou **🔴 NOT READY** + la liste des bloquants.

### Checklist auteur de PR
- [ ] `ruff check .` propre ; type hints présents
- [ ] `domain/` pur (aucun import `fastapi`/`uvicorn`/`pydantic`) ; ports `Protocol` dans `domain/`, impls dans `adapters/`
- [ ] Validation Pydantic à la frontière HTTP ; router → use case (pas d'appel direct à un adapter outbound)
- [ ] Aucun chemin/URL en dur ; reproductibilité des comparaisons préservée
- [ ] Commits `type(scope): description` ; pas de code de debug ; pas de secret
- [ ] Diff < 400 lignes ; description claire + lien ticket ; branche rebasée sur `main`
- [ ] **ADR écrit** si une décision structurante a été prise (`docs/adr/`)

## Cadrage du codebase (à re-vérifier — ne pas figer)

Le code vit sous `src/`. Au moment d'écrire ce skill il existe **un seul module métier**, `src/comparison/`, plus `src/main.py` (app FastAPI nommée `data-dacty` : titre/version `APP_NAME`/`APP_VERSION`, CORS, `include_router`, `/health`). **Vérifie toujours `ls src/` plutôt que de figer ce chiffre.** Les invariants stables ci-dessous sont plus fiables que tout comptage :

- **Découpage hexagonal en 3 couches** : `domain/` (cœur métier pur), `application/` (cas d'usage), `adapters/` — ce dernier scindé en `adapters/inbound/` (driver, ex. `http.py` FastAPI) et `adapters/outbound/` (driven, ex. `console_reporter.py`). ⚠️ La couche extérieure s'appelle **`adapters/`** ici (pas `infrastructure/` comme le backend NestJS) — ne reproche pas l'absence d'un dossier `infrastructure/`.
- **Domaine = Python pur** : `domain/models.py` n'expose que des `@dataclass(frozen=True)` (`ImagePair`, `ComparisonResult`) ; `domain/ports.py` définit les ports comme **`typing.Protocol`** (ex. `ComparisonReporter` avec `report(result) -> None`). Aucun FastAPI/Pydantic/uvicorn/IO ici.
- **Application** : le use case (`CompareImagesUseCase`, dans `application/compare_images.py`) reçoit ses ports par **constructeur** (inversion de dépendance) et ne connaît que le `Protocol`, pas l'implémentation.
- **Composition root = l'adaptateur inbound** : l'injection de dépendances se fait via les `Depends` de FastAPI (`get_reporter`, `get_compare_images_use_case` dans `adapters/inbound/http.py`). Le port concret y est câblé. Pas de conteneur DI tiers.
- **Frontière HTTP** : schémas **Pydantic** (`BaseModel`) en **camelCase via alias** (`Field(alias="firstImage")`, `model_config = ConfigDict(populate_by_name=True)`) côté requête, `serialization_alias` côté réponse — le domaine reste snake_case. Ne reproche pas le mismatch camel/snake : c'est volontaire (coller au front).
- **Pas de base de données, pas de persistance, pas de tests** au moment d'écrire (aucun `pytest` dans `pyproject.toml`, aucun `test_*.py`). N'exige pas une suite de tests « manquante » comme un bug ; propose-la en Info si la logique devient non triviale. Ne valide pas un pattern (repository, ORM, EventBus) qui n'existe pas dans ce service.

> Si de nouveaux modules apparaissent sous `src/`, applique le même cadre : `domain/` pur (dataclasses + `Protocol` ports) → `application/` (use case, ports par constructeur) → `adapters/{inbound,outbound}/` (FastAPI, IO). **Ne code jamais en dur la liste des modules** — énumère-les depuis `src/`.

## Process de review

Travaille **sur le diff** (`git diff`, fichiers de la PR), pas sur des fichiers isolés — pour attraper les effets transverses (ex. une signature de port changée sans mise à jour de ses implémentations/appelants). Si pas de diff fourni, demande le scope (module / PR / commit).

### Étape 1 — Cadrer
Identifier le scope et lister les fichiers changés. Repérer s'ils touchent : `domain/`, `application/`, `adapters/inbound/`, `adapters/outbound/`, `src/main.py`, ou la conf (`pyproject.toml`, `Dockerfile`, `compose.yaml`, `Makefile`).

### Étape 2 — Passes ordonnées
Scanner dans cet ordre de priorité (les vrais bloquants d'abord) :
1. **Correctness / logique** — edge cases non gérés, résultat non déterministe, exceptions non rattrapées aux frontières, signature de port modifiée sans màj des implémentations.
2. **Sécurité** — validation à la frontière, images uploadées, CORS, secrets, exposition de données. Voir « Pièges spécifiques data » ci-dessous.
3. **Architecture / conventions** — règle de dépendance, pureté du domaine, ports/adapters, DI. Vérifier **contre `AGENTS.md`** (ou, en son absence, contre le code et le `README.md`).
4. **Qualité / outillage** — ruff propre, type hints présents, pas de chemins en dur, reproductibilité.

À chaque passe, consulter la section **Pièges spécifiques data**.

### Étape 3 — Classer par sévérité

| Sévérité | Critère | Action |
|---|---|---|
| 🔴 **Critical** | Bloque le merge : faille de sécurité (upload non validé, secret en clair, path traversal), violation de la règle de dépendance (import FastAPI/Pydantic/uvicorn/IO dans `domain/`), résultat de comparaison non reproductible alors que la fiabilité est métier-critique | Corriger avant merge |
| ⚠️ **Warning** | Anti-pattern, dette, écart aux conventions (`AGENTS.md`/code), type hint manquant sur une API publique, gestion d'erreur absente à une frontière | Corriger ou justifier |
| 💡 **Info** | Suggestion, nit, incohérence mineure, test/refacto à envisager | À discuter |

Down-rank les nits stylistiques à faible confiance : un reviewer bruyant est ignoré. Précise en tête ce qui est bloquant vs optionnel.

### Étape 4 — Boucle de validation
Avant de finaliser, relire chaque finding : est-il vérifiable dans le code/diff ? est-il bien classé ? la convention citée existe-t-elle vraiment dans `AGENTS.md` ou le code (pas inventée) ? le nom de classe/port/fonction cité existe-t-il (grep avant d'affirmer) ? Supprimer les affirmations non étayées et tout reproche portant sur une feature absente du service (DB, tests, events).

### Étape 5 — Rapport
Produire le rapport au format défini plus bas. Chaque finding a la forme fixe : **`Fichier:ligne` · sévérité · WHAT (1 phrase) · WHY/impact (1 phrase) · FIX concret**.

## Pièges spécifiques data (checks prioritaires)

- **Pureté du domaine — `domain/` doit rester framework-free et sans IO.** Zéro import de `fastapi`, `pydantic`, `uvicorn`, `starlette`, ni de lecture fichier/réseau/`print`/`open` dans `domain/`. Un tel import est une **violation de la règle de dépendance**. 🔴
- **Cohérence ports ↔ adapters.** Tout `Protocol` de `domain/ports.py` doit avoir au moins une implémentation dans `adapters/outbound/` câblée dans la composition root (`adapters/inbound/http.py`). Si la signature d'un port change (nom, params, type de retour), **toutes** les implémentations ET le use case qui en dépend doivent suivre — sinon rupture silencieuse de contrat (les `Protocol` ne sont pas vérifiés à l'exécution). ⚠️→🔴
- **Validation Pydantic à la frontière HTTP, jamais dans le domaine.** Les `BaseModel` (`ComparisonRequest`/`ComparisonResponse`) vivent dans `adapters/inbound/http.py`. Toute entrée externe doit être contrainte (`min_length`, bornes, types) — un champ accepté trop largement franchit la frontière et atteint le use case. Le domaine ne valide que ses propres invariants (en Python pur). ⚠️
- **Gestion d'erreurs aux frontières.** Une erreur métier ou d'IO (port outbound qui échoue, entrée invalide non couverte par Pydantic) doit être traduite en réponse HTTP explicite (code + message), pas remonter en 500 brut ni avaler l'exception en silence. L'app n'a aucun exception handler global aujourd'hui — vérifie que les nouveaux chemins gèrent leurs échecs. ⚠️
- **Validation des images uploadées (sécurité).** Dès qu'un endpoint reçoit un fichier/`UploadFile` (la comparaison réelle d'empreintes le nécessitera) : valider le **content-type ET le contenu réel** (magic bytes, pas juste l'extension/le nom), borner la **taille**, refuser les chemins/noms dangereux (path traversal via `filename`), et ne jamais écrire l'upload à un emplacement dérivé d'une entrée utilisateur. Aujourd'hui l'API ne manipule que des **noms d'images en `str`** — flague tout passage à un vrai upload sans ces garde-fous. 🔴
- **Reproductibilité des résultats de comparaison.** Un résultat de comparaison d'empreintes doit être **déterministe** pour des entrées identiques : pas de seed aléatoire non fixée, pas d'ordre dépendant d'un dict/set non ordonné, pas d'horodatage/UUID injecté dans le cœur du calcul. ⚠️ ; 🔴 si l'indéterminisme touche une décision métier (score/match présenté à un enquêteur).
- **Pas de chemins ni de constantes d'environnement en dur.** Aucun chemin absolu (`/app/...`, `/Users/...`), URL, port ou origine codés dans le code métier ; passer par configuration/env. Note : le service tourne sur `:8000` (cf. `compose.yaml`/`Dockerfile`) — c'est de la conf, pas du code métier. ⚠️
- **Type hints présents.** Le projet est entièrement typé (dataclasses, `Protocol`, signatures annotées). Toute fonction publique/port ajouté sans annotations de params et de retour est un écart. ⚠️
- **ruff propre.** Le lint passe par `make lint`, qui exécute **ruff dans le conteneur** (`docker compose run --rm data uv run ruff check .`) ; en local hors Docker, l'équivalent est `uv run ruff check .`. Une PR qui introduit des warnings ruff ne doit pas merger. Il n'y a pas de section `[tool.ruff]` dans `pyproject.toml` (config par défaut, `ruff` est une dépendance de groupe `dev`) — vérifie avant de prescrire une règle spécifique. ⚠️

## Incohérences réelles à flaguer (état actuel — re-vérifier)

- **`AGENTS.md` absent.** Aucun `AGENTS.md` à la racine de `data-minuseek` aujourd'hui : les conventions ne vivent que dans le code et le `README.md`. 💡 — créer `AGENTS.md` (stack, règle de dépendance, nommage, commandes) et y centraliser ce que ce skill se contente de pointer.
- **CORS permissif** dans `src/main.py` (`allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`), commenté comme « POC / vertical slice ». Acceptable en POC ; à **restreindre avant prod** (origines explicites). 🔴 si la PR vise un déploiement public, sinon 💡.
- **Logique de comparaison encore factice.** `CompareImagesUseCase.execute` ne fait que **construire un message** (`f"comparaison effectuée entre ..."`) ; aucune analyse d'image réelle. Ne valide pas ce stub comme une « comparaison d'empreintes » fonctionnelle ; ne reproche pas non plus l'absence d'algo si la PR n'a pas pour but de l'ajouter. Quand l'algo arrive : appliquer pleinement les checks reproductibilité + upload ci-dessus.
- **Effet de bord `print` dans l'adaptateur outbound** : `ConsoleComparisonReporter.report` fait `print(result.message, flush=True)` (volontaire, c'est un reporter console). N'est PAS une violation de pureté car c'est dans `adapters/outbound/`, pas dans `domain/`. Ne le confonds pas avec un `print` oublié dans le domaine.
- **Drift README ↔ Makefile.** Le `README.md` est désynchronisé du `Makefile` réel :
  - il mentionne `make sync`, mais le `Makefile` n'expose que `help`, `dev`, `run`, `down`, `logs`, `lint` (**pas de cible `sync`**) ;
  - il présente `make dev`/`make run`/`make lint` comme de simples `uv run ...`, alors que ces cibles passent en réalité par **Docker Compose** (`docker compose -f compose.yaml ...`). 💡 — corriger le `README.md` (ou ajuster le `Makefile`) pour refléter l'exécution conteneurisée.

## Vérification de la règle de dépendance (greps)

La règle (`adapters → application → domain`, domaine framework-free et sans IO) et la liste exacte d'imports interdits devraient être définies **dans `AGENTS.md`** (seule source visée). Ci-dessous **l'outillage exécutable** pour la vérifier (mets-le à jour si la liste évolue là-bas). Cible les vrais dossiers, tolère d'éventuels tests.

```bash
# 1. Domaine framework-free + sans IO : ZÉRO résultat attendu
grep -rnE "fastapi|pydantic|uvicorn|starlette|\bprint\(|\bopen\(" src/comparison/domain

# 2. Application ne dépend pas des adapters ni du framework HTTP : ZÉRO attendu
grep -rnE "adapters|fastapi|pydantic|uvicorn" src/comparison/application

# 3. Chaque Protocol (port) a au moins une implémentation câblée
grep -rn "Protocol" src/comparison/domain/ports.py
grep -rn "class .*Reporter" src/comparison/adapters/outbound

# 4. Chemins en dur dans le code (hors conf Docker/Compose)
grep -rnE "/app/|/Users/|http://|https://" src --include="*.py"
```

> Note : `adapters/` peut légitimement importer `fastapi`/`pydantic` (c'est sa raison d'être) et `application/` peut importer les `Protocol` du `domain/` — ce ne sont pas des violations. Seuls les imports « vers l'extérieur » depuis `domain/`/`application/` le sont.

## Format du rapport

```markdown
# Review — {scope}

**Date** : YYYY-MM-DD · **Commit/PR** : {ref} · **Reviewer** : Agent

## Résumé
| Passe | Résultat |
|---|---|
| Correctness | ✅ / ⚠️ / ❌ |
| Sécurité | ✅ / ⚠️ / ❌ |
| Architecture / conventions | ✅ / ⚠️ / ❌ |
| Qualité / outillage (ruff, typing) | ✅ / ⚠️ / ❌ |

## Findings

### 🔴 Critical
| # | Fichier:ligne | Finding (what) | Impact (why) | Fix proposé |
|---|---|---|---|---|

### ⚠️ Warning
| # | Fichier:ligne | Finding (what) | Impact (why) | Fix proposé |
|---|---|---|---|---|

### 💡 Info
| # | Fichier:ligne | Finding (what) | Impact (why) | Fix proposé |
|---|---|---|---|---|

## Points positifs
- ...

## Prochaines étapes
- ...
```
