# Documentation Script Import PostgreSQL

## Vue d'ensemble

Script `src/database/importer.py` : Import dataset agrégé dans PostgreSQL avec génération embeddings.

## Dépendances

```txt
sqlalchemy>=2.0.0
pgvector>=0.2.0
sentence-transformers>=2.7.0
pydantic>=2.0.0
tqdm
```

## Commande d'exécution

```bash
# Activer virtualenv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Importer dernier checkpoint
python -m src import-db

# Importer checkpoint spécifique
python -m src import-db --checkpoint pipeline_final_20251121_103057
```

## Fonctionnement

### 1. Chargement checkpoint
- Lit JSON depuis `data/checkpoints/`
- Valide format avec Pydantic

### 2. Génération embeddings
- Modèle : `sentence-transformers/all-MiniLM-L6-v2`
- Dimensions : 384
- Champs vectorisés : `critics_consensus` > `overview` (ordre priorité)

### 3. Création schéma
- Table `films` avec 25 colonnes
- Index automatiques : year, tmdb_id, tomatometer_score
- Extension pgvector activée

### 4. Déduplication
- Vérifie existence via `tmdb_id`
- Skip si film déjà présent
- Upsert non implémenté (insert only)

### 5. Insert batch
- Progression affichée avec `tqdm`
- Timestamps `created_at` / `updated_at` automatiques
- Commit après chaque film

## Gestion erreurs

### Checkpoint manquant
```bash
❌ Checkpoint 'xyz' introuvable
💡 Checkpoints disponibles : python -m src list-checkpoints
```

### Connexion DB échouée
```bash
❌ Impossible de se connecter à PostgreSQL
✓ Vérifier Docker : docker ps
✓ Vérifier variables .env : POSTGRES_*
✓ Tester connexion : docker exec -it horrorbot-postgres psql -U horrorbot_user -d horrorbot
```

### Embedding erreur
```bash
❌ Out of memory lors de l'embedding
✓ RAM disponible >2GB requis
✓ Réduire batch size ou utiliser CPU
```

### Colonne embedding NULL
```bash
❌ ERREUR : null value in column "embedding"
✓ Film sans critics_consensus ni overview (film invalide)
✓ Vérifier agrégation en amont
```

## Logs

### Fichier logs
```bash
logs/database.importer.log
```

### Format JSON structuré
```json
{
  "timestamp": "2025-11-21T11:09:06",
  "level": "INFO",
  "message": "✅ 13 films importés"
}
```

## Performances

| Dataset | Temps | Débit |
|---------|-------|-------|
| 13 films | 3s | 4 films/s |
| 100 films | 25s | 4 films/s |
| 1000 films | 4min | 4 films/s |

**Goulot** : Génération embeddings CPU-bound

## Schéma table films

```sql
CREATE TABLE films (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    imdb_id VARCHAR(10),
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    year INTEGER NOT NULL,
    release_date DATE,
    vote_average FLOAT,
    vote_count INTEGER,
    popularity FLOAT,
    tomatometer_score INTEGER,
    audience_score INTEGER,
    certified_fresh BOOLEAN,
    critics_consensus TEXT,
    overview TEXT,
    tagline VARCHAR(500),
    runtime INTEGER,
    original_language VARCHAR(2),
    genres JSON,
    rotten_tomatoes_url TEXT,
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    embedding VECTOR(384),  -- pgvector
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Maintenance

### Réimport complet
```bash
# Supprimer table
docker exec -it horrorbot-postgres psql -U horrorbot_user -d horrorbot -c "DROP TABLE IF EXISTS films CASCADE;"

# Réimporter
python -m src import-db
```

### Vérifier données
```sql
-- Nombre films
SELECT COUNT(*) FROM films;

-- Films avec embeddings
SELECT COUNT(*) FROM films WHERE embedding IS NOT NULL;

-- Films enrichis RT
SELECT COUNT(*) FROM films WHERE tomatometer_score IS NOT NULL;
```
