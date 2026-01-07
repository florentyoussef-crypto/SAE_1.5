import os
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"


# ============================================================
# 1) Récupérer la liste des fichiers d'un type (voiture/vélo/relais)
# ============================================================
def fichiers_journaliers(suffixe):
    fichiers = []

    # On liste le contenu du dossier "donnees"
    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        # On ne garde que les fichiers du type "jour_XX_suffixe"
        if nom_fichier.startswith("jour_") and nom_fichier.endswith(suffixe):
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

    # On lit tous les fichiers et on les concatène
    dfs = []

    for chemin in fichiers:
        # Maintenant c'est un vrai CSV avec en-tête -> pd.read_csv suffit
        df = pd.read_csv(chemin)

        # On garde l'info du jour (nom du fichier) pour pouvoir trier/filtrer si besoin
        df["fichier"] = os.path.basename(chemin)

        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Sécurité : on convertit les colonnes numériques
    df["taux_occupation"] = pd.to_numeric(df["taux_occupation"], errors="coerce")

    # ------------------------------------------------------------
    # A) Courbe VILLE (taux global voiture)
    # ------------------------------------------------------------
    df_ville = df[df["type"] == "VILLE"].copy()
    df_ville = df_ville.dropna(subset=["taux_occupation"])

    if len(df_ville) > 0:
        # Si la colonne timestamp existe, on trie par le temps réel (plus propre)
        if "timestamp" in df_ville.columns:
            df_ville = df_ville.sort_values("timestamp")

        plt.figure()
        plt.plot(df_ville["taux_occupation"].values)
        plt.title("Taux d'occupation voiture - VILLE (semaine)")
        plt.xlabel("Mesure (1 par heure)")
        plt.ylabel("Taux d'occupation")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_voiture_ville_semaine.png"))
        plt.close()

    # ------------------------------------------------------------
    # B) Saturation : on considère saturé si taux >= 0.95
    # ------------------------------------------------------------
    df_p = df[df["type"] == "PARKING"].copy()
    df_p = df_p.dropna(subset=["taux_occupation"])

    df_p["sature"] = df_p["taux_occupation"] >= 0.95

    # Top parkings souvent saturés
    sat = df_p[df_p["sature"]].groupby("nom").size().sort_values(ascending=False)

    print("\nTop 10 parkings les plus souvent saturés (>=95%):")
    print(sat.head(10))

    # Top parkings les plus occupés en moyenne
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

    # Convertir en numérique
    if "taux_occupation_places" in df.columns:
        df["taux_occupation_places"] = pd.to_numeric(df["taux_occupation_places"], errors="coerce")

    # ------------------------------------------------------------
    # A) Courbe VÉLO : taux d'occupation des places (bornes occupées)
    # ------------------------------------------------------------
    # Dans ton fichier vélo, tu as surtout des lignes STATION.
    # On peut faire une courbe "moyenne ville" : moyenne des stations à chaque timestamp.
    df_s = df[df["type"] == "STATION"].copy()
    df_s = df_s.dropna(subset=["taux_occupation_places"])

    if len(df_s) > 0:
        if "timestamp" in df_s.columns:
            # On calcule la moyenne par timestamp
            moy_par_temps = df_s.groupby("timestamp")["taux_occupation_places"].mean().reset_index()
            moy_par_temps = moy_par_temps.sort_values("timestamp")

            plt.figure()
            plt.plot(moy_par_temps["taux_occupation_places"].values)
            plt.title("Occupation vélos - moyenne des stations (semaine)")
            plt.xlabel("Mesure (1 par heure)")
            plt.ylabel("Taux d'occupation des places")
            plt.ylim(0, 1)
            plt.tight_layout()
            plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_velo_moyenne_stations_semaine.png"))
            plt.close()
        else:
            # Sans timestamp, on trace juste l'ordre des lignes
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

    # Dans relais.csv : parking,relais_ok
    # Et une ligne "RESUME" avec une valeur décimale
    # Exemple : date,heure,timestamp,RESUME,0.63
    df["relais_ok"] = pd.to_numeric(df["relais_ok"], errors="coerce")

    df_resume = df[df["parking"] == "RESUME"].copy()
    df_resume = df_resume.dropna(subset=["relais_ok"])

    if len(df_resume) > 0:
        if "timestamp" in df_resume.columns:
            df_resume = df_resume.sort_values("timestamp")

        plt.figure()
        plt.plot(df_resume["relais_ok"].values)
        plt.title("Relais voiture/vélo - proportion OK (semaine)")
        plt.xlabel("Mesure (1 par heure)")
        plt.ylabel("Proportion relais OK")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_relais_semaine.png"))
        plt.close()


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
