import os
import json
import pandas as pd

DOSSIER_DONNEES = "donnees"


def exporter_un_type(suffixe_csv, nom_json):
    fichiers = []

    # On récupère tous les CSV qui finissent par le bon suffixe
    for nom in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom.endswith(suffixe_csv):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom))

    # Si on ne trouve rien, on crée quand même un JSON vide (pratique et propre)
    if len(fichiers) == 0:
        chemin_json = os.path.join(DOSSIER_DONNEES, nom_json)
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("Aucun fichier", suffixe_csv, "-> JSON vide cree :", chemin_json)
        return

    # On lit tous les fichiers
    dfs = []
    for chemin in fichiers:
        try:
            df = pd.read_csv(chemin)
            df["fichier_source"] = os.path.basename(chemin)
            dfs.append(df)
        except Exception:
            print("Impossible de lire :", chemin)

    # Si au final aucun df lisible
    if len(dfs) == 0:
        chemin_json = os.path.join(DOSSIER_DONNEES, nom_json)
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("Aucun CSV lisible -> JSON vide cree :", chemin_json)
        return

    df_final = pd.concat(dfs, ignore_index=True)

    # Conversion en liste de dictionnaires (format JSON)
    data = df_final.to_dict(orient="records")

    chemin_json = os.path.join(DOSSIER_DONNEES, nom_json)
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("JSON cree :", chemin_json)


def main():
    exporter_un_type("_voiture.csv", "export_voiture.json")
    exporter_un_type("_velo.csv", "export_velo.json")
    exporter_un_type("_relais.csv", "export_relais.json")


if __name__ == "__main__":
    main()
