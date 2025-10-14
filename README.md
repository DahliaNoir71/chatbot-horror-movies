# 🎬 HorrorBot - Chatbot spécialisé films d'horreur

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Projet de certification **Développeur en Intelligence Artificielle** - Blocs E1 à E5

## 📋 Description

**HorrorBot** est un chatbot thématique dédié aux films d'horreur. Il répond à des questions factuelles, propose des recommandations personnalisées et fournit des anecdotes sourcées sur l'univers du cinéma d'horreur.

### Caractéristiques principales

- ✅ **Base de données exhaustive** : 142 000+ films d'horreur
- ✅ **API REST sécurisée** : Authentification JWT, rate limiting
- ✅ **Pipeline ETL robuste** : 5 sources de données (API, scraping, CSV, PostgreSQL, Spark)
- ✅ **100% open-source** : Aucun service payant
- ✅ **Conformité RGPD** : Registre des traitements, procédures de tri

## 🏗️ Architecture technique

```
┌─────────────────────────────────────────────────────────────┐
│                      SOURCES DE DONNÉES                     │
├───────────┬──────────┬──────────┬──────────┬────────────────┤
│ TMDB API  │ Wikipedia│  CSV     │PostgreSQL│  Apache Spark  │
│  (REST)   │(Scraping)│ (Kaggle) │  (IMDb)  │   (Parquet)    │
└─────┬─────┴─────┬────┴────┬─────┴─────┬────┴────────┬───────┘
      │           │         │           │             │
      └───────────┴─────────┴───────────┴─────────────┘
                            │
                    ┌───────▼────────┐
                    │  ETL PIPELINE  │
                    │ • Extraction   │
                    │ • Agrégation   │
                    │ • Nettoyage    │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  PostgreSQL 16 │
                    │   + pgvector   │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │   API FastAPI  │
                    │  • JWT Auth    │
                    │  • Rate Limit  │
                    │  • OpenAPI     │
                    └───────┬────────┘
                            │
                    ┌───────▼────────┐
                    │  Front Next.js │
                    │  (Bloc E4)     │
                    └────────────────┘
```

## 🚀 Installation rapide

### Prérequis

- **Python 3.12+**
- **PostgreSQL 16**
- **Git**
- **8 GB RAM minimum** (16 GB recommandés pour Spark)

### Étape 1 : Cloner le repository

```bash
git clone https://github.com/DahliaNoir71/chatbot-horror-movies.git
cd chatbot-horror-movies
```

### Étape 2 : Créer l'environnement virtuel

```bash
python3.12 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### Étape 3 : Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Étape 4 : Configuration

```bash
# Copier le template .env
cp .env.example .env

# Éditer .env et remplir les valeurs
nano .env
```

**Variables critiques à configurer** :

```bash
TMDB_API_KEY=votre_cle_api_tmdb        # Obtenir sur https://www.themoviedb.org/settings/api
POSTGRES_PASSWORD=votre_mot_de_passe   # Choisir un mot de passe fort
JWT_SECRET_KEY=votre_secret_jwt        # Générer avec : openssl rand -hex 32
```

### Étape 5 : Créer la base de données PostgreSQL

```bash
# Créer utilisateur et base
sudo -u postgres createuser -P horrorbot_user
sudo -u postgres createdb -O horrorbot_user horrorbot

# Installer extension pgvector
sudo apt install postgresql-16-pgvector  # Ubuntu/Debian
# ou
brew install pgvector  # macOS

# Activer l'extension
psql -h localhost -U horrorbot_user -d horrorbot -c "CREATE EXTENSION vector;"
```

### Étape 6 : Créer le schéma de base de données

```bash
psql -h localhost -U horrorbot_user -d horrorbot -f database/schema.sql
```

### Étape 7 : Lancer le pipeline ETL

```bash
# Extraction des données (durée : ~45 minutes)
python etl/main.py

# Agrégation et nettoyage (durée : ~5 minutes)
python etl/run_aggregation.py

