# Synthèse Veille Réglementaire #1 — AI Act et chatbots conversationnels

**Période** : Décembre 2025
**Axe** : Veille réglementaire — Conformité IA et protection des données

## Contexte

Analyse de l'impact du Règlement européen sur l'intelligence artificielle (AI Act, Règlement (UE) 2024/1689) sur les systèmes de chatbots conversationnels, appliquée au projet HorrorBot.

## Points clés de l'AI Act

### Classification des chatbots

Les chatbots conversationnels sont classés en catégorie **« risque limité »** (Article 52) :

- Pas de classification « haut risque » (le chatbot ne prend pas de décisions impactant les droits fondamentaux des utilisateurs)
- Obligation principale : **transparence** — l'utilisateur doit être informé qu'il interagit avec un système d'IA

### Calendrier d'application

| Date | Obligation |
|------|-----------|
| Février 2025 | Obligations de transparence pour les systèmes conversationnels |
| Août 2025 | Codes de bonnes pratiques |
| Août 2026 | Obligations complètes pour les systèmes à haut risque |

### Obligations de transparence (Article 52)

Pour un chatbot comme HorrorBot :

1. **Information claire** : l'utilisateur doit savoir qu'il interagit avec une IA
2. **Pas d'usurpation** : le système ne doit pas se faire passer pour un humain
3. **Contenu généré** : les réponses doivent être identifiables comme produites par IA

## Impact sur HorrorBot

### Actions requises

- Ajout d'un **bandeau d'information** dans l'interface frontend indiquant la nature IA du chatbot
- Mention dans les conditions d'utilisation que les réponses sont générées par un modèle de langage
- Pas de personnification humaine dans les prompts système

### Conformité validée

- **Pas de classification haut risque** : HorrorBot fournit des recommandations de films, sans impact sur les droits des utilisateurs
- **Architecture locale** : pas de transfert de données vers des tiers (conforme AI Act Article 14 sur la gouvernance des données)

## Sources

- [EUR-Lex — Règlement (UE) 2024/1689](https://eur-lex.europa.eu) — Texte officiel AI Act
- [Commission européenne — AI Act](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai) — Guides d'application
- [Future of Life Institute](https://futureoflife.org/ai-policy/) — Analyses AI Act
- [CNIL — Intelligence Artificielle](https://www.cnil.fr/fr/intelligence-artificielle) — Recommandations françaises
