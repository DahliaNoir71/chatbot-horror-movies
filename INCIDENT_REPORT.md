# Rapport d'Incident — Regression Performance RAG

## Informations generales

| Champ | Valeur |
|-------|--------|
| Date de detection | _YYYY-MM-DD HH:MM_ |
| Duree de l'incident | _~XX minutes_ |
| Severite | Warning (degradation de performance) |
| Service impacte | RAG Retrieval (recherche vectorielle pgvector) |
| Alerte declenchee | `RAGRetrievalSlow` (Prometheus) + `RAG Retrieval Slow` (Grafana) |
| Branche | `fix/incident-rag-performance` |

---

## Chronologie

| Heure | Evenement |
|-------|-----------|
| _HH:MM_ | Deploiement du commit contenant la regression sur la branche `fix/incident-rag-performance` |
| _HH:MM_ | Demarrage du stack Docker (`docker compose up -d`) |
| _HH:MM_ | Debut de la generation de trafic (`scripts/generate_incident_traffic.py`) |
| _HH:MM_ | Detection du pic de latence sur le dashboard Grafana "RAG Performance" |
| _HH:MM_ | Alerte `RAGRetrievalSlow` passe en PENDING dans Prometheus |
| _HH:MM_ | Diagnostic : scan sequentiel identifie dans `src/services/rag/retriever.py` |
| _HH:MM_ | Application du correctif (suppression des `SET LOCAL`) |
| _HH:MM_ | Verification : latence de retrieval revenue a la normale |

---

## Symptomes observes

### Metriques baseline (avant incident)

| Metrique | Valeur nominale |
|----------|-----------------|
| `horrorbot_rag_retrieval_duration_seconds` P95 | ~50ms |
| `horrorbot_rag_retrieval_duration_seconds` P50 | ~30ms |
| Temps de reponse `/api/v1/chat` | < 2s |

### Metriques pendant l'incident

| Metrique | Valeur observee |
|----------|-----------------|
| `horrorbot_rag_retrieval_duration_seconds` P95 | _> XXXX ms_ |
| `horrorbot_rag_retrieval_duration_seconds` P50 | _> XXXX ms_ |
| Temps de reponse `/api/v1/chat` | _> X s_ |

### Sortie du script de trafic

```
(coller ici la sortie de scripts/generate_incident_traffic.py)
```

---

## Captures d'ecran

### Dashboard Grafana — RAG Retrieval Latency (pendant l'incident)

![RAG Latency Spike](screenshots/incident/grafana-rag-latency-spike.png)

### Prometheus Alerts (alerte declenchee)

![Prometheus Alert](screenshots/incident/prometheus-alert-firing.png)

### Dashboard Grafana — Apres correctif

![RAG Latency Fixed](screenshots/incident/grafana-rag-latency-fixed.png)

---

## Analyse de la cause racine

### Cause identifiee

Deux instructions SQL ont ete ajoutees dans la methode `_execute_search()` du fichier
`src/services/rag/retriever.py` :

```python
session.execute(text("SET LOCAL enable_indexscan = off"))
session.execute(text("SET LOCAL enable_bitmapscan = off"))
```

Ces instructions forcent PostgreSQL a **ignorer l'index IVFFlat**
(`idx_rag_documents_embedding`) lors des requetes de similarite vectorielle,
provoquant un **scan sequentiel** sur la table `rag_documents`.

Avec environ 10 000 lignes de vecteurs 384 dimensions, le scan sequentiel
est 30 a 50 fois plus lent que l'index IVFFlat (recherche approximative
par voisins les plus proches).

### Scenario de production equivalent

Ce type d'incident peut se produire en production dans les cas suivants :
- **Index corrompu** apres un crash PostgreSQL ou un `VACUUM FULL` interrompu
- **Index supprime** par une migration mal testee (`DROP INDEX` accidentel)
- **Configuration modifiee** par un DBA ajustant les parametres du planificateur
- **Mise a jour pgvector** sans reconstruction de l'index (`REINDEX`)

### Impact utilisateur

