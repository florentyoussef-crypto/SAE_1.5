import folium
import pandas as pd
import os

DOSSIER = "donnees"

df_v = pd.read_csv(os.path.join(DOSSIER, "export_voitures.json"))
df_b = pd.read_csv(os.path.join(DOSSIER, "export_velos.json"))

m = folium.Map(location=[43.61, 3.88], zoom_start=13)

# Parkings 
for _, r in df_v.iterrows():
    if r["type"] == "PARKING" and pd.notna(r["lat"]):
        folium.Marker(
            [r["lat"], r["lon"]],
            popup=f"""
            <b>{r['nom']}</b><br>
            Taux occupation : {round(r['taux_occupation'],2)}
            """,
            icon=folium.Icon(icon="car", prefix="fa", color="blue")
        ).add_to(m)

# Stations 
for _, r in df_b.iterrows():
    if r["type"] == "STATION" and pd.notna(r["lat"]):
        folium.Marker(
            [r["lat"], r["lon"]],
            popup=f"""
            <b>{r['nom']}</b><br>
            Vélos : {r['velos_dispo']}<br>
            Bornes libres : {r['bornes_libres']}
            """,
            icon=folium.Icon(icon="bicycle", prefix="fa", color="orange")
        ).add_to(m)

m.save(os.path.join(DOSSIER, "carte.html"))
print("Carte unique générée : donnees/carte.html")
