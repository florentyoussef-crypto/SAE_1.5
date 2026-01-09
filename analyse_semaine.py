import os
import re
import math
import pandas as pd
import matplotlib.pyplot as plt
import folium
from folium.plugins import MarkerCluster


DOSSIER_DONNEES = "donnees"

SUFFIXE_VOITURES = "_voitures.csv"
SUFFIXE_VELOS = "_velos.csv"

DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")


# ============================================================
# OUTILS
# ============================================================

def creer_dossier_si_absent(chemin):
    if not os.path.isdir(chemin):
        os.makedirs(chemin, exist_ok=True)


def slugifier(texte):
    if texte is None:
        return "inconnu"
    t = str(texte).strip().lower()
    t = t.replace("’", "'")
    t = re.sub(r"[^\w\s-]", "", t)
    t = re.sub(r"[\s-]+", "_", t)
    if len(t) == 0:
        return "inconnu"
    return t


def fichiers_journaliers(suffixe):
    fichiers = []
    if not os.path.isdir(DOSSIER_DONNEES):
        return fichiers
    for nom in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom.startswith("jour_") and nom.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom))
    return fichiers


def dernier_fichier_jour(suffixe):
    fichiers = fichiers_journaliers(suffixe)
    if len(fichiers) == 0:
        return None
    return fichiers[-1]


def charger_tous_csv(suffixe):
    fichiers = fichiers_journaliers(suffixe)
    if len(fichiers) == 0:
        return None

    dfs = []
    for chemin in fichiers:
        try:
            df = pd.read_csv(chemin)
            df["fichier_source"] = os.path.basename(chemin)
            dfs.append(df)
        except Exception:
            pass

    if len(dfs) == 0:
        return None

    df_final = pd.concat(dfs, ignore_index=True)

    if "timestamp" in df_final.columns:
        df_final["timestamp_dt"] = pd.to_datetime(df_final["timestamp"], errors="coerce")

    return df_final


def charger_dernier_csv(suffixe):
    chemin = dernier_fichier_jour(suffixe)
    if chemin is None:
        return None
    try:
        df = pd.read_csv(chemin)
        df["fichier_source"] = os.path.basename(chemin)
        if "timestamp" in df.columns:
            df["timestamp_dt"] = pd.to_datetime(df["timestamp"], errors="coerce")
        return df
    except Exception:
        return None


def centre_moyen(df_list):
    # centre carte = moyenne des lat/lon valides
    lats = []
    lons = []
    for df in df_list:
        if df is None:
            continue
        if "lat" in df.columns and "lon" in df.columns:
            la = pd.to_numeric(df["lat"], errors="coerce").dropna().values.tolist()
            lo = pd.to_numeric(df["lon"], errors="coerce").dropna().values.tolist()
            lats += la
            lons += lo

    if len(lats) == 0 or len(lons) == 0:
        return 43.6108, 3.8767  # centre Montpellier approx

    return sum(lats) / len(lats), sum(lons) / len(lons)


def plot_serie(d, col_y, titre, chemin_png):
    if len(d) == 0:
        return False

    d[col_y] = pd.to_numeric(d[col_y], errors="coerce")
    d = d.dropna(subset=[col_y])

    if "timestamp_dt" in d.columns:
        d = d.dropna(subset=["timestamp_dt"])
        d = d.sort_values("timestamp_dt")

    if len(d) == 0:
        return False

    plt.figure()
    plt.plot(d[col_y].values)
    plt.title(titre)
    plt.xlabel("Mesures (ordre chronologique)")
    plt.ylabel(col_y)
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(chemin_png)
    plt.close()
    return True


def couleur_parking(taux):
    try:
        x = float(taux)
    except Exception:
        return "gray"
    if x < 0.5:
        return "green"
    if x < 0.8:
        return "orange"
    return "red"


def couleur_station(velos, bornes):
    try:
        v = float(velos)
        b = float(bornes)
    except Exception:
        return "gray"
    if v >= 5 and b >= 5:
        return "green"
    if v >= 2 and b >= 2:
        return "orange"
    return "red"


