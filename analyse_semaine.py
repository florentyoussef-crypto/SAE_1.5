# ============================================================
# IMPORTS (bibliothèques Python utilisées)
# ============================================================
import os                 # Sert à gérer les chemins de fichiers/dossiers (ex: "donnees/images")
import json               # Sert à lire/écrire des fichiers JSON (ex: snapshots et résultats)
import pandas as pd       # Sert à manipuler des tableaux de données (DataFrame) et à faire des calculs (corrélation)
import matplotlib.pyplot as plt  # Sert à tracer des graphiques et à les sauvegarder en PNG


# ============================================================
# CONSTANTES / CHEMINS (où sont les fichiers)
# ============================================================

DOSSIER_DONNEES = "donnees"
# Dossier principal qui contient toutes les données générées.

DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")
# Dossier où l’on va enregistrer les images PNG (courbes).

DOSSIER_SERIES_GLOBAL = os.path.join(DOSSIER_DONNEES, "series_global")
# Dossier où l’on va enregistrer des séries JSON “globales”
# (pour Plotly sur le site web).

FICHIER_JSONL_VOITURE = os.path.join(DOSSIER_DONNEES, "brut_voitures.jsonl")
# Fichier “brut” qui contient tous les snapshots voiture (format JSONL).

FICHIER_JSONL_VELO = os.path.join(DOSSIER_DONNEES, "brut_velos.jsonl")
# Fichier “brut” qui contient tous les snapshots vélo (format JSONL).


# ============================================================
# AJOUT : PARAMETRES POUR EXCLURE LES CAPTEURS "BLOQUES"
# ============================================================

FICHIER_PARKINGS_EXCLUS = os.path.join(DOSSIER_DONNEES, "parkings_exclus.json")
# Fichier où l’on enregistre la liste des parkings considérés "buggés" / bloqués.

MIN_POINTS_CAPTEUR = 20
# Minimum de points (mesures) pour juger qu’un capteur est bloqué (sinon on ne conclut pas).

EPS_STD = 0.001
# Si l’écart-type du taux est inférieur à EPS_STD, on considère que ça bouge trop peu (suspect).

ROUND_FOR_UNIQUE = 3
# Pour compter les valeurs "différentes" on arrondit (sinon bruit flottant).
# Exemple : 0.3000000001 et 0.2999999999 deviennent 0.300

MAX_UNIQUE_VALUES = 2
# Si un parking a <= MAX_UNIQUE_VALUES valeurs différentes (après arrondi) sur beaucoup de points,
# c’est typiquement un capteur bloqué (toujours identique ou presque identique).


# ============================================================
# OUTILS "SYSTÈME" (dossiers / fichiers)
# ============================================================

def creer_dossier_si_absent(path):
    # Cette fonction vérifie si un dossier existe.
    # Si le dossier n’existe pas, elle le crée.
    # Exemple : créer "donnees/images" si ce dossier n’est pas encore créé.
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def fichiers_journaliers(suffixe):
    # Cette fonction cherche dans le dossier "donnees" tous les fichiers
    # qui commencent par "jour_" et qui finissent par le suffixe demandé.
    # Exemple : suffixe = "_voitures.csv"
    # → récupère tous les fichiers : jour_XXXX_voitures.csv
    fichiers = []
    if not os.path.isdir(DOSSIER_DONNEES):
        return fichiers

    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        # On ne garde que les fichiers journaliers du bon type
        if nom_fichier.startswith("jour_") and nom_fichier.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom_fichier))

    return fichiers


# ============================================================
# OUTIL "safe_get" (accès sécurisé dans un gros dictionnaire JSON)
# ============================================================

def safe_get(entite, *cles):
    # Cette fonction sert à récupérer une valeur dans un dictionnaire,
    # même si certaines clés n’existent pas.
    #
    # Exemple :
    # safe_get(p, "status", "value")
    # revient à essayer de faire :
    # p["status"]["value"]
    #
    # Si une des clés n’existe pas, on renvoie None au lieu de crasher.
    cur = entite
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


