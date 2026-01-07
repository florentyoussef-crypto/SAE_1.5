import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math

# ============================================================
#                     PARAMÈTRES DU PROJET
# ============================================================

# Date de début du projet : elle sert uniquement à numéroter les fichiers (jour_1, jour_2, ...)
# Exemple : si DATE_DEBUT = 2026-01-05
# - le 05/01/2026 => jour_1
# - le 06/01/2026 => jour_2
# - le 07/01/2026 => jour_3
DATE_DEBUT = datetime(2026, 1, 5, tzinfo=ZoneInfo("Europe/Paris"))

# Rayon (en mètres) pour dire "une station vélo est proche d'un parking voiture"
RAYON_RELAIS = 300

# Seuils pour dire si le relais voiture/vélo "fonctionne bien"
# - il faut au moins SEUIL_PLACES_VOITURE places libres dans le parking voiture
# - il faut au moins SEUIL_VELOS_DISPO vélos disponibles dans une station vélo proche
# - il faut au moins SEUIL_BORNES_LIBRES bornes libres dans une station vélo proche
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

# URLs des APIs (open data Montpellier)
URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation"

# Dossier dans lequel on stocke les fichiers CSV
DOSSIER_DONNEES = "donnees"


# ============================================================
#                     FONCTIONS OUTILS
# ============================================================

def distance_haversine_m(lat1, lon1, lat2, lon2):
    # Cette fonction calcule une distance en mètres entre deux points GPS (lat/lon)
    # Formule de Haversine (distance sur une sphère : approximation de la Terre)
    R = 6371000.0  # rayon de la Terre en mètres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def get_val(obj, *cles):
    # Cette fonction permet d'accéder facilement à un JSON imbriqué
    # Exemple : get_val(entite, "status", "value") revient à faire entite["status"]["value"]
    # Mais ici on évite les erreurs : si une clé manque, on retourne None.

    cur = obj
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


def creer_dossier_si_absent(chemin_dossier):
    # On crée le dossier de données s'il n'existe pas
    if not os.path.isdir(chemin_dossier):
        os.makedirs(chemin_dossier, exist_ok=True)


def ecrire_entete_si_fichier_vide(chemin_fichier, entete):
    # Objectif : écrire l'entête CSV (les noms de colonnes) une seule fois
    # - si le fichier n'existe pas => on l'écrit
    # - si le fichier existe mais est vide => on l'écrit
    if (not os.path.exists(chemin_fichier)) or os.path.getsize(chemin_fichier) == 0:
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write(entete + "\n")


def extraire_lat_lon(entite):
    # Dans l'API, les coordonnées sont stockées sous la forme :
    # entite["location"]["value"]["coordinates"] = [lon, lat]
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        lon = coords[0]
        lat = coords[1]
        return lat, lon
    return None, None


# ============================================================
#                 RÉCUPÉRATION DES DONNÉES API
# ============================================================

def recuperer_donnees_voiture():
    # On récupère la liste des parkings voitures au format JSON
    r = requests.get(URL_VOITURE, timeout=20)
    return r.json()


def recuperer_donnees_velo():
    # On récupère la liste des stations vélos au format JSON
    r = requests.get(URL_VELO, timeout=20)
    return r.json()


# ============================================================
#                 CALCULS : TAUX D'OCCUPATION VOITURE
# ============================================================

def calcul_taux_occupation_ville_voiture(parkings):
    # On calcule le taux d'occupation global (toute la ville) :
    # taux = (total - libres) / total

    somme_total = 0.0
    somme_libres = 0.0

    for p in parkings:
        # On ne garde que les parkings ouverts
        if get_val(p, "status", "value") != "Open":
            continue

        libres = get_val(p, "availableSpotNumber", "value")
        total = get_val(p, "totalSpotNumber", "value")

        # On ignore les parkings incomplets
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
#           RELAIS : ASSOCIER PARKINGS ET STATIONS VÉLOS
# ============================================================

