import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import math

# ==========================
# PARAMÈTRES
# ==========================
DATE_DEBUT = datetime(2026, 1, 5, tzinfo=ZoneInfo("Europe/Paris"))

RAYON_RELAIS = 300
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation"

DOSSIER_DONNEES = "donnees"


# ==========================
# OUTILS
# ==========================
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


def creer_dossier(path):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def ecrire_entete_si_vide(chemin, entete):
    # Si fichier n'existe pas ou vide => écrire l'entête
    if (not os.path.exists(chemin)) or os.path.getsize(chemin) == 0:
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(entete + "\n")


def extraire_lat_lon(entite):
    coords = get_val(entite, "location", "value", "coordinates")
    if coords and isinstance(coords, list) and len(coords) >= 2:
        return coords[1], coords[0]
    return None, None


# ==========================
# API
# ==========================
def recuperer_voiture():
    return requests.get(URL_VOITURE, timeout=20).json()


def recuperer_velo():
    return requests.get(URL_VELO, timeout=20).json()


# ==========================
# CALCULS
# ==========================
def taux_ville_voiture(parkings):
    total_places = 0.0
    libres = 0.0
    for p in parkings:
        if get_val(p, "status", "value") != "Open":
            continue
        l = get_val(p, "availableSpotNumber", "value")
        t = get_val(p, "totalSpotNumber", "value")
        if l is None or t is None or t <= 0:
            continue
        libres += float(l)
        total_places += float(t)
    if total_places <= 0:
        return None
    return (total_places - libres) / total_places


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


def relais_ok(parking, stations_proches):
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
            break

    return parking_ok and station_ok


# ==========================
# MAIN
# ==========================
def main():
    creer_dossier(DOSSIER_DONNEES)

    now = datetime.now(ZoneInfo("Europe/Paris"))
    date_str = now.strftime("%Y-%m-%d")
    heure_str = now.strftime("%H:%M:%S")
    jour = (now.date() - DATE_DEBUT.date()).days + 1

    fichier_voiture = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_voiture.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_velo.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, f"jour_{jour}_relais.csv")

    # Entêtes CSV
    ecrire_entete_si_vide(fichier_voiture, "date,heure,type,nom,libres,total,taux_occupation")
    ecrire_entete_si_vide(fichier_velo, "date,heure,type,nom,velos_dispo,bornes_libres,total,taux_occupation_places")
    ecrire_entete_si_vide(fichier_relais, "date,heure,parking,relais_ok")

    parkings = recuperer_voiture()
    stations = recuperer_velo()

    # ==========================
    # VOITURE
    # ==========================
    with open(fichier_voiture, "a", encoding="utf-8") as f:
        tv = taux_ville_voiture(parkings)
        if tv is not None:
            f.write(f"{date_str},{heure_str},VILLE,VILLE,0,0,{tv}\n")

        for p in parkings:
            if get_val(p, "status", "value") != "Open":
                continue
            nom = get_val(p, "name", "value")
            libres = get_val(p, "availableSpotNumber", "value")
            total = get_val(p, "totalSpotNumber", "value")
            if nom is None or libres is None or total is None or total <= 0:
                continue
            taux = (float(total) - float(libres)) / float(total)
            f.write(f"{date_str},{heure_str},PARKING,{nom},{int(float(libres))},{int(float(total))},{taux}\n")

    # ==========================
    # VELO
    # ==========================
    with open(fichier_velo, "a", encoding="utf-8") as f:
        for s in stations:
            # Dans ton JSON, le "nom" est dans address.value.streetAddress
            nom = get_val(s, "address", "value", "streetAddress")
            velos = get_val(s, "availableBikeNumber", "value")
            bornes = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes is None or total is None or total <= 0:
                continue

            taux = (float(total) - float(bornes)) / float(total)
            f.write(f"{date_str},{heure_str},STATION,{nom},{int(float(velos))},{int(float(bornes))},{int(float(total))},{taux}\n")

    # ==========================
    # RELAIS
    # ==========================
    assoc = associer_relais(parkings, stations)
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

            proches = assoc.get(pid, [])
            res = relais_ok(p, proches)
            if res is None:
                continue

            total_test += 1
            if res:
                ok_test += 1

            f.write(f"{date_str},{heure_str},{nom_p},{1 if res else 0}\n")

        if total_test > 0:
            f.write(f"{date_str},{heure_str},RESUME,{ok_test / total_test}\n")


if __name__ == "__main__":
    main()
