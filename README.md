# Chatbot VLM pour l'Analyse Tactique

**CY Cergy Universite | ETIS Lab | Master 2 Data Science & Machine Learning**

## Presentation du Projet
Ce projet de recherche vise a concevoir un systeme multimodal pour l'interpretation automatisee de sequences tactiques au football. L'objectif est de traduire des millions de coordonnees spatiales issues du tracking optique en diagnostics textuels exploitables par des experts metiers (entraineurs, analystes video).

Pour contourner les limites de la vision par ordinateur classique sur des flux videos (occlusions, biais de perspective), nous avons developpe un pipeline hybride innovant : appliquer des Modeles de Langage Visuels (VLM) sur des projections geometriques 2D epurees et semantiquement enrichies.

## Architecture du Pipeline Global
Le systeme fonctionne comme un moteur de raisonnement sequentiel :
1. **Acquisition et Tracking** : Ingestion du flux de donnees spatio temporel a tres haute frequence (25 fps).
2. **Modelisation Geometrique** : Generation de representations 2D abstraites (diagrammes de Voronoi, vecteurs cinematiques).
3. **Inference VLM** : Interrogation des modeles (Claude, GPT, Gemini) via un prompt expert structure en JSON.
4. **Analyse Tactique** : Detection d'evenements complexes comme la coordination d'une ligne defensive ou l'evaluation du pressing.

## Description des Modules Logiciels

- `match_viewer.py` : Moteur de rendu cinematique. Il genere une vue topologique avec anticipation des deplacements via des vecteurs predictifs calcules sur un delta temporel de 0.4 seconde.
- `terrain_combine.py` : Module d'analyse topologique. Il applique une partition spatiale (KDTree) pour quantifier le controle territorial et integre un scanner algorithmique detectant les pics d'intensite du pressing (minimisation de la distance euclidienne adverse).
- `remontee_bloc.py` : Coeur analytique dedie aux evenements complexes. Il detecte automatiquement les mouvements de la ligne defensive, calcule la dispersion du bloc (ecart type des positions) et classifie la qualite de l'alignement.

## Flux de Donnees (Input / Output)

**1. Input : Donnees de Tracking Brutes (Format TGV)**
Le pipeline ingere et normalise les coordonnees dynamiquement. Exemple d'une trame a l'instant T :
`1607803200000;0,1,0 : 0,439957,18,62.933,28.356;0,490285,10,56.392,25.068; : 52.7,33.2,0;`

**2. Transformation : Feature Engineering Spatial**
Calcul de la position moyenne et de l'ecart type de la ligne defensive :
- Alignement Parfait : σ < 2m
- Alignement Ambigu : 2m <= σ <= 5m
- Alignement Rompu : σ > 5m

**3. Output : Diagnostic VLM (Zero Shot)**
Apres analyse de la projection geometrique generee par nos scripts, le modele renvoie une evaluation structuree :
```json
{
  "alignment": "BROKEN",
  "sigma_m": 6.4,
  "vulnerable_players_vertical_pass": 5,
  "justification": "La ligne defensive presente une rupture majeure avec un ecart type de 6.4m. Le joueur numero 4 couvre une zone anormalement basse, ouvrant une cellule de Voronoi adverse exploitable."
}
```

## Evaluation et Benchmark VLM
Le pipeline a ete evalue sur 15 situations tactiques complexes validees par des experts. L'enrichissement geometrique s'est avere plus performant que l'optimisation pure du prompt (gain de 29%).

- **Claude 3.5 Sonnet** : 93% de precision (Meilleur raisonnement inter metriques et quantification des joueurs eliminables).
- **GPT-4o** : 87% de precision.
- **Gemini 1.5 Pro** : 73% de precision.

## References Principales
- Z. Wang, P. Velickovic, et al., *TacticAI: An AI assistant for football tactics*, Nature Communications, 2024.
- A. Rao, H. Wu, et al., *Towards universal soccer video understanding*, 2025.
- C. Moujane, *Rapport de Projet de Recherche M2*, CY Cergy Universite / ETIS Lab, 2026.
