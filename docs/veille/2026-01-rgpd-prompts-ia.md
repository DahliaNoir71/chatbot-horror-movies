# Synthèse Veille Réglementaire #2 — RGPD appliqué aux prompts utilisateurs

**Période** : Janvier 2026
**Axe** : Veille réglementaire — Conformité IA et protection des données

## Contexte

Analyse des recommandations de la CNIL sur le traitement des prompts utilisateurs dans les systèmes d'IA générative, appliquée au projet HorrorBot.

## Position de la CNIL

### Les prompts sont des données personnelles potentielles

La CNIL considère que les prompts soumis à un système d'IA générative peuvent constituer des **données personnelles** dès lors qu'ils contiennent des identifiants directs (nom, email) ou indirects (contexte permettant l'identification).

### Recommandations CNIL (juin 2024)

Les recommandations publiées par la CNIL pour les systèmes d'IA générative couvrent :

1. **Minimisation des données** : ne collecter que les données strictement nécessaires au traitement
2. **Information claire** : informer les utilisateurs de l'usage fait de leurs prompts
3. **Durée de conservation limitée** : ne pas conserver les prompts au-delà de la durée nécessaire
4. **Base légale** : identifier et documenter la base légale du traitement (consentement, intérêt légitime)
5. **Transparence** : indiquer clairement si les prompts sont utilisés pour entraîner le modèle

## Impact sur HorrorBot

### Architecture 100% locale — Conformité renforcée

L'architecture retenue pour HorrorBot offre une conformité RGPD renforcée :

| Aspect RGPD | Approche HorrorBot | Conformité |
|-------------|-------------------|------------|
| Transfert de données | Aucun transfert vers APIs cloud | Conforme |
| Conservation des prompts | Mémoire volatile (durée de session) | Conforme |
| Persistance conversations | Pas de stockage en base de données | Conforme |
| Sous-traitance | Aucun sous-traitant IA (modèle local) | Conforme |
| Entraînement sur prompts | Le modèle GGUF est statique (pas de fine-tuning) | Conforme |

### Avantages de l'approche locale

- **Pas de transfert hors UE** : les données restent sur le serveur hébergeant l'application
- **Pas de sous-traitant** : pas besoin de clause contractuelle avec un fournisseur d'IA cloud
- **Contrôle total** : la durée de rétention est maîtrisée (session uniquement)
- **Pas d'entraînement** : les prompts utilisateurs ne sont jamais utilisés pour modifier le modèle

### Actions documentées

- Pas de persistance des conversations en base de données
- Prompts traités en mémoire volatile et supprimés en fin de session
- Registre RGPD (`RGPDRegistry` dans le modèle de données) pour traçabilité des traitements

## Sources

- [CNIL — Recommandations IA générative (juin 2024)](https://www.cnil.fr/fr/intelligence-artificielle-la-cnil-publie-ses-premieres-recommandations) — Fiches pratiques
- [CNIL — RGPD et chatbots](https://www.cnil.fr/fr/chatbots-et-agents-conversationnels) — Guide sectoriel
- [EUR-Lex — RGPD](https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32016R0679) — Texte officiel
- [ANSSI — Guides sécurité IA](https://www.ssi.gouv.fr) — Recommandations techniques
