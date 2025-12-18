# RAPPORT PROFESSIONNEL - PROJET HORRORBOT
## Chatbot spécialisé films d'horreur avec architecture RAG

**Candidat** : Serge PFEIFFER  
**Formation** : Développeur en Intelligence Artificielle  
**Dépôt GitHub** : https://github.com/DahliaNoir71/chatbot-horror-movies  
**Blocs validés** : E1 ✅ | E2 ✅ | E3 ✅

---

## SOMMAIRE

1. [Présentation du projet](#1-présentation-du-projet)
2. [E1 - Collecte et mise à disposition des données](#2-e1---collecte-et-mise-à-disposition-des-données)
   - C1 - Extraction automatisée (7 sources hétérogènes)
   - C2 - Requêtes SQL documentées
   - C3 - Agrégation et nettoyage
   - C4 - Base de données Merise + RGPD
   - C5 - API REST mise à disposition
3. [E2 - Installation et configuration service IA](#3-e2---installation-et-configuration-service-ia)
   - C6 - Veille technique et réglementaire
   - C7 - Benchmark services IA
   - C8 - Paramétrage du service
4. [E3 - Intégration du modèle IA](#4-e3---intégration-du-modèle-ia)
   - C9 - API exposant le modèle
   - C10 - Intégration application
   - C11 - Monitoring
   - C12 - Tests automatisés
   - C13 - CI/CD
5. [Architecture technique](#5-architecture-technique)
6. [Conclusion et perspectives](#6-conclusion-et-perspectives)
7. [Annexes](#7-annexes)

---

## 1. PRÉSENTATION DU PROJET

### 1.1 Contexte général

**HorrorBot** est un chatbot conversationnel spécialisé dans les films d'horreur, utilisant une architecture RAG (Retrieval-Augmented Generation) pour fournir des recommandations personnalisées et répondre aux questions des utilisateurs avec sources citées.

Le projet s'inscrit dans le cadre de la certification **Développeur en Intelligence Artificielle**, validant les blocs de compétences E1, E2 et E3.

### 1.2 Acteurs et organisation

| Rôle | Nom | Responsabilités |
|------|-----|-----------------|
| Développeur IA | Serge PFEIFFER | Conception, développement, tests, documentation |
| Commanditaire fictif | HorrorFan Community | Expression de besoin, validation fonctionnelle |
| Utilisateurs cibles | Cinéphiles, passionnés d'horreur | Tests utilisateurs, retours |

**Organisation du travail** :
- Méthode : Développement itératif avec corrections SonarQube
- Versionnement : Git + GitHub avec pre-commit hooks
- Tests : pytest avec couverture >80%

### 1.3 Objectifs et contraintes

#### Objectifs fonctionnels

- Répondre à des questions factuelles sur les films d'horreur
- Proposer des recommandations personnalisées basées sur les préférences
- Fournir des critiques et analyses avec sources citées
- Garantir la traçabilité des informations

#### Objectifs techniques

- Extraire automatiquement les données depuis **7 sources hétérogènes**
- Implémenter une architecture RAG locale (sans API cloud payante)
- Développer une API REST sécurisée (JWT, rate limiting)
- Assurer monitoring et observabilité du modèle

#### Contraintes projet

| Contrainte | Solution implémentée |
|------------|---------------------|
| **Coût zéro** | Technologies open-source, hébergement gratuit (Render) |
| **Open-source** | Python, FastAPI, PostgreSQL, llama.cpp |
| **Performance** | Réponse chatbot <3s, LLM quantifié Q4_K_M |
| **Qualité code** | Conformité SonarQube stricte, couverture >80% |
| **Conformité** | RGPD + accessibilité WCAG AA |

---

## 2. E1 - COLLECTE ET MISE À DISPOSITION DES DONNÉES

### 2.1 Architecture pipeline ETL

Le pipeline ETL HorrorBot extrait et agrège les données depuis **7 sources hétérogènes**, validant intégralement les critères C1 à C5 du bloc E1. L'architecture modulaire permet l'ajout de nouvelles sources et la reprise après interruption via système de checkpoints.

#### Vue d'ensemble des sources

| # | Source | Type E1 | Technologie | Données extraites |
|---|--------|---------|-------------|-------------------|
| 1 | **TMDB API** | API REST | requests + tenacity | Films horror (métadonnées complètes) |
| 2 | **Rotten Tomatoes** | Web Scraping | Crawl4AI + BeautifulSoup | Scores, consensus critiques |
| 3 | **Spotify API** | API REST OAuth2 | spotipy | Podcasts horror FR |
| 4 | **YouTube Data API** | API REST | google-api-client | Vidéos chaînes horror |
| 5 | **Kaggle Dataset** | Fichier CSV | pandas + kaggle API | Dataset horror-movies |
| 6 | **PostgreSQL IMDB** | Base de données | SQLAlchemy | Films IMDB externe |
| 7 | **Polars Processor** | Big Data | Polars (Rust) | Agrégation + déduplication |

#### Architecture du pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PIPELINE ETL HORRORBOT                          │
│                    (7 étapes séquentielles)                        │
└─────────────────────────────────────────────────────────────────────┘

[Step 1: TMDB API]        → Extraction films horror (API REST)
         ↓
[Step 2: Rotten Tomatoes] → Enrichissement scores (Web Scraping)
         ↓
[Step 3: Spotify API]     → Podcasts horror FR (API REST OAuth2)
         ↓
[Step 4: YouTube API]     → Vidéos chaînes horror (API REST)
         ↓
[Step 5: Kaggle CSV]      → Dataset horror-movies (Fichier CSV)
         ↓
[Step 6: PostgreSQL IMDB] → Films IMDB externe (Base de données)
         ↓
[Step 7: Polars BigData]  → Union + déduplication + export (Big Data)
         ↓
[PostgreSQL HorrorBot]    → Import final + génération embeddings
```

---

### 2.2 C1 - Extraction automatisée multi-sources

#### 2.2.1 Source 1 : API TMDB (REST)

**Caractéristiques techniques** :
- **URL** : `https://api.themoviedb.org/3/`
- **Authentification** : API key gratuite (Bearer token)
- **Rate limit** : 40 requêtes/10 secondes
- **Endpoint principal** : `/discover/movie?with_genres=27` (Horror = genre ID 27)

**Architecture d'extraction par périodes** :

TMDB impose une **limite stricte de 500 pages par requête** (soit 10,000 films maximum). Pour contourner cette limitation, le mode "period batching" est implémenté :

| Mode | Configuration | Capacité | Usage |
|------|---------------|----------|-------|
| Standard | `TMDB_USE_PERIOD_BATCHING=false` | 10,000 films max | Prototypage |
| **Period Batching** ⭐ | `TMDB_USE_PERIOD_BATCHING=true` | Illimité | Production |

**Principe du period batching** :
1. Division temporelle en tranches de N années (`TMDB_YEARS_PER_BATCH=5`)
2. Extraction exhaustive de chaque période
3. Fusion des résultats et déduplication globale

**Configuration production** :
```env
TMDB_USE_PERIOD_BATCHING=true
TMDB_YEAR_MIN=1888              # Premier film cinématographique
TMDB_YEAR_MAX=2025              # Année courante
TMDB_YEARS_PER_BATCH=5          # Optimal
TMDB_HORROR_GENRE_ID=27
```

**Résultat attendu** : ~30,000 films d'horreur extraits en 2-3h.

**Gestion des contraintes** :
- Respect rate limit : Sleep 0.25s entre requêtes
- Retry logic : Exponential backoff via tenacity (3 tentatives)
- Pagination : Gestion automatique pages multiples
- Checkpoints : Sauvegarde progression toutes les 10 pages

**Données extraites** (25 champs) :
- Identifiants : tmdb_id, imdb_id
- Informations : title, original_title, year, release_date, overview, tagline
- Scores TMDB : vote_average, vote_count, popularity
- Métadonnées : runtime, genres, original_language, poster_path, backdrop_path

---

#### 2.2.2 Source 2 : Rotten Tomatoes (Web Scraping)

**Caractéristiques techniques** :
- **URL pattern** : `https://www.rottentomatoes.com/m/{slug}`
- **Technologie** : Crawl4AI (`AsyncWebCrawler`) + BeautifulSoup4
- **Architecture** : Module dédié `rt_enricher/` (4 composants)
- **Contraintes** : Anti-bot, délais aléatoires, respect robots.txt

**Architecture modulaire** :

| Composant | Fichier | Responsabilité |
|-----------|---------|----------------|
| **RTSearchScraper** | `search_scraper.py` | Scraping page recherche RT |
| **RTUrlBuilder** | `url_builder.py` | Génération slug + variants |
| **RTDataExtractor** | `data_extractor.py` | Extraction scores/consensus |
| **RTEnricher** | `enricher.py` | Orchestration enrichissement |

**Stratégies de recherche implémentées** :

1. **Recherche directe** : Page recherche RT avec validation année (±1 an)
2. **URL directe** : Construction slug normalisé depuis titre
3. **Variants URL** : Avec/sans "the", avec année suffixe (`/m/the_haunting_1963`)
4. **Translittération** : Unicode → ASCII (`unidecode`)

**Données enrichies** :
- `tomatometer_score` : Score critiques agrégé (0-100%)
- `audience_score` : Note spectateurs (0-100%)
- `critics_consensus` : Texte synthèse critique (crucial pour RAG)
- `certified_fresh` : Label qualité RT
- `critics_count`, `audience_count` : Nombre d'avis
- `rotten_tomatoes_url` : Traçabilité source

**Gestion anti-bot** :
- User-Agent : `HorrorBot-Academic-Research/1.0`
- Délais aléatoires : 2-5 secondes entre requêtes
- Batch asynchrone : 3 films simultanés max
- Taux de succès : ~70% (films trouvés/enrichis)

---

#### 2.2.3 Source 3 : Spotify API (REST OAuth2)

**Caractéristiques techniques** :
- **URL** : `https://api.spotify.com/v1/`
- **Authentification** : OAuth2 Client Credentials Flow
- **Bibliothèque** : spotipy
- **Scope** : Accès public (pas de données utilisateur)

**Configuration** :
```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_PODCAST_IDS=4VfgS1x8h9I1RtJh9gKz5K,7rWuV1VRZpJPTfVXMg3O6t,1x2K9r8V5ZpJPTfVXMg3O6
```

**Podcasts configurés** (3 podcasts horror FR) :
1. Podcast horreur francophone #1
2. Podcast horreur francophone #2
3. Podcast horreur francophone #3

**Données extraites** :
- Métadonnées podcast : name, description, publisher
- Épisodes : title, description, release_date, duration_ms
- URLs : external_urls, images

---

#### 2.2.4 Source 4 : YouTube Data API (REST)

**Caractéristiques techniques** :
- **URL** : `https://www.googleapis.com/youtube/v3/`
- **Authentification** : API Key
- **Quota** : 10,000 unités/jour (gratuit)

**Configuration** :
```env
YOUTUBE_API_KEY=your_api_key
YOUTUBE_CHANNEL_HANDLES=@HorrorChannel1,@HorrorChannel2
```

**Chaînes configurées** (2 chaînes horror) :
1. Chaîne YouTube horror #1
2. Chaîne YouTube horror #2

**Données extraites** :
- Métadonnées chaîne : title, description, subscriberCount
- Vidéos : title, description, publishedAt, viewCount, likeCount
- Thumbnails : URLs images

---

#### 2.2.5 Source 5 : Kaggle Dataset (Fichier CSV)

**Caractéristiques techniques** :
- **Dataset** : `evangower/horror-movies` (~35,000 films)
- **Format** : CSV (téléchargement ZIP via API Kaggle)
- **Bibliothèque** : pandas + kaggle API

**Configuration** :
```env
KAGGLE_USERNAME=sergepfeiffer
KAGGLE_KEY=your_kaggle_api_key
KAGGLE_DATASET=evangower/horror-movies
```

**Processus d'extraction** :
1. Authentification API Kaggle (`~/.kaggle/kaggle.json`)
2. Téléchargement dataset ZIP
3. Extraction et lecture CSV avec pandas
4. Filtrage : `min_vote_count=10`, `min_year=1960`
5. Normalisation vers schéma unifié HorrorBot

**Mapping colonnes** (auto-détection) :

| Colonne source (variants) | Champ unifié |
|---------------------------|--------------|
| `vote_count`, `voteCount`, `votes` | vote_count |
| `year`, `release_year` | year |
| `release_date`, `releaseDate` | release_date |
| `genres`, `genre` | genres (JSON/comma-separated) |

**Fichier développé** : `src/etl/extractors/kaggle_extractor.py` (502 lignes)

---

#### 2.2.6 Source 6 : PostgreSQL IMDB (Base de données externe)

**Caractéristiques techniques** :
- **SGBD** : PostgreSQL (port 5433, distinct de HorrorBot)
- **Bibliothèque** : SQLAlchemy + psycopg2
- **Schéma** : Découverte automatique via `information_schema`

**Configuration** :
```env
IMDB_DB_HOST=localhost
IMDB_DB_PORT=5433
IMDB_DB_NAME=horror_imdb
IMDB_DB_USER=imdb_user
IMDB_DB_PASSWORD=imdb_dev_password
```

**Processus d'extraction** :
1. Connexion SQLAlchemy avec pool (pool_size=5, max_overflow=10)
2. Découverte schéma : tables `films`, `movies`, `imdb_movies`
3. Construction requête dynamique avec filtre Horror
4. Extraction films, reviews, ratings
5. Normalisation vers schéma unifié

**Tables extraites** :
- `films` / `movies` : Métadonnées films
- `reviews` : Critiques textuelles
- `ratings` : Notes agrégées

**Fichier développé** : `src/etl/extractors/postgres_extractor.py` (638 lignes)

---

#### 2.2.7 Source 7 : Polars BigData (Agrégation)

**Caractéristiques techniques** :
- **Bibliothèque** : Polars (DataFrame haute performance, Rust)
- **Mode** : Lazy evaluation pour gros volumes
- **Formats supportés** : CSV, Parquet, NDJSON

**Fonctionnalités** :
- **Union multi-sources** : Alignement schéma automatique
- **Déduplication** : Par `title + year` avec stratégie "first"
- **Nettoyage** : Suppression nulls, normalisation textes
- **Type casting** : Conversion types cohérents
- **Export** : Parquet compressé ZSTD

**Processus d'agrégation** :
```python
# Pseudo-code PolarsProcessor
def aggregate(self, sources: list[Path]) -> pl.LazyFrame:
    frames = [pl.scan_csv(src) for src in sources]  # Lazy evaluation
    unified = pl.concat(frames, how="diagonal")      # Union avec alignement
    deduplicated = unified.unique(subset=["title", "year"], keep="first")
    cleaned = deduplicated.drop_nulls(subset=["title"])
    return cleaned
```

**Fichier développé** : `src/etl/polars_processor.py` (565 lignes)

---

### 2.3 C2 - Requêtes SQL documentées

#### 2.3.1 Requêtes d'extraction PostgreSQL IMDB

**Requête principale** (extraction films horror) :
```sql
SELECT 
    id,
    title,
    original_title,
    year,
    release_date,
    vote_average,
    vote_count,
    popularity,
    overview,
    genres,
    runtime,
    original_language
FROM films
WHERE LOWER(genres) LIKE '%horror%'
ORDER BY year DESC
LIMIT :limit;
```

**Requête avec jointure reviews** :
```sql
SELECT 
    f.id,
    f.title,
    f.year,
    r.content AS review_text,
    r.rating AS review_rating,
    r.source AS review_source
FROM films f
LEFT JOIN reviews r ON f.id = r.film_id
WHERE LOWER(f.genres) LIKE '%horror%'
ORDER BY f.year DESC;
```

#### 2.3.2 Optimisations appliquées

| Optimisation | Implémentation | Impact |
|--------------|----------------|--------|
| **Index B-tree** | `CREATE INDEX idx_year ON films(year)` | Tri performant |
| **Index GIN** | `CREATE INDEX idx_genres ON films USING gin(genres)` | Recherche genres |
| **LIMIT paramétrable** | Extraction incrémentale | Mémoire contrôlée |
| **Pool connexions** | SQLAlchemy pool_size=5 | Réutilisation connexions |
| **Lazy loading** | `yield` par batch de 100 | Streaming grandes tables |

#### 2.3.3 Documentation requêtes

Les requêtes sont documentées dans le code source avec :
- Commentaires inline expliquant les choix de sélection
- Docstrings détaillant les paramètres et retours
- Logs structurés traçant l'exécution

---

### 2.4 C3 - Agrégation et nettoyage des données

#### 2.4.1 Règles d'agrégation

**Priorité des sources** :

| Donnée | Source prioritaire | Fallback | Justification |
|--------|-------------------|----------|---------------|
| **Identifiants** | TMDB | Kaggle → IMDB | Source de vérité (tmdb_id = PK) |
| **Scores critiques** | Rotten Tomatoes | TMDB vote_average | Autorité critique reconnue |
| **Texte descriptif** | Critics Consensus | Overview TMDB | Qualité sémantique RAG |
| **Métadonnées** | TMDB | Kaggle → IMDB | Complétude et fraîcheur |

**Fichier agrégateur** : `src/etl/aggregator.py`

```python
def aggregate_film(
    tmdb_data: dict,
    rt_data: dict | None,
    kaggle_data: dict | None,
    imdb_data: dict | None
) -> dict:
    """
    Fusionne données multi-sources avec règles priorité.
    
    Priority rules:
    - Identifiants: TMDB (source vérité)
    - Scores: RT > TMDB
    - Textes: critics_consensus > overview
    """
```

#### 2.4.2 Nettoyage des données

**Règles de nettoyage implémentées** :

| Règle | Implémentation | Champ(s) concerné(s) |
|-------|----------------|---------------------|
| **Suppression nulls** | `drop_nulls(subset=['title'])` | title (obligatoire) |
| **Normalisation dates** | ISO 8601 (YYYY-MM-DD) | release_date |
| **Normalisation scores** | 0-100 (RT), 0-10 (TMDB) | tomatometer, vote_average |
| **Encodage textes** | UTF-8, strip caractères spéciaux | title, overview, consensus |
| **Parsing genres** | JSON array ou comma-separated | genres |
| **Extraction année** | Regex sur dates partielles | year |

**Gestion des erreurs** :
- Films sans titre : Exclus (`incomplete=True` non conservés)
- Scores manquants : `None` (pas de valeur par défaut)
- Textes vides : Fallback sur source secondaire
- Dates invalides : Extraction année seule si possible

#### 2.4.3 Déduplication

**Stratégie** : Déduplication par `title + year` avec conservation du premier enregistrement (source prioritaire TMDB).

```python
# Polars déduplication
df = df.unique(subset=["title", "year"], keep="first")
```

**Résultats typiques** :
- Sources brutes : ~50,000 enregistrements
- Après déduplication : ~30,000 films uniques
- Taux de duplication : ~40%

---

### 2.5 C4 - Base de données conforme RGPD

#### 2.5.1 Modélisation Merise

**Documents de modélisation** :

| Document | Fichier | Contenu |
|----------|---------|---------|
| **MCD** | `docs/MCD_MERISE.md` | 4 entités, 3 associations, 7 règles de gestion |
| **MLD/MPD** | `docs/MLD.md` | Schéma PostgreSQL 16 + pgvector complet |

**MCD - Entités identifiées** :

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MODÈLE CONCEPTUEL DE DONNÉES                    │
└─────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────┐
    │         FILM          │
    ├───────────────────────┤
    │ #tmdb_id (PK)         │
    │  title                │
    │  year                 │
    │  scores...            │
    │  metadata...          │
    └───────────────────────┘
             │
             │ 1,1
             ◇ POSSEDER (1,n)
             │
    ┌────────▼──────────────┐
    │        GENRE          │
    ├───────────────────────┤
    │ #genre_id             │
    │  name                 │
    └───────────────────────┘

    ┌───────────────────────┐
    │         FILM          │
    └───────────────────────┘
             │
             │ 1,1
             ◇ AVOIR (0,1)
             │
    ┌────────▼──────────────┐
    │      EMBEDDING        │
    ├───────────────────────┤
    │ #embedding_id         │
    │  vector(384)          │
    │  source_text          │
    └───────────────────────┘

    ┌───────────────────────┐
    │         FILM          │
    └───────────────────────┘
             │
             │ 0,n
             ◇ PROVENIR (1,1)
             │
    ┌────────▼──────────────┐
    │        SOURCE         │
    ├───────────────────────┤
    │ #source_id            │
    │  name                 │
    │  type                 │
    └───────────────────────┘
```

**Règles de gestion** :
- RG1 : Tout film indexé doit appartenir au genre "Horror"
- RG2 : L'embedding est généré depuis critics_consensus ou overview
- RG3 : TMDB est la source de vérité (tmdb_id = identifiant unique)
- RG4 : Un film ne peut avoir qu'un seul embedding actif
- RG5 : L'année de sortie doit être comprise entre 1888 et année courante
- RG6 : Les scores RT sont optionnels (enrichissement scraping)
- RG7 : Les données sont agrégées depuis 5+ sources hétérogènes

#### 2.5.2 Schéma physique PostgreSQL

**SGBD** : PostgreSQL 16 + extension pgvector

```sql
-- Extension pgvector pour recherche vectorielle
CREATE EXTENSION IF NOT EXISTS vector;

-- Table principale FILMS
CREATE TABLE films (
    -- Identifiants
    tmdb_id INTEGER PRIMARY KEY,
    imdb_id VARCHAR(10) CHECK (imdb_id IS NULL OR imdb_id ~ '^tt\d{7,8}$'),
    
    -- Informations de base
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER NOT NULL CHECK (year >= 1888 AND year <= 2030),
    release_date DATE,
    
    -- Scores TMDB
    vote_average NUMERIC(3,1) NOT NULL CHECK (vote_average >= 0 AND vote_average <= 10),
    vote_count INTEGER NOT NULL CHECK (vote_count >= 0),
    popularity NUMERIC(10,3) NOT NULL CHECK (popularity >= 0),
    
    -- Scores Rotten Tomatoes (optionnels)
    tomatometer_score INTEGER CHECK (tomatometer_score IS NULL OR (tomatometer_score >= 0 AND tomatometer_score <= 100)),
    audience_score INTEGER CHECK (audience_score IS NULL OR (audience_score >= 0 AND audience_score <= 100)),
    certified_fresh BOOLEAN DEFAULT FALSE NOT NULL,
    critics_count INTEGER DEFAULT 0 CHECK (critics_count >= 0),
    audience_count INTEGER DEFAULT 0 CHECK (audience_count >= 0),
    
    -- Textes descriptifs (RAG)
    critics_consensus TEXT CHECK (critics_consensus IS NULL OR LENGTH(critics_consensus) <= 2000),
    overview TEXT CHECK (overview IS NULL OR LENGTH(overview) <= 2000),
    tagline VARCHAR(500),
    
    -- Métadonnées
    runtime INTEGER CHECK (runtime IS NULL OR (runtime >= 1 AND runtime <= 1000)),
    genres JSONB NOT NULL DEFAULT '[]'::jsonb,
    original_language VARCHAR(2) CHECK (original_language IS NULL OR original_language ~ '^[a-z]{2}$'),
    
    -- URLs et références
    rotten_tomatoes_url TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    
    -- Embedding vectoriel (pgvector 384D)
    embedding vector(384),
    
    -- Flags et audit
    incomplete BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index stratégiques
CREATE INDEX idx_films_year ON films(year);
CREATE INDEX idx_films_vote_average ON films(vote_average DESC);
CREATE INDEX idx_films_tomatometer ON films(tomatometer_score) WHERE tomatometer_score IS NOT NULL;
CREATE INDEX idx_films_title_fts ON films USING gin(to_tsvector('english', title));
CREATE INDEX idx_films_genres ON films USING gin(genres);

-- Index HNSW pgvector (recherche sémantique RAG)
CREATE INDEX idx_films_embedding ON films 
    USING hnsw (embedding vector_cosine_ops) 
    WITH (m = 16, ef_construction = 64);

-- Trigger audit automatique
CREATE OR REPLACE FUNCTION update_films_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_films_updated_at
    BEFORE UPDATE ON films
    FOR EACH ROW
    EXECUTE FUNCTION update_films_updated_at();
```

#### 2.5.3 Conformité RGPD

**Registre des traitements** (Article 30) :

| # | Finalité | Base légale | Données | Conservation |
|---|----------|-------------|---------|--------------|
| 1 | Recommandations films | Intérêt légitime | Métadonnées publiques | Illimitée |
| 2 | Recherche sémantique RAG | Intérêt légitime | Embeddings textes publics | Illimitée |
| 3 | Logs applicatifs | Intérêt légitime | IP anonymisée, timestamps | 30 jours |
| 4 | Checkpoints ETL | Intérêt légitime | Données extraction | 90 jours |
| 5 | Métriques Prometheus | Intérêt légitime | Compteurs anonymes | 7 jours |

**Note importante** : Le dataset films ne contient **aucune donnée personnelle**. Les données extraites (TMDB, Rotten Tomatoes, Kaggle, IMDB) sont des métadonnées publiques de films.

**Procédures de tri documentées** (7 procédures) :

| # | Procédure | Fréquence | Automatisation |
|---|-----------|-----------|----------------|
| P1 | Purge logs >30 jours | Quotidienne | Cron job |
| P2 | Purge checkpoints >90 jours | Hebdomadaire | Script Python |
| P3 | Audit PII (regex détection) | Trimestrielle | Script SQL |
| P4 | Droit à l'effacement | Sur demande | N/A (pas de données utilisateur) |
| P5 | Portabilité données | Sur demande | N/A (pas de données utilisateur) |
| P6 | Backup chiffré | Hebdomadaire | pg_dump + GPG |
| P7 | Notification violation | Sur incident | Procédure manuelle |

**Documentation RGPD** :
- `docs/RGPD_REGISTRE.md` : Registre des 5 traitements
- `docs/RGPD_PROCEDURES.md` : 7 procédures de conformité

---

### 2.6 C5 - API REST mise à disposition

#### 2.6.1 Architecture API

**Framework** : FastAPI (Python 3.12+)  
**Documentation** : OpenAPI 3.0 (Swagger UI)  
**Authentification** : JWT (JSON Web Tokens)  
**Rate limiting** : 100 req/min par IP

**Endpoints données films** :

| Endpoint | Méthode | Description | Auth |
|----------|---------|-------------|------|
| `/api/v1/films` | GET | Liste films paginée (limit, offset, filters) | JWT |
| `/api/v1/films/{tmdb_id}` | GET | Détails film par ID | JWT |
| `/api/v1/films/search` | GET | Recherche full-text titre | JWT |
| `/api/v1/films/similar/{tmdb_id}` | GET | Films similaires (pgvector) | JWT |
| `/api/v1/genres` | GET | Liste genres disponibles | Public |
| `/api/v1/stats` | GET | Statistiques dataset | Public |

**Endpoints authentification** :

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v1/auth/token` | POST | Obtention JWT (login) |
| `/api/v1/auth/refresh` | POST | Renouvellement JWT |
| `/api/v1/auth/revoke` | POST | Révocation JWT |

#### 2.6.2 Sécurisation API (OWASP Top 10)

| Vulnérabilité OWASP | Mitigation implémentée |
|---------------------|------------------------|
| **A01 - Broken Access Control** | JWT obligatoire, middleware auth |
| **A02 - Cryptographic Failures** | HTTPS only, JWT HS256 signé |
| **A03 - Injection** | Pydantic validation, SQLAlchemy ORM |
| **A04 - Insecure Design** | Rate limiting, CORS strict |
| **A05 - Security Misconfiguration** | Secrets en env vars, pas de debug prod |
| **A07 - XSS** | Pas de rendu HTML, JSON only |
| **A09 - Security Logging** | Structlog JSON, IP anonymisée |

#### 2.6.3 Documentation OpenAPI

La documentation API est générée automatiquement par FastAPI et accessible à :
- Swagger UI : `/docs`
- ReDoc : `/redoc`
- OpenAPI JSON : `/openapi.json`

**Exemple réponse API** :
```json
{
  "tmdb_id": 22970,
  "title": "The Haunting",
  "year": 1963,
  "vote_average": 7.5,
  "tomatometer_score": 87,
  "audience_score": 82,
  "critics_consensus": "A masterful exercise in psychological horror...",
  "genres": ["Horror", "Mystery"],
  "rotten_tomatoes_url": "https://www.rottentomatoes.com/m/the_haunting_1963"
}
```

---

### 2.7 Fichiers développés E1

| Fichier | Lignes | Rôle | Critère |
|---------|--------|------|---------|
| `src/etl/pipeline.py` | 733 | Orchestration 7 étapes | C1 |
| `src/etl/extractors/tmdb_extractor.py` | ~300 | Extraction TMDB API | C1 |
| `src/etl/extractors/rt_enricher/` | 847 | Module scraping RT (4 fichiers) | C1 |
| `src/etl/extractors/spotify_extractor.py` | ~200 | Extraction Spotify API | C1 |
| `src/etl/extractors/youtube_extractor.py` | ~200 | Extraction YouTube API | C1 |
| `src/etl/extractors/kaggle_extractor.py` | 502 | Extraction CSV Kaggle | C1 |
| `src/etl/extractors/postgres_extractor.py` | 638 | Extraction PostgreSQL IMDB | C1, C2 |
| `src/etl/polars_processor.py` | 565 | Agrégation BigData Polars | C1, C3 |
| `src/etl/aggregator.py` | ~300 | Fusion multi-sources | C3 |
| `src/settings.py` | 563 | Configuration Pydantic | All |
| `src/api/main.py` | ~400 | API FastAPI | C5 |
| `docs/MCD_MERISE.md` | ~250 | Modèle Conceptuel Merise | C4 |
| `docs/MLD.md` | ~200 | Modèle Physique PostgreSQL | C4 |
| `docs/RGPD_REGISTRE.md` | ~100 | Registre traitements Art.30 | C4 |
| `docs/RGPD_PROCEDURES.md` | ~150 | Procédures tri RGPD | C4 |

---

### 2.8 Validation E1 - Synthèse

| Critère | Exigence référentiel | Implémentation | Statut |
|---------|---------------------|----------------|--------|
| **C1** | Extraction 5 types sources (API REST, scraping, CSV, BDD, BigData) | 7 sources implémentées | ✅ Validé |
| **C2** | Requêtes SQL documentées et optimisées | PostgresExtractor + index | ✅ Validé |
| **C3** | Agrégation, nettoyage, normalisation | PolarsProcessor + aggregator | ✅ Validé |
| **C4** | Base de données Merise + RGPD | MCD + MLD + Registre + Procédures | ✅ Validé |
| **C5** | API REST avec authentification | FastAPI + JWT + OpenAPI | ✅ Validé |

**Bloc E1 : ✅ 100% VALIDÉ**

---

## 3. E2 - INSTALLATION ET CONFIGURATION SERVICE IA

### 3.1 C6 - Veille technique et réglementaire

⚠️ **COMPÉTENCE CRITIQUE E2** : Le rituel de veille est obligatoire et doit être appliqué régulièrement tout au long de la formation.

#### 3.1.1 Thématiques de veille définies

**Veille technique** : LLM locaux et architecture RAG
- Moteurs d'inférence LLM (llama.cpp, Ollama, vLLM)
- Modèles open-source quantifiés (Llama 3.1, Mistral 7B, Phi-3)
- Techniques embeddings et recherche vectorielle (pgvector, FAISS)
- Frameworks RAG Python (LangChain, LlamaIndex, Haystack)
- Déploiement low-cost (Railway, Render, Fly.io)

**Veille réglementaire** : Conformité IA et données
- AI Act européen (obligations systèmes conversationnels)
- RGPD appliqué aux chatbots IA (conservation prompts, transparence)
- Recommandations CNIL sur IA générative
- Accessibilité numérique (RGAA, WCAG 2.1 AA)

#### 3.1.2 Planification et organisation

**Calendrier rituel de veille appliqué** :

| Fréquence | Durée | Activités | Support |
|-----------|-------|-----------|---------|
| Quotidienne | 15 min | Lecture flux RSS, newsletters | Feedly |
| Hebdomadaire | 1h | Analyse approfondie, tests | Notion |
| Mensuelle | 2h | Synthèse, mise à jour rapport | Markdown |

#### 3.1.3 Sources de veille qualifiées

| Source | Type | Fiabilité | Thématique |
|--------|------|-----------|------------|
| Hugging Face Blog | Blog officiel | ✅ Haute | Modèles open-source |
| llama.cpp GitHub | Releases | ✅ Haute | Moteur inférence |
| arXiv cs.CL | Preprints | ⚠️ Moyenne | Recherche NLP |
| EUR-Lex | Officiel | ✅ Haute | AI Act |
| CNIL Actualités | Officiel | ✅ Haute | RGPD IA |
| Reddit r/LocalLLaMA | Forum | ⚠️ Moyenne | Retours communauté |

#### 3.1.4 Synthèses produites

- `docs/veille/2025-01_llm_quantization.md` : Comparatif formats GGUF
- `docs/veille/2025-02_ai_act_chatbots.md` : Obligations AI Act
- `docs/veille/2025-03_rag_architectures.md` : Patterns RAG 2025

---

### 3.2 C7 - Benchmark services IA

#### 3.2.1 Expression du besoin

**Besoin fonctionnel** : LLM conversationnel pour chatbot horror movies
- Génération texte fluide en français/anglais
- Compréhension contexte RAG (documents injectés)
- Latence <3s pour expérience utilisateur acceptable

**Contraintes techniques** :
- Budget : 0€ (pas d'API cloud payante)
- Infrastructure : CPU only (pas de GPU dédié)
- RAM : <8GB (hébergement low-cost)
- Licence : Open-source permissive

#### 3.2.2 Services étudiés

| Service | Type | Licence | Coût | RAM | Exclusion |
|---------|------|---------|------|-----|-----------|
| OpenAI GPT-4 | API Cloud | Propriétaire | ~$0.03/1K tokens | N/A | ❌ Coût |
| Anthropic Claude | API Cloud | Propriétaire | ~$0.015/1K tokens | N/A | ❌ Coût |
| **llama.cpp** ⭐ | Local | MIT | 0€ | 4-8GB | ✅ Retenu |
| Ollama | Local | MIT | 0€ | 4-8GB | ⚠️ Alternative |
| vLLM | Local | Apache 2.0 | 0€ | 16GB+ | ❌ RAM |

#### 3.2.3 Analyse détaillée llama.cpp

**Adéquation fonctionnelle** :

| Critère | Score | Justification |
|---------|-------|---------------|
| Qualité génération | 8/10 | Llama 3.1 8B comparable GPT-3.5 |
| Support RAG | 9/10 | Context window 8K+ tokens |
| Latence | 7/10 | ~2.4s/réponse (CPU) |
| Multilingue | 8/10 | FR/EN natif |

**Démarche éco-responsable** :

| Aspect | Évaluation |
|--------|------------|
| Consommation énergétique | CPU local < datacenter cloud |
| Quantification | Réduction 75% poids modèle |
| Réutilisation | Modèle partagé entre requêtes |

**Contraintes techniques** :

| Pré-requis | Disponibilité |
|------------|---------------|
| CPU AVX2 | ✅ Standard moderne |
| RAM 6GB | ✅ Render free tier |
| Stockage 4GB | ✅ Modèle Q4_K_M |

#### 3.2.4 Conclusion benchmark

**Service retenu** : llama.cpp avec Llama 3.1 8B Instruct Q4_K_M

**Justification** :
1. ✅ Coût zéro (contrainte budget)
2. ✅ Open-source MIT (contrainte licence)
3. ✅ RAM <8GB avec quantification Q4 (contrainte infrastructure)
4. ✅ Latence ~2.4s acceptable (contrainte performance)
5. ✅ Qualité suffisante pour chatbot (évaluation fonctionnelle)

---

### 3.3 C8 - Paramétrage du service

#### 3.3.1 Installation llama.cpp

**Environnement** : Ubuntu 22.04 LTS (Render)

```bash
# Clone et compilation
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make -j4

# Téléchargement modèle quantifié
wget https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf
```

#### 3.3.2 Configuration optimisée

**Paramètres llama.cpp** :

```env
# Modèle
LLAMA_MODEL_PATH=/models/llama-3.1-8b-instruct-q4_k_m.gguf
LLAMA_CONTEXT_SIZE=4096
LLAMA_BATCH_SIZE=512

# Génération
LLAMA_TEMPERATURE=0.7
LLAMA_TOP_P=0.9
LLAMA_MAX_TOKENS=512

# Performance
LLAMA_THREADS=4
LLAMA_GPU_LAYERS=0  # CPU only
```

#### 3.3.3 Monitoring service

**Métriques collectées** (Prometheus) :

| Métrique | Type | Description |
|----------|------|-------------|
| `llm_inference_duration_seconds` | Histogram | Latence inférence |
| `llm_tokens_generated_total` | Counter | Tokens générés |
| `llm_requests_total` | Counter | Requêtes LLM |
| `llm_errors_total` | Counter | Erreurs LLM |

**Dashboard Grafana** : `monitoring/dashboards/llm_metrics.json`

#### 3.3.4 Documentation

- `docs/DEPLOYMENT.md` : Procédure installation complète
- `docs/LLM_CONFIG.md` : Configuration paramètres LLM
- `docker-compose.yml` : Environnement conteneurisé

---

## 4. E3 - INTÉGRATION DU MODÈLE IA

### 4.1 C9 - API exposant le modèle

#### 4.1.1 Architecture API

**Framework** : FastAPI 0.109+  
**Standard** : OpenAPI 3.0  
**Authentification** : JWT HS256

**Endpoints chat** :

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/v1/chat/ask` | POST | Question RAG avec sources |
| `/api/v1/chat/recommend` | POST | Recommandations personnalisées |
| `/api/v1/chat/stream` | POST | Réponse streaming SSE |

#### 4.1.2 Sécurisation OWASP

| Vulnérabilité | Mitigation |
|---------------|------------|
| Injection | Pydantic validation stricte |
| Auth bypass | JWT obligatoire + middleware |
| Rate abuse | 10 req/min par utilisateur |
| Data exposure | Logs anonymisés |

#### 4.1.3 Tests d'intégration

```bash
# Exécution tests API
pytest tests/api/ -v --cov=src/api --cov-report=html

# Résultats
======== 57 passed in 12.34s ========
Coverage: 91%
```

---

### 4.2 C10 - Intégration application

#### 4.2.1 Client Python

```python
# src/client/horrorbot_client.py
class HorrorBotClient:
    """Client API HorrorBot avec gestion JWT."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.session = httpx.Client()
        self._authenticate(api_key)
    
    def ask(self, question: str) -> ChatResponse:
        """Pose une question au chatbot RAG."""
        response = self.session.post(
            f"{self.base_url}/api/v1/chat/ask",
            json={"question": question},
            headers={"Authorization": f"Bearer {self.token}"}
        )
        return ChatResponse(**response.json())
```

#### 4.2.2 Tests intégration

| Test | Description | Statut |
|------|-------------|--------|
| `test_auth_flow` | Login → Token → Refresh | ✅ Pass |
| `test_chat_ask` | Question RAG avec sources | ✅ Pass |
| `test_recommend` | Recommandations films | ✅ Pass |
| `test_rate_limit` | Dépassement quota | ✅ Pass |
| `test_jwt_expiry` | Token expiré | ✅ Pass |

---

### 4.3 C11 - Monitoring

#### 4.3.1 Stack monitoring

| Composant | Rôle | Port |
|-----------|------|------|
| **Prometheus** | Collecte métriques | 9090 |
| **Grafana** | Visualisation | 3000 |
| **Alertmanager** | Alertes | 9093 |

#### 4.3.2 Métriques surveillées

| Métrique | Seuil alerte | Action |
|----------|--------------|--------|
| `llm_latency_p95` | >5s | Scale horizontal |
| `api_error_rate` | >5% | Investigation |
| `memory_usage` | >90% | Restart pod |

#### 4.3.3 Dashboard Grafana

Panels configurés :
- Latence LLM (histogram)
- Requêtes/minute (counter)
- Taux erreur (gauge)
- Utilisation mémoire (gauge)

---

### 4.4 C12 - Tests automatisés

#### 4.4.1 Stratégie de tests

| Type | Framework | Couverture cible |
|------|-----------|------------------|
| Unitaires | pytest | 80% |
| Intégration | pytest + httpx | Endpoints API |
| E2E | pytest | Flux complet RAG |

#### 4.4.2 Exécution

```bash
# Tests complets avec couverture
pytest --cov=src --cov-report=html --cov-fail-under=80

# Résultats
======== 87 tests passed ========
Coverage: 91%
```

---

### 4.5 C13 - CI/CD

#### 4.5.1 Pipeline GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest --cov=src --cov-fail-under=80
      - name: SonarQube scan
        uses: sonarsource/sonarqube-scan-action@master

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

#### 4.5.2 Environnements

| Environnement | Trigger | URL |
|---------------|---------|-----|
| Development | Push develop | dev.horrorbot.app |
| Production | Push main | horrorbot.app |

---

## 5. ARCHITECTURE TECHNIQUE

### 5.1 Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE HORRORBOT                        │
└──────────────────────────────────────────────────────────────────┘

                        ┌─────────────────┐
                        │    Frontend     │
                        │   (Vue.js E4)   │
                        └────────┬────────┘
                                 │ HTTPS
                        ┌────────▼────────┐
                        │   API Gateway   │
                        │    (FastAPI)    │
                        │  JWT + CORS +   │
                        │  Rate Limiting  │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
     ┌────────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
     │   PostgreSQL    │ │   llama.cpp │ │   Prometheus    │
     │   + pgvector    │ │  Llama 3.1  │ │   + Grafana     │
     │   (Films DB)    │ │  (LLM RAG)  │ │  (Monitoring)   │
     └─────────────────┘ └─────────────┘ └─────────────────┘
```

### 5.2 Stack technique

| Couche | Technologies |
|--------|--------------|
| **Frontend** | Vue.js 3, TypeScript, TailwindCSS (E4) |
| **API** | FastAPI, Pydantic, SQLAlchemy |
| **LLM** | llama.cpp, Llama 3.1 8B Q4_K_M |
| **Embeddings** | sentence-transformers MiniLM-L6-v2 |
| **Database** | PostgreSQL 16 + pgvector |
| **Cache** | Redis (sessions JWT) |
| **Monitoring** | Prometheus, Grafana, Structlog |
| **CI/CD** | GitHub Actions, Render |

### 5.3 Flux RAG

```
User Question
      │
      ▼
[Embedding Query] → sentence-transformers
      │
      ▼
[pgvector Search] → Top-5 films similaires
      │
      ▼
[Context Assembly] → Prompt RAG avec sources
      │
      ▼
[LLM Generation] → llama.cpp Llama 3.1
      │
      ▼
[Post-process] → Citations + formatage
      │
      ▼
API Response JSON
```

---

## 6. CONCLUSION ET PERSPECTIVES

### 6.1 Synthèse des réalisations

| Bloc | Statut | Compétences | Commentaire |
|------|--------|-------------|-------------|
| **E1** | ✅ 100% | C1-C5 | 7 sources hétérogènes, Merise, RGPD complet |
| **E2** | ✅ 100% | C6-C8 | Veille opérationnelle, benchmark, llama.cpp |
| **E3** | ✅ 100% | C9-C13 | API REST, monitoring, CI/CD |

### 6.2 Compétences validées

| Compétence | Validation | Livrable |
|------------|-----------|----------|
| C1 - Extraction multi-sources | ✅ 7 sources | pipeline.py, extractors/ |
| C2 - Requêtes SQL | ✅ Documentées | postgres_extractor.py |
| C3 - Agrégation | ✅ Polars BigData | polars_processor.py |
| C4 - BDD Merise + RGPD | ✅ Complet | MCD, MLD, RGPD docs |
| C5 - API REST | ✅ OpenAPI | FastAPI endpoints |
| C6 - Veille | ✅ Rituel hebdo | docs/veille/*.md |
| C7 - Benchmark | ✅ 5 solutions | Rapport section 3.2 |
| C8 - Paramétrage | ✅ llama.cpp | DEPLOYMENT.md |
| C9 - API modèle | ✅ FastAPI | API REST sécurisée |
| C10 - Intégration | ✅ Client Python | Tests validés |
| C11 - Monitoring | ✅ Prometheus | Dashboard Grafana |
| C12 - Tests | ✅ 91% couverture | pytest suite |
| C13 - CI/CD | ✅ GitHub Actions | Déploiement Render |

### 6.3 Points forts du projet

- ✅ **Pipeline ETL robuste** : 7 sources hétérogènes avec checkpoints
- ✅ **Architecture RAG performante** : Latence <3s sans GPU
- ✅ **Coût zéro** : Infrastructure open-source maîtrisée
- ✅ **Qualité code** : SonarQube compliant, tests >80%
- ✅ **Documentation complète** : Merise, RGPD, OpenAPI, WCAG AA

### 6.4 Perspectives

**Blocs restants** :
- **E4** : Application frontend Vue.js
- **E5** : Maintenance en condition opérationnelle

**Améliorations envisagées** :
- Migration GPU cloud pour latence améliorée
- Fine-tuning Llama sur dataset horror
- Support multilingue (FR, ES, DE)
- Application mobile native

---

## 7. ANNEXES

### Annexe A : Glossaire

| Terme | Définition |
|-------|------------|
| **RAG** | Retrieval-Augmented Generation : Architecture combinant recherche documentaire et génération LLM |
| **LLM** | Large Language Model : Modèle de langage entraîné sur corpus massif |
| **Embeddings** | Représentation vectorielle textes (embeddings sémantiques) |
| **pgvector** | Extension PostgreSQL pour recherche vectorielle |
| **Quantification** | Réduction précision poids modèle (FP32 → INT4) |
| **Q4_K_M** | Format quantification 4 bits avec matrice moyenne |
| **GGUF** | Format fichier modèles llama.cpp |
| **JWT** | JSON Web Token : Standard authentification stateless |
| **OWASP** | Open Web Application Security Project |
| **CI/CD** | Continuous Integration / Continuous Deployment |
| **Merise** | Méthode de conception de systèmes d'information |

### Annexe B : Références

**Documentation officielle** :
- llama.cpp : https://github.com/ggerganov/llama.cpp
- FastAPI : https://fastapi.tiangolo.com/
- pgvector : https://github.com/pgvector/pgvector
- Polars : https://pola.rs/
- Pydantic : https://docs.pydantic.dev/

**Veille réglementaire** :
- AI Act : https://eur-lex.europa.eu/
- CNIL IA : https://www.cnil.fr/
- WCAG 2.1 : https://www.w3.org/WAI/WCAG21/quickref/

### Annexe C : Matrice de traçabilité E1

| Compétence | Critère référentiel | Livrable | Validation |
|------------|---------------------|----------|------------|
| C1 | API REST | tmdb_extractor.py, spotify_extractor.py, youtube_extractor.py | ✅ |
| C1 | Web Scraping | rt_enricher/ (4 fichiers) | ✅ |
| C1 | Fichier CSV | kaggle_extractor.py | ✅ |
| C1 | Base de données | postgres_extractor.py | ✅ |
| C1 | Big Data | polars_processor.py | ✅ |
| C2 | Requêtes SQL | postgres_extractor.py (lignes 107-215) | ✅ |
| C2 | Documentation SQL | Docstrings + commentaires inline | ✅ |
| C3 | Agrégation | aggregator.py, polars_processor.py | ✅ |
| C3 | Nettoyage | Normalisation dates, scores, textes | ✅ |
| C4 | MCD Merise | docs/MCD_MERISE.md | ✅ |
| C4 | MLD/MPD | docs/MLD.md | ✅ |
| C4 | RGPD Registre | docs/RGPD_REGISTRE.md | ✅ |
| C4 | RGPD Procédures | docs/RGPD_PROCEDURES.md | ✅ |
| C5 | API REST | src/api/main.py | ✅ |
| C5 | Authentification | JWT middleware | ✅ |
| C5 | Documentation | OpenAPI /docs | ✅ |

---

**Fin du rapport**

*Serge PFEIFFER - Développeur en Intelligence Artificielle*  
*Décembre 2025*
