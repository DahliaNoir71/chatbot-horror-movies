# Deployment Guide — HorrorBot

## Prérequis

- **Docker** et **Docker Compose** v2+
- **Python 3.12** avec **uv** (gestionnaire de dépendances)
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
uv run python -m http.server 8080 --directory src/integration/
```

Interface chatbot : <http://localhost:8080>

Endpoints disponibles :

- API : http://localhost:8000/api/docs
- Métriques Prometheus : http://localhost:8000/metrics
- Health check : http://localhost:8000/api/v1/health
- Chat synchrone : POST http://localhost:8000/api/v1/chat
- Chat streaming : POST http://localhost:8000/api/v1/chat/stream

## Déploiement Production (Render)

### Configuration Render

- **Service Type** : Web Service
- **Runtime** : Docker ou Python 3.12
- **Plan** : Starter (7$/mois, 512 Mo RAM minimum)
- **Build Command** : `uv sync --group ml`
- **Start Command** : `uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`

### Variables d'environnement Render

Configurer via le dashboard Render :

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | URL PostgreSQL Render |
| `JWT_SECRET_KEY` | Clé secrète ≥32 chars |
| `LLM_MODEL_PATH` | Chemin vers le fichier GGUF |
| `LLM_N_GPU_LAYERS` | `0` (CPU only sur Render) |
| `ENVIRONMENT` | `production` |

### Contraintes Render

- **RAM limitée** : utiliser obligatoirement un modèle quantifié Q4_K_M
- **Pas de GPU** : configurer `LLM_N_GPU_LAYERS=0`
- **Spin-down** : le free tier met en veille après 15 min d'inactivité
- **Cold start** : le chargement du modèle LLM prend ~30s au premier démarrage

## Vérification du déploiement

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Métriques Prometheus
curl http://localhost:8000/metrics

# Authentification
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "demopass1234"}'

# Chat synchrone (remplacer <token> par le access_token obtenu)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Recommande-moi un film comme Hereditary"}'

# Chat streaming SSE
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Pourquoi le found footage est efficace ?"}'
```
