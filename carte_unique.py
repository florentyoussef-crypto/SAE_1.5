import os
import json
import pandas as pd
import matplotlib.pyplot as plt

import folium
from folium.plugins import MarkerCluster

DOSSIER = "donnees"
FICHIER_JSONL_VOITURE = os.path.join(DOSSIER, "brut_voitures.jsonl")
FICHIER_JSONL_VELO = os.path.join(DOSSIER, "brut_velos.jsonl")

DOSSIER_IMAGES = os.path.join(DOSSIER, "images")

# IMPORTANT : carte AU ROOT pour GitHub Pages (folder = / root)
FICHIER_CARTE = "carte.html"

# IMPORTANT : chemin des images VU DEPUIS la racine (carte.html est au root)
CHEMIN_IMAGES_HTML = "donnees/images"


# ============================================================
# OUTILS JSONL
# ============================================================

def lire_jsonl(chemin):
    lignes = []
    if not os.path.exists(chemin):
        return lignes

    with open(chemin, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line != "":
                try:
                    lignes.append(json.loads(line))
                except Exception:
                    pass
    return lignes


def extraire_lat_lon(entite):
    # location.value.coordinates = [lon, lat]
    try:
        coords = entite["location"]["value"]["coordinates"]
        if isinstance(coords, list) and len(coords) >= 2:
            return float(coords[1]), float(coords[0])
    except Exception:
        return None, None
    return None, None


def safe_get(entite, *cles):
    cur = entite
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


# ============================================================
# NORMALISATION DES DONNEES (JSON brut -> DataFrame)
# ============================================================

def snapshots_voiture_to_df(snapshots):
    rows = []
    for snap in snapshots:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if ts is None or not isinstance(donnees, list):
            continue

        for p in donnees:
            status = safe_get(p, "status", "value")
            if status != "Open":
                continue

            nom = safe_get(p, "name", "value")
            libres = safe_get(p, "availableSpotNumber", "value")
            total = safe_get(p, "totalSpotNumber", "value")
            lat, lon = extraire_lat_lon(p)

            if nom is None or libres is None or total is None:
                continue

            try:
                libres = float(libres)
                total = float(total)
            except Exception:
                continue

            if total <= 0:
                continue

            taux = (total - libres) / total

            rows.append({
                "timestamp": ts,
                "nom": str(nom),
                "libres": libres,
                "total": total,
                "taux": taux,
                "lat": lat,
                "lon": lon
            })

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "nom"])
    return df


def snapshots_velo_to_df(snapshots):
    rows = []
    for snap in snapshots:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if ts is None or not isinstance(donnees, list):
            continue

        for s in donnees:
            nom = safe_get(s, "address", "value", "streetAddress")
            velos = safe_get(s, "availableBikeNumber", "value")
            bornes = safe_get(s, "freeSlotNumber", "value")
            total = safe_get(s, "totalSlotNumber", "value")
            lat, lon = extraire_lat_lon(s)

            if nom is None or velos is None or bornes is None or total is None:
                continue

            try:
                velos = float(velos)
                bornes = float(bornes)
                total = float(total)
            except Exception:
                continue

            if total <= 0:
                continue

            taux_places = (total - bornes) / total

            rows.append({
                "timestamp": ts,
                "nom": str(nom),
                "velos": velos,
                "bornes_libres": bornes,
                "total": total,
                "taux_places": taux_places,
                "lat": lat,
                "lon": lon
            })

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "nom"])
    return df


# ============================================================
# GRAPHIQUES
# ============================================================

def nettoyer_nom_fichier(nom):
    for ch in ["/", "\\", ":", "?", "*", '"', "'"]:
        nom = nom.replace(ch, "_")
    return nom


def generer_graphe_journalier(df, colonne, nom_objet, prefix):
    if len(df) == 0:
        return None

    df2 = df[df["nom"] == nom_objet].copy()
    df2 = df2.dropna(subset=["timestamp", colonne])
    if len(df2) == 0:
        return None

    jour_max = df2["timestamp"].dt.date.max()
    df2 = df2[df2["timestamp"].dt.date == jour_max].copy()
    df2 = df2.sort_values("timestamp")
    if len(df2) == 0:
        return None

    nom_f = nettoyer_nom_fichier(nom_objet)
    fichier = f"{prefix}_{nom_f}_journalier.png"
    chemin = os.path.join(DOSSIER_IMAGES, fichier)

    plt.figure()
    plt.plot(df2["timestamp"], df2[colonne])
    plt.title(f"{nom_objet} - journalier ({jour_max})")
    plt.xlabel("Heure")
    plt.ylabel(colonne)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(chemin)
    plt.close()

    return fichier


def generer_graphe_global(df, colonne, nom_objet, prefix):
    if len(df) == 0:
        return None

    df2 = df[df["nom"] == nom_objet].copy()
    df2 = df2.dropna(subset=["timestamp", colonne])
    df2 = df2.sort_values("timestamp")
    if len(df2) == 0:
        return None

    nom_f = nettoyer_nom_fichier(nom_objet)
    fichier = f"{prefix}_{nom_f}_global.png"
    chemin = os.path.join(DOSSIER_IMAGES, fichier)

    plt.figure()
    plt.plot(df2["timestamp"], df2[colonne])
    plt.title(f"{nom_objet} - global")
    plt.xlabel("Temps")
    plt.ylabel(colonne)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(chemin)
    plt.close()

    return fichier


