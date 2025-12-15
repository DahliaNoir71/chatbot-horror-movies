# Registre des Traitements - HorrorBot

**Conformité RGPD Article 30** - Registre des activités de traitement

---

## Traitement #1 : Collecte données films TMDB

**Responsable de traitement** : HorrorBot (Projet académique - Serge PFEIFFER)  
**Finalité** : Constitution dataset films d'horreur pour chatbot RAG  
**Base légale** : Intérêt légitime (recherche académique, certification DIA)  
**Catégories de données** : Aucune donnée personnelle (métadonnées films publiques)  
**Origine** : API TMDB (https://www.themoviedb.org)  
**Destinataires** : Aucun (usage interne uniquement)  
**Transferts hors UE** : Non  
**Durée de conservation** : 2 ans (durée projet académique)  
**Mesures de sécurité** :
- Chiffrement en transit (HTTPS)
- Clé API stockée en variable d'environnement (non versionnée)
- Rate limiting respecté (40 req/10s)

---

## Traitement #2 : Stockage PostgreSQL

**Responsable de traitement** : HorrorBot  
**Finalité** : Base vectorielle pour Retrieval-Augmented Generation  
**Base légale** : N/A (pas de données personnelles traitées)  
**Catégories de données** : 
- Titres films (publics)
- Synopsis (publics)
- Scores critiques agrégés (publics)
- Embeddings vectoriels (dérivés de textes publics)

**Destinataires** : API REST HorrorBot (authentification JWT requise)  
**Transferts hors UE** : Non (hébergement local/EU)  
**Durée de conservation** : Indéterminée (données publiques non personnelles)  
**Mesures de sécurité** :
- Accès restreint par mot de passe PostgreSQL
- Port 5432 non exposé publiquement
- Logs applicatifs anonymisés (pas d'IP utilisateurs)
- Backups chiffrés

---

## Traitement #3 : Enrichissement Rotten Tomatoes

**Responsable de traitement** : HorrorBot  
**Finalité** : Enrichissement qualité corpus pour améliorer pertinence RAG  
**Base légale** : Intérêt légitime (données publiques agrégées)  
**Catégories de données** : Critiques agrégées publiques (Tomatometer, consensus)  
**Origine** : Web scraping RottenTomatoes.com (données publiques)  
**Destinataires** : Aucun  
**Transferts hors UE** : Non  
**Durée de conservation** : 2 ans  
**Mesures de sécurité** :
- Respect robots.txt
- Rate limiting (3 req/batch, délais aléatoires 2-5s)
- User-Agent identifié (projet académique)
- Pas de contournement anti-bot

---

## Traitement #4 : Logs application

**Responsable de traitement** : HorrorBot  
**Finalité** : Debug, monitoring, maintien en condition opérationnelle  
**Base légale** : Intérêt légitime (maintien service)  
**Catégories de données** : 
- Timestamps requêtes
- Messages erreurs techniques
- Métriques performances (latence, tokens générés)
- **AUCUNE donnée utilisateur** (pas d'IP, pas de requêtes loggées)

**Destinataires** : Développeur uniquement  
**Transferts hors UE** : Non  
**Durée de conservation** : 30 jours (purge automatique)  
**Mesures de sécurité** :
- Anonymisation automatique (pas d'IP loggées)
- Suppression rolling quotidienne (>30 jours)
- Logs JSON structurés sans PII

---

## Traitement #5 : Checkpoints ETL

**Responsable de traitement** : HorrorBot  
**Finalité** : Reprise pipeline après interruption, versioning datasets  
**Base légale** : N/A (données publiques non personnelles)  
**Catégories de données** : Exports JSON films agrégés  
**Destinataires** : Aucun  
**Transferts hors UE** : Non  
**Durée de conservation** : 90 jours (purge automatique)  
**Mesures de sécurité** :
- Stockage local `data/checkpoints/`
- Exclusion Git (.gitignore)
- Purge hebdomadaire (garde 5 derniers)

---

## Déclaration : Absence de données personnelles

**HorrorBot ne collecte, ne stocke, ni ne traite de données à caractère personnel** au sens du RGPD (Article 4 - identification directe ou indirecte de personnes physiques).

Les données traitées sont exclusivement :
- Métadonnées films publiques (titres, dates, genres)
- Critiques agrégées anonymes (scores, consensus textuels)
- Métriques techniques anonymisées

**Aucune donnée utilisateur** :
- Pas de comptes utilisateurs (futur : JWT anonymes)
- Pas d'historique conversations (stateless)
- Pas de tracking (pas d'analytics)
- Pas de cookies (API pure)

---

## Droits des personnes concernées

**Non applicable** : HorrorBot ne traite aucune donnée personnelle.

En cas de dérive future (ajout comptes utilisateurs), les droits suivants devront être implémentés :
- Droit d'accès (Art. 15)
- Droit de rectification (Art. 16)
- Droit à l'effacement (Art. 17)
- Droit à la portabilité (Art. 20)

**Contact DPO** : N/A (projet académique individuel)

---

## Analyse d'impact (AIPD)

**AIPD non requise** : Aucun traitement à risque élevé pour les droits et libertés (Art. 35).

---

## Mise à jour registre

**Dernière mise à jour** : 21/11/2025  
**Fréquence révision** : Trimestrielle ou à chaque évolution traitement  
**Responsable** : Serge PFEIFFER
