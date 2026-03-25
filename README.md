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

* `match_viewer.py` : Moteur de rendu cinématique. Il génère une vue topologique avec anticipation des déplacements via des vecteurs prédictifs calculés sur un delta temporel de 0.4 seconde.
* `terrain_combine.py` : Module d'analyse topologique. Il applique une partition spatiale (KDTree) pour quantifier le contrôle territorial et intègre un scanner algorithmique détectant les pics d'intensité du pressing (minimisation de la distance euclidienne adverse).
* `remontee_bloc.py` : Cœur analytique dédié aux événements complexes. Il détecte automatiquement les mouvements de la ligne défensive, calcule la dispersion du bloc (écart type des positions) et classifie la qualité de l'alignement.

## 📊 Flux de Données (Input / Output)

**1. Input : Données de Tracking Brutes (Format TGV)**
Le pipeline ingère et normalise les coordonnées dynamiquement. Exemple d'une trame à l'instant T :
`1607803200000;0,1,0 : 0,439957,18,62.933,28.356;0,490285,10,56.392,25.068; : 52.7,33.2,0;`

**2. Transformation : Feature Engineering Spatial**
Calcul de la position moyenne et de l'écart type de la ligne défensive :
* Alignement Parfait : $\sigma < 2m$
* Alignement Ambigu : $2m \le \sigma \le 5m$
* Alignement Rompu : $\sigma > 5m$

**3. Output : Diagnostic VLM (Zero Shot)**
Après analyse de la projection géométrique générée par nos scripts, le modèle renvoie une évaluation structurée :
```json
{
  "alignment": "BROKEN",
  "sigma_m": 6.4,
  "vulnerable_players_vertical_pass": 5,
  "justification": "La ligne défensive présente une rupture majeure avec un écart type de 6.4m. Le joueur numéro 4 couvre une zone anormalement basse, ouvrant une cellule de Voronoï adverse exploitable."
}
