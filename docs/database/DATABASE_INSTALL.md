# Installation PostgreSQL + pgvector

## Prérequis
- Docker Desktop installé
- 2GB RAM disponible
- PostgreSQL 16+

## Installation via Docker (recommandée)

```bash
# Pull image pgvector
docker pull pgvector/pgvector:pg16

# Créer volume persistant
docker volume create horrorbot_pgdata

# Lancer container
docker run -d \
  --name horrorbot-postgres \
  -e POSTGRES_DB=horrorbot \
  -e POSTGRES_USER=horrorbot_user \
  -e POSTGRES_PASSWORD=votre_mot_de_passe_securise \
  -p 5432:5432 \
  -v horrorbot_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16
```

## Vérification extension pgvector

```sql
-- Connexion psql
psql -h localhost -U horrorbot_user -d horrorbot

-- Vérifier pgvector
CREATE EXTENSION IF NOT EXISTS vector;
SELECT * FROM pg_extension WHERE extname = 'vector';
```

## Variables environnement (.env)

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=horrorbot
POSTGRES_USER=horrorbot_user
POSTGRES_PASSWORD=votre_mot_de_passe_securise
```

## Schéma créé automatiquement

Le script `import-db` crée automatiquement :
- Table `films` avec 25 colonnes
- Index : `ix_films_year`, `ix_films_tmdb_id`, `ix_films_tomatometer_score`
- Colonne `embedding VECTOR(384)` pour recherche sémantique

## Arrêt/Redémarrage

```bash
# Arrêter
docker stop horrorbot-postgres

# Redémarrer
docker start horrorbot-postgres

# Supprimer (ATTENTION : perte données)
docker rm -f horrorbot-postgres
docker volume rm horrorbot_pgdata
```

## Backup base de données

```bash
# Export
docker exec horrorbot-postgres pg_dump -U horrorbot_user horrorbot > backup.sql

# Import
docker exec -i horrorbot-postgres psql -U horrorbot_user horrorbot < backup.sql
```

## Résolution problèmes

**Port 5432 déjà utilisé** :
```bash
# Changer port dans docker run
-p 5433:5432

# Modifier .env
POSTGRES_PORT=5433
```

**Connexion refusée** :
- Vérifier Docker running : `docker ps`
- Vérifier logs : `docker logs horrorbot-postgres`
- Tester connexion : `docker exec -it horrorbot-postgres psql -U horrorbot_user -d horrorbot`
