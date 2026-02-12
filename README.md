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
| **E1** | ✅ Complet | 5 sources (TMDB, RT, Kaggle, IMDB, Spark), PostgreSQL + pgvector |
| **E2** | ✅ Complet | Veille, benchmark, paramétrage Qwen2.5-7B-Instruct via llama.cpp |
| **E3** | ⚠️ Partiel | API REST, monitoring, MLOps — code complet, rédactionnel en cours |
| **E4** | 📅 Planifié | Frontend Vue.js/Next.js |
| **E5** | 📅 Planifié | Monitoring applicatif |

### Caractéristiques implémentées

- ✅ **Pipeline ETL multi-sources** : TMDB API, Rotten Tomatoes (scraping), Kaggle CSV, IMDB SQLite, Apache Spark
- ✅ **Base vectorielle** : PostgreSQL 16 + pgvector pour recherche sémantique
- ✅ **Embeddings** : sentence-transformers (all-MiniLM-L6-v2)
- ✅ **LLM local** : Qwen2.5-7B-Instruct (Q5_K_M) via llama-cpp-python
- ✅ **Intent Classifier** : DeBERTa-v3 zero-shot (routage intelligent des requêtes)
- ✅ **Pipeline RAG** : Retriever pgvector + prompt builder + LLM (Qwen2.5-7B-Instruct)
- ✅ **Chatbot conversationnel** : Endpoints `/chat` + `/chat/stream` SSE, sessions multi-turn, routage par intent
- ✅ **API REST sécurisée** : FastAPI + JWT + rate limiting + CORS
- ✅ **Monitoring** : Prometheus + Grafana (21 métriques, 3 dashboards)
- ✅ **Configuration centralisée** : Pydantic Settings avec validation
- ✅ **Checkpoints** : Reprise automatique après interruption
- ✅ **100% open-source** : Aucun service payant

## 🏗️ Architecture technique

```
┌───────────────────────────────────────────────────────────────────────┐
│                        SOURCES DE DONNÉES                             │
├──────────┬──────────────┬──────────┬──────────────┬──────────────────┤
│ TMDB API │ Rotten Tom.  │  Kaggle  │ IMDB SQLite  │  Apache Spark   │
│  (REST)  │  (Scraping)  │  (CSV)   │   (Joins)    │   (SparkSQL)    │
└────┬─────┴───────┬──────┴─────┬────┴──────┬───────┴────────┬────────┘
     │             │            │           │                │
     └─────────────┴────────────┴─────┬─────┴────────────────┘
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
                   │   API FastAPI  │
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

# Lancer l'API
uv run uvicorn src.api.main:app --reload

# Lancer le frontend (dans un autre terminal)
uv run python -m http.server 8080 --directory src/integration/
# Accès chatbot : http://localhost:8080
```

## 📁 Structure du projet

```text
chatbot-horror-movies/
├── src/
│   ├── __main__.py           # CLI principal
│   ├── settings/             # Configuration Pydantic (package)
│   │   ├── ai.py             # LLMSettings, ClassifierSettings, EmbeddingSettings
│   │   ├── api.py            # APISettings
│   │   └── database.py       # DatabaseSettings
│   ├── etl/
│   │   ├── pipeline.py       # Orchestrateur ETL
│   │   ├── aggregator.py     # Agrégation et validation
│   │   └── extractors/       # Extracteurs par source
│   ├── services/
│   │   ├── llm/              # LLMService (wrapper llama-cpp-python)
│   │   ├── intent/           # IntentClassifier + IntentRouter + prompts
│   │   ├── chat/             # SessionManager (multi-turn)
│   │   ├── rag/              # DocumentRetriever, RAGPromptBuilder, RAGPipeline
│   │   └── embedding/        # EmbeddingService (sentence-transformers)
│   ├── database/
│   │   ├── models.py         # SQLAlchemy + pgvector
│   │   └── repositories/     # Repositories (films, RAG)
│   ├── api/
│   │   ├── main.py           # FastAPI app factory
│   │   ├── routers/          # Endpoints (films, auth, chat)
│   │   ├── schemas.py        # Modèles Pydantic
│   │   └── dependencies/     # JWT auth, rate limiting
│   └── monitoring/
│       ├── metrics.py        # Métriques Prometheus
│       └── middleware.py      # PrometheusMiddleware + /metrics
├── tests/                    # Tests pytest (seuil CI ≥ 50%)
├── docs/                     # Documentation technique
├── docker/                   # Config Prometheus, Grafana, init-db
├── docker-compose.yml        # PostgreSQL + pgvector + monitoring
├── pyproject.toml            # Dépendances et configuration (uv)
├── uv.lock                   # Lock file reproductible
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
| **Sources de données** | 5 (TMDB API, Rotten Tomatoes, Kaggle CSV, IMDB SQLite, Spark) |
| **Fichiers Python** | 149 (~23 500 lignes) |
| **Couverture tests** | ≥ 50% (seuil CI) |
| **Temps extraction** | ~2-3h pour 1950-2025 |

## 🛠️ Stack technique

### Backend

- **Python 3.12** avec typage strict
- **FastAPI** + **Uvicorn** (API REST async)
- **Pydantic 2** pour validation et settings
- **SQLAlchemy 2** ORM
- **PostgreSQL 16** + **pgvector** 0.5

### IA

- **llama-cpp-python** : LLM local (Qwen2.5-7B-Instruct Q5_K_M via GGUF)
- **transformers** : Intent Classifier (DeBERTa-v3 zero-shot)
- **sentence-transformers** : Embeddings (all-MiniLM-L6-v2)

### ETL

- **requests** + **tenacity** (retry) pour TMDB
- **Crawl4AI** + **BeautifulSoup4** pour Rotten Tomatoes
- **pandas** + **polars** pour Kaggle CSV
- **SQLAlchemy** pour IMDB SQLite
- **PySpark** pour Apache Spark

### Monitoring

- **Prometheus** + **Grafana** (3 dashboards : LLM, RAG, API)
- **prometheus_client** (21 métriques)

### Qualité

- **pytest** + **pytest-cov** + **pytest-benchmark**
- **Ruff** (linting + formatting), **Vulture** (dead code)
- **structlog** pour logging JSON

## 🗺️ Roadmap

- [x] Pipeline ETL 5 sources (TMDB, RT, Kaggle, IMDB, Spark)
- [x] Base PostgreSQL + pgvector
- [x] Embeddings sentence-transformers
- [x] API REST FastAPI (JWT, rate limiting, CORS)
- [x] Intégration LLM Qwen2.5-7B-Instruct via llama.cpp
- [x] Intent Classifier DeBERTa-v3 zero-shot
- [x] Monitoring Prometheus/Grafana (3 dashboards)
- [x] CI/CD GitHub Actions (5 jobs)
- [x] Pipeline RAG complet (retriever → prompt → LLM) (E3)
- [x] Endpoints chat + streaming SSE (E3)
- [x] Pipeline MLOps GitHub Actions (6 jobs : validation, évaluation, rapport, livraison) (E3)
- [ ] Frontend Vue.js (E4)
- [ ] Monitoring applicatif avancé (E5)

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE)

## 👤 Auteur

**Serge PFEIFFER**  
Développeur en Intelligence Artificielle (en formation)

- GitHub : [@DahliaNoir71](https://github.com/DahliaNoir71)