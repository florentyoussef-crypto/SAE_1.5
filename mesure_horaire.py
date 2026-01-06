import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math

# Date de début du projet (A MODIFIER UNE SEULE FOIS)
DATE_DEBUT = datetime(2026, 1, 5, tzinfo=ZoneInfo("Europe/Paris"))

# Rayon pour associer un parking voiture à une station vélo (relais) (en mètres)
RAYON_RELAIS = 300

# Seuils "relais OK"
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

# API voiture / vélo
URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation"

DOSSIER_DONNEES = "donnees"


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def get_val(obj, *keys):
    cur = obj
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return None
    return cur


def creer_dossier_donnees():
    if not os.path.isdir(DOSSIER_DONNEES):
        os.makedirs(DOSSIER_DONNEES, exist_ok=True)


def extraire_lat_lon(entite):
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        lon = coords[0]
        lat = coords[1]
        return lat, lon

    coords2 = get_val(entite, "location", "coordinates")
    if coords2 and isinstance(coords2, list) and len(coords2) >= 2:
        lon = coords2[0]
        lat = coords2[1]
        return lat, lon

    return None, None


def recuperer_voiture():
    r = requests.get(URL_VOITURE, timeout=20)
    return r.json()


def recuperer_velo():
    r = requests.get(URL_VELO, timeout=20)
    return r.json()


def taux_ville_voiture(parkings):
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


def associer_relais(parkings, stations):
    assoc = {}

    for p in parkings:
        pid = p.get("id", "")
        plat, plon = extraire_lat_lon(p)
        if plat is None:
            continue

        proches = []
        for s in stations:
            slat, slon = extraire_lat_lon(s)
            if slat is None:
                continue

            d = haversine_m(plat, plon, slat, slon)
            if d <= RAYON_RELAIS:
                proches.append((d, s))

        proches.sort(key=lambda x: x[0])
        assoc[pid] = proches

    return assoc


def relais_ok_pour_parking(parking, stations_proches):
    if get_val(parking, "status", "value") != "Open":
        return None

    libres = get_val(parking, "availableSpotNumber", "value")
    total = get_val(parking, "totalSpotNumber", "value")
    if libres is None or total is None or total <= 0:
        return None

    libres = float(libres)
    parking_ok = libres >= SEUIL_PLACES_VOITURE

    station_ok = False
    for (d, s) in stations_proches:
        statut_station = get_val(s, "status", "value")
        if statut_station is not None and statut_station != "working":
            continue

        velos = get_val(s, "availableBikeNumber", "value")
        bornes_libres = get_val(s, "freeSlotNumber", "value")
        if velos is None or bornes_libres is None:
            continue

        velos = float(velos)
        bornes_libres = float(bornes_libres)

        if velos >= SEUIL_VELOS_DISPO and bornes_libres >= SEUIL_BORNES_LIBRES:
            station_ok = True
            break

    return parking_ok and station_ok


def main():
    creer_dossier_donnees()

    now = datetime.now(ZoneInfo("Europe/Paris"))
    jour = (now.date() - DATE_DEBUT.date()).days + 1
    heure = now.strftime("%H:%M:%S")

    fichier_voiture = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_voiture.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_velo.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_relais.csv")

    parkings = recuperer_voiture()
    stations = recuperer_velo()

    # ==========================
    # VOITURE
    # ==========================
    with open(fichier_voiture, "a", encoding="utf-8") as f:
        tv = taux_ville_voiture(parkings)
        if tv is not None:
            f.write(heure + " VILLE VILLE 0 0 " + str(tv) + "\n")

        for p in parkings:
            if get_val(p, "status", "value") != "Open":
                continue

            nom = get_val(p, "name", "value")
            libres = get_val(p, "availableSpotNumber", "value")
            total = get_val(p, "totalSpotNumber", "value")

            if nom is None or libres is None or total is None or total <= 0:
                continue

            libres = float(libres)
            total = float(total)

            taux = (total - libres) / total
            if taux < 0:
                taux = 0.0
            if taux > 1:
                taux = 1.0

            f.write(
                heure + " PARKING " +
                nom.replace(" ", "_") + " " +
                str(libres) + " " +
                str(total) + " " +
                str(taux) + "\n"
            )

    # ==========================
    # VELO (TEST SÛR)
    # ==========================
    with open(fichier_velo, "a", encoding="utf-8") as f:
        nb_stations = 0

        for s in stations:
            nom = get_val(s, "name", "value")
            velos = get_val(s, "availableBikeNumber", "value")
            bornes_libres = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes_libres is None or total is None:
                continue
            if total <= 0:
                continue

            velos = float(velos)
            bornes_libres = float(bornes_libres)
            total = float(total)

            taux_occ_places = (total - bornes_libres) / total

            f.write(
                heure + " STATION " +
                nom.replace(" ", "_") + " " +
                str(velos) + " " +
                str(bornes_libres) + " " +
                str(total) + " " +
                str(taux_occ_places) + "\n"
            )

            nb_stations += 1

        # LIGNE DE TEST (toujours écrite)
        f.write(heure + " RESUME NB_STATIONS " + str(nb_stations) + "\n")

    # ==========================
    # RELAIS
    # ==========================
    assoc = associer_relais(parkings, stations)

    with open(fichier_relais, "a", encoding="utf-8") as f:
        nb_test = 0
        nb_ok = 0

        for p in parkings:
            if get_val(p, "status", "value") != "Open":
                continue

            pid = p.get("id", "")
            nom = get_val(p, "name", "value")
            if nom is None:
                continue

            proches = assoc.get(pid, [])
            ok = relais_ok_pour_parking(p, proches)
            if ok is None:
                continue

            nb_test += 1
            if ok:
                nb_ok += 1

            f.write(heure + " " + nom.replace(" ", "_") + " " + ("1" if ok else "0") + "\n")

        if nb_test > 0:
            f.write(heure + " RESUME " + str(nb_ok / nb_test) + "\n")


if __name__ == "__main__":
    main()
