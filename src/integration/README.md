# HorrorBot — Client d'integration API IA

> **Livrable C10 (E3)** : demonstration de la consommation des endpoints IA
> (`/chat` synchrone, `/chat/stream` SSE) avec authentification JWT.

## Architecture modulaire

Le client est structure en modules ES6 separes, chacun mappant vers un futur
composant Vue.js / Pinia prevu pour E4 :

| Module E3                | Role                          | Futur E4                  |
|--------------------------|-------------------------------|---------------------------|
| `js/api-client.js`       | Client HTTP generique (fetch) | `services/api.ts`         |
| `js/auth-service.js`     | Auth JWT (login, refresh)     | `stores/auth.ts` (Pinia)  |
| `js/chat-service.js`     | Chat sync + stream SSE        | `stores/chat.ts` (Pinia)  |
| `js/ui.js`               | Manipulation DOM              | `ChatView.vue`, `LoginView.vue` |
| `js/app.js`              | Orchestration / init          | `App.vue` + `router/`     |

## Prerequis

- Python 3.12 et [uv](https://docs.astral.sh/uv/)
- Le serveur API HorrorBot en fonctionnement (PostgreSQL + modeles IA charges)

## Lancement

### 1. Demarrer le serveur API

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Le client est monte automatiquement via `FastAPI.StaticFiles` sur `/client/`.

### 2. Ouvrir dans le navigateur

Aller sur [http://localhost:8000/client/](http://localhost:8000/client/).

Pas besoin de second serveur : le client est servi par la meme instance
FastAPI que l'API (meme origine, pas de probleme CORS, Docker-ready).

## Identifiants de demo

| Utilisateur | Mot de passe      |
|-------------|-------------------|
| `demo`      | `demopass123`     |
| `admin`     | `horrorbot2024!`  |

## Fonctionnalites demonstrees

1. **Authentification JWT** : login, stockage token (localStorage),
   countdown d'expiration, renouvellement automatique 2 min avant expiration
2. **Chat synchrone** (`/api/v1/chat`) : envoi de message, affichage
   reponse + badge intent colore + score de confiance
3. **Chat streaming** (`/api/v1/chat/stream`) : reception SSE via
   `fetch` + `ReadableStream` (POST, donc `EventSource` inutilisable),
   affichage progressif des tokens
4. **Sessions multi-turn** : persistance du `session_id` entre messages,
   bouton "Nouvelle session" pour reinitialiser

## Tests d'integration

Les tests Python verifient le contrat API sans base de donnees ni
modeles IA (tout est mocke).

```bash
# Depuis la racine du projet
uv run pytest tests/integration/ -v --no-cov
```

### Couverture

| Fichier               | Cas testes                                        |
|-----------------------|---------------------------------------------------|
| `test_auth_flow.py`   | Login valide/invalide, validation Pydantic, token acces/expire/renouvellement |
| `test_chat_api.py`    | Reponse par intent, schema, multi-turn, validation entree |
| `test_chat_sse.py`    | Content-Type SSE, chunks, event done, concatenation, erreur 503 |

## Notes techniques

- **SSE depuis POST** : le endpoint `/chat/stream` utilise `POST` avec
  `EventSourceResponse` (sse-starlette). Le navigateur ne peut pas utiliser
  l'API `EventSource` (qui ne supporte que GET). Le client utilise donc
  `fetch()` + `response.body.getReader()` + `TextDecoder` pour parser
  manuellement le flux SSE.

- **Token auto-refresh** : les credentials sont stockes uniquement en
  memoire (closure JavaScript), jamais en `localStorage`, pour limiter
  la surface d'attaque. Le refresh se declenche 2 minutes avant
  l'expiration du token (par defaut 30 min).

- **StaticFiles** : le client est monte via `FastAPI.StaticFiles` dans
  `_mount_integration_client()` (`src/api/main.py`). Il est servi sur
  `/client/` depuis le meme serveur que l'API, eliminant tout probleme
  CORS. Le JS detecte automatiquement l'origine pour utiliser des chemins
  relatifs (`app.js` : `API_BASE = ''` si meme origine).
