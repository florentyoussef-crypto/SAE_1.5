import os
import pandas as pd
import matplotlib.pyplot as plt

DOSSIER_DONNEES = "donnees"


# ============================================================
# 1) Récupérer la liste des fichiers d'un type (voiture/vélo/relais)
#    -> On garde uniquement les fichiers journaliers "jour_X_suffixe"
#    -> On peut limiter aux 7 derniers jours pour faire une vraie "semaine"
# ============================================================
def fichiers_journaliers(suffixe, limiter_a_semaine=True):
    fichiers = []

    # 1) On récupère tous les fichiers qui ressemblent à : jour_X_suffixe
    for nom_fichier in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom_fichier.startswith("jour_") and nom_fichier.endswith(suffixe):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom_fichier))

    # 2) Si on ne limite pas à une semaine, on renvoie tout
    if not limiter_a_semaine:
        return fichiers

    # 3) Si on limite à une semaine, on garde seulement les 7 derniers "jour_X"
    #    Exemple : si on a jour_1 ... jour_20
    #    on garde jour_14 à jour_20
    numeros = []
    for chemin in fichiers:
        nom = os.path.basename(chemin)
        # nom = "jour_12_voiture.csv" -> on veut récupérer 12
        morceaux = nom.split("_")
        if len(morceaux) >= 2:
            try:
                num = int(morceaux[1])
                numeros.append(num)
            except:
                pass

    if len(numeros) == 0:
        return fichiers

    max_jour = max(numeros)
    min_jour = max_jour - 6  # 7 jours : max-6, ..., max

    fichiers_semaine = []
    for chemin in fichiers:
        nom = os.path.basename(chemin)
        morceaux = nom.split("_")
        if len(morceaux) >= 2:
            try:
                num = int(morceaux[1])
                if num >= min_jour and num <= max_jour:
                    fichiers_semaine.append(chemin)
            except:
                pass

    return fichiers_semaine


# ============================================================
# 2) Analyse VOITURE sur la semaine
# ============================================================
def analyser_voiture():
    fichiers = fichiers_journaliers("_voiture.csv", limiter_a_semaine=True)

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

    # Conversion timestamp
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
        plt.title("Taux d'occupation voiture - VILLE (7 derniers jours)")
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

    print("\nTop 10 parkings les plus souvent saturés (>=95%) sur 7 jours :")
    print(sat.head(10))

    moy = df_p.groupby("nom")["taux_occupation"].mean().sort_values(ascending=False)

    print("\nTop 10 parkings les plus occupés (taux moyen sur 7 jours) :")
    print(moy.head(10))


# ============================================================
# 3) Analyse VÉLO sur la semaine
# ============================================================
def analyser_velo():
    fichiers = fichiers_journaliers("_velo.csv", limiter_a_semaine=True)

    if len(fichiers) == 0:
        print("Aucun fichier vélo trouvé dans donnees/")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    if "taux_occupation_places" in df.columns:
        df["taux_occupation_places"] = pd.to_numeric(df["taux_occupation_places"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # On garde uniquement les stations
    df_s = df[df["type"] == "STATION"].copy()
    df_s = df_s.dropna(subset=["taux_occupation_places"])

    if len(df_s) == 0:
        print("Données vélo insuffisantes pour tracer une courbe.")
        return

    # Courbe moyenne des stations par timestamp
    if "timestamp" in df_s.columns:
        df_s = df_s.dropna(subset=["timestamp"])

        moy_par_temps = df_s.groupby("timestamp")["taux_occupation_places"].mean().reset_index()
        moy_par_temps = moy_par_temps.sort_values("timestamp")

        plt.figure()
        plt.plot(moy_par_temps["taux_occupation_places"].values)
        plt.title("Occupation vélos - moyenne des stations (7 derniers jours)")
        plt.xlabel("Mesure (1 toutes les 30 minutes)")
        plt.ylabel("Taux d'occupation des places")
        plt.ylim(0, 1)
        plt.tight_layout()
        plt.savefig(os.path.join(DOSSIER_DONNEES, "courbe_velo_moyenne_stations_semaine.png"))
        plt.close()


# ============================================================
# 4) Analyse RELAIS sur la semaine
# ============================================================
def analyser_relais():
    fichiers = fichiers_journaliers("_relais.csv", limiter_a_semaine=True)

    if len(fichiers) == 0:
        print("Aucun fichier relais trouvé dans donnees/")
        return

    dfs = []
    for chemin in fichiers:
        df = pd.read_csv(chemin)
        df["fichier"] = os.path.basename(chemin)
        dfs.append(df)

    df = pd.concat(dfs, ignore_index=True)

    df["relais_ok"] = pd.to_numeric(df["relais_ok"], errors="coerce")

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    df_resume = df[df["parking"] == "RESUME"].copy()
    df_resume = df_resume.dropna(subset=["relais_ok"])

    if "timestamp" in df_resume.columns:
        df_resume = df_resume.dropna(subset=["timestamp"])
        df_resume = df_resume.sort_values("timestamp")

    if len(df_resume) > 0:
        plt.figure()
        plt.plot(df_resume["relais_ok"].values)
        plt.title("Relais voiture/vélo - proportion OK (7 derniers jours)")
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
