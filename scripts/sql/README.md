# Structure SQL - HorrorBot

## Architecture des bases de données

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PROJET HORRORBOT                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐         ┌─────────────────────┐           │
│  │  postgres (5432)    │         │  postgres_letterboxd│           │
│  │  horrorbot          │         │  (5433)             │           │
│  │                     │         │  horror_letterboxd  │           │
│  │  • films            │         │                     │           │
│  │  • youtube_stats    │◄────────┤  • movies           │           │
│  │  • kaggle_movies    │  sync   │  • letterboxd_films │           │
│  │  • genres           │         │                     │           │
│  │  • persons          │         └─────────────────────┘           │
│  │  • pgvector         │                                           │
│  └─────────────────────┘                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Structure des fichiers

```
chatbot-horror-movies/
├── docker-compose.yml              # Orchestration 2 containers
├── scripts/
│   └── sql/
│       ├── main/                   # Base principale (Port 5432)
│       │   ├── 01_init_pgvector.sql
│       │   └── 02_init_schema.sql
│       └── letterboxd/             # Base externe (Port 5433)
│           └── 01_init_schema.sql
└── data/
    └── raw/
        └── horror_movies_kaggle.csv
```

## Tables principales (Port 5432)

| Table | Description | Source |
|-------|-------------|--------|
| `films` | Table centrale agrégée | Toutes |
| `kaggle_movies` | Import CSV Kaggle | Source 3 (C1) |
| `letterboxd_sync` | Sync depuis base externe | Source 4 (C2) |
| `youtube_stats` | Stats YouTube | Source 5 (C2) |
| `genres`, `persons`, `collections` | Référentiels | TMDB |

## Tables base externe (Port 5433)

| Table | Description |
|-------|-------------|
| `movies` | Films importés depuis CSV Kaggle |
| `letterboxd_films` | Films avec données Letterboxd |

## Commandes utiles

### Démarrer les bases

```bash
docker-compose up -d
```

### Vérifier les tables

```bash
# Base principale
docker exec horrorbot_postgres psql -U horrorbot_user -d horrorbot -c "\dt"

# Base Letterboxd
docker exec horrorbot_postgres_letterboxd psql -U letterboxd_user -d horror_letterboxd -c "\dt"
```

### Réinitialiser (ATTENTION: perte de données)

```bash
docker-compose down -v
docker-compose up -d
```

### Vérifier youtube_stats

```bash
docker exec horrorbot_postgres psql -U horrorbot_user -d horrorbot -c "\d youtube_stats"
```

## Colonnes youtube_stats

La table `youtube_stats` est compatible avec `YouTubeSQLExtractor` :

| Colonne | Type | Description |
|---------|------|-------------|
| `tmdb_id` | INTEGER | ID TMDB pour matching |
| `title` | VARCHAR(500) | Titre du film |
| `year` | INTEGER | Année |
| `trailer_views` | BIGINT | Vues du trailer (agrégé) |
| `trailer_likes` | BIGINT | Likes du trailer |
| `video_id` | VARCHAR(20) | ID vidéo YouTube |
| `view_count` | BIGINT | Vues détaillées |

## Connexions

| Base | Host | Port | User | Password | Database |
|------|------|------|------|----------|----------|
| Principale | localhost | 5432 | horrorbot_user | horrorbot_dev_password | horrorbot |
| Letterboxd | localhost | 5433 | letterboxd_user | letterboxd_dev_password | horror_letterboxd |