# ============================================================
# LECTURE JSONL (format : 1 ligne = 1 JSON)
# ============================================================

def lire_jsonl(chemin):
    # JSONL = fichier texte où chaque ligne est un objet JSON.
    # Exemple :
    # {"timestamp": "...", "donnees": [...]}
    # {"timestamp": "...", "donnees": [...]}
    #
    # Cette fonction lit toutes les lignes et renvoie une liste d’objets Python (dict).
    lignes = []
    if not os.path.exists(chemin):
        return lignes

    with open(chemin, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    # json.loads transforme le texte JSON en dictionnaire Python
                    lignes.append(json.loads(line))
                except Exception:
                    # Si une ligne est cassée, on l’ignore
                    pass

    return lignes


# ============================================================
# AJOUT : DETECTION DES PARKINGS "BLOQUES" (CAPTEUR BUG)
# ============================================================

def detecter_parkings_bloques_depuis_brut():
    # Objectif :
    # - Lire brut_voitures.jsonl (snapshots)
    # - Reconstituer, pour chaque parking, la série de taux d'occupation
    # - Détecter ceux qui varient presque jamais (capteur bloqué)
    # - Retourner un set() de noms de parkings à exclure

    snaps = lire_jsonl(FICHIER_JSONL_VOITURE)

    # Dictionnaire : nom_parking -> liste des taux observés dans le temps
    series_by_name = {}

    for snap in snaps:
        donnees = snap.get("donnees", [])
        if not isinstance(donnees, list):
            continue

        for p in donnees:
            if safe_get(p, "status", "value") != "Open":
                continue

            nom = safe_get(p, "name", "value")
            libres = safe_get(p, "availableSpotNumber", "value")
            total = safe_get(p, "totalSpotNumber", "value")

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

            n = str(nom)
            if n not in series_by_name:
                series_by_name[n] = []
            series_by_name[n].append(float(taux))

    exclus = set()

    # On analyse chaque parking séparément
    for nom, vals in series_by_name.items():
        if len(vals) < MIN_POINTS_CAPTEUR:
            # Pas assez de points pour conclure -> on ne l'exclut pas
            continue

        s = pd.Series(vals)

        # 1) Mesure "bouge-t-il ?" -> écart-type
        std = float(s.std(ddof=0)) if len(s) > 0 else 999.0

        # 2) Combien de valeurs différentes (après arrondi) ?
        nunique = int(pd.Series([round(v, ROUND_FOR_UNIQUE) for v in vals]).nunique())

        # Critère de "capteur bloqué"
        if std <= EPS_STD or nunique <= MAX_UNIQUE_VALUES:
            exclus.add(nom)

    return exclus


def sauvegarder_parkings_exclus(exclus_set):
    # On écrit un JSON simple, lisible, utile pour ton site/diapo.
    creer_dossier_si_absent(DOSSIER_DONNEES)

    out = {
        "rule": {
            "min_points": int(MIN_POINTS_CAPTEUR),
            "eps_std": float(EPS_STD),
            "round_for_unique": int(ROUND_FOR_UNIQUE),
            "max_unique_values": int(MAX_UNIQUE_VALUES)
        },
        "count_excluded": int(len(exclus_set)),
        "excluded": sorted(list(exclus_set))
    }

    with open(FICHIER_PARKINGS_EXCLUS, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


# ============================================================
# CALCULS : TAUX D'OCCUPATION VOITURE (niveau "ville")
# ============================================================

def calculer_taux_ville_voiture(donnees_parking, exclude_names=None):
    # Ici, on calcule un taux global pour "la ville" à partir de tous les parkings.
    #
    # Formule pour 1 parking :
    # taux = (total - libres) / total
    #
    # Là, on additionne tous les totals et tous les libres pour faire un taux global.

    # AJOUT : exclude_names est un set() de parkings qu’on ignore (capteurs buggés).
    if exclude_names is None:
        exclude_names = set()

    somme_total = 0.0
    somme_libres = 0.0

    for p in donnees_parking:
        # On ignore les parkings fermés
        if safe_get(p, "status", "value") != "Open":
            continue

        # AJOUT : on ignore les parkings "exclus"
        nom = safe_get(p, "name", "value")
        if nom is not None and str(nom) in exclude_names:
            continue

        libres = safe_get(p, "availableSpotNumber", "value")
        total = safe_get(p, "totalSpotNumber", "value")

        if libres is None or total is None:
            continue

        try:
            libres = float(libres)
            total = float(total)
        except Exception:
            continue

        # On évite la division par zéro ou les valeurs invalides
        if total <= 0:
            continue

        somme_total += total
        somme_libres += libres

    if somme_total <= 0:
        return None

    # Taux global ville = (capacité totale - places libres) / capacité totale
    return (somme_total - somme_libres) / somme_total


# ============================================================
# CALCULS : TAUX D'OCCUPATION VELO (moyenne sur toutes les stations)
# ============================================================

def calculer_moyenne_taux_places_velo(donnees_stations):
    # Ici, on calcule un taux moyen côté vélo.
    #
    # Pour chaque station :
    # taux_places = (total - bornes_libres) / total
    #
    # Puis on fait la moyenne des taux de toutes les stations.
    vals = []

    for s in donnees_stations:
        bornes = safe_get(s, "freeSlotNumber", "value")   # bornes libres (places dispo)
        total = safe_get(s, "totalSlotNumber", "value")   # bornes totales

        if bornes is None or total is None:
            continue

        try:
            bornes = float(bornes)
            total = float(total)
        except Exception:
            continue

        if total <= 0:
            continue

        taux_places = (total - bornes) / total
        vals.append(taux_places)

    if len(vals) == 0:
        return None

    return sum(vals) / len(vals)


# ============================================================
# CORRELATION GLOBALE (depuis les fichiers brut_*.jsonl)
# ============================================================

def correlation_globale_depuis_brut(exclude_names=None):
    # Objectif :
    # - Lire tous les snapshots voiture et vélo
    # - Calculer une série "taux voiture ville" et une série "taux vélo moyen"
    # - Aligner uniquement les timestamps EXACTS communs
    # - Calculer la corrélation de Pearson sur ces points
    # - Écrire le résultat dans donnees/correlation_global.json

    # AJOUT : si exclude_names est fourni, on ignore ces parkings dans le taux voiture ville
    if exclude_names is None:
        exclude_names = set()

    snaps_v = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_b = lire_jsonl(FICHIER_JSONL_VELO)

    # Dictionnaire : timestamp -> taux voiture ville
    car_by_ts = {}
    for snap in snaps_v:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue

        v = calculer_taux_ville_voiture(donnees, exclude_names=exclude_names)
        if v is not None:
            car_by_ts[ts] = v

    # Dictionnaire : timestamp -> taux vélo moyen
    bike_by_ts = {}
    for snap in snaps_b:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue

        v = calculer_moyenne_taux_places_velo(donnees)
        if v is not None:
            bike_by_ts[ts] = v

    # On garde uniquement les timestamps communs (exactement les mêmes)
    common = sorted(set(car_by_ts.keys()) & set(bike_by_ts.keys()))

    # Si pas assez de points, on écrit "correlation: None"
    if len(common) < 5:
        out = {"correlation": None, "n_points": len(common), "method": "pearson", "aligned": "exact_timestamp"}
        with open(os.path.join(DOSSIER_DONNEES, "correlation_global.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        return

    # Série x = voiture, série y = vélo (alignées sur common)
    x = [car_by_ts[t] for t in common]
    y = [bike_by_ts[t] for t in common]

    # pd.Series(...).corr(...) calcule la corrélation de Pearson automatiquement
    s = pd.Series(x).corr(pd.Series(y))

    out = {"correlation": float(s), "n_points": len(common), "method": "pearson", "aligned": "exact_timestamp"}
    with open(os.path.join(DOSSIER_DONNEES, "correlation_global.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


# ============================================================
# CORRELATION GLISSANTE (rolling) pour afficher une courbe dans le site
# ============================================================

def correlation_glissante_depuis_brut(window=12, exclude_names=None):
    """
    Génère donnees/series_global/corr_voiture_velo.json
    Corrélation Pearson glissante sur timestamps EXACTS communs.
    """

    # AJOUT : si exclude_names est fourni, on ignore ces parkings dans le taux voiture ville
    if exclude_names is None:
        exclude_names = set()

    snaps_v = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_b = lire_jsonl(FICHIER_JSONL_VELO)

    car_by_ts = {}
    for snap in snaps_v:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue
        v = calculer_taux_ville_voiture(donnees, exclude_names=exclude_names)
        if v is not None:
            car_by_ts[ts] = v

    bike_by_ts = {}
    for snap in snaps_b:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue
        v = calculer_moyenne_taux_places_velo(donnees)
        if v is not None:
            bike_by_ts[ts] = v

    common = sorted(set(car_by_ts.keys()) & set(bike_by_ts.keys()))
    out_path = os.path.join(DOSSIER_SERIES_GLOBAL, "corr_voiture_velo.json")

    # Si on n’a pas assez de points pour faire une corrélation glissante
    if len(common) < max(5, window):
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "Corrélation voiture ↔ vélo (glissante)",
                "title": "Corrélation voiture ↔ vélo (glissante)",
                "window": int(window),
                "n_points": int(len(common)),
                "aligned": "exact_timestamp",
                "method": "pearson",
                "points": []
            }, f, ensure_ascii=False)
        return

    # On aligne dans un DataFrame (plus pratique pour rolling/corr)
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(common, errors="coerce"),
        "car": [car_by_ts[t] for t in common],
        "bike": [bike_by_ts[t] for t in common],
    }).dropna(subset=["timestamp", "car", "bike"]).sort_values("timestamp")

    if len(df) < max(5, window):
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "Corrélation voiture ↔ vélo (glissante)",
                "title": "Corrélation voiture ↔ vélo (glissante)",
                "window": int(window),
                "n_points": int(len(df)),
                "aligned": "exact_timestamp",
                "method": "pearson",
                "points": []
            }, f, ensure_ascii=False)
        return

    # rolling(window).corr(...) calcule la corrélation sur une fenêtre glissante
    corr_roll = df["car"].rolling(window).corr(df["bike"])

    # On prépare une liste de points {timestamp, value} pour Plotly
    points = []
    for ts, val in zip(df["timestamp"], corr_roll):
        # Au début, rolling renvoie NaN car pas assez de points
        if pd.isna(ts) or pd.isna(val):
            continue
        points.append({
            "timestamp": pd.to_datetime(ts).isoformat(),
            "value": float(val)
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "name": "Corrélation voiture ↔ vélo (glissante)",
            "title": "Corrélation voiture ↔ vélo (glissante)",
            "window": int(window),
            "n_points": int(len(df)),
            "aligned": "exact_timestamp",
            "method": "pearson",
            "points": points
        }, f, ensure_ascii=False)


