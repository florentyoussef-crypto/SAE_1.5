import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math
import json

# ============================================================
#                     PARAMÈTRES DU PROJET
# ============================================================

# Date de début EFFECTIVE de la collecte
# => le 09/01/2026 correspond à jour_1
DATE_DEBUT = datetime(2026, 1, 9, tzinfo=ZoneInfo("Europe/Paris"))

# Rayon (en mètres) pour associer parking voiture -> station vélo
RAYON_RELAIS = 300

# Seuils pour dire si le relais voiture/vélo "fonctionne bien"
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

# APIs Open Data Montpellier
URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation?limit=1000"

# Dossier de stockage des fichiers
DOSSIER_DONNEES = "donnees"


# ============================================================
#                     FONCTIONS OUTILS
# ============================================================

def distance_haversine_m(lat1, lon1, lat2, lon2):
    # Distance GPS en mètres (formule de Haversine)
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_val(obj, *cles):
    # Accès sécurisé à un JSON imbriqué
    cur = obj
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


def creer_dossier_si_absent(chemin_dossier):
    # Crée le dossier s'il n'existe pas
    if not os.path.isdir(chemin_dossier):
        os.makedirs(chemin_dossier, exist_ok=True)


def ecrire_entete_si_fichier_vide(chemin_fichier, entete):
    # Écrit l'entête CSV seulement si fichier absent ou vide
    if (not os.path.exists(chemin_fichier)) or os.path.getsize(chemin_fichier) == 0:
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write(entete + "\n")


def extraire_lat_lon(entite):
    # Dans l'API : coordinates = [lon, lat]
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        return coords[1], coords[0]
    return None, None


