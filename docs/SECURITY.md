# Security Guide — HorrorBot

## Authentification JWT

### Configuration

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `JWT_SECRET_KEY` | Clé secrète HMAC (≥32 caractères) | — (obligatoire) |
| `JWT_ALGORITHM` | Algorithme de signature | `HS256` |
| `JWT_EXPIRE_MINUTES` | Durée de validité du token | `30` |

### Rotation des secrets

La clé JWT doit être tournée périodiquement :

1. Générer une nouvelle clé : `python -c "import secrets; print(secrets.token_urlsafe(64))"`
2. Mettre à jour `JWT_SECRET_KEY` dans `.env`
3. Redémarrer l'API — tous les tokens existants deviennent invalides

### Flux d'authentification

```
Client → POST /api/v1/auth/token (username, password)
       ← 200 {access_token, token_type, expires_in}

Client → GET /api/v1/films (Authorization: Bearer <token>)
       ← 200 {data: [...]}

Client → GET /api/v1/films (token expiré)
       ← 401 Unauthorized
```

## Rate Limiting

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `RATE_LIMIT_PER_MINUTE` | Requêtes max par minute par IP | `100` |
| `RATE_LIMIT_PER_HOUR` | Requêtes max par heure par IP | `1000` |

Le rate limiting est appliqué via `slowapi` sur l'endpoint `/api/v1/auth/token` pour prévenir les attaques par force brute.

## CORS (Cross-Origin Resource Sharing)

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `CORS_ORIGINS` | Origines autorisées (séparées par virgule) | `http://localhost:3000` |

Méthodes autorisées : GET, POST, PUT, DELETE
Headers autorisés : Authorization, Content-Type

## OWASP Top 10 — Mesures appliquées

| Risque OWASP | Mesure HorrorBot |
|--------------|------------------|
| A01 Broken Access Control | JWT obligatoire sur tous les endpoints `/films/*` |
| A02 Cryptographic Failures | HS256 avec clé ≥32 chars, pas de stockage de mots de passe en clair |
| A03 Injection | Requêtes SQL paramétrées (SQLAlchemy ORM), validation Pydantic |
| A04 Insecure Design | Architecture 100% locale, pas de transfert de données vers le cloud |
| A05 Security Misconfiguration | CORS restrictif, headers de sécurité, rate limiting |
| A06 Vulnerable Components | CI/CD : Bandit, Safety, pip-audit, OWASP Dependency-Check |
| A07 Authentication Failures | Rate limiting sur `/auth/token`, expiration JWT 30min |
| A08 Data Integrity Failures | Dépendances lockées (`uv.lock`), CI vérifie l'intégrité |
| A09 Security Logging | Structured logging (structlog), métriques Prometheus |
| A10 SSRF | Pas d'appels sortants en production (modèles locaux) |

## Gestion des secrets

### Variables sensibles

| Variable | Sensibilité | Stockage |
|----------|-------------|----------|
| `JWT_SECRET_KEY` | Critique | `.env` (jamais en Git) |
| `POSTGRES_PASSWORD` | Haute | `.env` (jamais en Git) |
| `TMDB_API_KEY` | Moyenne | `.env` (jamais en Git) |

### Bonnes pratiques

- `.env` est dans `.gitignore` — ne jamais le committer
- `.env.example` contient des placeholders, pas de vrais secrets
- En production (Render), utiliser les variables d'environnement du dashboard
- La fonction `get_masked_settings()` masque les secrets dans les logs

## CI/CD — Scans de sécurité

Le pipeline GitHub Actions exécute 3 jobs de sécurité :

1. **Bandit** : analyse statique du code Python (détection de failles)
2. **Safety + pip-audit** : vérification des vulnérabilités dans les dépendances
3. **OWASP Dependency-Check** : scan CVE des dépendances (seuil CVSS ≥ 7)
