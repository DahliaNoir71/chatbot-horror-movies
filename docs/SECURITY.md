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

### Rôles et contrôle d'accès (RBAC)

L'API implémente un système RBAC avec deux rôles :

| Rôle | Attribution | Endpoints accessibles |
|------|------------|----------------------|
| `user` | Par défaut à l'inscription | `/api/v1/chat`, `/api/v1/chat/stream` |
| `admin` | Email dans `ADMIN_ALLOWED_EMAILS` | Tous (`/health`, `/films/*`, `/chat/*`) |

Le rôle est inclus dans le payload JWT (`role` claim) et vérifié par les dépendances FastAPI :

- `CurrentUser` : valide le JWT, accepte tout rôle authentifié
- `AdminUser` : valide le JWT + exige `role == "admin"` (retourne 403 sinon)

### Flux d'authentification

**Utilisateur (chatbot)** :

```
Client → POST /api/v1/auth/register (username, email, password)
       ← 201 {username, email, message}

Client → POST /api/v1/auth/token (username, password)
       ← 200 {access_token, token_type, expires_in}

Client → POST /api/v1/chat (Authorization: Bearer <token>)
       ← 200 {response, intent, confidence, session_id}
```

**Admin** :

```
Client → POST /api/v1/auth/admin/token (email, password)
       ← 200 {access_token, token_type, expires_in}

Client → GET /api/v1/health (Authorization: Bearer <admin_token>)
       ← 200 {status, version, components}

Client → GET /api/v1/films (Authorization: Bearer <admin_token>)
       ← 200 {data: [...]}
```

**Erreurs** :

```
Client → POST /api/v1/auth/token (mauvais credentials)
       ← 401 Unauthorized

Client → GET /api/v1/films (token user, pas admin)
       ← 403 Admin access required

Client → GET /api/v1/films (token expiré)
       ← 401 Token has expired
```

### Seeding du compte admin

Au démarrage, l'API crée automatiquement un compte admin si `ADMIN_ALLOWED_EMAILS` est configuré :

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `ADMIN_ALLOWED_EMAILS` | Liste d'emails admin (séparés par virgule) | — (optionnel) |
| `ADMIN_DEFAULT_PASSWORD` | Mot de passe initial du compte admin seedé | — (optionnel) |

La fonction `_seed_admin_account()` (dans `src/api/main.py`) :

1. Vérifie si un compte existe pour le premier email de la liste
2. Le crée avec `role="admin"` s'il n'existe pas
3. Met à jour le rôle et le mot de passe si le compte existe mais a divergé

**Important** : changer `ADMIN_DEFAULT_PASSWORD` en production après le premier déploiement.

## Rate Limiting

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `RATE_LIMIT_PER_MINUTE` | Requêtes max par minute par IP | `100` |
| `RATE_LIMIT_PER_HOUR` | Requêtes max par heure par IP | `1000` |

Le rate limiting est appliqué via `slowapi` sur les endpoints :

- `/api/v1/auth/token` : prévention des attaques par force brute
- `/api/v1/chat` et `/api/v1/chat/stream` : protection contre l'abus du LLM (ressource coûteuse en CPU/RAM)

## CORS (Cross-Origin Resource Sharing)

| Variable | Description | Valeur par défaut |
|----------|-------------|-------------------|
| `CORS_ORIGINS` | Origines autorisées (séparées par virgule) | `http://localhost:3000` |

Méthodes autorisées : GET, POST, PUT, DELETE
Headers autorisés : Authorization, Content-Type

## OWASP Top 10 — Mesures appliquées

| Risque OWASP | Mesure HorrorBot |
|--------------|------------------|
| A01 Broken Access Control | RBAC (rôles user/admin), JWT obligatoire, endpoints `/films/*` et `/health` réservés admin (403) |
| A02 Cryptographic Failures | HS256 avec clé ≥32 chars, mots de passe hashés bcrypt (passlib) |
| A03 Injection | Requêtes SQL paramétrées (SQLAlchemy ORM), validation Pydantic. Messages chat limités à 2000 caractères. System prompts non modifiables par l'utilisateur (protection injection de prompt). |
| A04 Insecure Design | Architecture 100% locale, pas de transfert de données vers le cloud |
| A05 Security Misconfiguration | CORS restrictif, headers de sécurité, rate limiting |
| A06 Vulnerable Components | CI/CD : Bandit, Safety, pip-audit, OWASP Dependency-Check |
| A07 Authentication Failures | Rate limiting sur `/auth/token` et `/auth/register`, expiration JWT 30min, flux séparés user/admin |
| A08 Data Integrity Failures | Dépendances lockées (`uv.lock`), CI vérifie l'intégrité |
| A09 Security Logging | Structured logging (structlog), métriques Prometheus |
| A10 SSRF | Pas d'appels sortants en production (modèles locaux) |

## Gestion des secrets

### Variables sensibles

| Variable | Sensibilité | Stockage |
|----------|-------------|----------|
| `JWT_SECRET_KEY` | Critique | `.env` (jamais en Git) |
| `POSTGRES_PASSWORD` | Haute | `.env` (jamais en Git) |
| `ADMIN_DEFAULT_PASSWORD` | Haute | `.env` (jamais en Git) |
| `ADMIN_ALLOWED_EMAILS` | Moyenne | `.env` (jamais en Git) |
| `TMDB_API_KEY` | Moyenne | `.env` (jamais en Git) |

### Bonnes pratiques

- `.env` est dans `.gitignore` — ne jamais le committer
- `.env.example` contient des placeholders, pas de vrais secrets
- En Docker, les secrets sont injectés via `env_file: .env` dans `docker-compose.yml`
- La fonction `get_masked_settings()` masque les secrets dans les logs

## CI/CD — Scans de sécurité

Le pipeline GitHub Actions exécute 3 jobs de sécurité :

1. **Bandit** : analyse statique du code Python (détection de failles)
2. **Safety + pip-audit** : vérification des vulnérabilités dans les dépendances
3. **OWASP Dependency-Check** : scan CVE des dépendances (seuil CVSS ≥ 7)
