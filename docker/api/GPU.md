# Exécution GPU (NVIDIA, llama-cpp) — WSL2 + Docker natif

> Cette branche (`feat/gpu`) offloade **le LLM** sur le GPU NVIDIA. L'embedding,
> le reranker et le classifier **restent CPU** (le LLM ≈ 95 % de la latence ; la
> VRAM 8 Go de la RTX 2000 Ada est trop juste pour tout mettre dessus).
> Gain attendu : ~90 s → quelques secondes par réponse.

## Pré-requis (hôte / WSL — une seule fois)

1. **Driver NVIDIA Windows** : déjà présent (≥ 596, supporte le passthrough WSL2).
   Ne **pas** installer de driver NVIDIA *dans* WSL (casserait le passthrough).
2. **Vérifier le passthrough** dans la distro WSL : `nvidia-smi` doit afficher la carte.
3. **NVIDIA Container Toolkit** dans la distro WSL qui héberge Docker :
   ```bash
   sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo service docker restart
   ```
4. **Gate (go/no-go)** — l'accès GPU depuis Docker (le seul vrai inconnu, p.ex. EDR) :
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
   ```
   Doit afficher la RTX 2000. Sinon → problème toolkit/EDR, pas applicatif.

## Build & run

```bash
docker compose -f docker-compose.yml build api
docker compose -f docker-compose.yml up -d --force-recreate api
docker compose -f docker-compose.yml logs -f api
```

Au boot, le log llama-cpp doit montrer les couches offloadées
(`offloaded 29/29 layers to GPU` ou similaire) et `nvidia-smi` la VRAM occupée
par le process.

## Tuning VRAM (8 Go — si OOM au chargement)

Dans l'ordre, du moins au plus impactant :

1. **Offload partiel** : `LLM_N_GPU_LAYERS=24` (au lieu de `-1`) dans `.env` — laisse ~1-2 Go de marge.
2. **Contexte** : `LLM_CONTEXT_LENGTH=3072` (au lieu de 4096).
3. **Quantization** : passer le GGUF en **Q4_K_M** (~4,4 Go vs ~5,4 Go) — grosse marge, qualité quasi identique. Repeupler le volume modèles en conséquence.

Repère : Qwen2.5-7B Q5_K_M (~5,4 Go) + KV-cache (~0,5 Go) + buffers (~1 Go) ≈ ~7 Go.

## Rollback (revenir CPU)

La stack CPU vit sur `main` / `feat/chatbot-demo-tuning`. Pour rebasculer :
```bash
git checkout feat/chatbot-demo-tuning
docker compose -f docker-compose.yml build api
docker compose -f docker-compose.yml up -d --force-recreate api
```

## À faire si la bascule GPU devient définitive

- Mettre à jour `CLAUDE.md` (la stack n'est plus « CPU-only »).
- Aligner la version CUDA du base image (`12.4.1`) et de l'index de wheel
  llama-cpp (`cu124`) si tu changes l'une des deux.