def ajouter_snapshot_jsonl(chemin_fichier, timestamp, donnees):
    # On enregistre un "instantané" complet dans un fichier .jsonl
    # Format : 1 ligne = 1 objet JSON
    # Avantage : on peut append sans casser le fichier
    ligne = {
        "timestamp": timestamp,
        "donnees": donnees
    }

    with open(chemin_fichier, "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


# ============================================================
#                 RÉCUPÉRATION DES DONNÉES API
# ============================================================

def recuperer_donnees_voiture():
    return requests.get(URL_VOITURE, timeout=20).json()


def recuperer_donnees_velo():
    return requests.get(URL_VELO, timeout=20).json()


# ============================================================
#                 CALCULS VOITURE
# ============================================================

def calcul_taux_occupation_ville_voiture(parkings):
    somme_total = 0.0
    somme_libres = 0.0

    for p in parkings:
        if get_val(p, "status", "value") != "Open":
            continue

        libres = get_val(p, "availableSpotNumber", "value")
        total = get_val(p, "totalSpotNumber", "value")

        if libres is None or total is None:
            continue
        if total <= 0:
            continue

        somme_total += float(total)
        somme_libres += float(libres)

    if somme_total <= 0:
        return None

    return (somme_total - somme_libres) / somme_total


# ============================================================
#           RELAIS VOITURE / VÉLO
# ============================================================

def associer_stations_proches(parkings, stations):
    associations = {}

    for p in parkings:
        pid = p.get("id", "")
        lat_p, lon_p = extraire_lat_lon(p)

        if lat_p is None or lon_p is None:
            continue

        proches = []

        for s in stations:
            lat_s, lon_s = extraire_lat_lon(s)
            if lat_s is None or lon_s is None:
                continue

            d = distance_haversine_m(lat_p, lon_p, lat_s, lon_s)
            if d <= RAYON_RELAIS:
                proches.append((d, s))

        proches.sort(key=lambda x: x[0])
        associations[pid] = proches

    return associations


def relais_est_ok(parking, stations_proches):
    libres = get_val(parking, "availableSpotNumber", "value")
    if libres is None:
        return None

    parking_ok = float(libres) >= SEUIL_PLACES_VOITURE

    station_ok = False
    for _, s in stations_proches:
        velos = get_val(s, "availableBikeNumber", "value")
        bornes = get_val(s, "freeSlotNumber", "value")

        if velos is None or bornes is None:
            continue

        if float(velos) >= SEUIL_VELOS_DISPO and float(bornes) >= SEUIL_BORNES_LIBRES:
            station_ok = True

    return parking_ok and station_ok


# ============================================================
#                           MAIN
# ============================================================

def main():
    # 1) Dossier donnees/
    creer_dossier_si_absent(DOSSIER_DONNEES)

    # 2) Date/heure France
    now = datetime.now(ZoneInfo("Europe/Paris"))
    date_str = now.strftime("%Y-%m-%d")
    heure_str = now.strftime("%H:%M:%S")
    timestamp = now.isoformat(timespec="seconds")

    # 3) Numéro du jour
    jour = (now.date() - DATE_DEBUT.date()).days + 1

    # 4) Fichiers du jour
    fichier_voiture = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_voitures.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_velos.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_relais1.csv")

    # 5) Entêtes (pour que GitHub/pandas lise bien)
    ecrire_entete_si_fichier_vide(
        fichier_voiture,
        "date,heure,timestamp,type,nom,libres,total,taux_occupation,lat,lon"
    )
    ecrire_entete_si_fichier_vide(
        fichier_velo,
        "date,heure,timestamp,type,nom,velos_dispo,bornes_libres,total,taux_occupation_places,lat,lon"
    )
    ecrire_entete_si_fichier_vide(
        fichier_relais,
        "date,heure,timestamp,parking,relais_ok"
    )

    # 6) Récupération API
    parkings = recuperer_donnees_voiture()
    stations = recuperer_donnees_velo()

    # ========================================================
    # 7) SAUVEGARDE BRUTE EN 2 FICHIERS UNIQUES (JSONL)
    # ========================================================
    fichier_brut_voiture = os.path.join(DOSSIER_DONNEES, "brut_voiture.jsonl")
    fichier_brut_velo = os.path.join(DOSSIER_DONNEES, "brut_velo.jsonl")

    ajouter_snapshot_jsonl(fichier_brut_voiture, timestamp, parkings)
    ajouter_snapshot_jsonl(fichier_brut_velo, timestamp, stations)

    # ========================================================
    #                       ÉCRITURE VOITURE
    # ========================================================
    with open(fichier_voiture, "a", encoding="utf-8") as f:
        taux_ville = calcul_taux_occupation_ville_voiture(parkings)
        if taux_ville is not None:
            f.write(f"{date_str},{heure_str},{timestamp},VILLE,VILLE,0,0,{taux_ville},,\n")

        for p in parkings:
            if get_val(p, "status", "value") != "Open":
                continue

            nom = get_val(p, "name", "value")
            libres = get_val(p, "availableSpotNumber", "value")
            total = get_val(p, "totalSpotNumber", "value")

            if nom is None or libres is None or total is None:
                continue
            if total <= 0:
                continue

            taux = (float(total) - float(libres)) / float(total)

            lat, lon = extraire_lat_lon(p)
            if lat is None or lon is None:
                lat, lon = "", ""

            nom_csv = str(nom).replace('"', "'")
            f.write(
                f'{date_str},{heure_str},{timestamp},PARKING,"{nom_csv}",{int(float(libres))},{int(float(total))},{taux},{lat},{lon}\n'
            )

    # ========================================================
    #                       ÉCRITURE VÉLO
    # ========================================================
    with open(fichier_velo, "a", encoding="utf-8") as f:
        for s in stations:
            nom = get_val(s, "address", "value", "streetAddress")
            velos = get_val(s, "availableBikeNumber", "value")
            bornes = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes is None or total is None:
                continue
            if total <= 0:
                continue

            taux_places = (float(total) - float(bornes)) / float(total)

            lat, lon = extraire_lat_lon(s)
            if lat is None or lon is None:
                lat, lon = "", ""

            nom_csv = str(nom).replace('"', "'")
            f.write(
                f'{date_str},{heure_str},{timestamp},STATION,"{nom_csv}",{int(float(velos))},{int(float(bornes))},{int(float(total))},{taux_places},{lat},{lon}\n'
            )

    # ========================================================
    #                       ÉCRITURE RELAIS
    # ========================================================
    associations = associer_stations_proches(parkings, stations)

    total_test = 0
    ok_test = 0

    with open(fichier_relais, "a", encoding="utf-8") as f:
        for p in parkings:
            if get_val(p, "status", "value") != "Open":
                continue

            pid = p.get("id", "")
            nom_p = get_val(p, "name", "value")
            if nom_p is None:
                continue

            stations_proches = associations.get(pid, [])
            res = relais_est_ok(p, stations_proches)

            if res is None:
                continue

            total_test += 1
            if res:
                ok_test += 1

            nom_csv = str(nom_p).replace('"', "'")
            f.write(f'{date_str},{heure_str},{timestamp},"{nom_csv}",{1 if res else 0}\n')

        if total_test > 0:
            f.write(f"{date_str},{heure_str},{timestamp},RESUME,{ok_test / total_test}\n")


if __name__ == "__main__":
    main()