def safe_int(x):
    try:
        return int(float(x))
    except Exception:
        return None


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


# ============================================================
# MAIN
# ============================================================

def main():
    creer_dossier_si_absent(DOSSIER_IMAGES)

    # Données globales + dernier jour
    df_voitures_global = charger_tous_csv(SUFFIXE_VOITURES)
    df_velos_global = charger_tous_csv(SUFFIXE_VELOS)

    df_voitures_jour = charger_dernier_csv(SUFFIXE_VOITURES)
    df_velos_jour = charger_dernier_csv(SUFFIXE_VELOS)

    if df_voitures_global is None and df_velos_global is None:
        print("Aucune donnée trouvée dans donnees/")
        return

    # centre carte
    centre_lat, centre_lon = centre_moyen([df_voitures_jour, df_velos_jour])

    carte = folium.Map(location=[centre_lat, centre_lon], zoom_start=13, tiles="OpenStreetMap")

    # Groupes (pratique pour activer/désactiver)
    groupe_voiture = folium.FeatureGroup(name="Parkings voitures")
    groupe_velo = folium.FeatureGroup(name="Stations vélos")

    cluster_voiture = MarkerCluster(name="Cluster parkings")
    cluster_velo = MarkerCluster(name="Cluster stations")

    # ========================================================
    # PARKINGS (voitures)
    # ========================================================
    if df_voitures_jour is not None:
        dpar = df_voitures_jour[df_voitures_jour.get("type") == "PARKING"].copy()
        dpar["lat"] = pd.to_numeric(dpar["lat"], errors="coerce")
        dpar["lon"] = pd.to_numeric(dpar["lon"], errors="coerce")

        for _, row in dpar.iterrows():
            nom = row.get("nom")
            lat = row.get("lat")
            lon = row.get("lon")
            if pd.isna(lat) or pd.isna(lon):
                continue

            slug = slugifier(nom)

            # ----- Données actuelles (dernier jour)
            libres = safe_int(row.get("libres"))
            total = safe_int(row.get("total"))
            taux = safe_float(row.get("taux_occupation"))
            date = row.get("date")
            heure = row.get("heure")

            # ----- Données globales du même parking
            dglob = None
            if df_voitures_global is not None:
                dglob = df_voitures_global[
                    (df_voitures_global.get("type") == "PARKING") & (df_voitures_global.get("nom") == nom)
                ].copy()

            # ----- Données jour du même parking
            djour = df_voitures_jour[
                (df_voitures_jour.get("type") == "PARKING") & (df_voitures_jour.get("nom") == nom)
            ].copy()

            # ----- Graphes (jour + global)
            img_jour = os.path.join("images", f"parking_{slug}_jour.png")
            img_global = os.path.join("images", f"parking_{slug}_global.png")

            chemin_img_jour = os.path.join(DOSSIER_IMAGES, f"parking_{slug}_jour.png")
            chemin_img_global = os.path.join(DOSSIER_IMAGES, f"parking_{slug}_global.png")

            ok_jour = plot_serie(djour, "taux_occupation", f"Parking {nom} - jour", chemin_img_jour)
            ok_global = False
            if dglob is not None:
                ok_global = plot_serie(dglob, "taux_occupation", f"Parking {nom} - global", chemin_img_global)

            if not ok_jour:
                img_jour = None
            if not ok_global:
                img_global = None

            # ----- Stats globales simples (pour “toutes les infos”)
            taux_moy = None
            taux_max = None
            taux_min = None

            if dglob is not None and "taux_occupation" in dglob.columns:
                serie = pd.to_numeric(dglob["taux_occupation"], errors="coerce").dropna()
                if len(serie) > 0:
                    taux_moy = float(serie.mean())
                    taux_max = float(serie.max())
                    taux_min = float(serie.min())

            # ----- Popup avec SELECT Journalier / Global
            # On met 2 <div> (jour/global) et on affiche/masque selon le choix
            div_jour_id = f"pj_{slug}"
            div_global_id = f"pg_{slug}"

            popup = []
            popup.append(f"<div style='font-family:Arial; width:320px;'>")
            popup.append(f"<h4 style='margin:0 0 8px 0;'>🚗 Parking : {nom}</h4>")
            popup.append(f"<b>Dernière mesure :</b> {date} {heure}<br>")
            popup.append(f"<b>Libres / Total :</b> {libres} / {total}<br>")
            popup.append(f"<b>Taux :</b> {taux}<br>")

            if taux_moy is not None:
                popup.append("<hr style='margin:8px 0;'>")
                popup.append("<b>Stats globales :</b><br>")
                popup.append(f"- moyenne : {taux_moy:.3f}<br>")
                popup.append(f"- min : {taux_min:.3f}<br>")
                popup.append(f"- max : {taux_max:.3f}<br>")

            popup.append("<hr style='margin:8px 0;'>")
            popup.append("<b>Affichage :</b> ")
            popup.append(
                f"<select onchange=\""
                f"var v=this.value;"
                f"document.getElementById('{div_jour_id}').style.display=(v=='jour'?'block':'none');"
                f"document.getElementById('{div_global_id}').style.display=(v=='global'?'block':'none');"
                f"\">"
                f"<option value='jour'>Journalier</option>"
                f"<option value='global'>Global</option>"
                f"</select>"
            )

            # Bloc JOUR
            popup.append(f"<div id='{div_jour_id}' style='display:block; margin-top:8px;'>")
            popup.append("<b>Graphe journalier :</b><br>")
            if img_jour is not None:
                popup.append(f"<img src='{img_jour}' style='width:100%; border:1px solid #ddd; border-radius:8px;'>")
            else:
                popup.append("<i>Pas assez de données pour le jour.</i>")
            popup.append("</div>")

            # Bloc GLOBAL
            popup.append(f"<div id='{div_global_id}' style='display:none; margin-top:8px;'>")
            popup.append("<b>Graphe global :</b><br>")
            if img_global is not None:
                popup.append(f"<img src='{img_global}' style='width:100%; border:1px solid #ddd; border-radius:8px;'>")
            else:
                popup.append("<i>Pas assez de données globales.</i>")
            popup.append("</div>")

            popup.append("</div>")

            # Icône voiture (FontAwesome)
            color = couleur_parking(taux)
            marker = folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color=color, icon="car", prefix="fa"),
                tooltip=f"Parking {nom}",
                popup=folium.Popup("".join(popup), max_width=380)
            )
            marker.add_to(cluster_voiture)

    # ========================================================
    # STATIONS (vélos)
    # ========================================================
    if df_velos_jour is not None:
        dsta = df_velos_jour[df_velos_jour.get("type") == "STATION"].copy()
        dsta["lat"] = pd.to_numeric(dsta["lat"], errors="coerce")
        dsta["lon"] = pd.to_numeric(dsta["lon"], errors="coerce")

        for _, row in dsta.iterrows():
            nom = row.get("nom")
            lat = row.get("lat")
            lon = row.get("lon")
            if pd.isna(lat) or pd.isna(lon):
                continue

            slug = slugifier(nom)

            velos = safe_int(row.get("velos_dispo"))
            bornes = safe_int(row.get("bornes_libres"))
            total = safe_int(row.get("total"))
            taux_places = safe_float(row.get("taux_occupation_places"))
            date = row.get("date")
            heure = row.get("heure")

            dglob = None
            if df_velos_global is not None:
                dglob = df_velos_global[
                    (df_velos_global.get("type") == "STATION") & (df_velos_global.get("nom") == nom)
                ].copy()

            djour = df_velos_jour[
                (df_velos_jour.get("type") == "STATION") & (df_velos_jour.get("nom") == nom)
            ].copy()

            img_jour = os.path.join("images", f"station_{slug}_jour.png")
            img_global = os.path.join("images", f"station_{slug}_global.png")

            chemin_img_jour = os.path.join(DOSSIER_IMAGES, f"station_{slug}_jour.png")
            chemin_img_global = os.path.join(DOSSIER_IMAGES, f"station_{slug}_global.png")

            ok_jour = plot_serie(djour, "taux_occupation_places", f"Station {nom} - jour", chemin_img_jour)
            ok_global = False
            if dglob is not None:
                ok_global = plot_serie(dglob, "taux_occupation_places", f"Station {nom} - global", chemin_img_global)

            if not ok_jour:
                img_jour = None
            if not ok_global:
                img_global = None

            taux_moy = None
            taux_max = None
            taux_min = None

            if dglob is not None and "taux_occupation_places" in dglob.columns:
                serie = pd.to_numeric(dglob["taux_occupation_places"], errors="coerce").dropna()
                if len(serie) > 0:
                    taux_moy = float(serie.mean())
                    taux_max = float(serie.max())
                    taux_min = float(serie.min())

            div_jour_id = f"vj_{slug}"
            div_global_id = f"vg_{slug}"

            popup = []
            popup.append(f"<div style='font-family:Arial; width:320px;'>")
            popup.append(f"<h4 style='margin:0 0 8px 0;'>🚲 Station vélo : {nom}</h4>")
            popup.append(f"<b>Dernière mesure :</b> {date} {heure}<br>")
            popup.append(f"<b>Vélos :</b> {velos} | <b>Bornes libres :</b> {bornes} | <b>Total :</b> {total}<br>")
            popup.append(f"<b>Taux occupation des places :</b> {taux_places}<br>")

            if taux_moy is not None:
                popup.append("<hr style='margin:8px 0;'>")
                popup.append("<b>Stats globales :</b><br>")
                popup.append(f"- moyenne : {taux_moy:.3f}<br>")
                popup.append(f"- min : {taux_min:.3f}<br>")
                popup.append(f"- max : {taux_max:.3f}<br>")

            popup.append("<hr style='margin:8px 0;'>")
            popup.append("<b>Affichage :</b> ")
            popup.append(
                f"<select onchange=\""
                f"var v=this.value;"
                f"document.getElementById('{div_jour_id}').style.display=(v=='jour'?'block':'none');"
                f"document.getElementById('{div_global_id}').style.display=(v=='global'?'block':'none');"
                f"\">"
                f"<option value='jour'>Journalier</option>"
                f"<option value='global'>Global</option>"
                f"</select>"
            )

            popup.append(f"<div id='{div_jour_id}' style='display:block; margin-top:8px;'>")
            popup.append("<b>Graphe journalier :</b><br>")
            if img_jour is not None:
                popup.append(f"<img src='{img_jour}' style='width:100%; border:1px solid #ddd; border-radius:8px;'>")
            else:
                popup.append("<i>Pas assez de données pour le jour.</i>")
            popup.append("</div>")

            popup.append(f"<div id='{div_global_id}' style='display:none; margin-top:8px;'>")
            popup.append("<b>Graphe global :</b><br>")
            if img_global is not None:
                popup.append(f"<img src='{img_global}' style='width:100%; border:1px solid #ddd; border-radius:8px;'>")
            else:
                popup.append("<i>Pas assez de données globales.</i>")
            popup.append("</div>")

            popup.append("</div>")

            # Icône vélo en ORANGE (demande)
            color = couleur_station(velos, bornes)
            # tu veux “orange” pour les vélos => on force orange, et on garde la couleur (vert/orange/rouge) en contour via CircleMarker sinon.
            # Ici on garde simple : orange pour toutes les stations (comme tu as demandé).
            marker = folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color="orange", icon="bicycle", prefix="fa"),
                tooltip=f"Station {nom}",
                popup=folium.Popup("".join(popup), max_width=380)
            )
            marker.add_to(cluster_velo)

    # Ajout clusters + groupes
    cluster_voiture.add_to(groupe_voiture)
    cluster_velo.add_to(groupe_velo)

    groupe_voiture.add_to(carte)
    groupe_velo.add_to(carte)

    # bouton pour activer/désactiver les couches
    folium.LayerControl(collapsed=False).add_to(carte)

    # Sauvegarde
    chemin_carte = os.path.join(DOSSIER_DONNEES, "carte.html")
    carte.save(chemin_carte)

    print("Carte unique générée :", chemin_carte)
    print("Images générées dans :", DOSSIER_IMAGES)


if __name__ == "__main__":
    main()
