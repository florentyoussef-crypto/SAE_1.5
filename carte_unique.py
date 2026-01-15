# ============================================================
# IMPORTS (bibliothèques)
# ============================================================

import os
# os = outils pour travailler avec les fichiers/dossiers du système :
# - construire des chemins de fichiers (os.path.join)
# - vérifier si un fichier existe
# - créer des dossiers (os.makedirs)

import json
# json = permet de lire/écrire des données au format JSON
# (format texte très utilisé par les API)

import pandas as pd
# pandas = bibliothèque très pratique pour manipuler des tableaux de données (DataFrame)
# ici on s’en sert pour transformer les snapshots en tableaux exploitables

import matplotlib.pyplot as plt
# matplotlib = bibliothèque pour tracer des graphiques et les sauvegarder en PNG

import urllib.parse
# urllib.parse = utile pour "encoder" un nom dans une URL
# ex: gérer les espaces, accents, caractères spéciaux dans une URL

import folium
# folium = bibliothèque pour générer une carte interactive (HTML) basée sur Leaflet

from folium.plugins import MarkerCluster
# MarkerCluster = plugin folium pour regrouper les marqueurs
# (évite d'avoir 200 points superposés : ça "cluster" en paquets)


# ============================================================
# PARAMÈTRES / CHEMINS
# ============================================================

DOSSIER = "donnees"
# Dossier principal où sont stockées toutes les données

FICHIER_JSONL_VOITURE = os.path.join(DOSSIER, "brut_voitures.jsonl")
FICHIER_JSONL_VELO = os.path.join(DOSSIER, "brut_velos.jsonl")
# Ces fichiers JSONL contiennent les snapshots bruts récupérés depuis l’API
# JSONL = JSON Lines : 1 ligne = 1 objet JSON (pratique pour ajouter au fur et à mesure)

DOSSIER_IMAGES = os.path.join(DOSSIER, "images")
# Dossier où on met les images PNG générées (graphiques)

DOSSIER_SERIES = os.path.join(DOSSIER, "series")
# Dossier où on met les séries JSON (pour les courbes interactives dans detail.html)

FICHIER_CARTE = "carte.html"
# Fichier HTML final généré par folium (la carte)

CHEMIN_IMAGES_HTML = "donnees/images"
# Chemin "vu depuis le site" pour afficher les PNG dans les popups de la carte
# (important : ce chemin doit correspondre à la structure de ton site)


# ============================================================
# OUTILS JSONL
# ============================================================

def lire_jsonl(chemin):
    # Cette fonction lit un fichier .jsonl
    # Chaque ligne du fichier est un JSON indépendant (un snapshot)

    lignes = []
    # "lignes" va contenir tous les objets JSON (donc tous les snapshots)

    if not os.path.exists(chemin):
        # Si le fichier n'existe pas, on renvoie une liste vide
        return lignes

    # Ouvrir le fichier en lecture ("r")
    with open(chemin, "r", encoding="utf-8") as f:
        # On lit ligne par ligne
        for line in f:
            line = line.strip()
            # .strip() supprime les espaces et retours à la ligne au début/fin

            if line != "":
                # On ignore les lignes vides
                try:
                    # json.loads transforme une chaîne JSON en dictionnaire Python
                    lignes.append(json.loads(line))
                except Exception:
                    # Si une ligne est cassée (JSON invalide), on l’ignore
                    pass

    return lignes
    # On renvoie la liste de snapshots (une liste de dict)


def extraire_lat_lon(entite):
    # Cette fonction récupère latitude/longitude dans une entité JSON de l’API Montpellier
    # Dans les données : "coordinates" est généralement [lon, lat]

    try:
        coords = entite["location"]["value"]["coordinates"]
        # On va chercher l’info dans l'objet JSON
        # S'il manque une clé quelque part, ça peut faire une erreur -> d'où le try/except

        if isinstance(coords, list) and len(coords) >= 2:
            # coords doit être une liste du style [lon, lat]
            return float(coords[1]), float(coords[0])
            # On renvoie (lat, lon) dans le bon ordre
    except Exception:
        # Si l'objet n'a pas les coordonnées ou si format inattendu
        return None, None

    return None, None
    # Par défaut, si rien de valide


