# Synthèse Veille Technique #5 — Choix du modèle LLM pour HorrorBot

**Période** : Février 2026
**Axe** : Veille technique — Sélection et compatibilité des modèles LLM locaux

## Contexte

Suite à l'intégration initiale de **Qwen3-8B** (Q4_K_M) comme LLM local, des problèmes de compatibilité binaire ont été rencontrés sur Windows avec `llama-cpp-python`. Cette veille compare les modèles candidats et justifie la migration vers **Qwen2.5-7B-Instruct**.

## Problème rencontré avec Qwen3-8B

L'inférence provoquait l'erreur `Windows Error 0xc000001d` (`STATUS_ILLEGAL_INSTRUCTION`) :

- **Cause** : Le modèle Qwen3-8B nécessite `llama-cpp-python` >= 0.3.10, mais les wheels CUDA Windows officiels ne sont disponibles que jusqu'à la version 0.3.4 sur l'index `abetlen/llama-cpp-python`
- **Wheel custom testé** : Un wheel tiers (`dougeeai/llama-cpp-python-wheels`, CUDA 13.0 + SM89 Ada) était compilé avec des instructions CPU non supportées par le matériel cible
- **Impact** : Le modèle se chargeait mais plantait systématiquement à la première inférence

## Modèles évalués

| Modèle | Taille | Quantification | Compatibilité llama-cpp 0.3.4 | Chat template | Licence |
|--------|--------|----------------|-------------------------------|---------------|---------|
| **Qwen3-8B** | 8B | Q4_K_M (5 Go) | Non (format GGUF trop récent) | ChatML | Apache 2.0 |
| **Qwen2.5-7B-Instruct** | 7B | Q5_K_M (5.5 Go) | Oui | ChatML | Apache 2.0 |
| **Llama 3.1-8B-Instruct** | 8B | Q4_K_M (4.9 Go) | Oui | Llama 3 | Llama License |
| **Mistral-7B-Instruct-v0.3** | 7B | Q4_K_M (4.4 Go) | Oui | Mistral Instruct | Apache 2.0 |
| **Phi-3-mini-4k** | 3.8B | Q4_K_M (2.4 Go) | Oui | ChatML | MIT |

## Critères de sélection

1. **Compatibilité wheels CUDA Windows** : Le modèle doit fonctionner avec `llama-cpp-python` 0.3.4 (dernière version avec wheel CUDA Windows officiel)
2. **Qualité en français** : Réponses fluides en français (langue principale du chatbot)
3. **Support ChatML** : Compatibilité avec l'API `create_chat_completion()` de llama-cpp-python
4. **Taille mémoire** : Doit tenir dans 8 Go VRAM (RTX 2000 Ada)
5. **Licence open-source** : Pas de restriction commerciale

## Analyse comparative

### Qwen2.5-7B-Instruct (retenu)

- **Multilingue excellent** : Entraîné sur des données multilingues incluant le français, performances supérieures à Llama 3.1 sur les benchmarks non-anglais
- **ChatML natif** : Utilise le format `<|im_start|>` / `<|im_end|>`, compatible avec l'API chat de llama-cpp-python sans template custom
- **Quantification Q5_K_M** : Meilleur ratio qualité/taille que Q4_K_M, reste dans le budget VRAM (5.5 Go)
- **Cohérence avec chatbot-api** : Le projet référence (`chatbot-api`) utilise déjà Qwen2.5-7B-Instruct avec succès

### Llama 3.1-8B-Instruct

- **Bon en anglais** : Performances de pointe sur les benchmarks anglophones
- **Français limité** : Qualité inférieure à Qwen2.5 sur les tâches en français
- **Template spécifique** : Nécessite le format Llama 3 (`<|begin_of_text|>`, `<|start_header_id|>`)
- **Licence restrictive** : Llama Community License (restrictions > 700M utilisateurs)

### Mistral-7B-Instruct-v0.3

- **Bon en français** : Développé par Mistral AI (France), bon support multilingue
- **Performances inférieures** : Benchmarks légèrement en dessous de Qwen2.5-7B sur les tâches de raisonnement
- **Template spécifique** : Format `[INST]` / `[/INST]`

### Phi-3-mini-4k

- **Très léger** : 2.4 Go, idéal pour le déploiement CPU
- **Contexte limité** : 4k tokens maximum (insuffisant pour RAG avec historique de conversation)
- **Anglais principalement** : Support français limité

## Décision

**Qwen2.5-7B-Instruct** (Q5_K_M) retenu pour les raisons suivantes :

1. **Compatible** avec `llama-cpp-python` 0.3.4 (wheel CUDA Windows officiel)
2. **Meilleur support français** parmi les modèles 7-8B open-source
3. **Format ChatML natif** : Aucune adaptation de template nécessaire
4. **Éprouvé** : Déjà utilisé avec succès dans le projet `chatbot-api`
5. **Quantification Q5_K_M** : Qualité supérieure au Q4_K_M de Qwen3 pour une taille similaire

## Migration effectuée

| Élément | Avant | Après |
|---------|-------|-------|
| Modèle | Qwen3-8B Q4_K_M | Qwen2.5-7B-Instruct Q5_K_M |
| llama-cpp-python | 0.3.16 (wheel custom) | 0.3.4 (wheel officiel cu124) |
| Source wheel | `dougeeai/llama-cpp-python-wheels` | `abetlen.github.io/llama-cpp-python/whl/cu124` |
| Repo HuggingFace | `Qwen/Qwen3-8B-GGUF` | `bartowski/Qwen2.5-7B-Instruct-GGUF` |

## Sources

- [Qwen2.5 Technical Report](https://arxiv.org/abs/2412.15115) — Benchmarks multilingues
- [llama-cpp-python Releases](https://github.com/abetlen/llama-cpp-python/releases) — Historique des versions et wheels
- [abetlen CUDA Wheels Index](https://abetlen.github.io/llama-cpp-python/whl/cu124/) — Disponibilité par plateforme
- [Open LLM Leaderboard](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) — Comparaison des performances
- [Reddit r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/) — Retours d'expérience compatibilité Windows
