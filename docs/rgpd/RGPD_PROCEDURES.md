# Procédures Tri Données - Conformité RGPD

**Objectif** : Garantir minimisation données, limitation conservation, intégrité (Art. 5 RGPD)

---

## Procédure P1 : Nettoyage logs anciens

**Fréquence** : Quotidienne (automatique - cron 02:00)  
**Automatisation** : Script `scripts/clean_logs.py`  
**Responsable** : Système (script automatisé)

### Commande manuelle
```bash
# Nettoyage logs >30 jours
python scripts/clean_logs.py --days 30

# Dry-run (aperçu sans suppression)
python scripts/clean_logs.py --days 30 --dry-run
```

### Actions effectuées
1. Analyse récursive `logs/*.log`
2. Suppression fichiers `modified_time > 30 jours`
3. Archive logs critiques (contenant "ERROR", "CRITICAL") dans `logs/archives/`
4. Log opération dans `logs/maintenance.log`

### Résultat attendu
```
✅ 15 fichiers logs supprimés (450 MB libérés)
✅ 3 logs critiques archivés
```

### Déclencheurs d'alerte
- Échec script 2 jours consécutifs → Email développeur
- Espace disque <500MB → Email + arrêt services non critiques

---

## Procédure P2 : Purge checkpoints obsolètes

**Fréquence** : Hebdomadaire (dimanche 03:00)  
**Automatisation** : Script `scripts/clean_checkpoints.py`  
**Responsable** : Système

### Commande manuelle
```bash
# Garder 5 derniers checkpoints pipeline
python scripts/clean_checkpoints.py --keep-last 5

# Supprimer checkpoints >90 jours
python scripts/clean_checkpoints.py --older-than 90
```

### Actions effectuées
1. Liste `data/checkpoints/*.json`
2. Tri par `modified_time` (plus récent → plus ancien)
3. Garde N derniers (`--keep-last`)
4. Supprime anciens >90 jours
5. Log opération

### Résultat attendu
```
✅ 12 checkpoints supprimés (2.3 GB libérés)
✅ 5 checkpoints conservés (derniers pipelines)
```

---

## Procédure P3 : Audit absence données personnelles

**Fréquence** : Trimestrielle (manuelle)  
**Automatisation** : Semi-automatique (requêtes SQL + revue manuelle)  
**Responsable** : Développeur

### Requêtes audit

#### Détection emails dans overview
```sql
SELECT id, title, overview 
FROM films 
WHERE overview ~* '([a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})';

-- Résultat attendu : 0 lignes
```

#### Détection noms propres suspects
```sql
SELECT id, title, overview 
FROM films 
WHERE overview ~* '(M\.|Mme|Mr\.|Mrs\.) [A-Z][a-z]+ [A-Z][a-z]+';

-- Examiner manuellement (peut être personnages fictifs)
```

#### Détection numéros téléphone
```sql
SELECT id, title, overview 
FROM films 
WHERE overview ~* '(\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}';

-- Résultat attendu : 0 lignes
```

### Actions si détection
1. **Alerte immédiate** : Notification développeur
2. **Anonymisation** : Remplacement texte sensible par `[REDACTED]`
3. **Update SQL** : 
```sql
UPDATE films 
SET overview = regexp_replace(overview, 'pattern_detecte', '[REDACTED]', 'g')
WHERE id = X;
```
4. **Documentation incident** : Ajout `data/rgpd_incidents.log`
5. **Révision sources** : Audit pipeline ETL (pourquoi PII présent ?)

### Rapport audit
```
Date audit : 21/11/2025
Films scannés : 13
PII détectées : 0
Actions correctives : Aucune
Prochaine audit : 21/02/2026
```

---

## Procédure P4 : Droit à l'oubli (si applicable futur)

**Déclencheur** : Demande utilisateur par email  
**Délai légal** : 30 jours max (Art. 17 RGPD)  
**Statut actuel** : **NON APPLICABLE** (HorrorBot ne stocke aucune donnée utilisateur)

