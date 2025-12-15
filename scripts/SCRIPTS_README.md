# Scripts Maintenance RGPD

Scripts automatisés conformité RGPD (procédures P1, P2, P6).

## Scripts disponibles

| Script | Procédure | Description |
|--------|-----------|-------------|
| `clean_logs.py` | P1 | Nettoyage logs >30 jours |
| `clean_checkpoints.py` | P2 | Purge checkpoints obsolètes |
| `backup_db.sh` | P6 | Backup PostgreSQL chiffré |

---

## Installation

```bash
# Copier scripts dans projet
mkdir -p scripts
cp clean_*.py scripts/
cp backup_db.sh scripts/
chmod +x scripts/*.py scripts/*.sh

# Installer dépendances Python (déjà présentes)
pip install -r requirements.txt
```

---

## Usage

### 1. Nettoyage logs (P1)

```bash
# Dry-run (aperçu sans suppression)
python scripts/clean_logs.py --days 30 --dry-run

# Suppression effective
python scripts/clean_logs.py --days 30

# Avec archivage logs critiques
python scripts/clean_logs.py --days 30 --archive

# Répertoire logs personnalisé
python scripts/clean_logs.py --days 30 --logs-dir /chemin/logs
```

**Sortie attendue** :
```
11:00:00 | scripts.clean_logs | INFO | clean_logs_started: days=30, dry_run=False
11:00:01 | scripts.clean_logs | INFO | deleted: etl.tmdb.log
11:00:01 | scripts.clean_logs | INFO | archived_critical_log: database.importer.log -> archived.log
11:00:02 | scripts.clean_logs | INFO | clean_logs_completed: deleted=15, size_mb=450.2
```

---

### 2. Purge checkpoints (P2)

```bash
# Garder 5 derniers checkpoints
python scripts/clean_checkpoints.py --keep-last 5

# Supprimer checkpoints >90 jours
python scripts/clean_checkpoints.py --older-than 90

# Combiner les 2 critères
python scripts/clean_checkpoints.py --keep-last 5 --older-than 90

# Dry-run
python scripts/clean_checkpoints.py --keep-last 5 --dry-run

# Répertoire personnalisé
python scripts/clean_checkpoints.py --keep-last 5 --checkpoint-dir /chemin/checkpoints
```

**Sortie attendue** :
```
11:05:00 | scripts.clean_checkpoints | INFO | clean_checkpoints_started: keep_last=5, older_than=None, dry_run=False
11:05:01 | scripts.clean_checkpoints | INFO | deleted: pipeline_final_20251021_103057.json
11:05:01 | scripts.clean_checkpoints | INFO | deleted: tmdb_discover_20251018_141522.json
11:05:02 | scripts.clean_checkpoints | INFO | clean_checkpoints_completed: deleted=12, kept=5, size_mb=2345.6
```

---

### 3. Backup PostgreSQL (P6)

```bash
# Backup standard (gzip uniquement)
./scripts/backup_db.sh

# Backup chiffré GPG (nécessite clé GPG configurée)
GPG_EMAIL="dev@horrorbot.local" ./scripts/backup_db.sh

# Variables personnalisées
POSTGRES_CONTAINER=mon-postgres \
POSTGRES_USER=admin \
POSTGRES_DB=horrorbot_prod \
BACKUP_DIR=/backups \
./scripts/backup_db.sh
```

**Sortie attendue** :
```
[INFO] Début backup PostgreSQL...
[INFO] Backup créé : ./backups/horrorbot_20251121_110000.sql.gz (125M)
[INFO] Chiffrement GPG avec clé : dev@horrorbot.local
[INFO] Backup chiffré : ./backups/horrorbot_20251121_110000.sql.gz.gpg
[INFO] Purge backups >30 jours...
[INFO] Supprimé : horrorbot_20251022_020000.sql.gz.gpg
[INFO] Purge terminée : 8 backups supprimés
[INFO] Statistiques backups :
[INFO]   - Nombre backups : 30
[INFO]   - Espace total : 3.2G
[INFO] ✅ Backup terminé avec succès
```

---

## Automatisation Cron

### Linux/Mac

