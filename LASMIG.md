# Skatekartan

Webbkarta för skatespots (Söderort, Vallentuna, Madeira). Live: https://xseb0.github.io/skatemap/
Detaljer och deploy: `README.md`.

## Var saker ligger

- `web/` – kartan (det som publiceras). `web/regions/` – färdigräknade regioner.
- `data/` – Overpass-svar och höjddata per region. `process.py`, `dem.py`, `sthlm_city.py` – bygger regionerna.
- `v1/` – gamla svenska versionen (Vallentuna–Täby), ligger kvar eftersom README hänvisar dit.

## Köra

Lokalt: `skatekartan` i `01_Privat/.claude/launch.json` → http://localhost:8472/web/
Ny region: `python3 process.py <region>`.
Madeira (handplockad för inlines, semester nov 2026): `python3 madeira.py` → `web/regions/madeira.json`. `madeira_scan.py` skannar hela ön efter släta bilfria sträckor. Råa OSM-svar hämtas om med `data/madeira/q_*.txt`.
