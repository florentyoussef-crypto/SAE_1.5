import os
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"

def fichiers_journaliers(suffixe):
    fichiers = []
    for f in sorted(os.listdir(DOSSIER_DONNEES)):
        if f.startswith("jour_") and f.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, f))
    return fichiers

def analyser_voiture():
    fichiers = fichiers_journaliers("_voiture.csv")
    if len(fichiers) == 0:
        print("Aucun fichier voiture.")
        return

    dfs = []
    for path in fichiers:
        df = pd.read_csv(path, sep=" ", header=None,
                         names=["heure", "type", "nom", "libres", "total", "taux"])
        df["fichier"] = os.path.basename(path)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # Courbe VILLE
    df_ville = df[df["type"] == "VILLE"].copy()
    df_ville["taux"] = pd.to_numeric(df_ville["taux"], errors="coerce")
    df_ville = df_ville.dropna(subset=["taux"])

    if len(df_ville) > 0:
        plt.figure()
        plt.plot(df_ville["taux"].values)
        plt.title("Taux d'occupation voiture - VILLE (semaine)")
        plt.xlabel("Mesure (1 par heure)")
        plt.ylabel("Taux")
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_voiture_ville_semaine.png"))
        plt.close()

    # Saturation (PARKING >= 95%)
    df_p = df[df["type"] == "PARKING"].copy()
    df_p["taux"] = pd.to_numeric(df_p["taux"], errors="coerce")
    df_p = df_p.dropna(subset=["taux"])
    df_p["sature"] = df_p["taux"] >= 0.95

    sat = df_p[df_p["sature"]].groupby("nom").size().sort_values(ascending=False)
    print("\nTop 10 parkings les plus souvent saturés (>=95%):")
    print(sat.head(10))

    moy = df_p.groupby("nom")["taux"].mean().sort_values(ascending=False)
    print("\nTop 10 parkings les plus occupés (taux moyen semaine):")
    print(moy.head(10))

def analyser_velo():
    fichiers = fichiers_journaliers("_velo.csv")
    if len(fichiers) == 0:
        print("Aucun fichier vélo.")
        return

    dfs = []
    for path in fichiers:
        df = pd.read_csv(path, sep=" ", header=None,
                         names=["heure", "type", "nom", "velos", "bornes_libres", "total", "taux_occ_places"])
        df["fichier"] = os.path.basename(path)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df_ville = df[df["type"] == "VILLE"].copy()
    df_ville["taux_occ_places"] = pd.to_numeric(df_ville["taux_occ_places"], errors="coerce")
    df_ville = df_ville.dropna(subset=["taux_occ_places"])

    if len(df_ville) > 0:
        plt.figure()
        plt.plot(df_ville["taux_occ_places"].values)
        plt.title("Occupation vélos - VILLE (places occupées) (semaine)")
        plt.xlabel("Mesure (1 par heure)")
        plt.ylabel("Taux occupation places")
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_velo_ville_semaine.png"))
        plt.close()

def analyser_relais():
    fichiers = fichiers_journaliers("_relais.csv")
    if len(fichiers) == 0:
        print("Aucun fichier relais.")
        return

    dfs = []
    for path in fichiers:
        df = pd.read_csv(path, sep=" ", header=None, names=["heure", "nom", "valeur"])
        df["fichier"] = os.path.basename(path)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    # On garde les lignes RESUME
    df_r = df[df["nom"] == "RESUME"].copy()
    df_r["valeur"] = pd.to_numeric(df_r["valeur"], errors="coerce")
    df_r = df_r.dropna(subset=["valeur"])

    if len(df_r) > 0:
        plt.figure()
        plt.plot(df_r["valeur"].values)
        plt.title("Relais voiture/vélo - proportion OK (semaine)")
        plt.xlabel("Mesure (1 par heure)")
        plt.ylabel("Proportion relais OK")
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_relais_semaine.png"))
        plt.close()

def main():
    analyser_voiture()
    analyser_velo()
    analyser_relais()
    print("\nGraphes enregistrés dans le dossier donnees/")

if __name__ == "__main__":
    main()
