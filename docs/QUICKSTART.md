# HorrorBot — Démarrage rapide

Guide pour lancer l'application en local depuis VS Code, après que le repo soit cloné et ouvert. Toutes les commandes se lancent depuis le terminal intégré (`Ctrl + ù`) à la racine du projet.

> Projet **CPU-only** (pas de GPU/CUDA). Tout tourne en `localhost`.

Suivre les sections **dans l'ordre §1 → §9**. Si une étape échoue, ne pas passer à la suivante.

---

## 0. Repartir de zéro (optionnel — état de validation propre)

À lancer si on veut tester le flow complet en partant d'une stack vierge (supprime **toutes** les données) :

```bash
docker compose down -v
```

Cela arrête tous les conteneurs, supprime les volumes (`pgdata`, `pgadmin`, `prometheus`, `grafana`) et le réseau Docker. Les bind mounts (`./models`, `./data`, `~/.cache/huggingface`) sont conservés.

---

## 1. Prérequis

- Docker Desktop avec Docker Compose v2 démarré
- `uv` ([astral.sh/uv](https://docs.astral.sh/uv/)) pour la gestion Python
- Fichier `.env` à la racine, déjà renseigné

---

## 2. Installer les dépendances Python

```bash
uv sync --group ml-api
```

---

## 3. Pré-télécharger les modèles IA

Sans cette étape, l'API met plusieurs minutes à démarrer à chaque run (warmup CPU du LLM Qwen 7B, embedding, classifier, reranker). Le script `init_models` les télécharge en local + dans le cache HuggingFace :

```bash
uv run python -m src.scripts.init_models
uv run python -m src.scripts.init_models --check
```

Téléchargement ciblé (si besoin) :

```bash
uv run python -m src.scripts.init_models --llm
uv run python -m src.scripts.init_models --classifier
uv run python -m src.scripts.init_models --embedding
uv run python -m src.scripts.init_models --reranker
```

Le GGUF du LLM est copié dans `./models/` (monté en volume dans le container `api`). Les autres modèles vont dans le cache HuggingFace (`~/.cache/huggingface/`), partagé via le bind mount par défaut de Docker Desktop.

---

## 4. Démarrer la stack Docker

Dans le terminal courant — build + démarrage en arrière-plan :

```bash
docker compose up -d --build
```

Dans un **nouveau terminal** (split VS Code, `Ctrl + Shift + 5`) — suivre le démarrage jusqu'à la ligne "All services ready", puis `Ctrl + C` pour quitter :

```bash
docker compose logs -f ready
```

L'ordre de démarrage est géré par `depends_on` + healthchecks : `db → api → frontend`, `prometheus → grafana`, `db → pgadmin`. Volumes montés sur `api` : `./models` (modèles IA) et `./data` (sortie ETL `rag_films.json` consommée par l'importer RAG).

---

## 5. Vérifier l'état des services

```bash
docker compose ps
```

Tous les services doivent être en `Up` avec `(healthy)` pour ceux qui ont un healthcheck (db, api, frontend).

> ⚠ **Services `healthy` ≠ données chargées.** À ce stade les bases sont vides : la table `films` et `rag_documents` ne seront peuplées qu'après §7 et §8. Le backend répondra `[]` sur `/films` et le chatbot ne trouvera rien tant que §7–§8 ne sont pas exécutées.

Si l'API est marquée `unhealthy` ou `restarting`, ouvrir un **nouveau terminal** par flux de logs (commandes bloquantes — `Ctrl + C` pour sortir) :

```bash
docker compose logs -f api
docker compose logs -f frontend
```

---

## 6. Initialiser le schéma applicatif et seeder les tables de référence

Le démarrage du conteneur `db` (§4) a déjà créé les bases vides via `docker/init-db/*.sql`. Il manque encore :

- les **tables applicatives** définies par les modèles SQLAlchemy (films, users, sessions, vectors, etc.)
- les **données de référence** (genres TMDB, langues ISO, registre RGPD) — pré-requises avant l'ETL §7

```bash
docker compose exec api uv run python -m src.scripts.init_database --seed
```

**Quand lancer cette commande :**

- ✅ Une fois après chaque `docker compose down -v` (suppression des volumes)
- ❌ Pas besoin après un simple `docker compose restart` ou `up -d` (les tables persistent dans le volume `pgdata`)

---

## 7. Lancer l'ETL (peuplement des données métier) — **OBLIGATOIRE**

> ⚠ **Étape facile à oublier.** Les services Docker `healthy` ne signifient pas que la base est peuplée. Sans cette étape, la table `films` reste vide et le backend renvoie des listes vides.

```bash
docker compose exec api uv run python -m src.etl.pipelines.main
```

Vérification à la fin :

```bash
docker compose exec db psql -U horrorbot_user -d horrorbot -c "SELECT COUNT(*) FROM films;"
```

Attendu : plusieurs milliers de lignes (dépend de `TMDB_MAX_PAGES`).

L'orchestrateur exécute 6 pipelines en séquence ([src/etl/pipelines/main.py](../src/etl/pipelines/main.py)) :

1. **TMDB** — extraction REST API (films, genres, keywords, credits)
2. **Kaggle CSV** — import dataset horror movies
3. **Spark** — analytics big data
4. **IMDB** — enrichissement
5. **Rotten Tomatoes** — scraping scores + critics consensus
6. **Aggregation** — export `data/processed/rag_films.json` (~50 MB, ~31 000 docs)

Arrête au premier échec. Durée : 30 min - 2 h selon `TMDB_MAX_PAGES` et la connectivité réseau.

---

## 8. Importer le corpus RAG (génération embeddings)

Lit `data/processed/rag_films.json`, génère les embeddings avec le modèle configuré (`EMBEDDING_MODEL_NAME`) et insère dans `horrorbot_vectors.rag_documents`.

```bash
docker compose exec api uv run python -m src.database.importer.rag_importer
```

Durée CPU : ~8-15 min pour ~31 000 documents avec `paraphrase-multilingual-MiniLM-L12-v2`.

Vérification :

```bash
docker compose exec db psql -U horrorbot_user -d horrorbot_vectors \
    -c "SELECT COUNT(*) FROM rag_documents;"
```

Attendu : ~31 244 lignes.

> **Si tu changes `EMBEDDING_MODEL_NAME` dans `.env`** : il faut TRUNCATE puis recréer le container API (`docker compose up -d --force-recreate api`) pour que la nouvelle var soit lue, puis relancer cette étape. Un simple `docker compose restart` ne relit pas `env_file`.

---

## 9. Accéder à l'application

**À quel moment ?** Le chatbot est **fonctionnel end-to-end** une fois que §8 est terminé (la commande `rag_importer` a rendu la main et le `SELECT COUNT(*) FROM rag_documents` retourne ~31 244). Avant §8, l'UI du chatbot se charge mais les requêtes RAG retourneront des résultats vides/erreurs — l'API a besoin que `rag_documents` soit peuplée.

Les URLs ci-dessous sont **joignables dès que les services sont `healthy`** (fin §5) — mais seul le chatbot nécessite §6-§8 pour répondre correctement. Les autres UIs (Grafana, pgAdmin, API docs) sont utilisables immédiatement.

| Service     | URL                                                       | Identifiants | Dispo après |
|-------------|-----------------------------------------------------------|--------------|-------------|
| **Chatbot** | [localhost:8080](http://localhost:8080)                   | —            | §8          |
| API Docs    | [localhost:8000/api/docs](http://localhost:8000/api/docs) | —            | §5          |
| Grafana     | [localhost:3000](http://localhost:3000)                   | cf. `.env`   | §5          |
| Prometheus  | [localhost:9090](http://localhost:9090)                   | —            | §5          |
| pgAdmin     | [localhost:5050](http://localhost:5050)                   | cf. `.env`   | §5          |
| PostgreSQL  | `localhost:5434`                                          | cf. `.env`   | §5          |

→ **Chatbot** : ouvrir [http://localhost:8080](http://localhost:8080) dans un navigateur une fois §8 terminé. Tester avec une requête FR type : "Quels films d'horreur japonais parlent de fantômes ?" — tu devrais voir des résultats pertinents (Paranormal Activity Tokyo Night, Yokai Monsters, etc.).

---

## 10. Commandes utiles

```bash
# Connexion aux bases
docker compose exec db psql -U horrorbot_user -d horrorbot
docker compose exec db psql -U horrorbot_user -d horrorbot_vectors

# Redémarrer un service (sans relire .env)
docker compose restart api

# Recréer un service (relit .env, applique les changements de docker-compose.yml)
docker compose up -d --force-recreate api

# Arrêter la stack (garde les volumes)
docker compose down

# Tout nettoyer (⚠ supprime les données — il faudra refaire §6-§8)
docker compose down -v

# Sandbox monitoring optionnelle (Prometheus/Grafana de test)
docker compose --profile monitoring-test up -d
# → Prometheus test : http://localhost:9091
# → Grafana test    : http://localhost:3001
```

---

## 11. Dépannage

```bash
# Healthcheck API qui échoue ?
docker compose logs api

# Reconstruire un service après changement de code
docker compose build api && docker compose up -d api

# Vérifier les volumes persistants
docker volume ls | grep horrorbot

# Vérifier que les vars d'env sont bien chargées dans le container
docker compose exec api env | grep -E "EMBEDDING|LLM|TMDB"
```
