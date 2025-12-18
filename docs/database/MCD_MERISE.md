# Modèle Conceptuel de Données (MCD) - HorrorBot

**Méthode** : MERISE  
**Projet** : HorrorBot - Chatbot RAG Films d'Horreur  
**Version** : 1.0  
**Date** : 2025-12-17  
**Auteur** : Serge PFEIFFER

---

## 1. Diagramme MCD

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MODÈLE CONCEPTUEL DE DONNÉES                        │
│                              HorrorBot - Merise                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────────────────────┐
    │               FILM                    │
    ├───────────────────────────────────────┤
    │ #tmdb_id (PK)                         │
    │  imdb_id                              │
    │  title                                │
    │  original_title                       │
    │  year                                 │
    │  release_date                         │
    │  vote_average                         │
    │  vote_count                           │
    │  popularity                           │
    │  tomatometer_score                    │
    │  audience_score                       │
    │  certified_fresh                      │
    │  critics_count                        │
    │  audience_count                       │
    │  critics_consensus                    │
    │  overview                             │
    │  tagline                              │
    │  runtime                              │
    │  original_language                    │
    │  rotten_tomatoes_url                  │
    │  poster_path                          │
    │  backdrop_path                        │
    │  incomplete                           │
    │  created_at                           │
    │  updated_at                           │
    └───────────────────────────────────────┘
                       │
                       │ 1,1
                       │
                       ◇ POSSEDER
                       │
                       │ 0,n
                       ▼
    ┌───────────────────────────────────────┐
    │               GENRE                   │
    ├───────────────────────────────────────┤
    │ #genre_id (PK)                        │
    │  name                                 │
    └───────────────────────────────────────┘


    ┌───────────────────────────────────────┐
    │               FILM                    │
    └───────────────────────────────────────┘
                       │
                       │ 1,1
                       │
                       ◇ AVOIR
                       │
                       │ 0,1
                       ▼
    ┌───────────────────────────────────────┐
    │            EMBEDDING                  │
    ├───────────────────────────────────────┤
    │ #embedding_id (PK)                    │
    │  vector                               │
    │  source_text                          │
    │  source_type                          │
    │  created_at                           │
    └───────────────────────────────────────┘


    ┌───────────────────────────────────────┐
    │               FILM                    │
    └───────────────────────────────────────┘
                       │
                       │ 0,n
                       │
                       ◇ PROVENIR
                       │
                       │ 1,1
                       ▼
    ┌───────────────────────────────────────┐
    │              SOURCE                   │
    ├───────────────────────────────────────┤
    │ #source_id (PK)                       │
    │  name                                 │
    │  type                                 │
    │  url                                  │
    └───────────────────────────────────────┘