# Import en base de données (durée : ~3 minutes)
python database/import_data.py
```

### Étape 8 : Lancer l'API

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

🎉 **L'API est accessible sur** : http://localhost:8000/docs

## 📚 Documentation

- **[Installation complète](docs/database/installation.md)** : Guide détaillé pas à pas
- **[Documentation API](http://localhost:8000/docs)** : Swagger UI (quand API lancée)
- **[Spécifications ETL](docs/specifications/ETL_extraction_specs.md)** : Détails techniques extraction
- **[Modélisation Merise](docs/database/merise_modeling.md)** : MCD, MLD, MPD
- **[Conformité RGPD](docs/rgpd/registre_traitements.md)** : Registre des traitements

## 🧪 Tests

```bash
# Lancer tous les tests
pytest tests/ -v

# Tests avec couverture
pytest tests/ -v --cov=etl --cov=api --cov-report=html

# Tests d'intégration API
pytest tests/test_api.py -v --integration
```

## 📊 Statistiques du projet

| Métrique | Valeur |
|----------|--------|
| **Films extraits** | 1 489 023 (bruts) → 142 583 (nettoyés) |
| **Sources de données** | 5 (API, scraping, CSV, PostgreSQL, Spark) |
| **Lignes de code Python** | 2 834 lignes |
| **Lignes de code SQL** | 542 lignes |
| **Tests automatisés** | 61 tests, 87% couverture |
| **Endpoints API** | 6 endpoints REST |
| **Temps de développement** | 140 heures (oct-déc 2025) |

## 🛠️ Stack technique

### Backend
- **Langage** : Python 3.12
- **Framework API** : FastAPI 0.104
- **ORM** : SQLAlchemy 2.0
- **Base de données** : PostgreSQL 16 + pgvector
- **Big Data** : Apache Spark 3.5

### ETL
- **Extraction API** : requests, tenacity (retry)
- **Web scraping** : BeautifulSoup4, lxml
- **Fichiers CSV** : pandas
- **Fuzzy matching** : jellyfish (Levenshtein)

### Sécurité
- **Authentification** : JWT (python-jose)
- **Rate limiting** : SlowAPI
- **Validation** : Pydantic 2.4
- **Hashing** : bcrypt (passlib)

### Tests et qualité
- **Tests** : pytest, pytest-cov
- **Linting** : flake8, black, isort
- **Type checking** : mypy

## 📁 Structure du projet

```
chatbot-horror-movies/
├── api/                    # API REST FastAPI
│   ├── routers/            # Endpoints (movies, auth, search)
│   ├── models/             # Schémas Pydantic
│   ├── security/           # JWT, rate limiting
│   └── main.py             # Point d'entrée API
├── etl/                    # Pipeline ETL
│   ├── extractors/         # 5 extracteurs (TMDB, Wikipedia, CSV, PostgreSQL, Spark)
│   ├── main.py             # Orchestrateur ETL
│   ├── aggregator.py       # Agrégation et nettoyage
│   ├── config.py           # Configuration centralisée
│   └── utils.py            # Helpers (logging, retry, checkpoints)
├── database/               # Base de données
│   ├── schema.sql          # DDL PostgreSQL
│   └── import_data.py      # Script d'import
├── data/                   # Données (gitignored)
│   ├── raw/                # CSV bruts
│   ├── processed/          # CSV nettoyés
│   ├── checkpoints/        # JSON intermédiaires
│   └── big_data/           # Parquet Spark
├── docs/                   # Documentation
│   ├── specifications/     # Specs ETL
│   ├── database/           # Merise, installation
│   ├── sql/                # Requêtes SQL documentées
│   ├── api/                # Specs API
│   └── rgpd/               # Registre RGPD
├── tests/                  # Tests automatisés
├── logs/                   # Logs (gitignored)
├── requirements.txt        # Dépendances Python
├── .env.example            # Template variables environnement
└── README.md               # Ce fichier
```

## 🤝 Contribution

Ce projet est développé dans le cadre d'une formation de certification. Les contributions externes ne sont pas acceptées pour le moment.

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE)

## 👤 Auteur

**Serge PFEIFFER**  
Développeur en Intelligence Artificielle (en formation)

- GitHub : [@DahliaNoir71](https://github.com/DahliaNoir71)
- Email : serge.pfeiffer@example.com

## 🙏 Remerciements

- **TMDB** pour l'API gratuite
- **Wikipedia** pour les données CC-BY-SA
- **Kaggle** pour les datasets publics
- **Anthropic** pour Claude (assistance développement)

---

⭐ **Si ce projet vous intéresse, n'hésitez pas à le star sur GitHub !**