import os
import json
import pandas as pd

DOSSIER_DONNEES = "donnees"


def exporter_un_type(suffixe_csv, nom_json):
    fichiers = []

    # On récupère tous les CSV journaliers qui finissent par le bon suffixe
    # Exemple : jour_1_voiture.csv, jour_2_voiture.csv, ...
    for nom in sorted(os.listdir(DOSSIER_DONNEES)):
        if nom.startswith("jour_") and nom.endswith(suffixe_csv):
            fichiers.append(os.path.join(DOSSIER_DONNEES, nom))

    chemin_json = os.path.join(DOSSIER_DONNEES, nom_json)

    # Si on ne trouve rien, on crée quand même un JSON vide
    if len(fichiers) == 0:
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("Aucun fichier", suffixe_csv, "-> JSON vide cree :", chemin_json)
        return

    # On lit tous les fichiers
    dfs = []
    for chemin in fichiers:
        try:
            df = pd.read_csv(chemin)

            # On garde la source (utile pour debug)
            df["fichier_source"] = os.path.basename(chemin)

            dfs.append(df)
        except Exception:
            print("Impossible de lire :", chemin)

    # Si au final aucun CSV lisible
    if len(dfs) == 0:
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("Aucun CSV lisible -> JSON vide cree :", chemin_json)
        return

    df_final = pd.concat(dfs, ignore_index=True)

    # Si on a un timestamp, on trie par ordre chronologique (plus propre)
    if "timestamp" in df_final.columns:
        df_final["timestamp"] = pd.to_datetime(df_final["timestamp"], errors="coerce")
        df_final = df_final.sort_values("timestamp")

    # On remplace les NaN (pandas) par None (JSON -> null)
    df_final = df_final.where(pd.notnull(df_final), None)

    # Conversion en liste de dictionnaires (JSON)
    data = df_final.to_dict(orient="records")

    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("JSON cree :", chemin_json)


def main():
    exporter_un_type("_voitures.csv", "export_voitures.json")
    exporter_un_type("_velos.csv", "export_velos.json")
    exporter_un_type("_relais1.csv", "export_relais1.json")

if __name__ == "__main__":
    main()
