import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math

# ============================================================
#                     PARAMÈTRES DU PROJET
# ============================================================
#
# L'objectif de ce programme est de faire une "mesure" à chaque exécution :
# - récupérer l'état des parkings voiture (places libres / total)
# - récupérer l'état des stations vélo (vélos dispo / bornes libres / total)
# - estimer si le "relais voiture -> vélo" fonctionne bien (selon des seuils)
#
# IMPORTANT :
# Sur GitHub Actions, le script est relancé régulièrement (ex : toutes les 30 minutes).
# Donc :
# - on ne fait PAS de boucle infinie
# - on écrit une mesure puis on s'arrête
# - le workflow se charge de relancer le script plus tard


# Date de début EFFECTIVE de la collecte
# Ici, on considère que le projet démarre le 07/01/2026
# => le 07/01/2026 correspond à jour_1
DATE_DEBUT = datetime(2026, 1, 7, tzinfo=ZoneInfo("Europe/Paris"))

# Rayon (en mètres) pour dire "une station vélo est proche d'un parking voiture"
RAYON_RELAIS = 300

# Seuils pour dire si le relais voiture/vélo "fonctionne bien"
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

# URLs des APIs open data Montpellier
URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation"

# Dossier de stockage des données
DOSSIER_DONNEES = "donnees"


# ============================================================
#                     FONCTIONS OUTILS
# ============================================================

def distance_haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_val(obj, *cles):
    cur = obj
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


def creer_dossier_si_absent(chemin_dossier):
    if not os.path.isdir(chemin_dossier):
        os.makedirs(chemin_dossier, exist_ok=True)


def ecrire_entete_si_fichier_vide(chemin_fichier, entete):
    if (not os.path.exists(chemin_fichier)) or os.path.getsize(chemin_fichier) == 0:
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write(entete + "\n")


def extraire_lat_lon(entite):
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        return coords[1], coords[0]
    return None, None


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

        if libres is None or total is None or total <= 0:
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
    creer_dossier_si_absent(DOSSIER_DONNEES)

    now = datetime.now(ZoneInfo("Europe/Paris"))
    date_str = now.strftime("%Y-%m-%d")
    heure_str = now.strftime("%H:%M:%S")
    timestamp = now.isoformat(timespec="seconds")

    jour = (now.date() - DATE_DEBUT.date()).days + 1

    fichier_voiture = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_voiture.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_velo.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_relais.csv")

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

    parkings = recuperer_donnees_voiture()
    stations = recuperer_donnees_velo()

    # (le reste ne change pas)

if __name__ == "__main__":
    main()
