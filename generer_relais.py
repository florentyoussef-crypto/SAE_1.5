import os
import json
import math

DOSSIER = "donnees"
CATALOG = os.path.join(DOSSIER, "catalog.json")
OUT_JSON = os.path.join(DOSSIER, "relais_pertinents.json")

# Réglages (tu peux ajuster)
MAX_DISTANCE_M = 800          # distance max parking↔station
MIN_POINTS = 12               # minimum de points communs
TOP_N = 30                    # nombre de couples gardés

def lire_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def haversine_m(lat1, lon1, lat2, lon2):
    # Distance en mètres
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

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
    # series_path dans catalog = "donnees/series/xxx.json"
    data = lire_json(series_path)
    if not data or "points" not in data:
        return None
    # points = [{"timestamp": "...", "value": ...}, ...]
    pts = data["points"]
    m = {}
    for p in pts:
        ts = p.get("timestamp")
        v = p.get("value")
        if ts is None or v is None:
            continue
        try:
            m[str(ts)] = float(v)
        except Exception:
            pass
    return m

def main():
    os.makedirs(DOSSIER, exist_ok=True)

    catalog = lire_json(CATALOG)
    if not catalog:
        print("❌ catalog.json introuvable :", CATALOG)
        return

    parkings = catalog.get("parkings", [])
    stations = catalog.get("stations", [])

    if len(parkings) == 0 or len(stations) == 0:
        print("❌ Pas assez d'objets dans catalog.json")
        return

    # Pré-charge toutes les séries (pour éviter de relire 1000 fois)
    series_cache = {}

    def get_series_map(item):
        path = item.get("series")
        if not path:
            return None
        if path not in series_cache:
            series_cache[path] = charger_points_series(path)
        return series_cache[path]

    candidats = []

    for p in parkings:
        plat = p.get("lat")
        plon = p.get("lon")
        if plat is None or plon is None:
            continue

        for s in stations:
            slat = s.get("lat")
            slon = s.get("lon")
            if slat is None or slon is None:
                continue

            d = haversine_m(float(plat), float(plon), float(slat), float(slon))
            if d > MAX_DISTANCE_M:
                continue

            mp = get_series_map(p)
            ms = get_series_map(s)
            if not mp or not ms:
                continue

            common = sorted(set(mp.keys()) & set(ms.keys()))
            if len(common) < MIN_POINTS:
                continue

            x = [mp[t] for t in common]
            y = [ms[t] for t in common]
            r = pearson(x, y)
            if r is None:
                continue

            candidats.append({
                "parking": p.get("name"),
                "station": s.get("name"),
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

    # Tri : meilleurs d'abord (|corr| DESC), puis distance ASC
    candidats.sort(key=lambda o: (-abs(o["correlation"]), o["distance_m"]))

    out = {
        "max_distance_m": MAX_DISTANCE_M,
        "min_points": MIN_POINTS,
        "count_total": len(candidats),
        "top_n": TOP_N,
        "items": candidats[:TOP_N]
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("✅ relais_pertinents.json généré :", OUT_JSON)
    print("✅ Couples trouvés :", len(candidats), " | gardés :", min(TOP_N, len(candidats)))

if __name__ == "__main__":
    main()
