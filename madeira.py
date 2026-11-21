"""Builds web/regions/madeira.json: the best inline-skating spots on Madeira, picked by hand (Nov 2026 trip).

Inputs (Overpass answers, refetch with the q_*.txt files in data/madeira/):
  paths1..4.json  footways, cycleways, paths and coastline for the whole island (q_paths1..4.txt)
  roads.json      Paul da Serra plateau roads and Porto Santo cycleway (q_roads.txt)
  prom.json       Funchal–Câmara de Lobos promenade (q_prom.txt)
  spots.json      skateparks and pump tracks (q_spots.txt)
How the picks were made: madeira_scan.py lists every smooth car-free stretch; most are steep alleys (veredas) or
narrow levada paths, so the routes below are the flat seafront ones, checked in satellite images and the news.
Each route gets a steepness and sharp-turn check from the terrain model (Mapterhorn zoom 13, ~8 m per pixel;
unreliable right at sea cliffs, so the check is shown only where it is believable).
Run: python3 madeira.py
"""
import glob, heapq, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "madeira")
os.environ.setdefault("DEM_Z", "13")
sys.path.insert(0, HERE); import dem

SRC = "picked by hand (Madeira trip, Nov 2026)"
SMOOTH = {"asphalt", "concrete", "concrete:lanes", "concrete:plates", "paved", "paving_stones"}


def dist(a, b):
    x = (b[1] - a[1]) * math.cos(math.radians(a[0])) * 111320; y = (b[0] - a[0]) * 110540
    return math.hypot(x, y)


# ---------- one graph of every path and road we have ----------
els, seen = [], set()
for f in sorted(glob.glob(os.path.join(D, "paths[0-9].json"))) + sorted(glob.glob(os.path.join(D, "roads[0-9].json"))) + [os.path.join(D, "roads.json"), os.path.join(D, "prom.json")]:
    for e in json.load(open(f))["elements"]:
        if e["id"] in seen or not e["tags"].get("highway"): continue
        seen.add(e["id"]); els.append(e)
FOOT = ("footway", "pedestrian", "cycleway", "path", "steps", "living_street")
adj, adjR, surf = {}, {}, {}  # adjR: car roads only, for the road routes
for e in els:
    t = e["tags"]; g = [(round(p["lat"], 6), round(p["lon"], 6)) for p in e["geometry"] if p]
    good = (t.get("surface") in SMOOTH or t.get("surface") is None and t.get("highway") not in FOOT) and t.get("access") != "no"
    for a, b in zip(g, g[1:]):
        w = dist(a, b) * (1 if good else 8)
        wf = w * (4 if t.get("highway") not in FOOT else 1)  # path routes keep off car roads
        adj.setdefault(a, []).append((b, wf)); adj.setdefault(b, []).append((a, wf))
        if t.get("highway") not in FOOT and not t.get("tunnel"): adjR.setdefault(a, []).append((b, w)); adjR.setdefault(b, []).append((a, w))
        surf[(a, b)] = surf[(b, a)] = t.get("surface", "asphalt" if t.get("highway") not in FOOT else "?")


def trace(*via, roads=False):
    """Shortest smooth way through the given points, as one polyline (roads=True: car roads only)."""
    adj_ = adjR if roads else adj
    out, tot = [], {}
    for A, B in zip(via, via[1:]):
        a = min(adj_, key=lambda q: dist(A, q)); b = min(adj_, key=lambda q: dist(B, q))
        best, prev, h = {a: 0}, {}, [(0, a)]
        while h:
            c, u = heapq.heappop(h)
            if u == b: break
            if c > best[u]: continue
            for v, w in adj_[u]:
                if c + w < best.get(v, 1e18): best[v] = c + w; prev[v] = u; heapq.heappush(h, (c + w, v))
        path = [b]
        while path[-1] != a: path.append(prev[path[-1]])
        path.reverse()
        for x, y in zip(path, path[1:]): tot[surf[(x, y)]] = tot.get(surf[(x, y)], 0) + dist(x, y)
        out += path if not out else path[1:]
    return [[round(p[0], 5), round(p[1], 5)] for p in out], tot