def safe_get(entite, *cles):
    # Fonction "accès sécurisé"
    # Elle permet de faire : safe_get(obj, "a", "b", "c")
    # au lieu de obj["a"]["b"]["c"] qui peut casser si une clé manque

    cur = entite
    # cur pointe sur l’objet courant (au départ l’entité complète)

    for c in cles:
        # On descend clé par clé dans l’objet
        if isinstance(cur, dict) and c in cur:
            # Si cur est bien un dict et contient la clé, on avance
            cur = cur[c]
        else:
            # Sinon on renvoie None (valeur "pas trouvée")
            return None

    return cur
    # Si toutes les clés existent, on renvoie la valeur finale


# ============================================================
# NORMALISATION (transformer snapshots -> DataFrame)
# ============================================================

def snapshots_voiture_to_df(snapshots):
    # Objectif : transformer les snapshots bruts voiture en tableau pandas (DataFrame)
    # On veut une ligne par parking et par timestamp

    rows = []
    # rows = liste de dictionnaires, qui deviendra un DataFrame

    for snap in snapshots:
        # snap = 1 snapshot (1 ligne jsonl)
        ts = snap.get("timestamp")
        # timestamp = date/heure du snapshot (ex: "2026-01-10T14:20:00+01:00")

        donnees = snap.get("donnees", [])
        # donnees = liste des parkings dans ce snapshot

        if ts is None or not isinstance(donnees, list):
            # Si pas de timestamp ou "donnees" pas une liste -> on ignore ce snapshot
            continue

        for p in donnees:
            # p = un parking

            status = safe_get(p, "status", "value")
            # status permet de savoir si le parking est "Open", "Closed", etc.

            if status != "Open":
                # On ne garde que les parkings ouverts
                continue

            nom = safe_get(p, "name", "value")
            # nom du parking

            libres = safe_get(p, "availableSpotNumber", "value")
            # nombre de places libres

            total = safe_get(p, "totalSpotNumber", "value")
            # nombre total de places

            lat, lon = extraire_lat_lon(p)
            # coordonnées GPS du parking

            if nom is None or libres is None or total is None:
                # Si une info manque, on ignore ce parking
                continue

            try:
                # Conversion en float pour être sûr de pouvoir calculer
                libres = float(libres)
                total = float(total)
            except Exception:
                # Si conversion impossible, on ignore
                continue

            if total <= 0:
                # On évite une division par 0 ou un total incohérent
                continue

            taux = (total - libres) / total
            # taux = taux d'occupation
            # Exemple :
            # total=100, libres=30 => occupées=70 => taux=70/100=0.70

            rows.append({
                "timestamp": ts,
                "nom": str(nom),
                "libres": libres,
                "total": total,
                "taux": taux,
                "lat": lat,
                "lon": lon
            })
            # On ajoute une ligne "propre" dans rows

    df = pd.DataFrame(rows)
    # Création du DataFrame à partir de la liste de lignes

    if len(df) == 0:
        # Si pas de données, on renvoie le DataFrame vide
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    # Conversion timestamp texte -> datetime pandas
    # errors="coerce" : si une date est invalide -> devient NaT (valeur manquante)

    df = df.dropna(subset=["timestamp", "nom"])
    # On supprime les lignes où timestamp ou nom est manquant

    return df


def snapshots_velo_to_df(snapshots):
    # Même principe que voiture mais pour les stations vélos

    rows = []

    for snap in snapshots:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if ts is None or not isinstance(donnees, list):
            continue

        for s in donnees:
            # s = une station vélo

            nom = safe_get(s, "address", "value", "streetAddress")
            # nom station (adresse)

            velos = safe_get(s, "availableBikeNumber", "value")
            # vélos disponibles

            bornes = safe_get(s, "freeSlotNumber", "value")
            # bornes libres (emplacements libres pour poser un vélo)

            total = safe_get(s, "totalSlotNumber", "value")
            # nb total d'emplacements

            lat, lon = extraire_lat_lon(s)
            # coordonnées GPS station

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
            # ici taux_places = taux d'occupation des emplacements
            # bornes = emplacements libres
            # total - bornes = emplacements occupés (vélo présent)
            # donc taux_places proche de 1 => station pleine de vélos

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
# GRAPHIQUES PNG
# ============================================================

def nettoyer_nom_fichier(nom):
    # But : éviter des caractères interdits dans un nom de fichier
    # exemple : "Parking/Comédie" -> "Parking_Comédie"

    for ch in ["/", "\\", ":", "?", "*", '"', "'"]:
        nom = nom.replace(ch, "_")
    return nom


