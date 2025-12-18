#!/usr/bin/env bash
# Script backup PostgreSQL chiffré (RGPD P6)
# Usage: ./scripts/backup_db.sh

set -euo pipefail

# Configuration
CONTAINER_NAME="${POSTGRES_CONTAINER:-horrorbot-postgres}"
DB_USER="${POSTGRES_USER:-horrorbot_user}"
DB_NAME="${POSTGRES_DB:-horrorbot}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS=30

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Vérifier Docker
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    log_error "Container PostgreSQL '$CONTAINER_NAME' non démarré"
    exit 1
fi

# Créer répertoire backups
mkdir -p "$BACKUP_DIR"

# Nom fichier avec timestamp
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/horrorbot_$DATE.sql.gz"

log_info "Début backup PostgreSQL..."

# Backup avec pg_dump + compression gzip
if docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Backup créé : $BACKUP_FILE ($BACKUP_SIZE)"
else
    log_error "Échec backup pg_dump"
    exit 1
fi

# Chiffrement GPG (optionnel - nécessite clé GPG configurée)
if command -v gpg &> /dev/null; then
    GPG_RECIPIENT="${GPG_EMAIL:-dev@horrorbot.local}"
    
    # Vérifier clé existe
    if gpg --list-keys "$GPG_RECIPIENT" &> /dev/null; then
        log_info "Chiffrement GPG avec clé : $GPG_RECIPIENT"
        
        if gpg --encrypt --recipient "$GPG_RECIPIENT" "$BACKUP_FILE"; then
            ENCRYPTED_FILE="$BACKUP_FILE.gpg"
            rm "$BACKUP_FILE"  # Supprimer version non chiffrée
            log_info "Backup chiffré : $ENCRYPTED_FILE"
        else
            log_warning "Échec chiffrement GPG (backup non chiffré conservé)"
        fi
    else
        log_warning "Clé GPG '$GPG_RECIPIENT' introuvable (backup non chiffré)"
    fi
else
    log_warning "GPG non installé (backup non chiffré)"
fi

# Purge anciens backups >30 jours
log_info "Purge backups >$RETENTION_DAYS jours..."
DELETED_COUNT=0

if find "$BACKUP_DIR" -name "horrorbot_*.sql.gz*" -mtime +$RETENTION_DAYS -type f | while read -r old_backup; do
    rm "$old_backup"
    log_info "Supprimé : $(basename "$old_backup")"
    DELETED_COUNT=$((DELETED_COUNT + 1))
done; then
    log_info "Purge terminée : $DELETED_COUNT backups supprimés"
fi

# Statistiques
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "horrorbot_*.sql.gz*" -type f | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

log_info "Statistiques backups :"
log_info "  - Nombre backups : $BACKUP_COUNT"
log_info "  - Espace total : $TOTAL_SIZE"
log_info "✅ Backup terminé avec succès"

exit 0
