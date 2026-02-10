# API Documentation — HorrorBot

## Vue d'ensemble

L'API REST HorrorBot est construite avec **FastAPI** et fournit :

- Authentification JWT
- Endpoints films (liste, détails, recherche sémantique)
- Rate limiting
- Métriques Prometheus

## Documentation interactive

FastAPI génère automatiquement la documentation OpenAPI 3.0 :

- **Swagger UI** : http://localhost:8000/api/docs
- **ReDoc** : http://localhost:8000/api/redoc
- **Schéma JSON** : http://localhost:8000/api/openapi.json

## Endpoints

### Health Check

```
GET /api/v1/health
```

Pas d'authentification requise.

**Réponse** :

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "llm": { "loaded": true, "memory_mb": 4900 },
    "database": { "connected": true, "pool_available": 8 },
    "embeddings": { "model_loaded": true }
  },
  "timestamp": "2026-01-15T10:45:32Z"
}
```

### Authentification

```
POST /api/v1/auth/token
```

Rate limited. Retourne un JWT Bearer token.

**Request** :

```json
{
  "username": "demo",
  "password": "demopass1234"
}
```

**Réponse** :

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Films — Liste paginée

```
GET /api/v1/films?page=1&size=20
Authorization: Bearer <token>
```

**Réponse** :

```json
{
  "data": [
    {
      "id": 1,
      "tmdb_id": 694,
      "title": "The Shining",
      "overview": "...",
      "release_date": "1980-05-23",
      "vote_average": 8.4,
      "poster_path": "/b6ko0IKC8MdYBBPkkA1aBPLe2yz.jpg"
    }
  ],
  "meta": {
    "page": 1,
    "size": 20,
    "total": 31255,
    "pages": 1563
  }
}
```

### Films — Détails

```
GET /api/v1/films/{film_id}
Authorization: Bearer <token>
```

### Films — Recherche sémantique

```
POST /api/v1/films/search
Authorization: Bearer <token>
```

**Request** :

```json
{
  "query": "film about a haunted hotel with a writer",
  "limit": 5
}
```

**Réponse** :

```json
{
  "query": "film about a haunted hotel with a writer",
  "results": [
    {
      "id": 1,
      "tmdb_id": 694,
      "title": "The Shining",
      "overview": "...",
      "release_date": "1980-05-23",
      "score": 0.87
    }
  ],
  "count": 5
}
```

### Métriques Prometheus

```
GET /metrics
```

Pas d'authentification requise. Retourne les métriques au format Prometheus text exposition.

## Authentification

Tous les endpoints `/api/v1/films/*` nécessitent un token JWT dans le header `Authorization: Bearer <token>`.

Les tokens expirent après 30 minutes (configurable via `JWT_EXPIRE_MINUTES`).

## Rate Limiting

- `/api/v1/auth/token` : limité par IP (configurable via `RATE_LIMIT_PER_MINUTE`)
- Limite par défaut : 100 requêtes/minute, 1000 requêtes/heure

## Codes d'erreur

| Code | Description |
|------|-------------|
| 200 | Succès |
| 401 | Token JWT invalide ou expiré |
| 404 | Film non trouvé |
| 422 | Erreur de validation des paramètres |
| 429 | Rate limit atteint |
| 500 | Erreur serveur |
