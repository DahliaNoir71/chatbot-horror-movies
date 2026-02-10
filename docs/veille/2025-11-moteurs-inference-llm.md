# Synthèse Veille Technique #1 — Moteurs d'inférence LLM locaux

**Période** : Novembre 2025
**Axe** : Veille technique — LLM locaux et architecture RAG on-premise

## Contexte

Cette synthèse compare les moteurs d'inférence LLM open-source pour exécution locale, dans le cadre du choix technologique pour le projet HorrorBot (chatbot RAG films d'horreur).

## Moteurs évalués

### llama.cpp

- **Description** : Moteur C++ optimisé pour l'inférence de LLM quantifiés au format GGUF
- **Bindings Python** : `llama-cpp-python` (API stable, support CUDA)
- **Performances** :
  - Llama 3.1-8B Q4_K_M : 4.9 Go VRAM, 18-25 tokens/s sur GPU GTX 1660 Ti
  - Mode CPU AVX2 : 8-12 tokens/s sur processeurs récents
- **Points forts** : contrôle fin de la quantification, API server compatible OpenAI, communauté très active
- **Points faibles** : compilation CMake nécessaire sans wheels pré-compilées

### Ollama

- **Description** : Surcouche Go sur llama.cpp, orientée prototypage rapide
- **Points forts** : Installation one-liner, CLI intuitive, catalogue de modèles intégré
- **Points faibles** : Couche d'abstraction supplémentaire réduisant le contrôle, peu adapté pour une intégration fine dans un pipeline RAG Python

### vLLM

- **Description** : Moteur haute performance avec PagedAttention pour throughput élevé
- **Points forts** : Performances supérieures en multi-utilisateurs, gestion dynamique de la mémoire GPU
- **Points faibles** : Nécessite GPU CUDA avec >8 Go VRAM, inadapté au déploiement CPU-only

### LocalAI

- **Description** : API compatible OpenAI supportant multiples backends
- **Points forts** : Drop-in replacement pour l'API OpenAI
- **Points faibles** : Overhead de compatibilité, moins performant que llama.cpp natif

## Décision

**llama.cpp** retenu via le package Python `llama-cpp-python` pour les raisons suivantes :

1. Contrôle total sur les paramètres d'inférence (température, top_p, contexte)
2. Support natif des modèles GGUF quantifiés (Q4_K_M pour le budget RAM)
3. Viabilité du déploiement CPU (8-12 tokens/s suffisant pour un chatbot)
4. Bindings Python stables avec API de haut niveau
5. Pas de dépendance réseau (exécution 100% locale)

## Sources

- [llama.cpp GitHub](https://github.com/ggerganov/llama.cpp) — Releases et benchmarks
- [Ollama](https://ollama.com) — Documentation officielle
- [vLLM](https://docs.vllm.ai) — Documentation technique
- [HuggingFace Blog](https://huggingface.co/blog) — Articles sur l'inférence locale
- [Reddit r/LocalLLaMA](https://www.reddit.com/r/LocalLLaMA/) — Retours d'expérience communautaires