def glen(g): return sum(dist(a, b) for a, b in zip(g, g[1:]))
def km(m): return f"{m / 1000:.1f} km"


def hill(g):
    """Steepest 100 m (in %) and sharp turns (over 60° within ~40 m) where the grade is over 6 %."""
    pts = [g[0]]
    for a, b in zip(g, g[1:]):
        d = dist(a, b); n = int(d // 20)
        for i in range(1, n + 1): pts.append((a[0] + (b[0] - a[0]) * i * 20 / d, a[1] + (b[1] - a[1]) * i * 20 / d))
        pts.append(tuple(b))
    h = [dem.elevation(*p) for p in pts]
    cum = [0]
    for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + dist(a, b))
    worst, steep, j = 0, set(), 0
    for i in range(len(pts)):
        while j < len(pts) - 1 and cum[j] - cum[i] < 100: j += 1
        if cum[j] - cum[i] >= 80:
            gr = abs(h[j] - h[i]) / (cum[j] - cum[i]); worst = max(worst, gr)
            if gr > 0.06: steep.update(range(i, j + 1))
    hd = lambda a, b: math.degrees(math.atan2((b[1] - a[1]) * math.cos(math.radians(a[0])), b[0] - a[0]))
    sharp, last = 0, -99
    for i in range(2, len(pts) - 2):
        if i in steep and i - last > 4 and abs((hd(pts[i - 2], pts[i]) - hd(pts[i], pts[i + 2]) + 180) % 360 - 180) > 60:
            sharp += 1; last = i
    return round(worst * 100), sharp, round(max(h) - min(h))


# ---------- point spots from the map data ----------
osm = {f'{e["type"]}/{e["id"]}': e for e in json.load(open(os.path.join(D, "spots.json")))["elements"]}
def pos(ref):
    e = osm[ref]; c = e.get("center") or e
    return [round(c["lat"], 5), round(c["lon"], 5)]