# ============================================================
# ECRITURE D'UNE SERIE JSON (pour Plotly sur le site)
# ============================================================

def ecrire_serie_global(nom_fichier, title, x_ts, y_vals):
    # Cette fonction écrit un fichier JSON de la forme :
    # {
    #   "title": "...",
    #   "points": [{"timestamp": "...", "value": ...}, ...]
    # }
    #
    # L’intérêt : le site web peut lire ce JSON et afficher une courbe Plotly.
    creer_dossier_si_absent(DOSSIER_SERIES_GLOBAL)

    points = []
    for t, v in zip(x_ts, y_vals):
        # On ignore les valeurs invalides
        if pd.isna(t) or pd.isna(v):
            continue
        points.append({
            "timestamp": pd.to_datetime(t).isoformat(),
            "value": float(v)
        })

    out = {"title": title, "points": points}
    with open(os.path.join(DOSSIER_SERIES_GLOBAL, nom_fichier), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


# ============================================================
# ANALYSE VOITURES (depuis les CSV journaliers)
# ============================================================

def analyser_voitures(exclude_names=None):
    # On récupère tous les fichiers journaliers voiture (jour_..._voitures.csv)
    fichiers = fichiers_journaliers("_voitures.csv")
    if len(fichiers) == 0:
        print("Aucun fichier _voitures.csv trouvé")
        return

    # On lit tous les CSV puis on les concatène en un seul grand DataFrame
    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        # On garde le nom du fichier d’origine (utile pour debug)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Convertir les colonnes en type numérique/date
    df["taux_occupation"] = pd.to_numeric(df["taux_occupation"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # --- Courbe "VILLE" ---
    df_ville = df[df["type"] == "VILLE"].dropna(subset=["taux_occupation", "timestamp"]).sort_values("timestamp")

    # AJOUT : si on a une liste de parkings exclus, on reconstruit une courbe "ville"
    # à partir des lignes PARKING (plus fiable), en ignorant les capteurs bloqués.
    df_p_all = df[df["type"] == "PARKING"].dropna(subset=["taux_occupation", "timestamp"]).copy()

    df_ville_calc = None
    if exclude_names is not None and len(df_p_all) > 0:
        df_p_ok = df_p_all[~df_p_all["nom"].astype(str).isin(set(exclude_names))].copy()
        if len(df_p_ok) > 0:
            # moyenne simple des taux par timestamp (démo claire et stable)
            df_ville_calc = df_p_ok.groupby("timestamp")["taux_occupation"].mean().reset_index()
            df_ville_calc = df_ville_calc.sort_values("timestamp")

    # Si on a des données, on trace une courbe globale et on la sauvegarde
    if df_ville_calc is not None and len(df_ville_calc) > 0:
        plt.figure()
        plt.plot(df_ville_calc["taux_occupation"].values)
        plt.title("Taux d'occupation voiture - VILLE (global)")
        plt.xlabel("Mesure (ordre chronologique)")
        plt.ylabel("Taux")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_IMAGES, "courbe_voitures_ville.png"))
        plt.close()

        # On écrit aussi la série en JSON pour le site
        ecrire_serie_global(
            "voiture_ville.json",
            "Taux d'occupation voiture - VILLE (global)",
            df_ville_calc["timestamp"].tolist(),
            df_ville_calc["taux_occupation"].tolist()
        )

    elif len(df_ville) > 0:
        plt.figure()
        plt.plot(df_ville["taux_occupation"].values)
        plt.title("Taux d'occupation voiture - VILLE (global)")
        plt.xlabel("Mesure (ordre chronologique)")
        plt.ylabel("Taux")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_IMAGES, "courbe_voitures_ville.png"))
        plt.close()

        # On écrit aussi la série en JSON pour le site
        ecrire_serie_global(
            "voiture_ville.json",
            "Taux d'occupation voiture - VILLE (global)",
            df_ville["timestamp"].tolist(),
            df_ville["taux_occupation"].tolist()
        )

    # --- Analyse par parking ---
    df_p = df[df["type"] == "PARKING"].dropna(subset=["taux_occupation", "timestamp"]).copy()

    # AJOUT : on retire les parkings exclus des stats "top 10" (sinon ça fausse)
    if exclude_names is not None and len(df_p) > 0:
        df_p = df_p[~df_p["nom"].astype(str).isin(set(exclude_names))].copy()

    if len(df_p) > 0:
        # Parking saturé = taux >= 0.95
        df_p["sature"] = df_p["taux_occupation"] >= 0.95

        # Compter le nombre de fois où chaque parking est saturé
        sat = df_p[df_p["sature"]].groupby("nom").size().sort_values(ascending=False)
        print("\nTop 10 parkings souvent saturés (>=95%)")
        print(sat.head(10))

        # Moyenne du taux d’occupation par parking
        moy = df_p.groupby("nom")["taux_occupation"].mean().sort_values(ascending=False)
        print("\nTop 10 parkings les plus occupés (moyenne)")
        print(moy.head(10))


