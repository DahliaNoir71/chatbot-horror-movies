# 🎬 HorrorBot - Chatbot spécialisé films d'horreur

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Projet de certification **Développeur en Intelligence Artificielle** - Blocs E1 à E5

## 📋 Description

**HorrorBot** est un chatbot conversationnel spécialisé dans les films d'horreur, utilisant une architecture **RAG** (Retrieval-Augmented Generation) pour fournir des recommandations personnalisées et répondre aux questions des utilisateurs avec sources citées.

### État actuel du projet

| Bloc | Statut | Description |
|------|--------|-------------|
| **E1** | ⚠️ Partiel | 2/5 sources (TMDB + Rotten Tomatoes) |
| **E2** | ✅ Complet | Veille, benchmark, paramétrage llama.cpp |
| **E3** | 🚧 En cours | API REST, monitoring, CI/CD |
| **E4** | 📅 Planifié | Frontend Vue.js/Next.js |
| **E5** | 📅 Planifié | Monitoring applicatif |

### Caractéristiques implémentées

- ✅ **Pipeline ETL robuste** : Extraction TMDB + enrichissement Rotten Tomatoes
- ✅ **Base vectorielle** : PostgreSQL 16 + pgvector pour recherche sémantique
- ✅ **Embeddings** : sentence-transformers (all-MiniLM-L6-v2)
- ✅ **Configuration centralisée** : Pydantic Settings avec validation
- ✅ **Checkpoints** : Reprise automatique après interruption
- ✅ **100% open-source** : Aucun service payant

## 🏗️ Architecture technique

```
┌─────────────────────────────────────────────────────────┐
│                   SOURCES DE DONNÉES                     │
├─────────────────────────┬───────────────────────────────┤
│       TMDB API          │      Rotten Tomatoes          │
│        (REST)           │       (Scraping)              │
└───────────┬─────────────┴───────────────┬───────────────┘
            │                             │
            └──────────────┬──────────────┘
                           │
                   ┌───────▼────────┐
                   │  ETL PIPELINE  │
                   │ • Extraction   │
                   │ • Agrégation   │
                   │ • Validation   │
                   └───────┬────────┘
                           │
                   ┌───────▼────────┐
                   │  PostgreSQL 16 │
                   │   + pgvector   │
                   │   + embeddings │
                   └───────┬────────┘
                           │
                   ┌───────▼────────┐
                   │   API FastAPI  │  ← E3 (en cours)
                   │  • JWT Auth    │
                   │  • Rate Limit  │
                   └───────┬────────┘
                           │
                   ┌───────▼────────┐
                   │  Frontend      │  ← E4 (planifié)
                   └────────────────┘
```

## 🚀 Installation rapide

### Prérequis

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (gestionnaire de dépendances)
- **Docker & Docker Compose**
- **Git**

### Étape 1 : Cloner le repository

```bash
git clone https://github.com/DahliaNoir71/chatbot-horror-movies.git
cd chatbot-horror-movies
```

### Étape 2 : Installer uv

```bash
# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Étape 3 : Installer les dépendances

```bash
# Dépendances core + dev (sans ML lourd)
uv sync

# Avec les dépendances ML lourdes (torch CUDA, transformers, etc.)
uv sync --group ml

# Installer les navigateurs Playwright (pour scraping RT)
uv run playwright install
```

### Étape 4 : Configuration

```bash
# Copier le template .env
cp .env.example .env

# Éditer .env avec vos valeurs
```

**Variables obligatoires** :

```env
# TMDB (obtenir sur https://www.themoviedb.org/settings/api)
TMDB_API_KEY=your_api_key_here

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=horrorbot
POSTGRES_USER=horrorbot_user
POSTGRES_PASSWORD=horrorbot_dev_password

# Extraction (optionnel)
TMDB_USE_PERIOD_BATCHING=true
TMDB_YEAR_MIN=1950
TMDB_YEAR_MAX=2025
```

### Étape 5 : Démarrer PostgreSQL

```bash
docker compose up -d

