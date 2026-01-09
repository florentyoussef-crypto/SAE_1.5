name: analyse-quotidienne

on:
  schedule:
    - cron: "15 2 * * *"   # 03:15 heure FR (hiver)
  workflow_dispatch:

permissions:
  contents: write

jobs:
  run:
    runs-on: ubuntu-latest

    steps:
      - name: Recuperation du depot
        uses: actions/checkout@v4

      - name: Installation de Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Installer les dependances
        run: |
          python -m pip install --upgrade pip
          pip install pandas matplotlib requests folium

      - name: Analyse + export JSON + carte
        run: |
          python analyse_semaine.py
          python export_json.py
          python carte_unique.py

      - name: Sauvegarder les resultats
        run: |
          git config user.name "github-actions"
          git config user.email "github-actions@github.com"
          git add donnees/
          git diff --cached --quiet && echo "rien a commit" || git commit -m "analyse quotidienne + graphes + carte + JSON"
          git push
