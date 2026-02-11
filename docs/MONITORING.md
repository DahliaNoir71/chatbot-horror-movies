# Monitoring Guide — HorrorBot

## Architecture

```
FastAPI (/metrics) → Prometheus (scrape 15s) → Grafana (dashboards)
```

- **FastAPI** expose les métriques via `PrometheusMiddleware` et l'endpoint `/metrics`
- **Prometheus** scrape les métriques toutes les 15 secondes
- **Grafana** visualise via 3 dashboards préconfigurés

## Démarrage du stack monitoring

```bash
docker-compose --profile monitoring up -d
```

Services disponibles :

| Service | URL | Identifiants par défaut |
|---------|-----|------------------------|
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin |

## Métriques collectées

### LLM (src/monitoring/metrics.py)

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_llm_request_duration_seconds` | Histogram | Latence inférence LLM |
| `horrorbot_llm_tokens_generated_total` | Counter | Tokens générés cumulés |
| `horrorbot_llm_prompt_tokens_total` | Counter | Tokens prompt cumulés |
| `horrorbot_llm_tokens_per_second` | Gauge | Débit génération LLM (tokens/s) |
| `horrorbot_llm_requests_total` | Counter | Requêtes LLM par statut (success/error/timeout) |

### Intent Classifier

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_classifier_request_duration_seconds` | Histogram | Latence classification intent |
| `horrorbot_classifier_requests_total` | Counter | Classifications par intent |
| `horrorbot_classifier_confidence` | Histogram | Distribution scores de confiance |

### Embeddings

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_embedding_request_duration_seconds` | Histogram | Latence encodage embeddings |

### Système

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_model_memory_bytes` | Gauge | Mémoire par modèle (llm/classifier/embedding) |
| `horrorbot_model` | Info | Métadonnées des modèles chargés |

### RAG Retrieval

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_rag_retrieval_duration_seconds` | Histogram | Latence recherche vectorielle pgvector |
| `horrorbot_rag_documents_retrieved` | Histogram | Nombre de documents retournés par requête RAG |
| `horrorbot_rag_top_similarity_score` | Histogram | Score de similarité cosine du document top-1 |

### Chat Endpoint

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_chat_requests_total` | Counter | Requêtes chat par intent et mode (sync/stream) |
| `horrorbot_chat_request_duration_seconds` | Histogram | Durée E2E d'une requête chat par intent |
| `horrorbot_chat_errors_total` | Counter | Erreurs chat par type (timeout/llm_crash/stream_error) |

### Sessions

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_active_sessions` | Gauge | Nombre de sessions de chat actives |
| `horrorbot_session_message_count` | Histogram | Nombre de messages par session au moment de l'interaction |

### HTTP (src/monitoring/middleware.py)

| Métrique | Type | Description |
|----------|------|-------------|
| `horrorbot_http_requests_total` | Counter | Requêtes HTTP (method, path, status) |
| `horrorbot_http_request_duration_seconds` | Histogram | Durée requêtes HTTP |

## Dashboards Grafana

Trois dashboards JSON sont provisionnés automatiquement dans `docker/grafana/dashboards/` :

### LLM Dashboard (`llm.json`)

- Latence inférence P95 / P50
- Tokens par seconde (gauge temps réel)
- Mémoire RAM du modèle LLM
- Requêtes par statut (success / error / timeout)
- Débit tokens générés vs prompt

### RAG Dashboard (`rag.json`)

- Latence intent classifier P95 / P50
- Distribution des scores de confiance
- Répartition des classifications par intent
- Latence encodage embeddings P95 / P50
- Mémoire par modèle (LLM / classifier / embedding)

### API Dashboard (`api.json`)

- Requêtes par endpoint (rate/s)
- Taux d'erreur par code HTTP
- Latence P95 par endpoint
- Taux d'erreur 5xx (%)
- Total requêtes sur 1h

## Seuils d'alerte recommandés

| Métrique | Seuil | Signification |
|----------|-------|---------------|
| LLM latence P95 | > 3s | Inférence trop lente |
| Classifier latence | > 200ms | Classification ralentie |
| Embedding latence P95 | > 100ms | Encodage lent |
| Confiance moyenne classifier | < 0.6 | Qualité classification dégradée |
| RAG retrieval latence P95 | > 500ms | Recherche vectorielle lente |
| Chat latence E2E P95 | > 5s | Réponse chatbot trop lente |
| Sessions actives | > 500 | Charge mémoire sessions |
| Taux 5xx | > 5% | Erreurs serveur excessives |
| Mémoire LLM | > 90% RAM dispo | Risque OOM |

## Alertes Grafana

Les alertes sont provisionnées automatiquement via les fichiers YAML dans
`docker/grafana/provisioning/alerting/`. Elles se déclenchent lorsqu'un seuil est dépassé
pendant 5 minutes consécutives (`for: 5m`).

### Fichiers de configuration

| Fichier | Rôle |
|---------|------|
| `provisioning/alerting/alert-rules.yml` | Définitions des 10 règles d'alerte |
| `provisioning/alerting/notification-policies.yml` | Politique de routage par sévérité |

### Règles d'alerte actives

#### Critiques (santé du service)

| Alerte | Seuil | Métrique |
|--------|-------|----------|
| LLM Inference Latency High | P95 > 3s | `horrorbot_llm_request_duration_seconds` |
| 5xx Error Rate High | > 5% | `horrorbot_http_requests_total` |
| Model Memory Usage High | > 90% de 16 GiB | `horrorbot_model_memory_bytes` |
| LLM Token Throughput Low | < 5 tok/s (actif) | `horrorbot_llm_tokens_per_second` |

#### Avertissements (dégradation performance)

| Alerte | Seuil | Métrique |
|--------|-------|----------|
| Classifier Latency High | P95 > 200ms | `horrorbot_classifier_request_duration_seconds` |
| Classifier Confidence Low | Médiane < 0.6 | `horrorbot_classifier_confidence` |
| RAG Retrieval Slow | P95 > 500ms | `horrorbot_rag_retrieval_duration_seconds` |
| RAG No Documents Returned | > 50% requêtes à 0 docs | `horrorbot_rag_documents_retrieved` |
| Embedding Latency High | P95 > 100ms | `horrorbot_embedding_request_duration_seconds` |
| API Request Rate High | > 1000 rpm | `horrorbot_http_requests_total` |

### Consultation des alertes

Les alertes sont visibles dans l'interface Grafana :

- **URL** : http://localhost:3000/alerting/list
- Les alertes critiques ont un intervalle de répétition de 1h
- Les alertes d'avertissement ont un intervalle de répétition de 4h
- État « Normal » = aucun problème ; « Pending » = seuil dépassé, en attente de confirmation ; « Firing » = alerte active

### Personnalisation

Pour modifier un seuil, éditer `docker/grafana/provisioning/alerting/alert-rules.yml`
et redémarrer Grafana :

```bash
docker-compose --profile monitoring restart grafana
```

Pour ajouter un canal de notification externe (email, Discord, Slack), créer
`docker/grafana/provisioning/alerting/contact-points.yml` avec la configuration
du receiver souhaité et mettre à jour les noms de receiver dans `notification-policies.yml`.

## Configuration Prometheus

Fichier : `docker/prometheus/prometheus.yml`

```yaml
scrape_configs:
  - job_name: "horrorbot-api"
    metrics_path: /metrics
    static_configs:
      - targets: ["host.docker.internal:8000"]
```

Pour modifier l'intervalle de scrape, ajuster `scrape_interval` (défaut : 15s).
