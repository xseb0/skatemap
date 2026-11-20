# Skate Map

Live: https://xseb0.github.io/skatemap/ (GitHub Pages, repo xseb0/skatemap, branch `gh-pages` = the `web/` folder).
Deploy after changes: commit, then `git push && git subtree push --prefix web origin gh-pages`. Bump `?v=` in `web/index.html` and the region `?v=` in `web/app.js` so phones load the new files.

A web map for finding skate spots: stairs (normal and long, low steps), hills, smooth paths, routes, skateparks, pump tracks, ledges, curbs, rails, plazas and flat ground for powerslides.

- `web/` – the map (Leaflet). Open via the `skatekartan` entry in `01_Privat/.claude/launch.json` → http://localhost:8472/web/
- `web/regions/<region>.json` – precomputed spots, hills, routes and route graph per region (`soder`, `vallentuna`, `madeira`).
- `madeira.py` – builds the Madeira holiday region by hand: picked parks and pump tracks (Overpass `data/madeira/q_spots.txt`) and the seafront promenade traced from `q_prom.txt`, with surfaces from OSM. No hills or route graph there.
- `process.py <region>` – builds a region from `data/<region>/spots.json` + `base.json` (Overpass answers to `q_*.txt`) and ground elevation from Mapterhorn terrain tiles (~1.2 m per pixel, `dem.py`, tiles cached in `data/dem_tiles/`, not in git). `--eudem` falls back to the old 25 m EU-DEM via opentopodata.org.
- Live search (magnifier button) finds spots anywhere via Overpass, but without hills and routes.
- My spots and notes live in the browser's localStorage; "Copy backup" / "Paste backup" moves them between devices.

Add a region: copy `data/soder/q_*.txt`, change the bbox, fetch both with Overpass, run `python3 process.py <name>`, and add the name to `REGIONS` in `web/app.js`.

Old v1 (Swedish, Vallentuna–Täby only, claude.ai artifact): https://claude.ai/artifact/KVHnKGMdMGMHQQcPjzPYsg. Its files are in `v1/`.
