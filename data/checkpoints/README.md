# Checkpoints ETL

Ce répertoire contient les checkpoints intermédiaires du pipeline ETL.

## Fichiers générés

- `tmdb_discover.json` : Checkpoint découverte films TMDB (par page)
- `tmdb_final.json` : Checkpoint final TMDB (tous les films extraits)
- `wikipedia_scraping.json` : Checkpoint scraping Wikipedia
- `csv_reading.json` : Checkpoint lecture CSV
- `postgres_extraction.json` : Checkpoint extraction PostgreSQL
- `spark_extraction.json` : Checkpoint extraction Spark

## Format

Tous les checkpoints sont au format JSON :

```json
{
  "timestamp": "2025-12-01T10:30:45",
  "data": ["item1", "item2", "item3"]
}
```

## Utilisation

Les checkpoints permettent de reprendre l'extraction en cas d'interruption sans tout recommencer depuis le début.

**Note** : Ces fichiers sont gitignorés (peuvent être volumineux).