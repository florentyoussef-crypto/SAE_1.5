import os
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"
DOSSIER_IMAGES = os.path.join(DOSSIER_DONNEES, "images")


def creer_dossier_si_absent(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def fichiers_journaliers(suffixe):
    fichiers = []
    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom_fichier.startswith("jour_") and nom_fichier.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom_fichier))
    return fichiers


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
    analyser_voitures()
    analyser_velos()
    analyser_relais()
    print("Images générées dans :", DOSSIER_IMAGES)


if __name__ == "__main__":
    main()
