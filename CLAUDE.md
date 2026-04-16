# CLAUDE.md — HorrorBot Project Rules

> Règles de développement pour HorrorBot. Toute génération de code par Claude doit
> respecter strictement ce document. En cas d'ambiguïté avec un prompt utilisateur,
> ce fichier prévaut sauf instruction contraire explicite.

---

## 1. Architecture

### Deux bases PostgreSQL découplées

- **`horrorbot`** — données relationnelles : `films`, `credits`, `keywords`, `genres`, etc.
- **`horrorbot_vectors`** — embeddings : `rag_documents` avec colonne `embedding vector(384)` (pgvector)
- **Jointure logique entre les deux** : via `tmdb_id`
  — `rag_documents.source_id = films.tmdb_id` (et **non** `films.id`)

### Schéma : pas d'Alembic

- Le schéma est **bootstrappé** au démarrage par les scripts `docker/init-db/*.sql`, exécutés
  dans l'ordre alphabétique par l'image Postgres officielle.
- **Toute évolution de schéma** = **nouveau script SQL idempotent** dans `docker/init-db/`
  (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, etc.).
- Les **scripts de backfill one-shot** (remplissage de données, migrations de contenu) vivent
  dans `scripts/migrations/` à titre historique. Ils ne sont rejoués ni au démarrage ni en CI.

### Stack technique

- **Backend** : FastAPI async, Pydantic v2, SQLAlchemy 2.x async
- **DB** : PostgreSQL + pgvector
- **LLM** : Qwen2.5-7B via `llama-cpp-python` — **intégration directe, pas de LangChain ni LiteLLM**
- **Embeddings** : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims, bilingue FR/EN)
- **Reranker** : `cross-encoder/mmarco-mMiniLMv2`
- **Classifier** : DeBERTa-v3 (zero-shot)
- **Runtime** : Python 3.12+, CPU-only, localhost-only — `docker compose -f docker-compose.yml up -d`
- **Package manager** : uv (groupes `dev`, `ml-api`, `etl`, `ml`)

---

## 2. Contraintes code

### Typage

- Typage complet obligatoire — **pas de `Any` implicite**, **pas de `dict` nu**
- `TypedDict` précis pour structures de données, `Protocol` pour interfaces
- `from __future__ import annotations` autorisé mais non requis

### Complexité & style

- **Max 500 lignes par classe**, **max 20 lignes par méthode**, **max 3 `return` par fonction**
- Complexité cognitive **< 15** (SonarQube Quality Gate strict — zéro code smell)
- `@staticmethod` dès que `self` n'est pas utilisé
- **SOLID + DRY**, injection de dépendances par constructeur (pas de singletons globaux)

### Docstrings & commentaires

- Docstrings **en anglais**, style Google : `Args:`, `Returns:`, `Raises:`
- Commentaires : **le pourquoi, pas le quoi**. Pas de paraphrase du code
- Pas de `TODO` / `FIXME` en production — ouvrir une issue GitHub

### Linting & sécurité

- Pre-commit obligatoire : **Ruff** (lint + format), **Vulture** (dead code, confidence 100),
  **Bandit** (SAST severity ≥ medium), **Gitleaks**, **uv-lock**
- Configuration centralisée dans `pyproject.toml` et `.pre-commit-config.yaml`

### Isolation admin / chatbot

- Utilisateurs admin et chatbot sont des **entités disjointes** :
  tables, sessions, localStorage, cookies — **jamais partagés** entre les deux espaces.

---

## 3. Workflow

### Validation avant commit

```bash
uv run pre-commit run --all-files && uv run pytest
```

Le pre-commit doit passer **sans `--no-verify`**. Si un hook bloque, corriger la cause racine —
jamais contourner.

### Tests

- **Framework** : pytest + pytest-asyncio (mode `auto`) + pytest-cov
- **Couverture minimale** : **50 %** sur la logique métier (`--cov-fail-under=50`)
- **Markers** : `unit`, `integration`, `slow`, `model`
- Par défaut, les tests `model` (dépendances ML lourdes) sont exclus via `-m "not model"`
- Conventions : fichiers `test_*.py`, classes `Test*`, fonctions `test_*`
- **Fixtures injectées par nom** — ne **jamais** préfixer un paramètre de test par `_`
- `pytest.mark.usefixtures` au niveau **classe** uniquement si les méthodes sont `@staticmethod`

---

## 4. Commits (Conventional Commits)

Format : `<type>(<scope>): <description>`

**Types autorisés** :

- `feat` — nouvelle fonctionnalité
- `fix` — correction de bug
- `refactor` — refonte sans changement fonctionnel
- `test` — ajout / modification de tests uniquement
- `docs` — documentation
- `chore` — outillage, deps, CI
- `perf` — amélioration de performance
- `ci` — pipeline CI/CD

**Exemples** :

```text
feat(retrieval): add bilingual title matching FR/EN
fix(rerank): apply score threshold to prevent LLM hallucination
refactor(services): extract popularity scorer from retriever
```

Le **corps** du commit explique le **pourquoi** (contexte, contrainte). Le **quoi** est dans le diff.

---

## 5. Arborescence

```text
src/
├── api/            # Routes FastAPI, dépendances HTTP, schémas I/O
├── database/       # Modèles SQLAlchemy, repositories, connexion (2 engines : horrorbot + horrorbot_vectors)
├── etl/            # Pipelines offline (extractors, loaders, transformers)
├── frontend/       # Assets statiques + TS chatbot/admin
├── integration/    # Clients externes (TMDB, Kaggle, scrapers)
├── monitoring/     # Prometheus, structlog
├── scripts/        # CLI utilitaires (non couverts par les tests)
├── services/       # Logique métier (RAG, retrieval, rerank, LLM)
└── settings/       # Configuration Pydantic Settings

tests/              # Miroir de src/ — api/ database/ etl/ services/ settings/ monitoring/ integration/
├── unit/           # Tests unitaires purs
├── model/          # Tests nécessitant les ML deps (marker `model`)
├── fixtures/       # Fixtures pytest partagées
└── data/           # Datasets de test

docker/init-db/     # Source de vérité du schéma SQL (idempotent, rejoué at startup)
scripts/migrations/ # Scripts one-shot archivés (backfills historiques, non rejoués)
```

- Code directement dans `src/` (**pas** `src/horrorbot/`) — `[tool.hatch.build.targets.wheel] packages = ["src"]`
- Imports first-party : `from src.<module>` (`known-first-party = ["src"]`)
- **Pas de `src/migrations/`** — Alembic n'est pas utilisé, le schéma vit dans `docker/init-db/`

---

## 6. Style de dialogue avec Claude

- **Concision extrême** — pas de verbosité pédagogique, pas de résumé en fin de réponse
- **Modifications ciblées** (diffs) — jamais de réécriture complète d'un fichier quand un patch suffit
- **Fichier par fichier** — attendre le **GO explicite** de l'utilisateur avant de passer au suivant
- **Une tâche du WORKPLAN à la fois** — ne jamais anticiper plusieurs étapes
- Avant toute correction, **demander les fichiers concernés** si le périmètre est ambigu
- Si un **swap de modèle LLM** est envisagé : **A/B test obligatoire** sur prompts réels
  fournis par l'utilisateur avant migration