- Latence de retrieval vectoriel multipliee par 30-50x (50ms → 1500-3000ms)
- Temps de reponse global du chatbot severement degrade (endpoint `/api/v1/chat`)
- Experience utilisateur deterioree : temps d'attente > 5 secondes par message
- Risque de timeouts sur les requetes les plus longues

---

## Detection

L'incident a ete detecte grace aux outils de monitoring mis en place :

1. **Dashboard Grafana "RAG Performance"** : panel "RAG Retrieval Latency (P95 / P50)"
   montrant un pic brutal de latence
2. **Alerte Prometheus** `RAGRetrievalSlow` : condition `histogram_quantile(0.95,
   rate(horrorbot_rag_retrieval_duration_seconds_bucket[5m])) > 0.5` depassee
3. **Alerte Grafana** `RAG Retrieval Slow` (uid: `horrorbot-rag-retrieval-slow`) :
   meme condition, notification via contact point configure
4. **Logs structlog** : durees de retrieval anormalement elevees dans les logs JSON
   (`duration_ms` > 1000 dans les entrees de `services.rag.retriever`)

---

## Resolution

### Recherche de solution

| Source consultee | Information obtenue |
|------------------|---------------------|
| [Documentation PostgreSQL — `enable_indexscan`](https://www.postgresql.org/docs/current/runtime-config-query.html) | Parametre du planificateur qui active/desactive l'utilisation des index scans |
| [Documentation pgvector — Indexes](https://github.com/pgvector/pgvector#indexing) | Les index IVFFlat necessitent `enable_indexscan = on` pour etre utilises |
| Analyse du code `retriever.py` | Les `SET LOCAL` modifient le comportement pour la transaction courante uniquement |

### Solutions envisagees

| Solution | Description | Retenue ? |
|----------|-------------|-----------|
| A — Supprimer les `SET LOCAL` | Retour a l'etat sain, PostgreSQL utilise l'index normalement | **Oui** |
| B — Forcer `SET LOCAL enable_indexscan = on` | Explicite mais ajoute du code inutile si le defaut est deja `on` | Non |
| C — Ajouter `SET LOCAL enable_indexscan = on` en garde permanente | Sur-ingenierie, masque le vrai probleme | Non |

**Choix : Solution A** — simplicite, retour a l'etat sain sans code superflu.

### Correctif applique

Suppression des deux lignes `SET LOCAL` dans `src/services/rag/retriever.py`,
methode `_execute_search()`.

### Verification post-correctif

1. Rebuild de l'image Docker API (`docker compose build api`)
2. Redemarrage du service (`docker compose up -d api`)
3. Generation de trafic de verification (15 nouvelles requetes via le script)
4. Confirmation du retour a la normale sur le dashboard Grafana RAG
5. Alertes `RAGRetrievalSlow` passent en RESOLVED
6. Tests unitaires et d'integration tous verts (`pytest`)

---

## Actions preventives

| Action | Description | Priorite |
|--------|-------------|----------|
| **Test de garde** | Ajouter un test de latence RAG dans la CI : assertion P95 < 500ms sur jeu de donnees de test | Haute |
| **Revue de code** | Tout changement dans `src/services/rag/` necessite une PR avec review obligatoire | Haute |
| **Runbook alerte** | Documenter la procedure de diagnostic pour l'alerte `RAGRetrievalSlow` | Moyenne |
| **Monitoring index** | Ajouter une metrique `pg_stat_user_indexes` pour suivre l'utilisation des index pgvector | Basse |

---

## Lecons apprises

1. **Le monitoring fonctionne** : l'incident a ete detecte en quelques minutes grace aux
   dashboards Grafana et aux alertes Prometheus/Grafana configures dans les phases precedentes.
2. **Les index sont critiques** : pour les recherches vectorielles sur des tables de taille
   significative, la presence et le bon fonctionnement de l'index IVFFlat est un facteur
   de performance majeur (x30-50 de difference).
3. **Les logs structures aident au diagnostic** : les logs JSON avec `request_id` et
   `duration_ms` permettent de correler rapidement les requetes lentes avec leur contexte.
4. **Un test de garde aurait prevenu la regression** : un test automatise verifiant la
   latence de retrieval aurait bloque le deploiement du code defectueux.