def generer_graphe_journalier(df, colonne, nom_objet, prefix):
    # Génère un PNG sur le dernier jour disponible pour un parking/station
    # colonne = la colonne à tracer (ex: "taux" ou "taux_places")
    # prefix = "parking" ou "velo" pour distinguer les fichiers

    if len(df) == 0:
        return None

    df2 = df[df["nom"] == nom_objet].copy()
    # df2 = toutes les lignes concernant l'objet (parking/station)

    df2 = df2.dropna(subset=["timestamp", colonne])
    # On supprime les lignes incomplètes

    if len(df2) == 0:
        return None

    jour_max = df2["timestamp"].dt.date.max()
    # On cherche la date la plus récente (dernier jour)

    df2 = df2[df2["timestamp"].dt.date == jour_max].copy()
    # On garde uniquement les points du dernier jour

    df2 = df2.sort_values("timestamp")
    # Tri chronologique pour que la courbe soit correcte

    if len(df2) == 0:
        return None

    nom_f = nettoyer_nom_fichier(nom_objet)
    # Nom sécurisé pour un fichier

    fichier = f"{prefix}_{nom_f}_journalier.png"
    # Exemple : parking_Parking_Comedie_journalier.png

    chemin = os.path.join(DOSSIER_IMAGES, fichier)
    # Chemin complet dans donnees/images/

    plt.figure()
    # On crée une nouvelle figure (graphique)

    plt.plot(df2["timestamp"], df2[colonne])
    # Courbe : x = temps, y = valeur

    plt.title(f"{nom_objet} - journalier ({jour_max})")
    plt.xlabel("Heure")
    plt.ylabel(colonne)

    plt.xticks(rotation=45)
    # Rotation des labels de dates pour que ce soit lisible

    plt.tight_layout()
    # Ajuste automatiquement la mise en page pour éviter que ça déborde

    plt.savefig(chemin)
    # Sauvegarde en PNG

    plt.close()
    # Ferme la figure (important pour ne pas consommer trop de mémoire)

    return fichier
    # On renvoie juste le nom du fichier (pour l'afficher dans le popup)


def generer_graphe_global(df, colonne, nom_objet, prefix):
    # Génère un PNG sur toute la période (pas seulement le dernier jour)

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
# SERIES JSON pour graphique interactif (detail.html)
# ============================================================

def ecrire_serie_json(df, nom_objet, colonne, prefix):
    # But : écrire un fichier JSON "points" (timestamp + value)
    # pour pouvoir faire un graphique interactif dans une page HTML

    df2 = df[df["nom"] == nom_objet].copy()
    df2 = df2.dropna(subset=["timestamp", colonne]).sort_values("timestamp")

    if len(df2) == 0:
        return None

    nom_f = nettoyer_nom_fichier(nom_objet)
    fichier = f"{prefix}_{nom_f}.json"
    chemin = os.path.join(DOSSIER_SERIES, fichier)

    data = []
    # data = liste de points pour le graphique

    for _, r in df2.iterrows():
        # iterrows() = on parcourt ligne par ligne le DataFrame
        data.append({
            "timestamp": r["timestamp"].isoformat(),
            "value": float(r[colonne])
        })

    with open(chemin, "w", encoding="utf-8") as f:
        # On écrit un vrai fichier JSON complet (pas jsonl ici)
        json.dump({
            "name": nom_objet,
            "column": colonne,
            "points": data
        }, f, ensure_ascii=False)

    return fichier


# ============================================================
# POPUPS HTML (texte quand on clique sur un point)
# ============================================================

def popup_parking(nom, libres, total, taux, img_j, img_g):
    # Fabrique le HTML affiché quand on clique sur un parking sur la carte

    nom_enc = urllib.parse.quote(nom)
    # Encode le nom pour le mettre dans une URL
    # ex: "Rue de la Loge" -> "Rue%20de%20la%20Loge"

    html = f"""
    <div style="width: 320px;">
      <h4 style="margin:0;">🚗 {nom}</h4>
      <hr style="margin:6px 0;">
      <b>Places libres :</b> {int(libres)}<br>
      <b>Capacité totale :</b> {int(total)}<br>
      <b>Taux occupation :</b> {taux:.2%}<br>
      <hr style="margin:6px 0;">
      <a href="detail.html?type=parking&name={nom_enc}" target="_blank">📈 Graphique interactif</a>
    """
    # {taux:.2%} = format pour afficher en pourcentage avec 2 décimales
    # exemple : 0.7234 -> 72.34%

    if img_j is not None:
        # Si le graphe journalier existe, on l’affiche
        html += f'<hr style="margin:6px 0;"><b>Courbe journalier</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_j}" width="300">'

    if img_g is not None:
        # Si le graphe global existe, on l’affiche
        html += f'<hr style="margin:6px 0;"><b>Courbe global</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_g}" width="300">'

    html += "</div>"
    return html


