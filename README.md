# Chatbot VLM pour l'Analyse Tactique ⚽🤖

**CY Cergy Université | ETIS Lab | Master 2 Data Science & Machine Learning**

## 📝 Présentation du Projet
Ce projet de recherche vise à concevoir un système multimodal pour l'interprétation automatisée de séquences tactiques au football. L'objectif est de traduire des millions de coordonnées spatiales issues du tracking optique en diagnostics textuels exploitables par des experts métiers (entraîneurs, analystes vidéo).

Pour contourner les limites de la vision par ordinateur classique sur des flux vidéos (occlusions, biais de perspective), nous avons développé un pipeline hybride innovant : appliquer des Modèles de Langage Visuels (VLM) sur des projections géométriques 2D épurées et sémantiquement enrichies.

## ⚙️ Architecture du Pipeline Global
Le système fonctionne comme un moteur de raisonnement séquentiel :
1. **Acquisition & Tracking** : Ingestion du flux de données spatio temporel à très haute fréquence (25 fps).
2. **Modélisation Géométrique** : Génération de représentations 2D abstraites (diagrammes de Voronoï, vecteurs cinématiques).
3. **Inférence VLM** : Interrogation des modèles (Claude, GPT, Gemini) via un prompt expert structuré en JSON.
4. **Analyse Tactique** : Détection d'événements complexes comme la coordination d'une ligne défensive ou l'évaluation du pressing.

## 🧩 Description des Modules Logiciels

* `match_viewer.py` : Moteur de rendu cinématique. Il génère une vue aérienne fluide avec anticipation des déplacements via des vecteurs prédictifs calculés sur un delta temporel de 0.4 seconde.
* `terrain_combine.py` : Module d'analyse topologique. Il applique une partition spatiale (KDTree) pour quantifier le contrôle territorial et intègre un scanner algorithmique détectant les pics d'intensité du pressing.
* `remontee_bloc.py` : Cœur analytique dédié aux événements complexes. Il détecte automatiquement les mouvements de la ligne défensive, calcule la dispersion du bloc (écart type des positions) et classifie la qualité de l'alignement.

## 📊 Format des Données (Input)
Le pipeline traite des données de tracking au format brut (TGV). Chaque trame est parsée et normalisée dynamiquement pour pallier les changements de côté à la mi temps.

Exemple de structure d'une trame (Timestamp | Méta | Joueurs | Ballon) :
`1607803200000;0,1,0 : 0,439957,18,62.933,28.356;0,490285,10,56.392,25.068; : 52.7,33.2,0;`

## 🖼️ Visualisations et Abstractions Spatiales

**Analyse de la Ligne Défensive**
Le système génère une bande de dispersion pour mesurer la compacité du bloc. Le VLM utilise cette abstraction pour évaluer la vulnérabilité de la défense.
![Analyse de la ligne défensive, Voronoï et cinématique](analyse_ligne_defensive.png)

**Scanner de Pressing**
L'algorithme parcourt le match complet pour isoler automatiquement les séquences où la distance euclidienne moyenne entre les adversaires est minimale.
![Top 6 des séquences de pressing intense](scanner_pressing.png)

## 📈 Évaluation et Benchmark VLM
Le pipeline a été évalué en conditions zero shot sur 15 situations tactiques complexes validées par des experts. L'enrichissement géométrique s'est avéré plus performant que l'optimisation pure du prompt (gain de 29%).

* **Claude 3.5 Sonnet** : 93% de précision (Meilleur raisonnement inter métriques et quantification des joueurs éliminables).
* **GPT-4o** : 87% de précision.
* **Gemini 1.5 Pro** : 73% de précision.

## 📚 Références Principales
* Z. Wang, P. Velickovic, et al., *TacticAI: An AI assistant for football tactics*, Nature Communications, 2024.
* A. Rao, H. Wu, et al., *Towards universal soccer video understanding*, 2025.
* C. Moujane, *Rapport de Projet de Recherche M2*, CY Cergy Université / ETIS Lab, 2026.
