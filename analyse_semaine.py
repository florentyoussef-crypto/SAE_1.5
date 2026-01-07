import os
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"


# ============================================================
# 1) Récupérer la liste des fichiers d'un type (voiture/vélo/relais)
# ============================================================
def fichiers_journaliers(suffixe):
    fichiers = []

    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        # On accepte deux formats :
        # - jour_1_voiture.csv, jour_2_velo.csv ...
        # - 2026-01-07_voiture.csv, 2026-01-07_velo.csv ...
        if nom_fichier.endswith(suffixe) and nom_fichier.endswith(".csv"):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom_fichier))

    return fichiers


# ============================================================
# 2) Analyse VOITURE sur la semaine
# ============================================================
def analyser_voiture():
    fichiers = fichiers_journaliers("_voiture.csv")

    if len(fichiers) == 0:
        print("Aucun fichier voiture trouvé dans donnees/")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Conversion des colonnes utiles
    df["taux_occupation"] = pd.to_numeric(df["taux_occupation"], errors="coerce")

    # On convertit le timestamp en datetime si possible
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ------------------------------------------------------------
    # A) Courbe VILLE (taux global voiture)
    # ------------------------------------------------------------
    df_ville = df[df["type"] == "VILLE"].copy()
    df_ville = df_ville.dropna(subset=["taux_occupation"])

    if "timestamp" in df_ville.columns:
        df_ville = df_ville.dropna(subset=["timestamp"])
        df_ville = df_ville.sort_values("timestamp")

    if len(df_ville) > 0:
        plt.figure()
        plt.plot(df_ville["taux_occupation"].values)
        plt.title("Taux d'occupation voiture - VILLE (semaine)")
        plt.xlabel("Mesure (1 toutes les 30 minutes)")
        plt.ylabel("Taux d'occupation")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_voiture_ville_semaine.png"))
        plt.close()

    # ------------------------------------------------------------
    # B) Parkings saturés (>= 95%)
    # ------------------------------------------------------------
    df_p = df[df["type"] == "PARKING"].copy()
    df_p = df_p.dropna(subset=["taux_occupation"])
    df_p["sature"] = df_p["taux_occupation"] >= 0.95

    sat = df_p[df_p["sature"]].groupby("nom").size().sort_values(ascending=False)

    print("\nTop 10 parkings les plus souvent saturés (>=95%):")
    print(sat.head(10))

    moy = df_p.groupby("nom")["taux_occupation"].mean().sort_values(ascending=False)

    print("\nTop 10 parkings les plus occupés (taux moyen semaine):")
    print(moy.head(10))


# ============================================================
# 3) Analyse VÉLO sur la semaine
# ============================================================
def analyser_velo():
    fichiers = fichiers_journaliers("_velo.csv")

    if len(fichiers) == 0:
        print("Aucun fichier vélo trouvé dans donnees/")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Conversion
    if "taux_occupation_places" in df.columns:
        df["taux_occupation_places"] = pd.to_numeric(df["taux_occupation_places"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # On garde les stations
    df_s = df[df["type"] == "STATION"].copy()
    df_s = df_s.dropna(subset=["taux_occupation_places"])

    if len(df_s) == 0:
        print("Données vélo insuffisantes pour tracer une courbe.")
        return

    # Courbe moyenne des stations par timestamp (plus lisible)
    if "timestamp" in df_s.columns:
        df_s = df_s.dropna(subset=["timestamp"])

        moy_par_temps = df_s.groupby("timestamp")["taux_occupation_places"].mean().reset_index()
        moy_par_temps = moy_par_temps.sort_values("timestamp")

        plt.figure()
        plt.plot(moy_par_temps["taux_occupation_places"].values)
        plt.title("Occupation vélos - moyenne des stations (semaine)")
        plt.xlabel("Mesure (1 toutes les 30 minutes)")
        plt.ylabel("Taux d'occupation des places")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_velo_moyenne_stations_semaine.png"))
        plt.close()
    else:
        # Si pas de timestamp, on trace l'ordre des lignes
        plt.figure()
        plt.plot(df_s["taux_occupation_places"].values)
        plt.title("Occupation vélos - stations (semaine)")
        plt.xlabel("Mesure")
        plt.ylabel("Taux d'occupation des places")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_velo_stations_semaine.png"))
        plt.close()


# ============================================================
# 4) Analyse RELAIS sur la semaine
# ============================================================
def analyser_relais():
    fichiers = fichiers_journaliers("_relais.csv")

    if len(fichiers) == 0:
        print("Aucun fichier relais trouvé dans donnees/")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Conversion
    df["relais_ok"] = pd.to_numeric(df["relais_ok"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # On garde uniquement les lignes RESUME
    df_resume = df[df["parking"] == "RESUME"].copy()
    df_resume = df_resume.dropna(subset=["relais_ok"])

    if "timestamp" in df_resume.columns:
        df_resume = df_resume.dropna(subset=["timestamp"])
        df_resume = df_resume.sort_values("timestamp")

    if len(df_resume) > 0:
        plt.figure()
        plt.plot(df_resume["relais_ok"].values)
        plt.title("Relais voiture/vélo - proportion OK (semaine)")
        plt.xlabel("Mesure (1 toutes les 30 minutes)")
        plt.ylabel("Proportion relais OK")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_relais_semaine.png"))
        plt.close()
    else:
        print("Pas de lignes RESUME dans les données relais.")


# ============================================================
# MAIN
# ============================================================
def main():
    analyser_voiture()
    analyser_velo()
    analyser_relais()
    print("\nGraphes enregistrés dans le dossier donnees/")


if __name__ == "__main__":
    main()
