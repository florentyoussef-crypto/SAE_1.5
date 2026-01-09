import os
import json
from collections import defaultdict

import folium
from folium.plugins import MarkerCluster

DOSSIER_DONNEES = "donnees"

FICHIER_BRUT_VOITURES = os.path.join(DOSSIER_DONNEES, "brut_voitures.jsonl")
FICHIER_BRUT_VELOS = os.path.join(DOSSIER_DONNEES, "brut_velos.jsonl")

DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")
FICHIER_CARTE = os.path.join(DOSSIER_DONNEES, "carte.html")


def lire_jsonl(chemin):
    lignes = []
    if not os.path.exists(chemin):
        return lignes
    with open(chemin, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    lignes.append(json.loads(line))
                except Exception:
                    pass
    return lignes


def extraire_coord(entite):
    loc = entite.get("location", {}).get("value", {}).get("coordinates", None)
    if isinstance(loc, list) and len(loc) >= 2:
        lon = loc[0]
        lat = loc[1]
        return lat, lon
    return None, None


def main():
    os.makedirs(DOSSIER_DONNEES, exist_ok=True)

    data_voitures = lire_jsonl(FICHIER_BRUT_VOITURES)
    data_velos = lire_jsonl(FICHIER_BRUT_VELOS)

    if len(data_voitures) == 0 and len(data_velos) == 0:
        print("Aucun snapshot trouvé pour créer la carte.")
        return

    # Centre carte (Montpellier)
    m = folium.Map(location=[43.6119, 3.8772], zoom_start=13)

    cluster_voitures = MarkerCluster(name="Parkings voiture").add_to(m)
    cluster_velos = MarkerCluster(name="Stations vélos").add_to(m)

    # On prend le dernier snapshot pour placer les points (position fixe)
    dernier_voitures = data_voitures[-1]["donnees"] if len(data_voitures) > 0 else []
    dernier_velos = data_velos[-1]["donnees"] if len(data_velos) > 0 else []

    # PARKINGS
    for p in dernier_voitures:
        nom = p.get("name", {}).get("value", "Parking")
        lat, lon = extraire_coord(p)
        if lat is None or lon is None:
            continue

        popup_html = f"""
        <b>🚗 Parking :</b> {nom}<br>
        <br>
        <i>Les graphes seront ajoutés ici ensuite :</i><br>
        - journalier<br>
        - global<br>
        """

        folium.Marker(
            location=[lat, lon],
            tooltip=f"🚗 {nom}",
            popup=folium.Popup(popup_html, max_width=400),
            icon=folium.Icon(color="blue", icon="car", prefix="fa"),
        ).add_to(cluster_voitures)

    # STATIONS VELO
    for s in dernier_velos:
        nom = s.get("address", {}).get("value", {}).get("streetAddress", "Station")
        lat, lon = extraire_coord(s)
        if lat is None or lon is None:
            continue

        popup_html = f"""
        <b>🚲 Station :</b> {nom}<br>
        <br>
        <i>Les graphes seront ajoutés ici ensuite :</i><br>
        - journalier<br>
        - global<br>
        """

        folium.Marker(
            location=[lat, lon],
            tooltip=f"🚲 {nom}",
            popup=folium.Popup(popup_html, max_width=400),
            icon=folium.Icon(color="orange", icon="bicycle", prefix="fa"),
        ).add_to(cluster_velos)

    folium.LayerControl().add_to(m)
    m.save(FICHIER_CARTE)

    print("Carte unique générée :", FICHIER_CARTE)


if __name__ == "__main__":
    main()
