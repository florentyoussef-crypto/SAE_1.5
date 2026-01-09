import os
import json
import math
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import folium

DOSSIER_DONNEES = "donnees"
DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")

FICHIER_BRUT_VOITURES = os.path.join(DOSSIER_DONNEES, "brut_voitures.jsonl")
FICHIER_BRUT_VELOS = os.path.join(DOSSIER_DONNEES, "brut_velos.jsonl")

# ============================================================
# OUTILS JSON
# ============================================================

def get_val(obj, *cles):
    cur = obj
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur

def extraire_lat_lon(entite):
    # Dans l'API : coordinates = [lon, lat]
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        lon = coords[0]
        lat = coords[1]
        return lat, lon
    return None, None

def lire_jsonl_snapshots(chemin):
    # On lit un fichier .jsonl : 1 ligne = 1 objet JSON
    snapshots = []

    if not os.path.exists(chemin):
        return snapshots

    with open(chemin, "r", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne == "":
                continue
            try:
                obj = json.loads(ligne)
                # obj attendu : {"timestamp": "...", "donnees": [...]}
                ts = obj.get("timestamp", None)
                data = obj.get("donnees", None)
                if ts is not None and data is not None:
                    snapshots.append((ts, data))
            except Exception:
                pass

    return snapshots

def creer_dossiers():
    if not os.path.isdir(DOSSIER_DONNEES):
        os.makedirs(DOSSIER_DONNEES, exist_ok=True)
    if not os.path.isdir(DOSSIER_IMAGES):
        os.makedirs(DOSSIER_IMAGES, exist_ok=True)

# ============================================================
# CONVERSION SNAPSHOTS -> TABLES (DATAFRAMES)
# ============================================================

def construire_df_voitures(snapshots):
    # On transforme la donnée brute en tableau propre :
    # colonnes : timestamp, nom, libres, total, taux_occupation, lat, lon

    lignes = []

    for ts, parkings in snapshots:
        for p in parkings:
            # On ne garde que les parkings "Open"
            if get_val(p, "status", "value") != "Open":
                continue

            nom = get_val(p, "name", "value")
            libres = get_val(p, "availableSpotNumber", "value")
            total = get_val(p, "totalSpotNumber", "value")

            if nom is None or libres is None or total is None:
                continue
            if float(total) <= 0:
                continue

            lat, lon = extraire_lat_lon(p)

            taux = (float(total) - float(libres)) / float(total)

            lignes.append({
                "timestamp": ts,
                "nom": str(nom),
                "libres": float(libres),
                "total": float(total),
                "taux_occupation": float(taux),
                "lat": lat,
                "lon": lon
            })

    if len(lignes) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(lignes)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")

    return df

def construire_df_velos(snapshots):
    # Colonnes : timestamp, nom, velos_dispo, bornes_libres, total, lat, lon

    lignes = []

    for ts, stations in snapshots:
        for s in stations:
            nom = get_val(s, "address", "value", "streetAddress")
            velos = get_val(s, "availableBikeNumber", "value")
            bornes = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes is None or total is None:
                continue
            if float(total) <= 0:
                continue

            lat, lon = extraire_lat_lon(s)

            lignes.append({
                "timestamp": ts,
                "nom": str(nom),
                "velos_dispo": float(velos),
                "bornes_libres": float(bornes),
                "total": float(total),
                "lat": lat,
                "lon": lon
            })

    if len(lignes) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(lignes)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df = df.sort_values("timestamp")

    return df

# ============================================================
# GRAPHIQUES PAR POINT (PARKING / STATION)
# ============================================================

def nom_fichier_safe(texte):
    # Pour faire des fichiers images stables
    t = texte.replace(" ", "_").replace("/", "_").replace("\\", "_").replace("'", "_").replace('"', "_")
    t = t.replace("é", "e").replace("è", "e").replace("ê", "e")
    t = t.replace("à", "a").replace("ç", "c")
    return t

def graphe_parking(df_parking, nom):
    # Graph taux d'occupation dans le temps
    dfp = df_parking[df_parking["nom"] == nom].copy()
    if len(dfp) == 0:
        return None

    fichier = os.path.join(DOSSIER_IMAGES, f"parking_{nom_fichier_safe(nom)}.png")

    plt.figure()
    plt.plot(dfp["timestamp"].values, dfp["taux_occupation"].values)
    plt.title("Parking : " + nom)
    plt.xlabel("Temps")
    plt.ylabel("Taux d'occupation")
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(fichier)
    plt.close()

    return fichier

def graphe_station(df_station, nom):
    # Graph vélos dispo + bornes libres
    dfs = df_station[df_station["nom"] == nom].copy()
    if len(dfs) == 0:
        return None

    fichier = os.path.join(DOSSIER_IMAGES, f"velo_{nom_fichier_safe(nom)}.png")

    plt.figure()
    plt.plot(dfs["timestamp"].values, dfs["velos_dispo"].values, label="Vélos dispo")
    plt.plot(dfs["timestamp"].values, dfs["bornes_libres"].values, label="Bornes libres")
    plt.title("Station vélo : " + nom)
    plt.xlabel("Temps")
    plt.ylabel("Nombre")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fichier)
    plt.close()

    return fichier

