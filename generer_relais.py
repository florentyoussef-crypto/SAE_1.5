# ============================================================
#  Ce script sert à trouver des "relais" pertinents entre :
#   - un parking voiture
#   - une station vélo
#
#  Idée :
#   1) On prend des séries temporelles (taux d’occupation) pour chaque parking/station
#   2) On ne garde que les couples proches (distance <= MAX_DISTANCE_M)
#   3) On calcule une corrélation (Pearson) sur leurs valeurs alignées dans le temps
#   4) On filtre : on veut des corrélations NÉGATIVES (relais "inverse")
#   5) On trie (distance prioritaire), puis on exporte un JSON final
# ============================================================


import os     # gérer les chemins fichiers/dossiers (ex: os.path.join)
import json   # lire/écrire des fichiers JSON + JSONL
import math   # fonctions math (sqrt, radians, sin, cos, atan2...) pour Haversine + Pearson


# ============================================================
#  CHEMINS DES FICHIERS / DOSSIERS
# ============================================================

DOSSIER = "donnees"  # dossier racine où sont stockées toutes les données

# catalog.json est créé par carte_unique.py
# Il contient la liste des parkings + stations et le chemin vers leurs séries JSON.
CATALOG = os.path.join(DOSSIER, "catalog.json")

# fichiers bruts JSONL (collectés dans ton script de collecte)
# Ici ils servent de "fallback" pour récupérer les coordonnées GPS si elles ne sont pas dans catalog.json
FICHIER_JSONL_VOITURE = os.path.join(DOSSIER, "brut_voitures.jsonl")
FICHIER_JSONL_VELO = os.path.join(DOSSIER, "brut_velos.jsonl")

# fichier de sortie : le résultat final "top relais"
OUT_JSON = os.path.join(DOSSIER, "relais_pertinents.json")


# ============================================================
#  REGLAGES (tu peux ajuster)
# ============================================================

MAX_DISTANCE_M = 800          # distance max parking↔station (proximité)
MIN_POINTS = 12               # minimum de timestamps communs pour calcul fiable
TOP_N = 30                    # nombre de couples gardés dans le fichier final

ONLY_NEGATIVE = True          # True = garder seulement corr < 0 (relais inverse)
MAX_CORR_FOR_RELAIS = -0.20   # seuil : ex -0.20 => on ignore les corr trop proches de 0


# ============================================================
#  OUTILS : lecture JSON / JSONL
# ============================================================

def lire_json(path):
    # Lit un fichier JSON classique et renvoie l'objet Python (dict ou list)
    # Si le fichier n'existe pas : on renvoie None
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def lire_jsonl(path):
    # Lit un fichier .jsonl :
    # - 1 ligne = 1 objet JSON (snapshot)
    # Renvoie une liste d'objets Python
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()           # on enlève \n et espaces
            if not line:
                continue                  # si ligne vide, on saute
            try:
                out.append(json.loads(line))  # convertir la ligne JSON -> objet Python
            except Exception:
                # si une ligne est cassée (JSON invalide), on l'ignore
                pass
    return out


# ============================================================
#  OUTILS : accès "sécurisé" dans un JSON imbriqué
# ============================================================

def safe_get(entite, *cles):
    # But : éviter les KeyError dans un JSON profond
    #
    # Exemple :
    #   safe_get(p, "status", "value")  -> renvoie p["status"]["value"] si ça existe
    #   sinon -> renvoie None
    cur = entite
    for c in cles:
        if isinstance(cur, dict) and c in cur:
            cur = cur[c]
        else:
            return None
    return cur


# ============================================================
#  OUTILS : extraction coordonnées + distance GPS
# ============================================================

def extraire_lat_lon(entite):
    # Dans l'API Montpellier : coordinates = [lon, lat]
    # On renvoie (lat, lon) dans l'ordre logique "latitude, longitude"
    try:
        coords = entite["location"]["value"]["coordinates"]
        if isinstance(coords, list) and len(coords) >= 2:
            return float(coords[1]), float(coords[0])
    except Exception:
        return None, None
    return None, None

def haversine_m(lat1, lon1, lat2, lon2):
    # Distance entre 2 points GPS (lat/lon) en mètres
    # Formule Haversine : adaptée aux distances sur une sphère (la Terre)
    R = 6371000.0  # rayon approximatif de la Terre en mètres

    # conversion degrés -> radians (math.sin/cos utilisent des radians)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    # formule haversine
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