### Actions si implémentation future comptes utilisateurs

1. **Vérification identité demandeur** : Copie ID + email confirmé
2. **Localisation données** :
```sql
SELECT * FROM users WHERE email = 'user@example.com';
SELECT * FROM conversations WHERE user_id = X;
```
3. **Suppression définitive** :
```sql
BEGIN;
DELETE FROM conversations WHERE user_id = X;
DELETE FROM users WHERE id = X;
COMMIT;
```
4. **Confirmation écrite** : Email "Vos données ont été supprimées" sous 7 jours

---

## Procédure P5 : Export données (portabilité)

**Déclencheur** : Demande utilisateur (Art. 20 RGPD)  
**Délai** : 30 jours  
**Statut** : **NON APPLICABLE** (pas de données personnelles)

### Actions si implémentation future

```bash
# Script export JSON
python scripts/export_user_data.py --user-id X --output user_export.json

# Format JSON standardisé
{
  "user_id": 123,
  "email": "user@example.com",
  "conversations": [...],
  "exported_at": "2025-11-21T10:00:00Z"
}
```

---

## Procédure P6 : Backup sécurisé

**Fréquence** : Hebdomadaire (dimanche 04:00)  
**Automatisation** : Script `scripts/backup_db.sh`

```bash
#!/bin/bash
# Backup PostgreSQL chiffré
DATE=$(date +%Y%m%d)
docker exec horrorbot-postgres pg_dump -U horrorbot_user horrorbot \
  | gzip | gpg --encrypt --recipient dev@horrorbot.local \
  > backups/horrorbot_$DATE.sql.gz.gpg

# Purge backups >30 jours
find backups/ -name "*.sql.gz.gpg" -mtime +30 -delete
```

**Stockage** : Local + Cloud chiffré (si déploiement production)

---

## Procédure P7 : Violation données (Breach)

**Déclencheur** : Détection accès non autorisé, fuite données  
**Délai notification CNIL** : 72h (Art. 33 RGPD)  
**Statut** : **RISQUE FAIBLE** (pas de données personnelles)

### Actions si violation future

1. **Containment** : Isolation système compromis
2. **Investigation** : Analyse logs, étendue violation
3. **Notification CNIL** : https://www.cnil.fr/fr/notifier-une-violation-de-donnees-personnelles
4. **Notification utilisateurs** : Si risque élevé droits/libertés
5. **Rapport incident** : Documentation complète
6. **Mesures correctrices** : Patch vulnérabilité, renforcement sécurité

---

## Registre exécutions procédures

**Fichier** : `data/rgpd_audit.log` (append-only)

```json
{
  "date": "2025-11-21",
  "procedure": "P3_audit_pii",
  "status": "success",
  "findings": "0 PII detected",
  "action_taken": "none"
}
```

---

## Responsabilités

| Procédure | Responsable | Fréquence | Automatisation |
|-----------|-------------|-----------|----------------|
| P1 - Logs | Système | Quotidienne | ✅ 100% |
| P2 - Checkpoints | Système | Hebdomadaire | ✅ 100% |
| P3 - Audit PII | Développeur | Trimestrielle | ⚠️ 50% (SQL auto, revue manuelle) |
| P4 - Droit oubli | Développeur | À la demande | ❌ Manuelle |
| P5 - Portabilité | Développeur | À la demande | ⚠️ 80% |
| P6 - Backup | Système | Hebdomadaire | ✅ 100% |
| P7 - Breach | Développeur | Incident | ❌ Manuelle |

---

## Prochaines révisions

- **Date prochaine révision** : 21/02/2026
- **Déclencheurs révision anticipée** :
  - Ajout fonctionnalité comptes utilisateurs
  - Intégration analytics/tracking
  - Modification finalités traitement
  - Évolution législation (AI Act, DSA)

---

**Document validé** : 21/11/2025  
**Responsable conformité** : Serge PFEIFFER