# ============================================================
# ANALYSE VELOS (depuis les CSV journaliers)
# ============================================================

def analyser_velos():
    # On récupère tous les fichiers journaliers vélo (jour_..._velos.csv)
    fichiers = fichiers_journaliers("_velos.csv")
    if len(fichiers) == 0:
        print("Aucun fichier _velos.csv trouvé")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df["taux_occupation_places"] = pd.to_numeric(df["taux_occupation_places"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # On garde uniquement les stations
    df_s = df[df["type"] == "STATION"].dropna(subset=["taux_occupation_places", "timestamp"]).copy()

    if len(df_s) > 0:
        # Moyenne des taux sur toutes les stations, à chaque timestamp
        moy_par_temps = df_s.groupby("timestamp")["taux_occupation_places"].mean().reset_index()
        moy_par_temps = moy_par_temps.sort_values("timestamp")

        plt.figure()
        plt.plot(moy_par_temps["taux_occupation_places"].values)
        plt.title("Occupation vélos - moyenne stations (global)")
        plt.xlabel("Mesure (ordre chronologique)")
        plt.ylabel("Taux occupation places")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_IMAGES, "courbe_velos_moyenne.png"))
        plt.close()

        ecrire_serie_global(
            "velo_moyenne.json",
            "Occupation vélos - moyenne stations (global)",
            moy_par_temps["timestamp"].tolist(),
            moy_par_temps["taux_occupation_places"].tolist()
        )