# ============================================================
#  OUTILS : corrélation Pearson
# ============================================================

def pearson(x, y):
    # Corrélation de Pearson entre deux listes x et y
    # résultat dans [-1 ; +1]
    # - +1 : évoluent ensemble (montent/descendent pareil)
    # -  0 : pas de lien linéaire
    # - -1 : évoluent en sens inverse (relais "parfait" théorique)
    n = len(x)
    if n < 3:
        return None

    # moyennes
    mx = sum(x) / n
    my = sum(y) / n

    # numérateur = somme( (xi-mx)*(yi-my) )
    # dx, dy = sommes des carrés (variances non normalisées)
    num = 0.0
    dx = 0.0
    dy = 0.0
    for i in range(n):
        a = x[i] - mx
        b = y[i] - my
        num += a * b
        dx += a * a
        dy += b * b

    # si dx ou dy = 0, ça veut dire série constante -> corr impossible
    if dx <= 0 or dy <= 0:
        return None

    return num / math.sqrt(dx * dy)


# ============================================================
#  OUTILS : lecture d’une "série" JSON (timestamp -> value)
# ============================================================

def charger_points_series(series_path):
    # series_path vient de catalog.json : "donnees/series/xxx.json"
    # Ce fichier contient :
    #   {"points":[{"timestamp":"...", "value":...}, ...]}
    data = lire_json(series_path)
    if not data or "points" not in data:
        return None

    # On transforme la liste en dictionnaire :
    #   clé = timestamp (string)
    #   valeur = value (float)
    # Avantage : retrouver rapidement les timestamps communs entre 2 séries
    m = {}
    for p in data["points"]:
        ts = p.get("timestamp")
        v = p.get("value")
        if ts is None or v is None:
            continue
        try:
            m[str(ts)] = float(v)
        except Exception:
            pass
    return m


# ============================================================
#  COORDONNEES (fallback via brut_*.jsonl)
# ============================================================

def coords_parkings_depuis_brut():
    # Objectif : créer un dictionnaire :
    #   coords["Nom du parking"] = (lat, lon)
    #
    # On lit les snapshots bruts voiture, on récupère location + name
    snaps = lire_jsonl(FICHIER_JSONL_VOITURE)
    coords = {}
    for snap in snaps:
        donnees = snap.get("donnees", [])
        if not isinstance(donnees, list):
            continue
        for p in donnees:
            # on ignore les parkings fermés
            if safe_get(p, "status", "value") != "Open":
                continue

            # nom du parking
            nom = safe_get(p, "name", "value")
            if not nom:
                continue

            # coords GPS
            lat, lon = extraire_lat_lon(p)
            if lat is None or lon is None:
                continue

            coords[str(nom)] = (float(lat), float(lon))
    return coords

def coords_stations_depuis_brut():
    # Même principe que coords_parkings_depuis_brut, mais pour les stations vélo.
    # Ici le nom est l'adresse streetAddress (comme dans ton CSV vélo).
    snaps = lire_jsonl(FICHIER_JSONL_VELO)
    coords = {}
    for snap in snaps:
        donnees = snap.get("donnees", [])
        if not isinstance(donnees, list):
            continue
        for s in donnees:
            nom = safe_get(s, "address", "value", "streetAddress")
            if not nom:
                continue
            lat, lon = extraire_lat_lon(s)
            if lat is None or lon is None:
                continue
            coords[str(nom)] = (float(lat), float(lon))
    return coords


# ============================================================
#  MAIN : génération du classement "relais"
# ============================================================

