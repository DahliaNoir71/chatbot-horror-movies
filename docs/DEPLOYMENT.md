# Deployment Guide — HorrorBot

## Prérequis

- **Docker** et **Docker Compose** v2+
- **Python 3.12** avec **uv** (gestionnaire de dépendances)
- **Node.js 22+** + **npm** (frontend Vue.js)
- **16 Go RAM** minimum (32 Go recommandé pour CPU-only)
- **GPU (optionnel)** : NVIDIA GTX 1660 Ti ou supérieur (6 Go+ VRAM)

## Déploiement Local (Développement)

### 1. Clone et configuration

```bash
git clone https://github.com/DahliaNoir71/HorrorBot.git
cd HorrorBot
cp .env.example .env
# Éditer .env avec vos variables (cf. docs/SECURITY.md pour les secrets)
```

### 2. Démarrage des services Docker

```bash
# Base de données PostgreSQL + pgvector
docker-compose up -d

# Optionnel : monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d

# Optionnel : pgAdmin (interface administration DB)
docker-compose --profile tools up -d
```

### 3. Installation des dépendances Python

```bash
# Dépendances core + dev (sans ML, rapide)
uv sync

# Avec dépendances ML (PyTorch, transformers, llama-cpp-python)
uv sync --group ml
```

### 4. Téléchargement des modèles IA

```bash
# Télécharge automatiquement le LLM (Qwen2.5-7B-Instruct GGUF),
# le classifier (DeBERTa-v3) et l'embedding (MiniLM) depuis HuggingFace
uv run python -m src.scripts.init_models

# Vérifier que tous les modèles sont présents
uv run python -m src.scripts.init_models --check

# Télécharger un modèle spécifique uniquement
uv run python -m src.scripts.init_models --llm         # LLM seulement
uv run python -m src.scripts.init_models --classifier   # Classifier seulement
uv run python -m src.scripts.init_models --embedding    # Embedding seulement
```

### 5. Initialisation de la base de données

```bash
# Pipeline complet : ETL + Import DB
uv run python -m src full

# Ou par étapes :
uv run python -m src etl              # Extraction + enrichissement
uv run python -m src import-db        # Import en base avec embeddings
```

### 6. Lancement de l'API

```bash
uv run uvicorn src.api.main:app --reload --port 8000
```

### 7. Lancement du frontend

```bash
# Dans un autre terminal
cd src/frontend
npm install
npm run dev
```

Interface chatbot : <http://localhost:5173>

Le dev server Vite proxy automatiquement `/api` vers le backend (`localhost:8000`).

Endpoints disponibles :

- Frontend chatbot : <http://localhost:5173>
- API Swagger : <http://localhost:8000/api/docs>
- Métriques Prometheus : <http://localhost:8000/metrics>
- Health check (admin) : `GET /api/v1/health` (nécessite un token admin)
- Chat synchrone : `POST /api/v1/chat`
- Chat streaming : `POST /api/v1/chat/stream`

## Déploiement Production (Render)

### Backend API

- **Service Type** : Web Service
- **Runtime** : Docker ou Python 3.12
- **Plan** : Starter (7$/mois, 512 Mo RAM minimum)
- **Build Command** : `uv sync --group ml`
- **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

### Frontend Vue.js

- **Service Type** : Static Site
- **Build Command** : `cd src/frontend && npm ci && npm run build`
- **Publish Directory** : `src/frontend/dist`
- **Déploiement automatique** : via le workflow `.github/workflows/frontend-cd.yml` (déclenché après CI success sur `main`)

### Variables d'environnement Render

Configurer via le dashboard Render :

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL PostgreSQL Render |
| `JWT_SECRET_KEY` | Clé secrète ≥32 chars |
| `LLM_MODEL_PATH` | Chemin vers le fichier GGUF |
| `LLM_N_GPU_LAYERS` | `0` (CPU only sur Render) |
| `ENVIRONMENT` | `production` |
| `ADMIN_ALLOWED_EMAILS` | Emails admin (séparés par virgule) |
| `ADMIN_DEFAULT_PASSWORD` | Mot de passe initial du compte admin |
| `CORS_ORIGINS` | URL du frontend Render (ex: `https://horrorbot.onrender.com`) |

### Contraintes Render

- **RAM limitée** : utiliser obligatoirement un modèle quantifié Q4_K_M
- **Pas de GPU** : configurer `LLM_N_GPU_LAYERS=0`
- **Spin-down** : le free tier met en veille après 15 min d'inactivité
- **Cold start** : le chargement du modèle LLM prend ~30s au premier démarrage

## Vérification du déploiement

```bash
# 1. Inscription d'un utilisateur
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "email": "demo@example.com", "password": "demopass1234"}'

# 2. Login utilisateur (chatbot)
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demopass1234"}'

# 3. Chat synchrone (remplacer <token> par le access_token obtenu)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Recommande-moi un film comme Hereditary"}'

# 4. Chat streaming SSE
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Pourquoi le found footage est efficace ?"}'

# 5. Login admin (nécessite ADMIN_ALLOWED_EMAILS configuré)
curl -X POST http://localhost:8000/api/v1/auth/admin/token \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "adminpassword"}'

# 6. Health check (admin uniquement)
curl http://localhost:8000/api/v1/health \
  -H "Authorization: Bearer <admin_token>"

# 7. Métriques Prometheus (pas d'auth requise)
curl http://localhost:8000/metrics
```
