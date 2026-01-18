# SAE 1.5 – Analyse et Visualisation de Données
> Projet réalisé dans le cadre de la SAE 1.5 du B.U.T. Réseaux et Télécommunications.

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Folium](https://img.shields.io/badge/Folium-77B829?style=for-the-badge&logo=Leaflet&logoColor=white)

Ce projet a pour objectif l’analyse de données temporelles (horaires et hebdomadaires) à l’aide de scripts Python, ainsi que la génération de visualisations interactives permettant d’interpréter les résultats obtenus.

---

## Contexte du projet

Dans le cadre de cette SAE, l'objectif est d'exploiter un ensemble de données brutes afin de :
- **Extraire** des informations pertinentes et traiter les données massives.
- **Identifier** des tendances, des cycles et des corrélations.
- **Restituer** les résultats de manière visuelle et interactive.

Les résultats sont présentés sous forme de fichiers HTML interactifs (cartes, heatmaps, graphiques).

---

## Objectifs

- [x] Analyser des données temporelles complexes.
- [x] Mettre en évidence des corrélations statistiques.
- [x] Générer des cartographies dynamiques (Folium).
- [x] Exporter les résultats sous formats interopérables (HTML, JSON).

---

## Structure du dépôt

```text
SAE_1.5/
├── donnees/                # Données sources utilisées pour l’analyse
├── donnees_anciennes/      # Archives de données
├── analyse_semaine.py      # Analyse statistique par semaine
├── mesure_horaire.py       # Analyse des tendances horaires
├── generer_heatmap.py      # Génération de cartes de chaleur
├── generer_relais.py       # Algorithme de sélection des relais pertinents
├── carte_unique.py         # Génération d’une carte globale
├── export_json.py          # Script d'exportation des données traitées
├── index.html              # Page principale (Dashboard)
├── style.css               # Design des pages HTML
└── README.md               # Documentation