def main():
    # On s'assure que donnees/ existe (sinon on ne peut pas écrire le fichier OUT_JSON)
    os.makedirs(DOSSIER, exist_ok=True)

    # 1) Lecture du catalog (créé par la carte)
    catalog = lire_json(CATALOG)
    if not catalog:
        print("catalog.json introuvable :", CATALOG)
        return

    # 2) Récupération des listes parkings/stations
    parkings = catalog.get("parkings", [])
    stations = catalog.get("stations", [])

    if len(parkings) == 0 or len(stations) == 0:
        print("Pas assez d'objets dans catalog.json")
        return

    # 3) fallback coords : si catalog n'a pas les coordonnées, on les reconstitue depuis les bruts JSONL
    coordsP = coords_parkings_depuis_brut()
    coordsS = coords_stations_depuis_brut()

    # 4) cache séries : éviter de relire 200 fois le même fichier JSON
    series_cache = {}

    def get_series_map(item):
        # item = un parking ou une station venant du catalog
        # item["series"] = chemin vers son fichier de série JSON
        path = item.get("series")
        if not path:
            return None
        if path not in series_cache:
            series_cache[path] = charger_points_series(path)
        return series_cache[path]

    # 5) liste des couples qui passent tous les filtres
    candidats = []

    # 6) boucle sur tous les couples parking x station
    for p in parkings:
        p_name = p.get("name")
        if not p_name:
            continue

        # coords parking : soit dans catalog (lat/lon), soit via coordsP (brut JSONL)
        plat = p.get("lat")
        plon = p.get("lon")
        if plat is None or plon is None:
            c = coordsP.get(str(p_name))
            if not c:
                continue
            plat, plon = c

        # série temporelle du parking (timestamp -> valeur)
        mp = get_series_map(p)
        if not mp:
            continue

        for s in stations:
            s_name = s.get("name")
            if not s_name:
                continue

            # coords station : soit dans catalog, soit fallback coordsS
            slat = s.get("lat")
            slon = s.get("lon")
            if slat is None or slon is None:
                c = coordsS.get(str(s_name))
                if not c:
                    continue
                slat, slon = c

            # 1er filtre : proximité
            d = haversine_m(float(plat), float(plon), float(slat), float(slon))
            if d > MAX_DISTANCE_M:
                continue

            # série temporelle station
            ms = get_series_map(s)
            if not ms:
                continue

            # 2e filtre : timestamps communs EXACTS
            common = sorted(set(mp.keys()) & set(ms.keys()))
            if len(common) < MIN_POINTS:
                continue

            # listes alignées (mêmes timestamps dans le même ordre)
            x = [mp[t] for t in common]
            y = [ms[t] for t in common]

            # corr Pearson
            r = pearson(x, y)
            if r is None:
                continue

            # 3e filtre : relais = corr négative (si ONLY_NEGATIVE)
            if ONLY_NEGATIVE and r >= 0:
                continue

            # 4e filtre : corr suffisamment négative (pas trop proche de 0)
            # ex : -0.05 n'est pas un relais clair
            if r > MAX_CORR_FOR_RELAIS:
                continue

            # si tout passe, on enregistre le couple
            candidats.append({
                "parking": str(p_name),
                "station": str(s_name),
                "distance_m": float(d),
                "correlation": float(r),
                "n_points": int(len(common)),
                "parking_series": p.get("series"),
                "station_series": s.get("series"),
                "parking_lat": float(plat),
                "parking_lon": float(plon),
                "station_lat": float(slat),
                "station_lon": float(slon),
            })

    # ============================================================
    # TRI : DISTANCE PRIORITAIRE
    # ============================================================
    # candidats.sort(key=...)
    # -> Python va "classer" la liste en utilisant la clé retournée.
    #
    # Ici la clé est un tuple :
    #   (distance_m, correlation, -n_points)
    #
    # Donc :
    # 1) distance la plus petite en premier
    # 2) si même distance : correlation la plus petite en premier (ex: -0.90 avant -0.30)
    # 3) si encore égal : on veut plus de points => donc on met -n_points (plus grand n_points => plus petit -n_points)
    # ============================================================

    candidats.sort(key=lambda o: (o["distance_m"], o["correlation"], -o["n_points"]))

    # 7) objet final exporté en JSON
    out = {
        "max_distance_m": MAX_DISTANCE_M,
        "min_points": MIN_POINTS,
        "top_n": TOP_N,
        "only_negative": bool(ONLY_NEGATIVE),
        "min_relais_corr": float(MAX_CORR_FOR_RELAIS),
        "sort": "distance ASC, correlation ASC (plus negative), n_points DESC",
        "count_total": int(len(candidats)),
        "items": candidats[:TOP_N]
    }

    # 8) écriture du fichier final (utilisé par relais_pertinents.html)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # logs console (facultatif)
    print("relais_pertinents.json généré :", OUT_JSON)
    print("Couples trouvés :", len(candidats), " | gardés :", min(TOP_N, len(candidats)))


if __name__ == "__main__":
    main()
