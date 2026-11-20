"""Builds web/regions/madeira.json: hand-picked spots on Madeira (holiday region, no full OSM scan).

Inputs: data/madeira/spots.json (Overpass, q_spots.txt), data/madeira/prom.json (Overpass, q_prom.txt).
Promenade geometry is traced along the Passeio Público Marítimo; surfaces come from OSM tags.
Run: python3 madeira.py
"""
import heapq, json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "madeira")
PROMENADE = ("Passeio Público Marítimo", "Túnel da Doca do Cavacas", "Cais do Carvão")


def dist(a, b):
    x = (b[1] - a[1]) * math.cos(math.radians(a[0])) * 111320
    y = (b[0] - a[0]) * 110540
    return math.hypot(x, y)


# ---------- promenade routes ----------
prom = json.load(open(os.path.join(D, "prom.json")))
adj, surf = {}, {}
for e in prom["elements"]:
    g = [(round(p["lat"], 6), round(p["lon"], 6)) for p in e["geometry"]]
    s = e["tags"].get("surface", "?")
    k = 1 if e["tags"].get("name") in PROMENADE else 6  # stay on the promenade
    for a, b in zip(g, g[1:]):
        w = dist(a, b) * k
        adj.setdefault(a, []).append((b, w)); adj.setdefault(b, []).append((a, w))
        surf[(a, b)] = surf[(b, a)] = s


def trace(A, B):
    a = min(adj, key=lambda q: dist(A, q)); b = min(adj, key=lambda q: dist(B, q))
    best, prev, h = {a: 0}, {}, [(0, a)]
    while h:
        c, u = heapq.heappop(h)
        if u == b: break
        if c > best[u]: continue
        for v, w in adj[u]:
            if c + w < best.get(v, 1e18): best[v] = c + w; prev[v] = u; heapq.heappush(h, (c + w, v))
    path = [b]
    while path[-1] != a: path.append(prev[path[-1]])
    path.reverse()
    tot = {}
    for x, y in zip(path, path[1:]): tot[surf[(x, y)]] = tot.get(surf[(x, y)], 0) + dist(x, y)
    return [[round(p[0], 5), round(p[1], 5)] for p in path], tot


LIDO, PONTA = (32.6356, -16.9328), (32.63421, -16.94663)
CAVACAS, FORMOSA, CDL = (32.6357, -16.9478), (32.6407, -16.9527), (32.64519, -16.96948)
g_lido, t_lido = trace(LIDO, PONTA)
g_w1, t_w1 = trace(CAVACAS, FORMOSA)
g_w2, t_w2 = trace(FORMOSA, CDL)
g_west = g_w1 + g_w2[1:]
glen = lambda g: sum(dist(a, b) for a, b in zip(g, g[1:]))
km = lambda m: f"{m / 1000:.1f} km"
share = lambda t, k: round(100 * t.get(k, 0) / max(1, sum(t.values())))

# ---------- spots ----------
osm = {f'{e["type"]}/{e["id"]}': e for e in json.load(open(os.path.join(D, "spots.json")))["elements"]}
def pos(ref):
    e = osm[ref]; c = e.get("center") or e
    return [round(c["lat"], 5), round(c["lon"], 5)]