def associer_stations_proches(parkings, stations):
    # Pour chaque parking, on construit une liste des stations vélos proches
    # sous la forme : [(distance, station), (distance, station), ...]
    # On trie ensuite cette liste par distance croissante.

    associations = {}

    for p in parkings:
        pid = p.get("id", "")
        lat_p, lon_p = extraire_lat_lon(p)

        if lat_p is None or lon_p is None:
            continue

        liste_proches = []

        for s in stations:
            lat_s, lon_s = extraire_lat_lon(s)
            if lat_s is None or lon_s is None:
                continue

            d = distance_haversine_m(lat_p, lon_p, lat_s, lon_s)

            if d <= RAYON_RELAIS:
                liste_proches.append((d, s))

        # tri par distance
        liste_proches.sort(key=lambda x: x[0])

        associations[pid] = liste_proches

    return associations


def relais_est_ok(parking, stations_proches):
    # "Relais OK" si :
    # - parking : libres >= SEUIL_PLACES_VOITURE
    # - ET au moins UNE station proche qui vérifie :
    #       vélos_dispo >= SEUIL_VELOS_DISPO
    #       bornes_libres >= SEUIL_BORNES_LIBRES
    #
    # IMPORTANT : tu as demandé "pas de break", donc on parcourt toutes les stations
    # et on garde un booléen station_ok qui passe à True si on trouve une station correcte.

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
            # pas de break : on continue à parcourir, mais station_ok reste True

    return parking_ok and station_ok


# ============================================================
#                           MAIN
# ============================================================

def main():
    # 1) On s'assure que le dossier "donnees" existe
    creer_dossier_si_absent(DOSSIER_DONNEES)

    # 2) On récupère la date et l'heure "propres" en France (Paris)
    now = datetime.now(ZoneInfo("Europe/Paris"))

    # Date et heure "lisibles"
    date_str = now.strftime("%Y-%m-%d")      # ex : 2026-01-07
    heure_str = now.strftime("%H:%M:%S")     # ex : 16:09:41

    # Timestamp complet (super pratique pour trier plus tard)
    timestamp = now.isoformat(timespec="seconds")  # ex : 2026-01-07T16:09:41+01:00

    # 3) On calcule le numéro du jour (jour_1, jour_2, ...)
    jour = (now.date() - DATE_DEBUT.date()).days + 1

    # 4) On prépare les chemins des fichiers du jour
    fichier_voiture = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_voiture.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_velo.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_relais.csv")

    # 5) On écrit les entêtes (si nécessaire)
    # IMPORTANT : on ajoute lat/lon pour faire la carte
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

    # 6) On récupère les données depuis les APIs
    parkings = recuperer_donnees_voiture()
    stations = recuperer_donnees_velo()

    # ========================================================
    #                       ÉCRITURE VOITURE
    # ========================================================
    with open(fichier_voiture, "a", encoding="utf-8") as f:
        # 6a) Taux global "ville"
        taux_ville = calcul_taux_occupation_ville_voiture(parkings)
        if taux_ville is not None:
            f.write(f"{date_str},{heure_str},{timestamp},VILLE,VILLE,0,0,{taux_ville},,\n")

        # 6b) Taux par parking
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

            f.write(
                f"{date_str},{heure_str},{timestamp},PARKING,{nom},{int(float(libres))},{int(float(total))},{taux},{lat},{lon}\n"
            )

    # ========================================================
    #                       ÉCRITURE VÉLO
    # ========================================================
    with open(fichier_velo, "a", encoding="utf-8") as f:
        for s in stations:
            # Dans le JSON vélo, le "nom" se trouve ici :
            nom = get_val(s, "address", "value", "streetAddress")

            velos = get_val(s, "availableBikeNumber", "value")
            bornes = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes is None or total is None:
                continue
            if total <= 0:
                continue

            # taux occupation des PLACES (bornes occupées)
            taux_places = (float(total) - float(bornes)) / float(total)

            lat, lon = extraire_lat_lon(s)
            if lat is None or lon is None:
                lat, lon = "", ""

            f.write(
                f"{date_str},{heure_str},{timestamp},STATION,{nom},{int(float(velos))},{int(float(bornes))},{int(float(total))},{taux_places},{lat},{lon}\n"
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

            f.write(f"{date_str},{heure_str},{timestamp},{nom_p},{1 if res else 0}\n")

        if total_test > 0:
            f.write(f"{date_str},{heure_str},{timestamp},RESUME,{ok_test / total_test}\n")


if __name__ == "__main__":
    main()