# ============================================================
# ANALYSE RELAIS (depuis les CSV journaliers relais1)
# ============================================================

def analyser_relais():
    # On récupère tous les fichiers journaliers relais (jour_..._relais1.csv)
    fichiers = fichiers_journaliers("_relais1.csv")
    if len(fichiers) == 0:
        print("Aucun fichier _relais1.csv trouvé")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df["relais_ok"] = pd.to_numeric(df["relais_ok"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # On ne garde que la ligne "RESUME" (résumé global)
    df_resume = df[df["parking"] == "RESUME"].dropna(subset=["relais_ok", "timestamp"]).sort_values("timestamp")

    if len(df_resume) > 0:
        plt.figure()
        plt.plot(df_resume["relais_ok"].values)
        plt.title("Relais voiture/vélo - proportion OK (global)")
        plt.xlabel("Mesure (ordre chronologique)")
        plt.ylabel("Proportion")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_IMAGES, "courbe_relais.png"))
        plt.close()

        ecrire_serie_global(
            "relais_ok.json",
            "Relais voiture/vélo - proportion OK (global)",
            df_resume["timestamp"].tolist(),
            df_resume["relais_ok"].tolist()
        )


# ============================================================
# MAIN (fonction principale)
# ============================================================

def main():
    # On crée les dossiers nécessaires
    creer_dossier_si_absent(DOSSIER_IMAGES)
    creer_dossier_si_absent(DOSSIER_SERIES_GLOBAL)

    # AJOUT : on détecte les parkings "capteur bloqué" et on les enregistre
    exclus = detecter_parkings_bloques_depuis_brut()
    sauvegarder_parkings_exclus(exclus)

    # Analyses à partir des CSV journaliers
    analyser_voitures(exclude_names=exclus)
    analyser_velos()
    analyser_relais()

    # Corrélation globale (fichier correlation_global.json)
    correlation_globale_depuis_brut(exclude_names=exclus)

    # Corrélation glissante (fichier corr_voiture_velo.json pour correlation.html)
    correlation_glissante_depuis_brut(window=12, exclude_names=exclus)

    # résumé console
    print("Images générées dans :", DOSSIER_IMAGES)
    print("Séries globales JSON générées dans :", DOSSIER_SERIES_GLOBAL)

    # AJOUT : petit résumé de l’exclusion (pour comprendre dans les logs)
    print("Parkings exclus (capteurs bloqués) :", len(exclus))
    if len(exclus) > 0:
        print("Exemples :", list(sorted(exclus))[:10])

if __name__ == "__main__":
    main()
