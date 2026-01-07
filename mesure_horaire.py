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


# Date de début du projet : elle sert uniquement à numéroter les fichiers (jour_1, jour_2, ...)
# Exemple : si DATE_DEBUT = 2026-01-05
# - le 05/01/2026 => jour_1
# - le 06/01/2026 => jour_2
# - le 07/01/2026 => jour_3
DATE_DEBUT = datetime(2026, 1, 5, tzinfo=ZoneInfo("Europe/Paris"))

# Rayon (en mètres) pour dire "une station vélo est proche d'un parking voiture"
# Ici 300 m : on considère qu'à pied c'est raisonnable pour rejoindre une station vélo
RAYON_RELAIS = 300

# Seuils pour dire si le relais voiture/vélo "fonctionne bien"
# Choix simple :
# - si un parking a suffisamment de places libres, alors on peut se garer
# - si une station proche a assez de vélos ET assez de bornes libres, alors on peut louer / rendre un vélo
SEUIL_PLACES_VOITURE = 30
SEUIL_VELOS_DISPO = 5
SEUIL_BORNES_LIBRES = 5

# URLs des APIs (open data Montpellier)
# - offstreetparking : parkings voitures
# - bikestation : stations vélos
URL_VOITURE = "https://portail-api-data.montpellier3m.fr/offstreetparking?limit=1000"
URL_VELO = "https://portail-api-data.montpellier3m.fr/bikestation"

# Dossier dans lequel on stocke les fichiers CSV
# On stocke toutes les mesures dans des fichiers journaliers
DOSSIER_DONNEES = "donnees"


# ============================================================
#                     FONCTIONS OUTILS
# ============================================================

def distance_haversine_m(lat1, lon1, lat2, lon2):
    # Calcul de la distance entre deux points GPS (en mètres).
    # On utilise la formule de Haversine, classique pour une distance sur une sphère.
    # Résultat : distance approximative en mètres.

    R = 6371000.0  # rayon moyen de la Terre en mètres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def get_val(obj, *cles):
    # Fonction utilitaire pour lire un JSON imbriqué sans provoquer d'erreur.
    #
    # Exemple :
    # get_val(p, "status", "value") équivaut à p["status"]["value"]
    # mais si une clé manque, on renvoie None au lieu de planter.

    cur = obj
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


def creer_dossier_si_absent(chemin_dossier):
    # GitHub ne garde pas un dossier vide, donc on s'assure qu'il existe.
    # Si le dossier existe déjà, il ne se passe rien.
    if not os.path.isdir(chemin_dossier):
        os.makedirs(chemin_dossier, exist_ok=True)


def ecrire_entete_si_fichier_vide(chemin_fichier, entete):
    # Le but des fichiers CSV est d'être facilement lisibles ensuite (Excel/pandas).
    # On écrit donc une ligne d'entête (noms des colonnes) UNE SEULE FOIS :
    # - si le fichier n'existe pas encore
    # - ou s'il existe mais qu'il est vide

    if (not os.path.exists(chemin_fichier)) or os.path.getsize(chemin_fichier) == 0:
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            f.write(entete + "\n")


def extraire_lat_lon(entite):
    # Dans cette API, les coordonnées sont fournies en GeoJSON :
    # coordinates = [longitude, latitude]
    #
    # Pour faire une carte ensuite, on préfère retourner (latitude, longitude).

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
    # On envoie une requête HTTP GET vers l'API des parkings voitures.
    # timeout=20 : évite que ça bloque trop longtemps si l'API répond mal.
    r = requests.get(URL_VOITURE, timeout=20)
    return r.json()


def recuperer_donnees_velo():
    # Même principe pour les stations vélo.
    r = requests.get(URL_VELO, timeout=20)
    return r.json()


# ============================================================
#                 CALCULS : TAUX D'OCCUPATION VOITURE
# ============================================================

def calcul_taux_occupation_ville_voiture(parkings):
    # Taux d'occupation global pour la ville :
    # taux = (total - libres) / total
    #
    # On additionne les capacités de tous les parkings ouverts.

    somme_total = 0.0
    somme_libres = 0.0

    for p in parkings:
        # On ignore les parkings fermés
        if get_val(p, "status", "value") != "Open":
            continue

        libres = get_val(p, "availableSpotNumber", "value")
        total = get_val(p, "totalSpotNumber", "value")

        # Si les données sont incomplètes, on ignore ce parking
        if libres is None or total is None:
            continue
        if total <= 0:
            continue

        somme_total += float(total)
        somme_libres += float(libres)

    # Si aucun parking n'a pu être utilisé, on renvoie None
    if somme_total <= 0:
        return None

    return (somme_total - somme_libres) / somme_total


# ============================================================
#           RELAIS : ASSOCIER PARKINGS ET STATIONS VÉLOS
# ============================================================