NOFLAG = {"indoor": False, "dirt": False}
spots = [
    # parks and tracks
    {"id": "mad-funchal", "k": "park", "n": "Skate Park do Funchal", "osm": "way/439681059", "s": 5,
     "w": "The island's main skatepark, by the sea next to the Monte cable car. Concrete, about 900 m², lit, free. Quarters, banks, funboxes, pyramid, rails, curbs. Busy after school, quiet in the morning.",
     "i": {"Surface": "concrete", "Lit": "yes", "Rain": "open air", "Source": SRC}, "tf": "https://trucksandfins.com/en/spots/skateparks/Funchal-skatepark/2082", "f": NOFLAG},
    {"id": "mad-prazeres", "k": "park", "n": "Patinódromo dos Prazeres (speed skating track)", "osm": "way/925740671", "s": 4,
     "w": "A real inline speed-skating track (€619k, national championships June 2026), up in Prazeres on the dry south-west. Run by the club CDR Prazeres: ask the club before you skate. Their skaters also know where to get frames and wheels on the island.",
     "i": {"Type": "speed skating track", "Surface": "track surface", "Access": "ask CDR Prazeres", "Source": SRC}, "f": NOFLAG},
    {"id": "mad-aguadepena", "k": "park", "n": "Skate Park Água de Pena (under the runway)", "osm": "way/286841835", "s": 4,
     "w": "Under the airport runway pillars, so it stays dry: the best rain option. Inside a paid sports complex (weekdays 10–18, shorter at weekends). The complex is run down and works were announced for 2026, so check recent photos.",
     "i": {"Surface": "unknown", "Rain": "covered", "Hours": "Mon–Fri 10–18, Sat–Sun 10–17", "Source": SRC},
     "tf": "https://trucksandfins.com/en/spots/skateparks/aeroporto-skatepark/25201", "f": NOFLAG},
    {"id": "mad-graca", "k": "park", "n": "Jardins da Graça Skatepark (Machico)", "osm": "way/557467935", "s": 3,
     "w": "Concrete skatepark in Machico, lit. Only known from the map data, no reviews found. Combine with the smooth seafront on the east side of the bay.",
     "i": {"Surface": "concrete", "Lit": "yes", "Source": SRC}, "f": NOFLAG},
    {"id": "mad-faial", "k": "park", "n": "Roller track Faial (north coast)", "osm": "way/138481140", "s": 3,
     "w": "Roller skating track on the north side, probably the venue of the Biosfera Roller Skate race. Wetter side of the island. Access not checked.",
     "i": {"Type": "roller skating track", "Surface": "unknown", "Source": SRC}, "f": NOFLAG},
    {"id": "mad-cdl-pump", "k": "pump", "n": "Pump track Câmara de Lobos", "osm": "way/1417537845", "s": 5,
     "w": "Concrete pump track in the new sports park (opened July 2025), for skates, boards, bikes and scooters. The best confirmed new spot on the island.",
     "i": {"Surface": "concrete", "Opened": "July 2025", "Source": SRC}, "f": NOFLAG},
    {"id": "mad-garajau-pump", "k": "pump", "n": "Pumptrack Parque do Garajau (Caniço)", "osm": "way/736909674", "s": 2,
     "w": "Only known from the map data, tagged as a BMX track. Surface unknown: could be dirt. Check the satellite view before you drive there.",
     "i": {"Surface": "unknown", "Source": SRC}, "f": NOFLAG},
]
for s in spots: s["p"] = pos(s["osm"])

# smooth squares (too short or too broken up to be routes)
spots += [
    {"id": "mad-z-funchal", "k": "plaza", "n": "Funchal: Praça do Povo and the marina", "p": [32.64655, -16.9095], "osm": "way/166623172", "s": 4, "sub": "smoothplaza",
     "w": "The smooth part of Funchal's seafront: excellent concrete squares by Praça do Povo and along the marina, lit at night. Laps rather than a cruise. The rest of the seafront and Avenida Arriaga is Madeiran cobble: avoid. Cruise passengers fill it from about 10 to 17, so skate before 9 or after 18.",
     "i": {"Surface": "concrete, smooth pavers", "Lit": "yes", "Crowds": "very busy 10–17", "Source": SRC}, "f": {"su": "concrete", "area": 1}},
    {"id": "mad-z-machico", "k": "plaza", "n": "Machico: east side of the bay", "p": [32.7189, -16.76146], "osm": "way/556484075", "s": 3, "sub": "smoothplaza",
     "w": "Excellent concrete square and a 250 m asphalt path by the beach on the São Roque side of Machico bay. Flat and quiet. The town seafront is cobble. Jardins da Graça skatepark is a few minutes away.",
     "i": {"Surface": "concrete, asphalt", "Crowds": "quiet", "Source": SRC}, "f": {"su": "concrete", "area": 1}},
]