# Vérifier que PostgreSQL est ready
docker compose logs -f postgres
# Attendre "database system is ready to accept connections"
```

### Étape 6 : Lancer le pipeline

```bash
# Pipeline complet : ETL + Import DB
uv run python -m src full

# Ou par étapes :
uv run python -m src etl              # Extraction + enrichissement
uv run python -m src import-db        # Import en base avec embeddings
```

## 📖 Commandes CLI

```bash
# Pipeline ETL complet
uv run python -m src full --max-pages 5

# ETL seul (sans import DB)
uv run python -m src etl --max-pages 5

# Reprendre depuis une étape
uv run python -m src etl --resume-from 2   # 1=TMDB, 2=RT, 3=Agrégation

# Import checkpoint en base
uv run python -m src import-db

# Lister les checkpoints
uv run python -m src list-checkpoints

# Lancer l'API (E3 - en développement)
uv run python -m src api
```

## 📁 Structure du projet

```
chatbot-horror-movies/
├── src/
│   ├── __main__.py           # CLI principal
│   ├── settings.py           # Configuration Pydantic
│   ├── etl/
│   │   ├── pipeline.py       # Orchestrateur ETL
│   │   ├── aggregator.py     # Agrégation et validation
│   │   ├── utils.py          # Logging, checkpoints
│   │   └── extractors/
│   │       ├── base_extractor.py
│   │       ├── tmdb_extractor.py
│   │       └── rotten_tomatoes_enricher.py
│   ├── database/
│   │   ├── models.py         # SQLAlchemy + pgvector
│   │   └── importer.py       # Import avec embeddings
│   └── api/                  # (E3 - en cours)
├── data/
│   ├── checkpoints/          # JSON intermédiaires
│   └── processed/            # Données finales
├── logs/                     # Logs structurés JSON
├── tests/                    # Tests pytest
├── docs/                     # Documentation
├── docker-compose.yml        # PostgreSQL + pgvector
├── pyproject.toml          # Dépendances et configuration (uv)
├── uv.lock                 # Lock file reproductible
├── .env.example
└── README.md
```

## 🧪 Tests

```bash
# Lancer tous les tests
uv run pytest tests/ -v

# Tests avec couverture
uv run pytest tests/ -v --cov=src --cov-report=html
```

## 📊 Statistiques actuelles

| Métrique | Valeur |
|----------|--------|
| **Sources de données** | 2 (TMDB API + Rotten Tomatoes scraping) |
| **Lignes de code Python** | ~2 800 |
| **Couverture tests** | ~91% |
| **Temps extraction** | ~2-3h pour 1950-2025 |

## 🛠️ Stack technique

### Backend
- **Python 3.12** avec typage strict
- **Pydantic 2** pour validation et settings
- **SQLAlchemy 2** ORM
- **PostgreSQL 16** + **pgvector** 0.5

### ETL
- **requests** + **tenacity** (retry) pour TMDB
- **Crawl4AI** + **BeautifulSoup4** pour Rotten Tomatoes
- **sentence-transformers** pour embeddings

### Qualité
- **pytest** + **pytest-cov**
- **Black**, **Ruff**, **SonarQube**
- **structlog** pour logging JSON

## 🗺️ Roadmap

- [x] Pipeline ETL TMDB + Rotten Tomatoes
- [x] Base PostgreSQL + pgvector
- [x] Embeddings sentence-transformers
- [ ] API REST FastAPI (E3)
- [ ] Authentification JWT (E3)
- [ ] Intégration LLM llama.cpp (E3)
- [ ] Frontend Vue.js (E4)
- [ ] Monitoring Prometheus/Grafana (E5)

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE)

## 👤 Auteur

**Serge PFEIFFER**  
Développeur en Intelligence Artificielle (en formation)

- GitHub : [@DahliaNoir71](https://github.com/DahliaNoir71)