def associer_stations_proches(parkings, stations):
    # Objectif : pour chaque parking, trouver les stations vélo proches (<= RAYON_RELAIS).
    #
    # On retourne un dictionnaire :
    # associations[id_parking] = [(distance, station), (distance, station), ...]
    #
    # L'intérêt :
    # - ensuite, pour chaque parking, on sait quelles stations regarder pour décider si le relais marche.

    associations = {}

    for p in parkings:
        pid = p.get("id", "")
        lat_p, lon_p = extraire_lat_lon(p)

        # Si on n'a pas de coordonnées, on ne peut pas associer
        if lat_p is None or lon_p is None:
            continue

        liste_proches = []

        for s in stations:
            lat_s, lon_s = extraire_lat_lon(s)
            if lat_s is None or lon_s is None:
                continue

            d = distance_haversine_m(lat_p, lon_p, lat_s, lon_s)

            # On garde uniquement les stations dans le rayon choisi
            if d <= RAYON_RELAIS:
                liste_proches.append((d, s))

        # Tri par distance croissante (optionnel mais pratique)
        liste_proches.sort(key=lambda x: x[0])

        associations[pid] = liste_proches

    return associations


def relais_est_ok(parking, stations_proches):
    # On veut savoir si, pour ce parking, le relais voiture -> vélo est "OK".
    #
    # Conditions :
    # 1) Le parking doit avoir assez de places libres (SEUIL_PLACES_VOITURE)
    # 2) Il doit exister au moins une station proche qui a :
    #       - assez de vélos disponibles (SEUIL_VELOS_DISPO)
    #       - assez de bornes libres (SEUIL_BORNES_LIBRES)
    #
    # Important : on évite "break" pour rester simple, on parcourt tout et on mémorise station_ok.

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
            # pas de break : on continue, mais station_ok reste True

    return parking_ok and station_ok


# ============================================================
#                           MAIN
# ============================================================

def main():
    # 1) On s'assure que le dossier "donnees" existe
    creer_dossier_si_absent(DOSSIER_DONNEES)

    # 2) On récupère l'heure en France (Paris)
    # Ceci évite que les fichiers aient une heure UTC (qui serait décalée)
    now = datetime.now(ZoneInfo("Europe/Paris"))

    # 3) On fabrique une date et une heure "lisibles"
    date_str = now.strftime("%Y-%m-%d")      # ex : 2026-01-07
    heure_str = now.strftime("%H:%M:%S")     # ex : 16:09:41

    # 4) Timestamp complet (utile pour trier précisément)
    # Exemple : 2026-01-07T16:09:41+01:00
    timestamp = now.isoformat(timespec="seconds")

    # 5) Numéro de jour (jour_1, jour_2, ...)
    jour = (now.date() - DATE_DEBUT.date()).days + 1

    # 6) Chemins des fichiers journaliers
    # Ces fichiers vont se remplir progressivement car on ouvre en mode "a" (append)
    fichier_voiture = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_voiture.csv")
    fichier_velo = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_velo.csv")
    fichier_relais = os.path.join(DOSSIER_DONNEES, "jour_" + str(jour) + "_relais.csv")

    # 7) Entêtes CSV
    # On ajoute lat/lon car on voudra ensuite afficher une carte (Folium, etc.)
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

    # 8) Récupération des données API
    parkings = recuperer_donnees_voiture()
    stations = recuperer_donnees_velo()

    # ========================================================
    #                       ÉCRITURE VOITURE
    # ========================================================
    with open(fichier_voiture, "a", encoding="utf-8") as f:
        # 8a) Ligne "VILLE" (indicateur global)
        taux_ville = calcul_taux_occupation_ville_voiture(parkings)
        if taux_ville is not None:
            # lat/lon vides pour une ligne ville (pas un point précis)
            f.write(f"{date_str},{heure_str},{timestamp},VILLE,VILLE,0,0,{taux_ville},,\n")

        # 8b) Lignes détaillées par parking
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

            # taux d'occupation = (total - libres) / total
            taux = (float(total) - float(libres)) / float(total)

            lat, lon = extraire_lat_lon(p)
            if lat is None or lon is None:
                lat, lon = "", ""

            # On stocke des entiers pour libres/total (plus lisible)
            f.write(
                f"{date_str},{heure_str},{timestamp},PARKING,{nom},{int(float(libres))},{int(float(total))},{taux},{lat},{lon}\n"
            )

    # ========================================================
    #                       ÉCRITURE VÉLO
    # ========================================================
    with open(fichier_velo, "a", encoding="utf-8") as f:
        for s in stations:
            # Dans ce JSON, le nom humain est souvent dans streetAddress
            nom = get_val(s, "address", "value", "streetAddress")

            velos = get_val(s, "availableBikeNumber", "value")
            bornes = get_val(s, "freeSlotNumber", "value")
            total = get_val(s, "totalSlotNumber", "value")

            if nom is None or velos is None or bornes is None or total is None:
                continue
            if total <= 0:
                continue

            # Ici on mesure l'occupation des places (bornes occupées)
            # bornes occupées = total - bornes libres
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
    # On prépare l'association (stations proches pour chaque parking)
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

            # Calcul du relais OK ou non
            res = relais_est_ok(p, stations_proches)
            if res is None:
                continue

            total_test += 1
            if res:
                ok_test += 1

            # On enregistre 1 si OK, 0 sinon
            f.write(f"{date_str},{heure_str},{timestamp},{nom_p},{1 if res else 0}\n")

        # On ajoute une ligne RESUME pour tracer facilement l'évolution dans le temps
        if total_test > 0:
            f.write(f"{date_str},{heure_str},{timestamp},RESUME,{ok_test / total_test}\n")


# Ce bloc permet de lancer main() uniquement si on exécute ce fichier directement.
# (utile si plus tard on importe certaines fonctions dans un autre script)
if __name__ == "__main__":
    main()
