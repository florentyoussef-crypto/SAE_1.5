import os
import json
import math

DOSSIER = "donnees"
CATALOG = os.path.join(DOSSIER, "catalog.json")
OUT_JSON = os.path.join(DOSSIER, "heatmap_corr.json")

# ==========================
# REGLAGES
# ==========================
MIN_POINTS = 12          # minimum de points communs pour calculer une corrélation
TOP_PARKINGS = 30        # nombre de parkings à afficher (évite une heatmap gigantesque)
TOP_STATIONS = 40        # nombre de stations à afficher
SELECTION = "recent"     # "recent" ou "most_points"
# - "recent"     : prend les parkings/stations présents dans les séries (ordre du catalog)
# - "most_points": prend ceux qui ont le plus de points disponibles

# ==========================
# OUTILS
# ==========================

def lire_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    num = 0.0
    dx = 0.0
    dy = 0.0
    for i in range(n):
        a = x[i] - mx
        b = y[i] - my
        num += a * b
        dx += a * a
        dy += b * b
    if dx <= 0 or dy <= 0:
        return None
    return num / math.sqrt(dx * dy)

def charger_points_series(series_path):
    data = lire_json(series_path)
    if not data or "points" not in data:
        return None

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

def score_item_by_points(item, series_cache):
    path = item.get("series")
    if not path:
        return 0
    if path not in series_cache:
        series_cache[path] = charger_points_series(path)
    mp = series_cache.get(path)
    return len(mp) if mp else 0

# ==========================
# MAIN
# ==========================

def main():
    os.makedirs(DOSSIER, exist_ok=True)

    catalog = lire_json(CATALOG)
    if not catalog:
        print("catalog.json introuvable :", CATALOG)
        return

    parkings = catalog.get("parkings", [])
    stations = catalog.get("stations", [])

    if len(parkings) == 0 or len(stations) == 0:
        print("Pas assez d'objets dans catalog.json")
        return

    # Cache des séries (évite de relire 1000 fois)
    series_cache = {}

    # Sélection des items (pour limiter taille heatmap)
    if SELECTION == "most_points":
        parkings_sorted = sorted(parkings, key=lambda it: -score_item_by_points(it, series_cache))
        stations_sorted = sorted(stations, key=lambda it: -score_item_by_points(it, series_cache))
    else:
        parkings_sorted = list(parkings)
        stations_sorted = list(stations)

    parkings_sel = parkings_sorted[:TOP_PARKINGS]
    stations_sel = stations_sorted[:TOP_STATIONS]

    # Préchargement séries sélectionnées
    def get_series_map(item):
        path = item.get("series")
        if not path:
            return None
        if path not in series_cache:
            series_cache[path] = charger_points_series(path)
        return series_cache.get(path)

    p_names = [p.get("name", "?") for p in parkings_sel]
    s_names = [s.get("name", "?") for s in stations_sel]

    # Matrice corr (lignes=parkings, colonnes=stations)
    matrix = []
    npoints_matrix = []

    for p in parkings_sel:
        mp = get_series_map(p)
        row_corr = []
        row_npts = []

        for s in stations_sel:
            ms = get_series_map(s)

            if not mp or not ms:
                row_corr.append(None)
                row_npts.append(0)
                continue

            common = sorted(set(mp.keys()) & set(ms.keys()))
            if len(common) < MIN_POINTS:
                row_corr.append(None)
                row_npts.append(len(common))
                continue

            x = [mp[t] for t in common]
            y = [ms[t] for t in common]
            r = pearson(x, y)

            row_corr.append(float(r) if r is not None else None)
            row_npts.append(int(len(common)))

        matrix.append(row_corr)
        npoints_matrix.append(row_npts)

    out = {
        "title": "Heatmap des corrélations (Pearson) parking ↔ station",
        "method": "pearson",
        "aligned": "exact_timestamp",
        "min_points": int(MIN_POINTS),
        "parkings_count": int(len(p_names)),
        "stations_count": int(len(s_names)),
        "parkings": p_names,
        "stations": s_names,
        "corr": matrix,
        "n_points": npoints_matrix
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("heatmap_corr.json généré :", OUT_JSON)
    print("   parkings:", len(p_names), "| stations:", len(s_names))

if __name__ == "__main__":
    main()