# ============================================================
# CARTE UNIQUE
# ============================================================

def creer_carte(df_voitures, df_velos):
    # Centrage simple sur Montpellier
    m = folium.Map(location=[43.61, 3.88], zoom_start=13)

    # Pour chaque parking : on prend la dernière mesure dispo (dernier timestamp)
    if len(df_voitures) > 0:
        df_last_p = df_voitures.sort_values("timestamp").groupby("nom").tail(1)

        for _, r in df_last_p.iterrows():
            if pd.isna(r["lat"]) or pd.isna(r["lon"]):
                continue

            nom = str(r["nom"])
            img = graphe_parking(df_voitures, nom)

            libres = int(float(r["libres"]))
            total = int(float(r["total"]))
            taux = float(r["taux_occupation"])
            ts = str(r["timestamp"])

            html = f"""
            <div style="width: 320px;">
              <h4 style="margin:0;">🚗 Parking : {nom}</h4>
              <p style="margin:0;">
                <b>Date/heure :</b> {ts}<br>
                <b>Libres :</b> {libres} / {total}<br>
                <b>Taux :</b> {round(taux, 3)}
              </p>
            """

            if img is not None:
                # image relative (dans donnees/images)
                rel = os.path.relpath(img, DOSSIER_DONNEES)
                html += f'<img src="{rel}" style="width: 100%; margin-top: 6px;">'

            html += "</div>"

            folium.Marker(
                location=[float(r["lat"]), float(r["lon"])],
                popup=folium.Popup(html, max_width=350),
                icon=folium.Icon(color="blue", icon="car", prefix="fa")
            ).add_to(m)

    # Pour chaque station vélo : dernière mesure dispo
    if len(df_velos) > 0:
        df_last_s = df_velos.sort_values("timestamp").groupby("nom").tail(1)

        for _, r in df_last_s.iterrows():
            if pd.isna(r["lat"]) or pd.isna(r["lon"]):
                continue

            nom = str(r["nom"])
            img = graphe_station(df_velos, nom)

            velos = int(float(r["velos_dispo"]))
            bornes = int(float(r["bornes_libres"]))
            total = int(float(r["total"]))
            ts = str(r["timestamp"])

            html = f"""
            <div style="width: 320px;">
              <h4 style="margin:0;">🚲 Station vélo : {nom}</h4>
              <p style="margin:0;">
                <b>Date/heure :</b> {ts}<br>
                <b>Vélos dispo :</b> {velos}<br>
                <b>Bornes libres :</b> {bornes} / {total}
              </p>
            """

            if img is not None:
                rel = os.path.relpath(img, DOSSIER_DONNEES)
                html += f'<img src="{rel}" style="width: 100%; margin-top: 6px;">'

            html += "</div>"

            folium.Marker(
                location=[float(r["lat"]), float(r["lon"])],
                popup=folium.Popup(html, max_width=350),
                icon=folium.Icon(color="orange", icon="bicycle", prefix="fa")
            ).add_to(m)

    fichier_html = os.path.join(DOSSIER_DONNEES, "carte.html")
    m.save(fichier_html)
    print("Carte unique générée :", fichier_html)
    print("Images générées dans :", DOSSIER_IMAGES)

# ============================================================
# MAIN
# ============================================================

def main():
    creer_dossiers()

    snapshots_voitures = lire_jsonl_snapshots(FICHIER_BRUT_VOITURES)
    snapshots_velos = lire_jsonl_snapshots(FICHIER_BRUT_VELOS)

    if len(snapshots_voitures) == 0:
        print("Aucun snapshot voitures trouvé :", FICHIER_BRUT_VOITURES)

    if len(snapshots_velos) == 0:
        print("Aucun snapshot vélos trouvé :", FICHIER_BRUT_VELOS)

    df_voitures = construire_df_voitures(snapshots_voitures)
    df_velos = construire_df_velos(snapshots_velos)

    creer_carte(df_voitures, df_velos)

if __name__ == "__main__":
    main()
