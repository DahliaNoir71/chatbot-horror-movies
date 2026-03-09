# Guide des commandes Frontend

> **Toutes les commandes ci-dessous se lancent depuis `src/frontend/`.**
>
> ```bash
> cd src/frontend
> ```

## Prérequis

- **Node.js 22** (LTS) — runtime JavaScript, équivalent de Python 3.12
- **npm** — gestionnaire de paquets, installé avec Node.js (équivalent de `uv`/`pip`)

Vérifier l'installation :

```bash
node --version   # v22.x.x attendu
npm --version    # 10.x.x attendu
```

## Installation des dépendances

```bash
cd src/frontend
npm ci
```

| Commande | Rôle | Équivalent Python |
|----------|------|-------------------|
| `npm ci` | Installe les dépendances exactes depuis `package-lock.json` (reproductible, utilisé en CI) | `uv sync --locked` |
| `npm install` | Installe et met à jour `package-lock.json` si besoin (développement) | `uv sync` |

Le fichier `package-lock.json` est l'équivalent de `uv.lock` : il verrouille les versions exactes de toutes les dépendances.

## Serveur de développement

```bash
cd src/frontend
npm run dev
```

Lance un serveur local sur `http://localhost:5173` avec **hot-reload** (les modifications de code sont appliquées instantanément dans le navigateur sans rechargement manuel).

Équivalent de `uv run uvicorn src.main:app --reload` pour le backend FastAPI.

## Vérification du code

### Linter (ESLint)

```bash
cd src/frontend
npx eslint src/
```

Détecte les erreurs de style et les problèmes potentiels dans le code JavaScript/TypeScript.

Équivalent de `uv run ruff check .`

### Vérification des types (TypeScript)

```bash
cd src/frontend
npx vue-tsc -b --noEmit
```

Vérifie que tous les types TypeScript sont cohérents sans générer de fichiers de sortie.

- `vue-tsc` : version de `tsc` (compilateur TypeScript) adaptée aux fichiers `.vue`
- `-b` : mode build (vérifie tout le projet)
- `--noEmit` : ne génère pas de fichiers JS, vérifie uniquement les types

Équivalent de `uv run mypy src/`

### Formatage (Prettier)

```bash
cd src/frontend
npx prettier --check src/
npx prettier --write src/    # corrige automatiquement
```

Équivalent de `uv run ruff format --check .` / `uv run ruff format .`

## Tests unitaires

### Lancer tous les tests

```bash
cd src/frontend
npx vitest run
```

Exécute tous les fichiers `*.spec.ts` une seule fois et affiche les résultats.

Équivalent de `uv run pytest`

### Mode watch (développement)

```bash
cd src/frontend
npx vitest
```

Relance automatiquement les tests concernés à chaque modification de fichier. Très utile pendant le développement. Quitter avec `q`.

Équivalent de `uv run pytest-watch` (si installé)

### Avec couverture de code

```bash
cd src/frontend
npx vitest run --coverage
```

Génère un rapport de couverture de code.

Équivalent de `uv run pytest --cov=src`

### Lancer un seul fichier de test

```bash
cd src/frontend
npx vitest run src/stores/__tests__/auth.store.spec.ts
```

Équivalent de `uv run pytest tests/test_auth.py`

## Build de production

```bash
cd src/frontend
npm run build
```

Compile le TypeScript, optimise et minifie le code pour la production. Le résultat est dans `src/frontend/dist/`.

Cette commande exécute `vue-tsc -b && vite build` :

1. Vérifie les types TypeScript (si erreur TS, le build échoue)
2. Bundle le code avec Vite (tree-shaking, minification, etc.)

## Tableau de correspondances Python / Node.js

| Besoin | Python / uv | Node.js / npm |
|--------|------------|---------------|
| Installer les dépendances | `uv sync --locked` | `npm ci` |
| Ajouter une dépendance | `uv add <package>` | `npm install <package>` |
| Lock file | `uv.lock` | `package-lock.json` |
| Fichier de config | `pyproject.toml` | `package.json` |
| Lancer les tests | `uv run pytest` | `npx vitest run` |
| Couverture | `uv run pytest --cov` | `npx vitest run --coverage` |
| Linter | `uv run ruff check .` | `npx eslint src/` |
| Formatage | `uv run ruff format .` | `npx prettier --write src/` |
| Type-check | `uv run mypy src/` | `npx vue-tsc -b --noEmit` |
| Serveur dev | `uv run uvicorn ... --reload` | `npm run dev` |
| Build production | `uv run pip install .` | `npm run build` |
| Exécuter un outil local | `uv run <outil>` | `npx <outil>` |

## Pre-commit (hooks automatiques)

Les hooks pre-commit frontend sont configurés dans `.pre-commit-config.yaml`, au même endroit que les hooks Python (ruff, vulture). Ils se déclenchent automatiquement sur `git commit` quand des fichiers `src/frontend/src/` sont modifiés.

| Hook | Ce qu'il fait | Équivalent Python |
|------|--------------|-------------------|
| `frontend-eslint` | Lint + auto-fix des fichiers `.ts`/`.vue` modifiés | `ruff --fix` |
| `frontend-prettier` | Formatage auto des fichiers `.ts`/`.vue`/`.css`/`.json` | `ruff-format` |
| `frontend-typecheck` | Vérification des types TypeScript (projet entier) | `mypy` (via vulture) |

### Commandes manuelles

```bash
# Lancer tous les hooks sur tous les fichiers
pre-commit run --all-files

# Lancer un hook spécifique
pre-commit run frontend-eslint --all-files
pre-commit run frontend-prettier --all-files
pre-commit run frontend-typecheck --all-files
```

### Prérequis

Les hooks frontend nécessitent que `npm ci` ait été exécuté dans `src/frontend/` au préalable (les outils sont dans `node_modules/`).

## CI/CD

Le job `frontend-tests` dans `.github/workflows/ci.yml` exécute automatiquement :

1. `npm ci` — installation des dépendances
2. `npx eslint src/` — linter
3. `npx vue-tsc -b --noEmit` — type-check
4. `npx vitest run` — tests unitaires
5. `npm run build` — build de production

Le pipeline ne passe au vert que si toutes ces étapes réussissent (backend ET frontend).

## Aide-mémoire rapide

```bash
cd src/frontend

# Vérification complète (ce que fait la CI)
npx eslint src/ && npx vue-tsc -b --noEmit && npx vitest run && npm run build

# Développement quotidien
npm run dev              # serveur local
npx vitest               # tests en mode watch

# Avant un commit
npx eslint src/          # linter
npx vitest run           # tests
```