# ---------- shops for inline parts (Google ratings read on Google Maps, 21 Nov 2026) ----------
GM = "https://www.google.com/maps/search/?api=1&query="
SHOPS = [
    ("mad-shop-decathlon", "Decathlon Funchal", [32.65335, -16.94307], 5, "4.5 (3,909 reviews)", "https://www.decathlon.pt", "Decathlon Funchal",
     "Best bet for inline wheels and bearings (Oxelo wheels and bearings, Powerslide bearings). Frames are rare in store: call first. Can also order Decathlon's own items to the store.",
     {"Address": "Azinhaga do Poço Barral 14, Funchal", "Hours": "opens 9:00 (check)", "Phone": "+351 291 143 852"}),
    ("mad-shop-omni", "Omni Skate Shop", [32.64886, -16.90637], 4, "3.6 (85 reviews)", "https://www.facebook.com/OmniSkateSurfShop/", "Omni Skate Shop Funchal",
     "The island's only real skate shop. Skateboard bearings are the same size (608) as inline bearings. Inline wheels and frames unlikely, but the staff know the local skaters.",
     {"Address": "Rua 31 de Janeiro 13, Funchal", "Hours": "Mon–Fri 10–20, Sat 10–17, Sun closed", "Phone": "965 063 946"}),
    ("mad-shop-connect", "Decathlon Connect Funchal (old town)", [32.64941, -16.90785], 3, "4.3 (91 reviews)", "https://www.decathlon.pt", "Decathlon Connect Funchal",
     "Small pickup store: order on decathlon.pt and collect here. Little skate stock in the shop itself. Marketplace items (most frames) cannot be collected here and take 8–10 working days to Madeira.",
     {"Address": "Rua dos Ferreiros 70, Funchal", "Hours": "Mon–Fri 9:30–19:30, Sat 10–18:30, Sun closed", "Phone": "969 245 369"}),
    ("mad-shop-ericeira", "Ericeira Surf & Skate (Madeira Shopping)", [32.65974, -16.9506], 2, "4.2 (51 reviews)", "https://ericeirasurfskate.pt", "Ericeira Surf & Skate MadeiraShopping",
     "Skate shop in the mall, mostly clothing. Maybe skateboard bearings (608 fits inlines). Inline wheels and frames unlikely. Sport Zone is in the same mall.",
     {"Address": "Madeira Shopping, Caminho Santa Quitéria 45, Funchal", "Hours": "daily 10–23", "Phone": "261 860 330"}),
    ("mad-shop-sz-ms", "Sport Zone (Madeira Shopping)", [32.65847, -16.95036], 2, "3.9 (131 reviews)", "https://www.sprintersports.com/pt", "Sport Zone MadeiraShopping Funchal",
     "May have complete recreational skates. Spare parts unlikely.",
     {"Address": "Caminho de Santa Quitéria, Madeira Shopping, Funchal", "Hours": "daily 10–23", "Phone": "930 588 432"}),
    ("mad-shop-sz-forum", "Sport Zone (Fórum Madeira)", [32.63671, -16.94302], 2, "4.2 (289 reviews)", "https://www.sprintersports.com/pt", "Sport Zone Fórum Madeira",
     "May have complete recreational skates. Spare parts unlikely.",
     {"Address": "Estrada Monumental 390, Fórum Madeira, Funchal", "Hours": "daily 10–23", "Phone": "930 585 645"}),
]
for sid, n, p, s_, rating, web, q, w, i in SHOPS:
    spots.append({"id": sid, "k": "shop", "n": n, "p": p, "s": s_, "w": w, "web": web, "gm": GM + q.replace(" ", "+"),
                  "i": dict({"Google rating": rating + ", Nov 2026"}, **i, Source=SRC), "osm": "", "f": {}})

