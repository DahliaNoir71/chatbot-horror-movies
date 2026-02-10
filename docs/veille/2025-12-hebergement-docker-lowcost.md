# Synthèse Veille Technique #2 — Hébergement dockerisé low-cost

**Période** : Décembre 2025
**Axe** : Veille technique — Solutions de déploiement

## Contexte

Comparatif des plateformes d'hébergement Docker adaptées au budget du projet HorrorBot (max 7€/mois) pour déployer une API FastAPI avec modèle LLM local.

## Plateformes évaluées

| Plateforme | Offre gratuite | RAM | Limitations | Pricing payant |
|------------|----------------|-----|-------------|----------------|
| **Railway** | 5$ crédits/mois | 512 Mo | Sleep après inactivité | 0.01$/h compute |
| **Render** | 750h/mois | 512 Mo | Spin-down après 15 min | 7$/mois starter |
| **Fly.io** | 3 VM 256 Mo | 256 Mo | RAM très limitée | 2$/mois VM shared-cpu |
| **Heroku** | Eco 5$/mois | Variable | Pas de free tier | 5$/mois eco dyno |

## Analyse détaillée

### Render (retenu)

- **Free tier** : 750h/mois, suffisant pour le développement
- **Starter** : 7$/mois, 512 Mo RAM, disque persistant
- **Avantages** : Déploiement Git automatique, certificat SSL, logs intégrés
- **Inconvénients** : Spin-down en free tier (cold start ~30s pour charger le LLM)

### Railway

- **Bonne alternative** : ratio performance/prix intéressant
- **Inconvénient** : 5$ crédits/mois peuvent être insuffisants pour un LLM actif

### Fly.io

- **RAM insuffisante** : 256 Mo ne permet pas de charger un LLM quantifié (minimum ~4 Go)
- **Configuration complexe** : fichier `fly.toml` nécessaire

### Heroku

- **Plus cher** que Render pour des specs équivalentes
- **Eco dynos** : 5$/mois avec limitations similaires à Render free

## Décision

**Render** retenu :

- Free tier suffisant pour le développement et les démos
- Upgrade 7$/mois en production (dans le budget)
- Déploiement Git-push simple et reproductible
- Compatible Docker et Python natif

## Contrainte identifiée

Aucune plateforme low-cost ne fournit de GPU. Le déploiement production utilisera obligatoirement le mode **CPU-only** (`LLM_N_GPU_LAYERS=0`) avec un modèle quantifié Q4_K_M.

## Sources

- [Render Documentation](https://render.com/docs) — Pricing et limitations
- [Railway Documentation](https://docs.railway.app) — Free tier details
- [Fly.io Documentation](https://fly.io/docs) — Configuration VMs
- [Reddit r/selfhosted](https://www.reddit.com/r/selfhosted/) — Retours d'expérience