# ============================================================
# POPUPS HTML
# ============================================================

def popup_parking(nom, libres, total, taux, img_j, img_g):
    html = f"""
    <div style="width: 320px;">
      <h4 style="margin:0;">🚗 {nom}</h4>
      <hr style="margin:6px 0;">
      <b>Places libres :</b> {int(libres)}<br>
      <b>Capacité totale :</b> {int(total)}<br>
      <b>Taux occupation :</b> {taux:.2%}<br>
    """
    if img_j is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe journalier</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_j}" width="300">'
    if img_g is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe global</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_g}" width="300">'
    html += "</div>"
    return html


def popup_velo(nom, velos, bornes_libres, total, taux_places, img_j, img_g):
    html = f"""
    <div style="width: 320px;">
      <h4 style="margin:0;">🚲 {nom}</h4>
      <hr style="margin:6px 0;">
      <b>Vélos dispo :</b> {int(velos)}<br>
      <b>Bornes libres :</b> {int(bornes_libres)}<br>
      <b>Total bornes :</b> {int(total)}<br>
      <b>Taux occupation places :</b> {taux_places:.2%}<br>
    """
    if img_j is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe journalier</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_j}" width="300">'
    if img_g is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe global</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_g}" width="300">'
    html += "</div>"
    return html


# ============================================================
# MAIN
# ============================================================

def main():
    os.makedirs(DOSSIER, exist_ok=True)
    os.makedirs(DOSSIER_IMAGES, exist_ok=True)

    snaps_voiture = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_velo = lire_jsonl(FICHIER_JSONL_VELO)

    df_voiture = snapshots_voiture_to_df(snaps_voiture)
    df_velo = snapshots_velo_to_df(snaps_velo)

    if len(df_voiture) == 0 and len(df_velo) == 0:
        print("Aucune donnée snapshot trouvée (JSONL).")
        return

    # Centre carte = moyenne des points (voiture + vélo)
    latitudes = []
    longitudes = []

    if len(df_voiture) > 0:
        df_vp = df_voiture.dropna(subset=["lat", "lon"])
        latitudes += list(df_vp["lat"].values)
        longitudes += list(df_vp["lon"].values)

    if len(df_velo) > 0:
        df_vs = df_velo.dropna(subset=["lat", "lon"])
        latitudes += list(df_vs["lat"].values)
        longitudes += list(df_vs["lon"].values)

    if len(latitudes) == 0:
        print("Pas de coordonnées GPS exploitables.")
        return

    centre_lat = sum(latitudes) / len(latitudes)
    centre_lon = sum(longitudes) / len(longitudes)

    # IMPORTANT : tiles bien compatibles GitHub Pages
    carte = folium.Map(location=[centre_lat, centre_lon], zoom_start=13, tiles="OpenStreetMap")

    cluster_voiture = MarkerCluster(name="🚗 Parkings voiture")
    cluster_velo = MarkerCluster(name="🚲 Stations vélo")

    # -------------------------
    # Points voiture : dernier état connu par parking
    # -------------------------
    if len(df_voiture) > 0:
        df_voiture_ok = df_voiture.dropna(subset=["lat", "lon"]).copy()
        df_voiture_ok = df_voiture_ok.sort_values("timestamp")
        dernier = df_voiture_ok.groupby("nom").tail(1)

        for _, row in dernier.iterrows():
            nom = row["nom"]
            libres = row["libres"]
            total = row["total"]
            taux = row["taux"]
            lat = row["lat"]
            lon = row["lon"]

            img_j = generer_graphe_journalier(df_voiture_ok, "taux", nom, "parking")
            img_g = generer_graphe_global(df_voiture_ok, "taux", nom, "parking")

            pop = popup_parking(nom, libres, total, taux, img_j, img_g)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(pop, max_width=420),
                icon=folium.Icon(color="blue", icon="car", prefix="fa")
            ).add_to(cluster_voiture)

    # -------------------------
    # Points vélo : dernier état connu par station
    # -------------------------
    if len(df_velo) > 0:
        df_velo_ok = df_velo.dropna(subset=["lat", "lon"]).copy()
        df_velo_ok = df_velo_ok.sort_values("timestamp")
        dernier = df_velo_ok.groupby("nom").tail(1)

        for _, row in dernier.iterrows():
            nom = row["nom"]
            velos = row["velos"]
            bornes_libres = row["bornes_libres"]
            total = row["total"]
            taux_places = row["taux_places"]
            lat = row["lat"]
            lon = row["lon"]

            img_j = generer_graphe_journalier(df_velo_ok, "taux_places", nom, "velo")
            img_g = generer_graphe_global(df_velo_ok, "taux_places", nom, "velo")

            pop = popup_velo(nom, velos, bornes_libres, total, taux_places, img_j, img_g)

            # NOTE: folium n’a pas "orange" en couleur standard -> on met green
            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(pop, max_width=420),
                icon=folium.Icon(color="green", icon="bicycle", prefix="fa")
            ).add_to(cluster_velo)

    cluster_voiture.add_to(carte)
    cluster_velo.add_to(carte)

    folium.LayerControl(collapsed=False).add_to(carte)

    carte.save(FICHIER_CARTE)

    print("✅ Carte générée :", FICHIER_CARTE)
    print("✅ Images générées dans :", DOSSIER_IMAGES)


if __name__ == "__main__":
    main()
