# API Documentation — HorrorBot

## Vue d'ensemble

L'API REST HorrorBot est construite avec **FastAPI** et fournit :

- Authentification JWT
- Endpoints films (liste, détails, recherche sémantique)
- Chatbot conversationnel (synchrone + streaming SSE)
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
    "llm": { "loaded": true, "memory_mb": 4500 },
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

### Chat — Réponse synchrone

```
POST /api/v1/chat
Authorization: Bearer <token>
```

Authentification JWT requise. Rate limited. Envoie un message au chatbot et reçoit une réponse synchrone complète.

Le chatbot classe automatiquement l'intent de la requête (recommandation, discussion, trivia, détails film, salutation, hors sujet) et route vers le pipeline approprié (RAG + LLM, LLM seul, query DB, ou réponse template).

**Request** :

```json
{
  "message": "Recommande-moi un film comme Hereditary",
  "session_id": null
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `message` | string | Oui | Message utilisateur (1-2000 caractères) |
| `session_id` | string | Non | UUID de session pour conversation multi-turn. Omis pour nouvelle session. |

**Réponse** :

```json
{
  "response": "Si vous avez aimé Hereditary, je vous recommande vivement **Midsommar** (2019)...",
  "intent": "horror_recommendation",
  "confidence": 0.9234,
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| Champ | Type | Description |
|-------|------|-------------|
| `response` | string | Réponse du chatbot |
| `intent` | string | Intent classifié (`horror_recommendation`, `film_details`, `horror_discussion`, `horror_trivia`, `greeting`, `farewell`, `out_of_scope`) |
| `confidence` | float | Score de confiance du classifier (0.0-1.0) |
| `session_id` | string | UUID de session à renvoyer pour la suite de la conversation |

**Codes d'erreur spécifiques** :

| Code | Description |
|------|-------------|
| 400 | `session_id` n'est pas un UUID valide |
| 504 | Timeout du LLM (> 30s) |
| 503 | Service de chat temporairement indisponible |

### Chat — Streaming SSE

```
POST /api/v1/chat/stream
Authorization: Bearer <token>
```

Authentification JWT requise. Rate limited. Même fonctionnalité que `/chat` mais avec réponse en streaming via **Server-Sent Events** (SSE).

**Request** : identique à `/chat`.

**Réponse** : flux SSE avec des événements JSON.

Chaque événement `data:` contient un JSON de type `StreamChunk` :

```
data: {"type": "chunk", "content": "Si vous avez aimé"}
data: {"type": "chunk", "content": " Hereditary, je vous"}
data: {"type": "chunk", "content": " recommande..."}
data: {"type": "done", "intent": "horror_recommendation", "confidence": 0.9234, "session_id": "a1b2c3d4-..."}
```

| Type | Champs | Description |
|------|--------|-------------|
| `chunk` | `content` | Fragment de texte de la réponse |
| `done` | `intent`, `confidence`, `session_id` | Métadonnées finales |
| `error` | `content` | Message d'erreur si le stream est interrompu |

**Note** : Pour les intents non-streamables (`greeting`, `farewell`, `out_of_scope`, `film_details`), la réponse complète est envoyée en un seul chunk suivi du `done`.

### Métriques Prometheus

```
GET /metrics
```

Pas d'authentification requise. Retourne les métriques au format Prometheus text exposition.

## Authentification

Tous les endpoints `/api/v1/films/*` et `/api/v1/chat/*` nécessitent un token JWT dans le header `Authorization: Bearer <token>`.

Les tokens expirent après 30 minutes (configurable via `JWT_EXPIRE_MINUTES`).

## Rate Limiting

- `/api/v1/auth/token` : limité par IP (configurable via `RATE_LIMIT_PER_MINUTE`)
- Limite par défaut : 100 requêtes/minute, 1000 requêtes/heure

## Codes d'erreur

| Code | Description |
|------|-------------|
| 200 | Succès |
| 400 | Paramètre invalide (ex: session_id non UUID) |
| 401 | Token JWT invalide ou expiré |
| 404 | Film non trouvé |
| 422 | Erreur de validation des paramètres |
| 429 | Rate limit atteint |
| 500 | Erreur serveur |
| 503 | Service temporairement indisponible (LLM crash) |
| 504 | Timeout du LLM (inférence trop longue) |