SRC = "added by hand (Madeira trip, Nov 2026)"
spots = [
    {"id": "mad-funchal", "k": "park", "n": "Skate Park do Funchal", "osm": "way/439681059", "s": 5,
     "w": "The island's main skatepark. Concrete, about 900 m², lit, free. Quarters, banks, funboxes, pyramid, rails, curbs, step-up. Seafront next to the Monte cable car.",
     "i": {"Surface": "concrete", "Lit": "yes", "Size": "~900 m²", "Source": SRC},
     "tf": "https://trucksandfins.com/en/spots/skateparks/Funchal-skatepark/2082", "f": {"indoor": False, "dirt": False}},
    {"id": "mad-aguadepena", "k": "park", "n": "Skate Park Água de Pena (under the runway)", "osm": "way/286841835", "s": 4,
     "w": "Under the airport runway pillars, so covered: works in rain. The sports park around it was reported run down in 2024, so check recent photos first.",
     "i": {"Surface": "unknown", "Covered": "yes", "Source": SRC},
     "tf": "https://trucksandfins.com/en/spots/skateparks/aeroporto-skatepark/25201", "f": {"indoor": False, "dirt": False}},
    {"id": "mad-graca", "k": "park", "n": "Jardins da Graça Skatepark (Machico)", "osm": "way/557467935", "s": 4,
     "w": "Concrete skatepark in Machico, lit. Only known from the map data, no reviews found.",
     "i": {"Surface": "concrete", "Lit": "yes", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-prazeres", "k": "park", "n": "Pista de Patinagem dos Prazeres", "osm": "way/925740671", "s": 2,
     "w": "Skating area up in Prazeres (Calheta). Only known from the map data: size and surface unknown.",
     "i": {"Surface": "unknown", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-santodaserra", "k": "park", "n": "Roller skating track (Santo da Serra)", "osm": "way/138481140", "s": 2,
     "w": "Roller skating track in the map data. Nothing else known: check the satellite view first.",
     "i": {"Type": "roller skating track", "Surface": "unknown", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-smartinho", "k": "park", "n": "Small skate area (São Martinho)", "osm": "way/1108231881", "s": 1,
     "w": "Marked as a skate area in the map data, but traced automatically from satellite images. May not exist.",
     "i": {"Surface": "unknown", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-cdl-pump", "k": "pump", "n": "Pump track Câmara de Lobos", "osm": "way/1417537845", "s": 5,
     "w": "Concrete pump track in the new sports park (opened July 2025). Built for skateboards, bikes, skates and scooters.",
     "i": {"Surface": "concrete", "Opened": "July 2025", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-garajau-pump", "k": "pump", "n": "Pumptrack Parque do Garajau (Caniço)", "osm": "way/736909674", "s": 3,
     "w": "Pump track in Parque do Garajau. Surface not known: could be asphalt or dirt, check before you go.",
     "i": {"Surface": "unknown", "Source": SRC}, "f": {"indoor": False, "dirt": False}},
    {"id": "mad-povo", "k": "plaza", "n": "Praça do Povo (Funchal)", "osm": "way/316457941", "s": 3,
     "w": "New open seafront square by the harbour. The tourist board lists rollerblading and cycling there. Check the paving: much of Funchal is Madeiran cobble.",
     "i": {"Surface": "unknown", "Source": SRC}, "sub": None, "f": {"su": "unknown", "area": 1}},
]
KNOWN = {"way/316457941": [32.64662, -16.90805]}  # Praça do Povo, from Nominatim
for s in spots: s["p"] = KNOWN.get(s["osm"]) or pos(s["osm"])

spots += [
    {"id": "mad-prom-west", "k": "route", "n": "Promenade: Doca do Cavacas → Praia Formosa → Câmara de Lobos", "p": g_west[0], "g": g_west, "s": 5,
     "w": f"The best cruise found on the island: {km(glen(g_west))} along the sea, {share({k: t_w1.get(k, 0) + t_w2.get(k, 0) for k in set(t_w1) | set(t_w2)}, 'concrete')}% concrete in the map data, through the tunnel at Doca do Cavacas. Parts close or get damaged after storms. Ends near the pump track in Câmara de Lobos.",
     "i": {"Length": km(glen(g_west)), "Surface": "concrete", "Source": SRC}, "f": {"su": "concrete"}},
    {"id": "mad-prom-lido", "k": "route", "n": "Promenade: Lido → Ponta da Cruz", "p": g_lido[0], "g": g_lido, "s": 3,
     "w": f"{km(glen(g_lido))} along the sea from the Lido pools, but {share(t_lido, 'paving_stones') + share(t_lido, 'sett')}% paving stones in the map data, so expect joints. The link on to the Doca do Cavacas tunnel is missing in the map data and was reported closed.",
     "i": {"Length": km(glen(g_lido)), "Surface": "paving stones", "Source": SRC}, "f": {"su": "paving stones"}},
]

# surface layer: smooth (3) = concrete, okay (2) = paving stones
lines = {"1": [], "2": [], "3": []}
for e in prom["elements"]:
    t = e["tags"]
    if t.get("name") not in PROMENADE: continue
    q = {"concrete": "3", "asphalt": "3", "paving_stones": "2", "sett": "1"}.get(t.get("surface"))
    if q: lines[q].append([[round(p["lat"], 5), round(p["lon"], 5)] for p in e["geometry"]])

out = {"name": "madeira", "bbox": [32.6, 32.9, -17.3, -16.6], "surf": lines, "spots": spots, "graph": {"n": [], "e": []}, "built": "2026-11-20"}
json.dump(out, open(os.path.join(HERE, "web", "regions", "madeira.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(len(spots), "spots;", "west", km(glen(g_west)), t_w1, t_w2, "| lido", km(glen(g_lido)), t_lido)
