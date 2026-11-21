# Skatekartan

Webbkarta för skatespots (Söderort, Vallentuna, Madeira). Live: https://xseb0.github.io/skatemap/
Detaljer och deploy: `README.md`.

## Var saker ligger

- `web/` – kartan (det som publiceras). `web/regions/` – färdigräknade regioner.
- `data/` – Overpass-svar och höjddata per region. `process.py`, `dem.py`, `sthlm_city.py` – bygger regionerna.
- Ikoner per spottyp (som Fotokartan): `ICON` överst i `web/app.js`, används i punkter, chips, filter, lista, sök och kort. Punkterna blir ikoner när högst ~120 spots syns (eller ~350 från zoom 14), annars små prickar — Söder har tusentals.
- Kortet: Street View kan öppnas stort (lightbox). På rutter och backar flyttar man Street View genom att klicka på linjen eller med ‹ › (100 m), även i lightboxen; en gul kamera på kartan visar var och åt vilket håll. "Photos nearby" hämtar geotaggade bilder från Wikimedia Commons live (150 m runt punkter, 250 m längs linjer) och öppnas i lightbox.
- `98_Arkiv/` – backuper före ändringar.
- `v1/` – gamla svenska versionen (Vallentuna–Täby), ligger kvar eftersom README hänvisar dit.

## Köra

Lokalt: `skatekartan` i `01_Privat/.claude/launch.json` → http://localhost:8472/web/
Ny region: `python3 process.py <region>`.
Madeira (handplockad för inlines, semester nov 2026): `python3 madeira.py` → `web/regions/madeira.json`. `madeira_scan.py` skannar hela ön efter släta bilfria sträckor, `madeira_roads.py` efter platta lugna bilvägar (de får varning och streckad linje). Råa OSM-svar hämtas om med `data/madeira/q_*.txt`.