# ---------- routes ----------
CROWD_FX = "Funchal's seafront fills with cruise passengers from about 10 to 17: skate before 9 or after 18."
ROUTES = [
    # id, name, stars, via points, text, info, show the hill check
    ("mad-r-ribeirabrava", "Ribeira Brava: old coast road cycleway", 5, [(32.67105, -17.06623), (32.67286, -17.06904), (32.67695, -17.07815)],
     "Flat red-asphalt cycle lane, separated by a curb from a quiet road, along the old coast road west of Ribeira Brava: cliffs on one side, sea on the other, on the dry, sunny south-west. The last 340 m by town is excellent concrete. A dead end in the west (the old road beyond is closed by rockfall), so skate it out and back.",
     {"Environment": "coast, cliffs", "Traffic": "own lane next to a quiet road", "Crowds": "quiet", "Rain": "dry side", "Street View": "2026: wide, smooth red asphalt the whole way"}, False),
    ("mad-r-calheta", "Calheta: beach and marina promenade", 4, [(32.7168, -17.16918), (32.71744, -17.17201), (32.71964, -17.17454), (32.72077, -17.17808)],
     "Wide, flat concrete promenade along Calheta's sandy beach and marina on the driest, sunniest coast. Short, so do laps. Closed for a few weeks in January 2026 after rockfall, open again since.",
     {"Environment": "coast, beach", "Traffic": "none", "Crowds": "busy around the beach in the afternoon", "Rain": "dry side", "Street View": "smooth asphalt by the sea, concrete and pavers at the marina (2016–2024 photos)"}, False),
    ("mad-r-cavacas", "Funchal: Doca do Cavacas → Praia Formosa", 4, [(32.6357, -16.9478), (32.6407, -16.9527)],
     "Concrete cycleway and promenade from the Doca do Cavacas tunnel to Praia Formosa beach. Sea views, some short ramps. The promenade further west to Câmara de Lobos is closed after Storm Charles (Nov 2026): check the barriers, crossing them gets fined.",
     {"Environment": "coast", "Traffic": "none", "Crowds": "walkers, busy at weekends", "Status": "check before you go", "Street View": "wide smooth concrete, a few cracks by Praia Formosa"}, False),
    ("mad-r-formosa-cdl", "CLOSED: Praia Formosa → Câmara de Lobos promenade", 3, [(32.6407, -16.9527), (32.64519, -16.96948)],
     "The best concrete promenade on the island (2.6 km, along the cliffs to the pump track in Câmara de Lobos), but closed since Storm Charles on 10–11 Nov 2026: the sea broke part of the walkway. Still closed on 17 Nov for a technical check; about two weeks were estimated. Do not cross the barriers.",
     {"Environment": "coast, cliffs", "Traffic": "none", "Status": "closed (Nov 2026)", "Street View": "smooth concrete with drain covers (before the storm)"}, False),
    ("mad-r-lido", "Funchal: Lido → Ponta da Cruz", 3, [(32.6356, -16.9328), (32.63421, -16.94663)],
     "Seafront promenade from the Lido pools, mostly paving stones in good condition, so expect joints. " + CROWD_FX,
     {"Environment": "coast, hotels", "Traffic": "none", "Surface": "paving stones", "Crowds": "busy", "Street View": "interlocking pavers with joints, a cobble stripe in places"}, False),
    ("mad-r-jardimdomar", "Jardim do Mar promenade", 4, [(32.73531, -17.20895), (32.73979, -17.2126)],
     "Wide seafront promenade in the small village of Jardim do Mar under steep cliffs, on the dry south-west. Looks even in Street View (the map data says paving stones). Nature and surf spot; quiet.",
     {"Environment": "coast, cliffs, village", "Traffic": "none", "Crowds": "quiet", "Street View": "wide, even surface along the sea wall"}, False),
    ("mad-r-monumental", "Funchal: Estrada Monumental cycle path (Lido → Praia Formosa)", 3, [(32.63852, -16.93362), (32.63544, -16.94234), (32.6406, -16.94852)],
     "Concrete cycle path along Funchal's hotel road, linking the Lido to Praia Formosa above the closed seafront. Separated from the road by hedges and bollards, smooth red surface at the Lido end. City setting with traffic noise.",
     {"Environment": "city, hotels", "Traffic": "own path next to a busy road", "Street View": "smooth red lane at the Lido end; elsewhere only seen from the road"}, False),
    ("mad-r-madalena", "Madalena do Mar promenade", 3, [(32.70045, -17.13519), (32.70318, -17.13795)],
     "Short seafront promenade of large concrete plates in the banana village of Madalena do Mar, cliffs behind, waves alongside. Joints between the plates. South-west, dry side.",
     {"Environment": "coast, cliffs, village", "Traffic": "none", "Crowds": "quiet", "Street View": "large concrete plates with joints"}, False),
    ("mad-r-canical", "Caniçal seafront promenade", 2, [(32.73571, -16.73989), (32.73544, -16.74582)],
     "Paver promenade along the cliffs by the whale museum in Caniçal, on the far east. Narrow and with joints, but quiet and wild.",
     {"Environment": "coast, cliffs", "Traffic": "none", "Crowds": "quiet", "Street View": "narrow pavers"}, False),
    ("mad-r-portosanto", "Porto Santo: seafront cycleway (ferry)", 5, [(33.0479, -16.3539), (33.0254, -16.3799)],
     "The longest smooth car-free route in the archipelago: 3.8 km of asphalt cycleway along the 9 km beach, gentle slopes, and the driest island. Rollerblading is explicitly allowed on the promenade. Needs the ferry from Funchal (about 2.5 h).",
     {"Environment": "coast, beach", "Traffic": "none (cycleway)", "Rain": "driest island", "Surface": "asphalt", "Slope": "gentle", "Street View": "only from the road; the cycleway itself is not shown. The town promenade is cobble"}, False),
]
for rid, n, s, via, w, info, check in ROUTES:
    g, tot = trace(*via)
    L = glen(g); top = max(tot, key=tot.get)
    i = {"Length": km(L)}
    i.update(info)
    i.setdefault("Surface", top.replace("_", " "))
    if check:
        worst, sharp, rise = hill(g)
        i["Steepest 100 m"] = f"{worst} %"; i["Sharp turns on steep parts"] = str(sharp); i["Height difference"] = f"{rise} m"
    i["Source"] = SRC
    spots.append({"id": rid, "k": "route", "n": n, "p": g[0], "g": g, "s": s, "w": w, "i": i, "f": {}})
    print(f"{n}: {km(L)} {({k: round(v) for k, v in tot.items()})} {i.get('Steepest 100 m', '')} {i.get('Sharp turns on steep parts', '')}")