```

---

## 2. Dictionnaire des Entités

### FILM
Entité centrale représentant un film d'horreur agrégé depuis plusieurs sources.

| Propriété | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| tmdb_id | Entier | ✅ | Identifiant unique TMDB (clé primaire) |
| imdb_id | Chaîne(10) | ❌ | Identifiant IMDB (format tt0000000) |
| title | Chaîne(500) | ✅ | Titre du film (langue cible) |
| original_title | Chaîne(500) | ❌ | Titre original (langue source) |
| year | Entier | ✅ | Année de sortie (1888-2030) |
| release_date | Date | ❌ | Date de sortie complète |
| vote_average | Décimal(3,1) | ✅ | Note moyenne TMDB (0-10) |
| vote_count | Entier | ✅ | Nombre de votes TMDB |
| popularity | Décimal(10,3) | ✅ | Score popularité TMDB |
| tomatometer_score | Entier | ❌ | Score critiques RT (0-100) |
| audience_score | Entier | ❌ | Score audience RT (0-100) |
| certified_fresh | Booléen | ❌ | Label "Certified Fresh" RT |
| critics_count | Entier | ❌ | Nombre de critiques RT |
| audience_count | Entier | ❌ | Nombre d'avis audience RT |
| critics_consensus | Texte | ❌ | Consensus critique RT (priorité RAG) |
| overview | Texte | ❌ | Synopsis du film |
| tagline | Chaîne(500) | ❌ | Accroche marketing |
| runtime | Entier | ❌ | Durée en minutes (1-1000) |
| original_language | Chaîne(2) | ❌ | Code langue ISO 639-1 |
| rotten_tomatoes_url | Texte | ❌ | URL page Rotten Tomatoes |
| poster_path | Chaîne(255) | ❌ | Chemin poster TMDB |
| backdrop_path | Chaîne(255) | ❌ | Chemin backdrop TMDB |
| incomplete | Booléen | ❌ | Flag données incomplètes |
| created_at | Timestamp | ✅ | Date création enregistrement |
| updated_at | Timestamp | ✅ | Date dernière modification |

### GENRE
Entité représentant un genre cinématographique.

| Propriété | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| genre_id | Entier | ✅ | Identifiant unique genre |
| name | Chaîne(50) | ✅ | Nom du genre (Horror, Thriller...) |

### EMBEDDING
Entité représentant un vecteur d'embedding pour la recherche sémantique RAG.

| Propriété | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| embedding_id | Entier | ✅ | Identifiant unique embedding |
| vector | Vector(384) | ✅ | Vecteur 384 dimensions (MiniLM-L6-v2) |
| source_text | Texte | ✅ | Texte source ayant généré l'embedding |
| source_type | Chaîne(20) | ✅ | Type source (critics_consensus, overview) |
| created_at | Timestamp | ✅ | Date génération embedding |

### SOURCE
Entité représentant une source de données ETL.

| Propriété | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| source_id | Entier | ✅ | Identifiant unique source |
| name | Chaîne(50) | ✅ | Nom source (TMDB, Rotten Tomatoes, Kaggle...) |
| type | Chaîne(20) | ✅ | Type source (api_rest, scraping, csv, bdd, bigdata) |
| url | Texte | ❌ | URL de la source |

---

## 3. Dictionnaire des Associations

### POSSEDER (FILM — GENRE)
Un film possède un ou plusieurs genres. Un genre peut être associé à plusieurs films.

| Cardinalité côté FILM | Cardinalité côté GENRE |
|-----------------------|------------------------|
| 1,1 (tout film a au moins 1 genre) | 0,n (un genre peut n'avoir aucun film) |

**Règle de gestion** : RG1 - Tout film doit avoir au minimum le genre "Horror".

### AVOIR (FILM — EMBEDDING)
Un film peut avoir un embedding vectoriel pour la recherche sémantique.

| Cardinalité côté FILM | Cardinalité côté EMBEDDING |
|-----------------------|----------------------------|
| 1,1 (l'embedding appartient à 1 seul film) | 0,1 (un film peut ne pas avoir d'embedding) |

**Règle de gestion** : RG2 - L'embedding est généré depuis `critics_consensus` (prioritaire) ou `overview`.

### PROVENIR (FILM — SOURCE)
Un film provient d'une source de données ETL.

| Cardinalité côté FILM | Cardinalité côté SOURCE |
|-----------------------|-------------------------|
| 0,n (une source fournit plusieurs films) | 1,1 (un film a une source principale) |

**Règle de gestion** : RG3 - La source TMDB est la source de vérité (tmdb_id = clé primaire).

---

## 4. Règles de Gestion

| Code | Règle | Entité/Association |
|------|-------|-------------------|
| RG1 | Tout film indexé doit appartenir au genre "Horror" | FILM, POSSEDER |
| RG2 | L'embedding est généré depuis critics_consensus ou overview | EMBEDDING |
| RG3 | TMDB est la source de vérité (tmdb_id = identifiant unique) | FILM, SOURCE |
| RG4 | Un film ne peut avoir qu'un seul embedding actif | AVOIR |
| RG5 | L'année de sortie doit être comprise entre 1888 et année courante | FILM |
| RG6 | Les scores RT sont optionnels (enrichissement scraping) | FILM |
| RG7 | Les données sont agrégées depuis 5 sources hétérogènes minimum | SOURCE |

---

## 5. Passage MCD → MLD

### Règles de transformation appliquées

1. **Entité → Table** : Chaque entité devient une table
2. **Identifiant → Clé primaire** : L'identifiant devient PK
3. **Association 1,1 — 0,n** : La clé étrangère migre côté 1,1
4. **Association n,m** : Création table de jointure

### MLD Résultant

```
FILM (tmdb_id PK, imdb_id, title, original_title, year, release_date,
      vote_average, vote_count, popularity, tomatometer_score, audience_score,
      certified_fresh, critics_count, audience_count, critics_consensus,
      overview, tagline, runtime, original_language, rotten_tomatoes_url,
      poster_path, backdrop_path, incomplete, created_at, updated_at)

GENRE (genre_id PK, name)

FILM_GENRE (film_id FK→FILM, genre_id FK→GENRE)  -- Table de jointure

EMBEDDING (embedding_id PK, film_id FK→FILM UNIQUE, vector, source_text,
           source_type, created_at)

SOURCE (source_id PK, name, type, url)
```

**Note** : Dans l'implémentation actuelle, les genres sont stockés en JSONB dans la table FILM pour simplifier les requêtes (dénormalisation contrôlée).

---

## 6. Passage MLD → MPD (PostgreSQL)

Voir fichier `MLD.md` pour le schéma physique complet avec :
- Types PostgreSQL spécifiques
- Contraintes CHECK
- Index (B-tree, GIN, HNSW pgvector)
- Triggers audit

---

## 7. Diagramme Entité-Association Simplifié

```
                                    ┌─────────┐
                                    │  SOURCE │
                                    └────┬────┘
                                         │
                                    provenir
                                    (0,n-1,1)
                                         │
┌───────┐     posséder      ┌────────────┴────────────┐     avoir       ┌───────────┐
│ GENRE │◄────(1,1-0,n)────►│          FILM           │◄───(1,1-0,1)───►│ EMBEDDING │
└───────┘                   └─────────────────────────┘                 └───────────┘
                                      │
                                      │ Clé primaire: tmdb_id
                                      │ Source vérité: TMDB API
                                      │
```

---

## 8. Justification Choix de Conception

### Pourquoi tmdb_id comme clé primaire ?
- TMDB est la source la plus complète et fiable
- Identifiant stable et universel
- Permet déduplication lors agrégation multi-sources

### Pourquoi genres en JSONB ?
- Simplifie les requêtes (pas de jointure)
- Performances optimales avec index GIN
- Flexibilité (genres peuvent varier selon sources)

### Pourquoi embedding dans table séparée ?
- Séparation des responsabilités (données vs. IA)
- Permet régénération embeddings sans modifier films
- Facilite migration vers autre modèle d'embedding

### Pourquoi SOURCE comme entité ?
- Traçabilité origine des données (conformité RGPD)
- Permet audit et statistiques par source
- Facilite ajout nouvelles sources ETL

---

**Document conforme au formalisme MERISE**  
**Validation E1 - Critère C4 : Modélisation données**