def popup_velo(nom, velos, bornes_libres, total, taux_places, img_j, img_g):
    # Même principe que parking mais pour station vélo

    nom_enc = urllib.parse.quote(nom)

    html = f"""
    <div style="width: 320px;">
      <h4 style="margin:0;">🚲 {nom}</h4>
      <hr style="margin:6px 0;">
      <b>Vélos dispo :</b> {int(velos)}<br>
      <b>Bornes libres :</b> {int(bornes_libres)}<br>
      <b>Total bornes :</b> {int(total)}<br>
      <b>Taux occupation places :</b> {taux_places:.2%}<br>
      <hr style="margin:6px 0;">
      <a href="detail.html?type=velo&name={nom_enc}" target="_blank">📈 Graphique interactif</a>
    """

    if img_j is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe journalier</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_j}" width="300">'
    if img_g is not None:
        html += f'<hr style="margin:6px 0;"><b>Courbe global</b><br><img src="{CHEMIN_IMAGES_HTML}/{img_g}" width="300">'
    html += "</div>"
    return html


# ============================================================
# MAIN (ce qui s’exécute réellement)
# ============================================================

def main():
    # ----------------------------------------------------------
    # 1) Créer les dossiers si besoin
    # ----------------------------------------------------------
    os.makedirs(DOSSIER, exist_ok=True)
    os.makedirs(DOSSIER_IMAGES, exist_ok=True)
    os.makedirs(DOSSIER_SERIES, exist_ok=True)
    # exist_ok=True = si le dossier existe déjà, pas d’erreur

    # ----------------------------------------------------------
    # 2) Lire les snapshots bruts (jsonl)
    # ----------------------------------------------------------
    snaps_voiture = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_velo = lire_jsonl(FICHIER_JSONL_VELO)

    # ----------------------------------------------------------
    # 3) Convertir snapshots -> DataFrame (tableau)
    # ----------------------------------------------------------
    df_voiture = snapshots_voiture_to_df(snaps_voiture)
    df_velo = snapshots_velo_to_df(snaps_velo)

    if len(df_voiture) == 0 and len(df_velo) == 0:
        # Si aucun des deux n'a de données, la carte ne peut pas être faite
        print("Aucune donnée snapshot trouvée (JSONL).")
        return

    # ----------------------------------------------------------
    # 4) Calcul "dernière mise à jour" (pour index.html)
    # ----------------------------------------------------------
    last_ts = None

    if len(df_voiture) > 0:
        last_ts = df_voiture["timestamp"].max()
        # max() = la date la plus récente

    if len(df_velo) > 0:
        v = df_velo["timestamp"].max()
        if last_ts is None or v > last_ts:
            last_ts = v

    if last_ts is not None:
        # On écrit un fichier JSON simple
        with open(os.path.join(DOSSIER, "last_update.json"), "w", encoding="utf-8") as f:
            json.dump({"last_update": last_ts.isoformat()}, f, ensure_ascii=False)

    # ----------------------------------------------------------
    # 5) Calcul du centre de la carte (moyenne des lat/lon)
    # ----------------------------------------------------------
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
        # Si on n'a aucune coordonnée valide, impossible de placer la carte
        print("Pas de coordonnées GPS exploitables.")
        return

    centre_lat = sum(latitudes) / len(latitudes)
    centre_lon = sum(longitudes) / len(longitudes)
    # On prend la moyenne des positions pour centrer Montpellier automatiquement

    # ----------------------------------------------------------
    # 6) Création de la carte folium
    # ----------------------------------------------------------
    carte = folium.Map(location=[centre_lat, centre_lon], zoom_start=13, tiles="OpenStreetMap")
    # location = centre
    # zoom_start = niveau de zoom initial
    # tiles = fond de carte OpenStreetMap

    # ----------------------------------------------------------
    # 7) Ajout de boutons HTML fixes sur la carte
    # ----------------------------------------------------------
    boutons = """
    <div style="
      position: fixed;
      top: 70px;
      left: 15px;
      z-index: 99999;
      background: white;
      padding: 10px 12px;
      border-radius: 12px;
      box-shadow: 0 10px 20px rgba(0,0,0,0.12);
      border: 1px solid #ebedf0;
      font-family: Outfit, sans-serif;
      display: flex;
      gap: 10px;
      align-items: center;
    ">
      <a href="index.html" style="text-decoration:none;font-weight:700;color:#3498db;">← Retour</a>
      <span style="color:#dfe6e9;">|</span>
      <a href="analyse_globale.html" style="text-decoration:none;font-weight:700;color:#2d3436;">📊 Analyse globale</a>
    </div>
    """
    # Ce gros HTML sert à afficher un petit panneau avec des liens
    # position: fixed = reste fixe même si on bouge la carte

    carte.get_root().html.add_child(folium.Element(boutons))
    # On injecte ce HTML dans la page folium

    # ----------------------------------------------------------
    # 8) Clusters de marqueurs (regroupement)
    # ----------------------------------------------------------
    cluster_voiture = MarkerCluster(name="🚗 Parkings voiture")
    cluster_velo = MarkerCluster(name="🚲 Stations vélo")
    # name = nom affiché dans le contrôle de couches (LayerControl)

    # ----------------------------------------------------------
    # 9) Catalog = liste des séries, pour d'autres pages (detail, correlation)
    # ----------------------------------------------------------
    catalog = {
        "parkings": [],
        "stations": []
    }

    # ----------------------------------------------------------
    # 10) Ajout des marqueurs voitures
    # ----------------------------------------------------------
    if len(df_voiture) > 0:
        df_voiture_ok = df_voiture.dropna(subset=["lat", "lon"]).copy()
        # On supprime les lignes sans coordonnées GPS

        df_voiture_ok = df_voiture_ok.sort_values("timestamp")
        # Tri par date

        dernier = df_voiture_ok.groupby("nom").tail(1)
        # groupby("nom") = groupe par parking
        # tail(1) = on garde la dernière mesure de chaque parking
        # => donc 1 marqueur par parking sur la carte, avec données les plus récentes

        for _, row in dernier.iterrows():
            # On boucle sur chaque parking

            nom = row["nom"]
            libres = row["libres"]
            total = row["total"]
            taux = row["taux"]
            lat = row["lat"]
            lon = row["lon"]

            # Génération des images PNG
            img_j = generer_graphe_journalier(df_voiture_ok, "taux", nom, "parking")
            img_g = generer_graphe_global(df_voiture_ok, "taux", nom, "parking")

            # Génération de la série JSON (pour detail.html)
            serie_file = ecrire_serie_json(df_voiture_ok, nom, "taux", "parking")
            if serie_file:
                catalog["parkings"].append({
                    "name": nom,
                    "series": f"donnees/series/{serie_file}"
                })
                # On stocke le nom et le chemin vers la série pour les pages web

            pop = popup_parking(nom, libres, total, taux, img_j, img_g)
            # pop = HTML du popup

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(pop, max_width=420),
                icon=folium.Icon(color="blue", icon="car", prefix="fa")
            ).add_to(cluster_voiture)
            # On ajoute le marqueur au cluster voiture

    # ----------------------------------------------------------
    # 11) Ajout des marqueurs vélos
    # ----------------------------------------------------------
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

            serie_file = ecrire_serie_json(df_velo_ok, nom, "taux_places", "velo")
            if serie_file:
                catalog["stations"].append({
                    "name": nom,
                    "series": f"donnees/series/{serie_file}"
                })

            pop = popup_velo(nom, velos, bornes_libres, total, taux_places, img_j, img_g)

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(pop, max_width=420),
                icon=folium.Icon(color="green", icon="bicycle", prefix="fa")
            ).add_to(cluster_velo)

    # ----------------------------------------------------------
    # 12) Sauvegarde du catalogue
    # ----------------------------------------------------------
    with open(os.path.join(DOSSIER, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    # indent=2 = joli JSON bien formaté, plus lisible

    # ----------------------------------------------------------
    # 13) Ajout des clusters à la carte + contrôle des couches
    # ----------------------------------------------------------
    cluster_voiture.add_to(carte)
    cluster_velo.add_to(carte)

    folium.LayerControl(collapsed=False).add_to(carte)
    # LayerControl = petit menu pour activer/désactiver les couches

    # ----------------------------------------------------------
    # 14) Sauvegarde HTML final
    # ----------------------------------------------------------
    carte.save(FICHIER_CARTE)


# ============================================================
# POINT D’ENTRÉE (si on lance le script directement)
# ============================================================

if __name__ == "__main__":
    main()
    # Cette ligne lance la fonction main() uniquement si on exécute ce fichier :
    # python carte_unique.py
    # (et pas si le fichier est importé par un autre script)