# ---------- car roads: quiet, smooth, flat stretches (madeira_roads.py, checked in Street View) ----------
ROAD_WARN = "Car road: you share it with traffic. In Portugal skaters count as pedestrians, so keep to the edge, skate in daylight and good visibility, and wear something bright."
ROADS = [
    ("mad-road-madalena", "Car road: Madalena do Mar seafront (ER101)", 4, [(32.70041, -17.13508), (32.69414, -17.1265)],
     "The old coast road through the banana village of Madalena do Mar, right along the sea. Wide and smooth asphalt, flat, and it looked quiet in Street View. A paver pavement runs next to it if cars come. Dry, sunny south-west; combine with the promenade at the west end.",
     {"Environment": "coast, village", "Traffic": "light (local traffic)", "Street View": "2026: wide smooth asphalt, few cars, sea wall on one side"}),
    ("mad-road-saovicente", "Car road: São Vicente coast road (ER101)", 4, [(32.8146, -17.02599), (32.81077, -17.0412)],
     "Flat coast road at São Vicente on the north coast, between green cliffs and the sea. Smooth asphalt and little traffic in Street View. The north side is wetter: pick a dry day.",
     {"Environment": "coast, cliffs, nature", "Traffic": "light", "Rain": "wetter side", "Street View": "2026: smooth asphalt, very few cars"}),
    ("mad-road-paulserra", "Car road: Paul da Serra plateau (ER105/ER209)", 4, [(32.7644, -17.0822), (32.7578, -17.0972), (32.7515, -17.1115)],
     "Asphalt road across the high plateau, a mostly gentle descent westwards from about 1,490 to 1,385 m (3–4 % on average): moorland, wind turbines, views and wide open nature. Often in fog and wind: go on a clear day. Drive up: every road down is long and steep with hairpins.",
     {"Environment": "mountain plateau, nature", "Traffic": "tourist cars and buses", "Rain": "fog and wind common", "Street View": "2026: good asphalt, wide verges"}),
    ("mad-road-paulserra-e", "Car road: Paul da Serra east, wind farm (ER105)", 3, [(32.75284, -17.05857), (32.76366, -17.0712)],
     "The eastern end of the plateau road among the wind turbines and yellow broom at about 1,550 m. Smooth asphalt, wide open views. Same fog and wind warning as the rest of the plateau.",
     {"Environment": "mountain plateau, nature", "Traffic": "tourist cars", "Rain": "fog and wind common", "Street View": "2026: smooth asphalt, empty road"}),
    ("mad-road-fanal", "Car road: ER209 towards Fanal", 3, [(32.77932, -17.12683), (32.78677, -17.12729)],
     "Straight plateau road through heath and old laurel trees on the way to the Fanal forest. Good asphalt, but often deep in fog: only on a clear day.",
     {"Environment": "forest, nature", "Traffic": "tourist cars", "Rain": "fog very common", "Street View": "2026: good asphalt, fog"}),
    ("mad-road-er105n", "Car road: ER105 north plateau (towards Porto Moniz)", 3, [(32.81639, -17.18999), (32.82409, -17.19227)],
     "Flat stretch of the plateau road north of Fanal, through heath and woodland at about 1,000 m. Smooth asphalt with centre lines.",
     {"Environment": "forest, nature", "Traffic": "tourist cars", "Rain": "wetter side", "Street View": "2026: smooth asphalt"}),
    ("mad-road-lombo", "Car road: Caminho Lombo da Rocha, Prazeres", 3, [(32.7544, -17.2102), (32.75371, -17.20414)],
     "Quiet village road on the Prazeres plateau with smooth asphalt and a pavement, close to the speed-skating track. Good for a warm-up or a few laps after the track.",
     {"Environment": "village, farmland", "Traffic": "light (local traffic)", "Street View": "2026: smooth asphalt, quiet"}),
]
for rid, n, s_, via, w, info in ROADS:
    g, tot = trace(*via, roads=True)
    L = glen(g)
    worst, sharp, rise = hill(g)
    i = {"Length": km(L), "Type": "car road"}
    i.update(info)
    i.setdefault("Surface", "asphalt")
    i["Steepest 100 m"] = f"{worst} %"; i["Sharp turns on steep parts"] = str(sharp); i["Height difference"] = f"{rise} m"
    i["Source"] = SRC
    spots.append({"id": rid, "k": "route", "n": n, "p": g[0], "g": g, "s": s_, "w": w, "warn": ROAD_WARN, "i": i, "f": {"road": True}})
    print(f"{n}: {km(L)} steepest {worst} %, sharp {sharp}, rise {rise} m")

# ---------- surface layer: the seafront and cycleways we checked ----------
lines = {"1": [], "2": [], "3": []}
for e in els:
    t = e["tags"]
    if t.get("highway") not in ("footway", "pedestrian", "cycleway"): continue
    g = [[round(p["lat"], 5), round(p["lon"], 5)] for p in e["geometry"] if p]
    if not any(min(dist(p, r["g"][k]) for k in range(0, len(r["g"]), 3)) < 40 for r in spots if r["k"] == "route" for p in g[:: max(1, len(g) // 3)]): continue
    q = {"concrete": "3", "asphalt": "3", "concrete:lanes": "3", "paved": "2", "paving_stones": "2"}.get(t.get("surface"), "1" if t.get("surface") in ("sett", "unhewn_cobblestone", "cobblestone") else None)
    if q: lines[q].append(g)

out = {"name": "madeira", "bbox": [32.6, 33.1, -17.3, -16.25], "surf": lines, "spots": spots, "graph": {"n": [], "e": []}, "built": "2026-11-21"}
json.dump(out, open(os.path.join(HERE, "web", "regions", "madeira.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(len(spots), "spots,", sum(len(v) for v in lines.values()), "surface lines")
