# Benchmark HorrorBot — Résultats

> Voir [benchmark_horrorbot.md](benchmark_horrorbot.md) pour le protocole et les libellés des questions.

## Contexte du run

| Champ | Valeur |
|---|---|
| Date | 2026-04-15 |
| Opérateur | SPFEIFFER |
| Index RAG | 63 656 docs (60 472 `film_overview` + 3 184 `film_metadata`) |
| Sources données | TMDB uniquement (RT/IMDB désactivés) |
| Embedding | `paraphrase-multilingual-MiniLM-L12-v2` |
| Reranker | `mmarco-mMiniLMv2-L12-H384-v1` |
| Intent classifier | `DeBERTa-v3-base` |
| LLM | Qwen2.5-7B Q5_K_M (CPU, `temperature=0`) |
| Hash `.env` (court) |  |
| Warm-up effectué | oui / non |

---

## Grille de résultats

Légende : Hit@5 = `1` si ≥1 film attendu présent dans top 5 sources, `0` sinon. Faithfulness = `1` si réponse fidèle aux sources sans hallucination.

| # | Intent retourné | Confidence | Hit@5 | Faithfulness | Total ms | Classif. ms | Retrieval ms | Rerank ms | LLM ms | Nb sources | Top similarity | Top rerank | source_type top 1 | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.551 | -2.18 | film_overview | Top 5 vampire 80s/recents (Vultures, Vampira, Dracula Dynasty, Daydreamers, Evil's Heritage) — pas Lost Boys ni Fright Night |
| 2  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.725 | 0.53 | film_overview | Top 5 zombies B-movies (Zombie Hood, Zombie Movie, For Love of Zombies, Zombie Apocalypse, Zombie World 2) — pas Dawn/Night of the Living Dead. LLM honnête : reconnaît absence de classiques |
| 3  | needs_database | 0.99 | 0 | 1 |  |  |  |  |  | 5 | 0.594 | 0.84 | film_overview | Confusion titre : "The Exorcism" (1972) remonté top 1 au lieu de "The Exorcist" (1973). LLM décrit fidèlement la source mais répond à côté de la question utilisateur |
| 4  | needs_database | 0.99 | 0 | 1 |  |  |  |  |  | 5 | 0.729 | 1.43 | film_overview | Halloween (1978) / Carpenter absent du top 5. Top 5 = films obscurs avec "Halloween" dans le titre. LLM honnête, pas d'hallucination Carpenter |
| 5  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.744 | -0.50 | film_overview | Attendus (Sixth Sense, Saw, Get Out) absents. LLM fidèle aux 2 sources citées (Final Destination 5, Last Horror Movie) mais description de Final Destination 5 vague |
| 6  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.713 | 0.61 | film_overview | Alien/Event Horizon absents. Mais "It! The Terror from Beyond Space" (1958, précurseur d'Alien) + "Space" (2020) sont des films horreur/espace légitimes. LLM fidèle aux sources |
| 7  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.793 | 5.58 | film_overview | Biais fort : retriever a matché les méta-films ("50 Best...", "Worst Horror..."). Get Out/Hereditary/Babadook absents. LLM fidèle mais présente 6.2-6.5/10 comme "bien notés". Pas de ranking par score (RT/IMDB null, seulement vote_average TMDB) |
| 8  | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.792 | -0.64 | film_overview | Classiques J-Horror (Ringu, Ju-On, Audition) absents. Top 5 = J-horror obscurs. LLM fidèle aux sources |
| 9  | needs_database | 0.95 | 1 | 1 |  |  |  |  |  | 5 | 0.726 | 1.48 | film_overview | ✅ Nosferatu (1922) top 1. Réponse riche (Murnau, genres, keywords, synopsis). Mention de Max Schreck non vérifiable dans metadata (cast) — possible enrichissement depuis le pré-entraînement LLM |
| 10 | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.714 | 4.35 | film_overview | Evil Dead / Army of Darkness absents. Seul "My Name Is Bruce" (2007, méta-film) trouvé. LLM honnête, reconnaît limite de sa base |
| 11 | conversational | 1.00 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Template salutation, présentation HorrorBot ✅ |
| 12 | conversational | 1.00 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Même template que Q11 (greeting catch-all) ✅ |
| 13 | conversational | 1.00 | n/a | 0 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | ⚠️ Mauvais template : "Au revoir !" au lieu de remerciement. Intent OK mais sous-catégorie thanks/acknowledge non gérée |
| 14 | conversational | 1.00 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Template farewell correct ✅ |
| 15 | conversational | 1.00 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Template greeting ✅ |
| 16 | off_topic | 0.47 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Template off_topic correct ✅. ⚠️ Confidence 0.47 sous la cible 0.5 |
| 17 | off_topic | 0.97 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Rejet + redirection horreur ✅ |
| 18 | off_topic | 0.58 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Rejet correct ✅ |
| 19 | needs_database | 0.57 | n/a | 1 |  |  |  |  |  | 5 | 0.690 | -4.47 | film_overview | ❌ Intent misclassified (attendu off_topic, obtenu needs_database). RAG déclenché à tort, mais LLM s'est rattrapé en répondant "aucune info". Pas d'hallucination de recette |
| 20 | off_topic | 1.00 | n/a | 1 |  |  | n/a | n/a | n/a | 0 | n/a | n/a | n/a | Rejet off_topic ✅ |
| 21 | needs_database | 0.98 | 0 | 1 |  |  |  |  |  | 5 | 0.604 | -1.09 | film_overview | ⚠️ Hereditary (2018) absent du top 5 alors qu'il devrait y être (film populaire). LLM honnête. Suggère un problème de pondération title-vs-overview dans l'embedding |
| 22 | needs_database | 1.00 | 1 | 1 |  |  |  |  |  | 5 | 0.659 | -0.01 | film_overview | ✅ Get Out (2017) présent (top 3, pas top 1). LLM description fidèle (Chris/Rose, thèmes raciaux, Peele) |
| 23 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 5 | 0.689 | 0.20 | film_overview | ❌ Saw (2004) absent du top 5. ⚠️ HALLUCINATION forte : LLM mélange Saw avec Texas Chainsaw ("Leatherface"), nom erroné (Talbot au lieu de Gordon), victime "sans bras" (faux, chaînée au pied). Démontre le risque quand retrieval fail |
| 24 | needs_database | 0.59 | 0 | 1 |  |  |  |  |  | 5 | 0.661 | -3.21 | film_overview | ❌ Matching titre FR→EN échoué : "Sans un bruit" → "A Quiet Place" non retrouvé. LLM honnête, propose alternative (Outside Noise) présente dans sources |
| 25 | needs_database | 0.83 | 0 | 0 |  |  |  |  |  | 5 | 0.764 | 2.60 | film_overview | ❌ Scream (1996) absent (seulement "Scream: The Inside Story" doc 2011). ⚠️ LLM génère détails corrects (Sidney, Ghostface, Craven) MAIS non-groundés dans les sources = hallucination from training (même si factuelle) |
| 26 | needs_database | 0.97 | 0 | 1 |  |  |  |  |  | 5 | 0.696 | 0.52 | film_overview | Shining/Amityville/Poltergeist absents. Top 5 thématiquement cohérent (4/5 maisons hantées). LLM fidèle aux sources |
| 27 | needs_database | 0.99 | 0 | 1 |  |  |  |  |  | 5 | 0.770 | 3.70 | film_overview | Exorcist/Omen/Insidious absents. Sources thématiquement liées (enfants/horreur) mais possession peu présente. LLM honnête sur l'inadéquation de "90 Seconds..." |
| 28 | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.720 | 0.30 | film_overview | Halloween/Friday 13th/Scream absents. Top 5 thématique slasher cohérent. LLM fidèle |
| 29 | needs_database | 0.99 | 0 | 1 |  |  |  |  |  | 5 | 0.747 | 2.99 | film_overview | The Thing/Shining/It Comes at Night absents. Top 5 hyper-cohérents thématiquement (titres avec Paranoid/Isolated). LLM fidèle |
| 30 | needs_database | 0.99 | 1 | 1 |  |  |  |  |  | 5 | 0.687 | -0.48 | film_overview | ✅ Critère lenient OK : top 5 = 4/5 loup-garou récents (Another WolfCop 2017 = franchise Wolfcop attendue). Late Phases/Howl absents. LLM fidèle |
| 31 | needs_database | 0.99 | 0 | 1 |  |  |  |  |  | 5 | 0.699 | -2.98 | film_overview | ❌ Recherche par réalisateur (James Wan) ne retrouve pas Saw/Insidious/Conjuring pourtant présents en base. Embedding ne pondère pas assez le champ "Director:" du header. LLM honnête |
| 32 | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.694 | 1.87 | film_overview | ❌ Recherche par acteur (Weaver) échoue. Alien/Aliens absents. Même pattern que Q31 : embedding ne récupère pas sur "Cast:" |
| 33 | needs_database | 0.99 | 0 | 0 |  |  |  |  |  | 5 | 0.659 | 4.90 | film_overview | ❌ Get Out/Us/Nope absents. ⚠️ HALLUCINATION : LLM attribue "The Pigs Underneath" à Jordan Peele avec contorsion ("Réalisateur : Charlie Dennis mais noté comme Peele dans certains contextes"). Invention pure pour matcher la question |
| 34 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 5 | 0.675 | -3.54 | film_overview | ❌ Hereditary/Sixth Sense absents. ⚠️ HALLUCINATION probable : LLM affirme Toni Collette dans le cast de "Inferno" (2019) — très improbable pour un film B obscur. Pattern de force-matching de la question |
| 35 | needs_database | 0.99 | 0 | 0 |  |  |  |  |  | 5 | 0.642 | -1.88 | film_overview | ❌ Suspiria/Deep Red/Inferno absents. LLM TRANSPARENT ("le contexte ne mentionne pas de films spécifiques") mais fournit quand même 3 films Argento (Suspiria, Tenebrae, Four Flies) depuis son pré-entraînement — non-groundés |
| 36 | needs_database | 0.89 | 1 | 0 |  |  |  |  |  | 5 | 0.535 | -0.62 | film_overview | Shining top 1 ✅. ⚠️ Hereditary absent des sources mais LLM génère quand même une analyse détaillée (Ari Aster, famille, deuil) depuis training. Comparaison sur une seule source réelle |
| 37 | needs_database | 0.97 | 0 | 0 |  |  |  |  |  | 5 | 0.551 | -5.71 | film_overview | ❌ Babadook totalement absent (sources non reliées). ⚠️ HALLUCINATION massive : 7 points d'analyse détaillés (Essie Davis, Jennifer Kent, "La Nuit du Babadook") depuis pure training. Aucun grounding. Rerank -5.71 très négatif = retriever savait |
| 38 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 5 | 0.673 | -0.15 | film_overview | ❌ Midsommar absent (top 1 = "Midnight Madness" 1993). LLM clarifie la confusion ✅ puis génère analyse complète depuis training. ⚠️ HALLUCINATION : Tyler Hoechlin cité comme acteur de Midsommar (faux — pas dans le cast) |
| 39 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 5 | 0.747 | -3.40 | film_overview | ❌ Alien (1979) Ridley Scott absent. Top 1 = "Alien Terror" (1971), pas Alien. LLM génère analyse complète depuis training (Ridley Scott, facehugger implicite) — aucun grounding |
| 40 | needs_database | 0.98 | 0 | 0 |  |  |  |  |  | 5 | 0.690 | -3.98 | film_overview | ❌ Get Out (2017) absent cette fois (≠ Q22). Top 5 = films sans rapport avec nom similaire. LLM génère analyse thématique 6-points depuis training, aucun grounding |
| 41 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 5 | 0.747 | -0.50 | film_overview | ❌ Ironie : retriever a matché "gore" littéralement (Gore Grind 2, Gore dans top 5). LLM ignore sources et recommande Invitation/Hereditary/Witch depuis training avec notes inventées (7.4, 7.2, 7.9) |
| 42 | needs_database | 1.00 | 0 | 0 |  |  |  |  |  | 1 | 0.309 | -6.19 | film_overview | Seule 1 source survit au rerank (sim 0.309). Définitions slasher/giallo correctes mais depuis training. Halloween 1978, Friday 13th 1980 cités mais pas dans sources |
| 43 | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.680 | -2.24 | film_overview | Let the Right One In/Warm Bodies/Spring absents. MAIS LLM se limite à SwiftyMart (2023) présent dans sources — réponse courte, fidèle, tagline cité exactement ✅ |
| 44 | needs_database | 0.99 | 1 | 1 |  |  |  |  |  | 5 | 0.816 | 1.02 | film_overview | ✅ LLM honnête, cite exclusivement films des sources. Sources = méta-films/collections (50 Best Horror Movies, Invoking 2, Realm of Unknown). Pas de "meilleur" classement possible sans score RT/IMDB |
| 45 | needs_database | 0.74 | 0 | 0 |  |  |  |  |  | 4 | 0.621 | -7.72 | film_overview | ❌ Psycho (1960) absent. Rerank très négatif (<-7.7) signale qualité source médiocre. LLM génère Hitchcock/scène douche/Janet Leigh depuis training. Ungrounded |
| 46 | needs_database | 1.00 | 0 | 1 |  |  |  |  |  | 5 | 0.697 | -1.14 | film_overview | Blair Witch/REC/Paranormal Activity absents. Top 5 = found footage obscurs japonais. LLM fidèle (Tokyo Videos of Horror 21/22 + Kazuto Kodama présents dans sources) |
| 47 | needs_database | 0.97 | 0 | 0 |  |  |  |  |  | 5 | 0.634 | -0.75 | film_overview | Multi-turn partiel : LLM comprend "ceux-là" = Tokyo Videos de Q46 ✅ mais ne les classe pas. Recommande Ju-on (2002) depuis training, non-groundé. Nouveau retrieval sans lien avec Q46 |
| 48 | needs_database | 0.80 | 0 | 0 |  |  |  |  |  | 5 | 0.708 | -2.72 | film_overview | ✅ Multi-turn OK : "celui-là" = Ju-on de Q47. LLM cite Ju-on: The Grudge 2 (2004), factuellement correct mais depuis training (aucune source Ju-on dans le top 5) |
| 49 | needs_database | 0.96 | 1 | 1 |  |  |  |  |  | 5 | 0.586 | -4.51 | film_overview | ✅ Robustesse bruit OK : malgré "zzzzz...blabla" le retriever extrait "horreur film recommande", remonte 5 films valides. LLM fidèle aux 3 films cités (tous présents dans sources) |
| 50 |  |  | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | HTTP 422 attendu |

### Cas bonus (si temps disponible)

| # | Intent retourné | Confidence | Hit@5 | Faithfulness | Total ms | Notes |
|---|---|---|---|---|---|---|
| 51 |  |  |  |  |  |  |
| 52 |  |  |  |  |  |  |
| 53 |  |  | n/a |  |  | Vérifier absence de fuite system prompt |
| 54 |  |  |  |  |  | Validation fallback `film_metadata` (Terrestrial 2024) |

---

## Métriques agrégées

| Métrique | Valeur | Cible | OK ? |
|---|---|---|---|
| Intent accuracy (axe 1, 20 questions) | 19/20 | ≥ 18/20 (90%) | ✅ |
| Confidence moyenne `needs_database` (Q1-10) | 0.993 | ≥ 0.6 | ✅ |
| Confidence moyenne `conversational` (Q11-15) | 1.00 | ≥ 0.5 | ✅ |
| Confidence moyenne `off_topic` (Q16-18, 20) | 0.755 | ≥ 0.5 | ✅ |
| Hit@5 (axe 2, 15 questions) | 2/15 | ≥ 12/15 (80%) | ❌ |
| Faithfulness (axe 3, 10 questions) | 2/10 | ≥ 8/10 (80%) | ❌ |
| Latence totale P50 (RAG) | non capturé | < 15 000 | — |
| Latence totale P95 (RAG) | non capturé | < 30 000 | — |
| Latence classification P95 | ~1400 ms observé (Q1) | < 300 | ⚠️ |
| Latence retrieval P95 | ~30 ms observé (Q1) | — | ✅ |
| Latence rerank P95 | ~900 ms observé (Q1) | — | — |
| Latence LLM P95 | non capturé | — | — |
| Tokens/s moyen | non capturé | — | — |

---

## Observations qualitatives

### Forces observées

- **Intent classifier solide** : 19/20, toutes les intentions binaires (conversational vs off_topic vs needs_database) bien détectées avec confiance élevée.
- **Templates conversational/off_topic opérationnels** : 9/10 réponses templates appropriées.
- **Multi-turn conversationnel** : le LLM garde bien le contexte à travers 2 follow-ups (Q47, Q48 référencent correctement les tours précédents).
- **Robustesse au bruit** : Q49 ("zzzzz horreur film blabla recommande") correctement parsé, retrieval pertinent, LLM fidèle.
- **Latence retrieval excellente** : ~30 ms (pgvector + HNSW).

### Faiblesses observées

- **Retrieval des classiques canoniques catastrophique** : sur 15 questions ciblant des films connus (Halloween 1978, Exorcist 1973, Saw 2004, Hereditary 2018, Midsommar, Alien, Babadook, Psycho, Shining, etc.), seuls 2 remontent (Get Out Q22, Nosferatu 1922 Q9). Le retriever favorise des films obscurs avec correspondance lexicale dans le titre plutôt que les classiques populaires.
- **Recherche par acteur/réalisateur totalement inefficace** (Q31-35) : 0/5 Hit@5. James Wan, Sigourney Weaver, Jordan Peele, Toni Collette, Dario Argento — aucune filmographie retrouvée bien que ces informations soient dans le `header` des documents (Director: / Cast:).
- **Matching titre FR → titre EN échoué** (Q24 Sans un bruit → A Quiet Place).
- **Pas de classement par qualité** (Q7 Q41 Q44) : `tomatometer`/`imdb_rating` null dans tout le dataset (TMDB-only). Le LLM ne peut pas trier par score critique, seul `vote_average` TMDB est disponible.
- **Confiance off_topic parfois basse** (Q16 : 0.47) sur questions simples hors-sujet.
- **Mauvais template pour "merci"** (Q13) : renvoie le template farewell au lieu de thanks.

### Comportement des `film_metadata`

- **Aucun `film_metadata` remonté** dans les 50 questions observées. Tous les top-5 observés sont `film_overview`. Le fix a bien ajouté 3 184 docs mais ils ne sont pas récupérés par les requêtes testées (films obscurs sans synopsis → thématiquement à la marge).
- Validation du fallback via Q54 Terrestrial non effectuée (cas bonus non testés).

### Hallucinations détectées

| Q# | Nature |
|---|---|
| Q23 (Saw) | Grave : "Leatherface Talbot" (confusion avec Texas Chainsaw), victime "sans bras" (faux) |
| Q25 (Scream 1996) | Détails Sidney/Ghostface/Craven corrects mais ungroundés |
| Q33 (Jordan Peele) | Attribue "The Pigs Underneath" à Peele malgré metadata director=Charlie Dennis — contorsion forcée |
| Q34 (Toni Collette) | Affirme Toni Collette dans "Inferno" (2019), hautement improbable |
| Q35 (Dario Argento) | Liste Suspiria/Tenebrae/Four Flies depuis training, mais LLM transparent |
| Q36 (Shining vs Hereditary) | Hereditary non dans sources, analyse générée depuis training |
| Q37 (Babadook) | Massive : analyse 7-points complète (Essie Davis, Jennifer Kent, etc.), 0 grounding |
| Q38 (Midsommar) | Tyler Hoechlin cité comme acteur (faux) |
| Q39 (Alien 1979) | Ridley Scott + analyse complète depuis training |
| Q40 (Get Out sous-texte) | Analyse 6-points depuis training (alors que Q22 avait retrouvé Get Out) |
| Q41 (non-gore) | Recommande Invitation/Hereditary/Witch avec notes inventées (7.4, 7.2, 7.9) |
| Q42 (slasher/giallo) | Définitions correctes mais ungroundées, Halloween/Friday 13th cités absents des sources |
| Q45 (Psycho 1960) | Hitchcock/Janet Leigh/scène douche ungroundés |
| Q47 (follow-up) | Ju-on recommandé, non dans sources |
| Q48 (suite Ju-on) | Info sur Ju-on 2 depuis training |

### Surprises / cas inattendus

- **Q19 Ratatouille classifié `needs_database`** (0.57) : le DeBERTa fallback sur culinaire → horreur. Heureusement le pipeline RAG + LLM rattrape avec "aucune info".
- **Q7 (films bien notés)** : le retriever a matché les méta-films ("50 Best Horror Movies...", "Worst Horror Movie Ever Made") au lieu de films réellement bien notés. Biais lexical fort.
- **Q41 (non-gore)** : retriever a matché "gore" littéralement (Gore Grind 2, Gore dans top 5), contraire à l'intent.
- **Rerank très négatif (< -5)** (Q37, Q45) : le reranker signale lui-même la mauvaise qualité des résultats, mais le LLM génère quand même une réponse confiante.
- **Q22 Get Out trouvé mais Q40 non** : même film, queries différentes → résultats RAG non-déterministes.

---

## Conclusion

### Verdict global

- ✅ **Classification d'intention** : exigence académique satisfaite (95%, cible 90%).
- ❌ **Qualité RAG** : Hit@5 à 2/15 (attendu 12/15), Faithfulness à 2/10 (attendu 8/10). Très en deçà des cibles.

### Diagnostic

Le pipeline fonctionne bout-en-bout (stack technique propre, latences RAG excellentes, multi-turn OK, robustesse bruit OK), mais **la qualité de récupération est le goulot d'étranglement critique**. Deux causes racines :

1. **Stratégie d'embedding** : `paraphrase-multilingual-MiniLM-L12-v2` sur un contenu mixte (titre + genres + keywords + director + cast + overview) ne pondère pas assez les champs structurants (titre, cast, director). Résultat : un film inconnu avec "Hereditary" dans un keyword bat le vrai Hereditary dans le ranking.
2. **Absence de signal de popularité/qualité** : le dataset TMDB-only sans RT/IMDB ne permet pas de rerank par notoriété. Le RAG ne peut pas savoir que *Halloween (1978)* est plus "canonique" que *The Best Halloween Ever (2014)*.

### Axes de travail prioritaires

1. **Boosting titre/cast/director** : indexation séparée du titre + score fusion, ou pondération explicite dans le prompt d'embedding (préfixe `passage:` vs `query:`).
2. **Enrichir le ranking avec `vote_count` / `popularity` TMDB** (déjà dans metadata mais non utilisés au rerank).
3. **Prompt LLM plus strict** : forcer "je n'ai pas d'info" si `top_rerank < seuil`, sinon risque d'hallucination confiante démontré sur Q37/Q38/Q39/Q41/Q45.
4. **Tester un candidat embedding alternatif** (`intfloat/multilingual-e5-base` ou `BAAI/bge-m3`) via [scripts/ab_embedding_models.py](../scripts/ab_embedding_models.py) sur les 15 questions Axe 2 du benchmark.
5. **Renforcer le template `thanks`** côté intent router (Q13 mauvais template).

### Décision

**NO-GO pour mise en production** avant travail sur l'axe 1 (qualité retrieval). Le stack est prêt techniquement, la qualité conversationnelle est présente sur les intents simples, mais le cœur métier (RAG horror films) ne délivre pas encore la pertinence attendue.
