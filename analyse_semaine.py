import os
import json
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"
DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")

FICHIER_JSONL_VOITURE = os.path.join(DOSSIER_DONNEES, "brut_voitures.jsonl")
FICHIER_JSONL_VELO = os.path.join(DOSSIER_DONNEES, "brut_velos.jsonl")

DOSSIER_SERIES_GLOBAL = os.path.join(DOSSIER_DONNEES, "series_global")


def creer_dossier_si_absent(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def fichiers_journaliers(suffixe):
    fichiers = []
    if not os.path.isdir(DOSSIER_DONNEES):
        return fichiers
    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom_fichier.startswith("jour_") and nom_fichier.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom_fichier))
    return fichiers


def safe_get(entite, *cles):
    cur = entite
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


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


def calculer_taux_ville_voiture(donnees_parking):
    somme_total = 0.0
    somme_libres = 0.0
    for p in donnees_parking:
        if safe_get(p, "status", "value") != "Open":
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
        if total <= 0:
            continue
        somme_total += total
        somme_libres += libres
    if somme_total <= 0:
        return None
    return (somme_total - somme_libres) / somme_total


def calculer_moyenne_taux_places_velo(donnees_stations):
    vals = []
    for s in donnees_stations:
        bornes = safe_get(s, "freeSlotNumber", "value")
        total = safe_get(s, "totalSlotNumber", "value")
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


def ecrire_serie_global_json(nom_fichier, title, column, points):
    # points = [{"timestamp": "...", "value": 0.123}, ...]
    out = {
        "title": title,
        "column": column,
        "points": points
    }
    with open(os.path.join(DOSSIER_SERIES_GLOBAL, nom_fichier), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


def generer_series_global_depuis_brut():
    creer_dossier_si_absent(DOSSIER_SERIES_GLOBAL)

    snaps_v = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_b = lire_jsonl(FICHIER_JSONL_VELO)

    # --- Série voiture ville ---
    points_voiture = []
    for snap in snaps_v:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue
        v = calculer_taux_ville_voiture(donnees)
        if v is None:
            continue
        points_voiture.append({"timestamp": ts, "value": float(v)})

    # --- Série vélo moyenne stations ---
    points_velo = []
    for snap in snaps_b:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue
        v = calculer_moyenne_taux_places_velo(donnees)
        if v is None:
            continue
        points_velo.append({"timestamp": ts, "value": float(v)})

    # Trier par temps (au cas où)
    def sort_points(pts):
        try:
            return sorted(pts, key=lambda p: p["timestamp"])
        except Exception:
            return pts

    points_voiture = sort_points(points_voiture)
    points_velo = sort_points(points_velo)

    ecrire_serie_global_json(
        "voiture_ville.json",
        "Taux d'occupation voiture - VILLE (global)",
        "taux",
        points_voiture
    )

    ecrire_serie_global_json(
        "velo_moyenne.json",
        "Occupation vélos - moyenne stations (global)",
        "taux_occupation_places",
        points_velo
    )


def generer_serie_relais_depuis_csv():
    creer_dossier_si_absent(DOSSIER_SERIES_GLOBAL)

    fichiers = fichiers_journaliers("_relais1.csv")
    if len(fichiers) == 0:
        # Crée quand même un fichier vide pour éviter erreur côté HTML
        ecrire_serie_global_json(
            "relais_ok.json",
            "Relais voiture/vélo - proportion OK (global)",
            "proportion_ok",
            []
        )
        return

    dfs = []
    for chemin in fichiers:
        try:
            df = pd.read_csv(chemin)
            dfs.append(df)
        except Exception:
            pass

    if len(dfs) == 0:
        ecrire_serie_global_json(
            "relais_ok.json",
            "Relais voiture/vélo - proportion OK (global)",
            "proportion_ok",
            []
        )
        return

    df = pd.concat(dfs, ignore_index=True)

    df["relais_ok"] = pd.to_numeric(df.get("relais_ok"), errors="coerce")
    df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

    df_resume = df[df.get("parking") == "RESUME"].dropna(subset=["relais_ok", "timestamp"]).sort_values("timestamp")
    points = []
    for _, r in df_resume.iterrows():
        points.append({
            "timestamp": r["timestamp"].isoformat(),
            "value": float(r["relais_ok"])
        })

    ecrire_serie_global_json(
        "relais_ok.json",
        "Relais voiture/vélo - proportion OK (global)",
        "proportion_ok",
        points
    )


def correlation_globale_depuis_brut():
    snaps_v = lire_jsonl(FICHIER_JSONL_VOITURE)
    snaps_b = lire_jsonl(FICHIER_JSONL_VELO)

    car_by_ts = {}
    for snap in snaps_v:
        ts = snap.get("timestamp")
        donnees = snap.get("donnees", [])
        if not ts or not isinstance(donnees, list):
            continue
        v = calculer_taux_ville_voiture(donnees)
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
    if len(common) < 5:
        out = {"correlation": None, "n_points": len(common)}
        with open(os.path.join(DOSSIER_DONNEES, "correlation_global.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
        return

    x = [car_by_ts[t] for t in common]
    y = [bike_by_ts[t] for t in common]

    s = pd.Series(x).corr(pd.Series(y))  # Pearson
    out = {"correlation": float(s), "n_points": len(common), "method": "pearson", "aligned": "exact_timestamp"}

    with open(os.path.join(DOSSIER_DONNEES, "correlation_global.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)


def analyser_voitures():
    fichiers = fichiers_journaliers("_voitures.csv")
    if len(fichiers) == 0:
        print("Aucun fichier _voitures.csv trouvé")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df["taux_occupation"] = pd.to_numeric(df["taux_occupation"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    df_ville = df[df["type"] == "VILLE"].dropna(subset=["taux_occupation", "timestamp"]).sort_values("timestamp")
    if len(df_ville) > 0:
        plt.figure()
        plt.plot(df_ville["taux_occupation"].values)
        plt.title("Taux d'occupation voiture - VILLE (global)")
        plt.xlabel("Mesure (ordre chronologique)")
        plt.ylabel("Taux")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_IMAGES, "courbe_voitures_ville.png"))
        plt.close()

    df_p = df[df["type"] == "PARKING"].dropna(subset=["taux_occupation", "timestamp"]).copy()
    if len(df_p) > 0:
        df_p["sature"] = df_p["taux_occupation"] >= 0.95
        sat = df_p[df_p["sature"]].groupby("nom").size().sort_values(ascending=False)
        print("\nTop 10 parkings souvent saturés (>=95%)")
        print(sat.head(10))

        moy = df_p.groupby("nom")["taux_occupation"].mean().sort_values(ascending=False)
        print("\nTop 10 parkings les plus occupés (moyenne)")
        print(moy.head(10))


def analyser_velos():
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

    df_s = df[df["type"] == "STATION"].dropna(subset=["taux_occupation_places", "timestamp"]).copy()
    if len(df_s) > 0:
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


def analyser_relais():
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


def main():
    creer_dossier_si_absent(DOSSIER_IMAGES)
    creer_dossier_si_absent(DOSSIER_SERIES_GLOBAL)

    analyser_voitures()
    analyser_velos()
    analyser_relais()

    # Corrélation globale depuis brut jsonl
    correlation_globale_depuis_brut()

    # NOUVEAU : séries interactives pour analyse_globale.html
    generer_series_global_depuis_brut()
    generer_serie_relais_depuis_csv()

    print("Images générées dans :", DOSSIER_IMAGES)
    print("Séries globales générées dans :", DOSSIER_SERIES_GLOBAL)


if __name__ == "__main__":
    main()