```bash
# Éditer crontab
crontab -e

# Ajouter les tâches automatisées
# P1 - Nettoyage logs quotidien 02:00
0 2 * * * cd /chemin/projet && /chemin/projet/.venv/bin/python scripts/clean_logs.py --days 30 --archive >> logs/cron.log 2>&1

# P2 - Purge checkpoints hebdomadaire dimanche 03:00
0 3 * * 0 cd /chemin/projet && /chemin/projet/.venv/bin/python scripts/clean_checkpoints.py --keep-last 5 >> logs/cron.log 2>&1

# P6 - Backup PostgreSQL hebdomadaire dimanche 04:00
0 4 * * 0 cd /chemin/projet && /chemin/projet/scripts/backup_db.sh >> logs/cron.log 2>&1
```

### Windows (Planificateur de tâches)

```powershell
# P1 - Logs (quotidien 02:00)
schtasks /create /tn "HorrorBot_Clean_Logs" /tr "C:\projet\.venv\Scripts\python.exe C:\projet\scripts\clean_logs.py --days 30" /sc daily /st 02:00

# P2 - Checkpoints (hebdomadaire dimanche 03:00)
schtasks /create /tn "HorrorBot_Clean_Checkpoints" /tr "C:\projet\.venv\Scripts\python.exe C:\projet\scripts\clean_checkpoints.py --keep-last 5" /sc weekly /d SUN /st 03:00

# P6 - Backup (hebdomadaire dimanche 04:00)
schtasks /create /tn "HorrorBot_Backup_DB" /tr "C:\projet\scripts\backup_db.sh" /sc weekly /d SUN /st 04:00
```

---

## Configuration GPG (chiffrement backups)

### Générer clé GPG

```bash
# Générer nouvelle clé
gpg --full-generate-key
# Choisir : RSA, 4096 bits, validité 2 ans
# Email : dev@horrorbot.local

# Lister clés
gpg --list-keys

# Exporter clé publique (partage)
gpg --export --armor dev@horrorbot.local > horrorbot_public.asc
```

### Restaurer backup chiffré

```bash
# Déchiffrer backup
gpg --decrypt backups/horrorbot_20251121_110000.sql.gz.gpg > backup.sql.gz

# Décompresser
gunzip backup.sql.gz

# Restaurer dans PostgreSQL
docker exec -i horrorbot-postgres psql -U horrorbot_user -d horrorbot < backup.sql
```

---

## Tests manuels

```bash
# Test P1 (dry-run)
python scripts/clean_logs.py --days 0 --dry-run

# Test P2 (dry-run)
python scripts/clean_checkpoints.py --keep-last 999 --dry-run

# Test P6 (backup test)
BACKUP_DIR=./test_backups ./scripts/backup_db.sh
```

---

## Logs maintenance

Tous les scripts loguent dans :
- `logs/scripts.clean_logs.log`
- `logs/scripts.clean_checkpoints.log`
- `logs/cron.log` (si cron)

Format JSON structuré :
```json
{
  "timestamp": "2025-11-21T11:00:00",
  "level": "INFO",
  "message": "clean_logs_completed: deleted=15, size_mb=450.2"
}
```

---

## Troubleshooting

### Erreur "Module src.etl.utils not found"

```bash
# Ajouter PYTHONPATH dans cron
0 2 * * * cd /projet && PYTHONPATH=/projet /projet/.venv/bin/python scripts/clean_logs.py ...
```

### Backup échoue "Container not found"

```bash
# Vérifier nom container
docker ps --filter name=postgres

# Spécifier nom correct
POSTGRES_CONTAINER=mon-container ./scripts/backup_db.sh
```

### GPG "No secret key"

```bash
# Vérifier clé importée
gpg --list-secret-keys

# Spécifier clé explicitement
GPG_EMAIL="autre@email.com" ./scripts/backup_db.sh
```

---

## Conformité RGPD

Ces scripts implémentent les procédures RGPD suivantes :

| Procédure | Article RGPD | Description |
|-----------|--------------|-------------|
| P1 | Art. 5.1.e (limitation conservation) | Suppression logs >30 jours |
| P2 | Art. 5.1.c (minimisation données) | Purge checkpoints obsolètes |
| P6 | Art. 32 (sécurité traitement) | Backups réguliers chiffrés |

Registre exécutions : `data/rgpd_audit.log`
