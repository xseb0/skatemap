#!/usr/bin/env python3
"""Builds web/regions/<region>.js for the skate map from OSM data and elevations.

Usage: python3 process.py <region> [--no-fetch]
  data/<region>/spots.json, base.json  (Overpass answers from q_spots.txt / q_base.txt)
  data/<region>/elev_cache.json        (opentopodata.org EU-DEM 25 m, cached)
"""
import json, math, os, sys, time, urllib.request, collections, heapq, re

HERE = os.path.dirname(os.path.abspath(__file__))
REGION = sys.argv[1]
D = os.path.join(HERE, "data", REGION)
spots = json.load(open(os.path.join(D, "spots.json")))["elements"]
base = json.load(open(os.path.join(D, "base.json")))["elements"]
bbox = [float(x) for x in open(os.path.join(D, "q_spots.txt")).read().split('"skateboard|roller|bmx|pump"](')[1].split(")")[0].split(",")]
CACHE = os.path.join(D, "elev_cache.json")
elev = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

R = 6371000.0
def dist(a, b):
    la1, lo1 = map(math.radians, a[:2]); la2, lo2 = map(math.radians, b[:2])
    return R * math.hypot((lo2 - lo1) * math.cos((la1 + la2) / 2), la2 - la1)
def glen(g): return sum(dist(g[i], g[i + 1]) for i in range(len(g) - 1))
def area(g):
    if len(g) < 3: return 0
    k = math.cos(math.radians(g[0][0])); pts = [(p[1] * k * 111320, p[0] * 110574) for p in g]
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
def centroid(g): return (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))
def geom(el):
    if el["type"] == "node": return [(el["lat"], el["lon"])]
    if el["type"] == "way": return [(p["lat"], p["lon"]) for p in el.get("geometry", []) if p]
    out = []
    for m in el.get("members", []):
        if m.get("role") in ("outer", "") and m.get("geometry"): out += [(p["lat"], p["lon"]) for p in m["geometry"] if p]
    return out
def r5(g): return [[round(p[0], 5), round(p[1], 5)] for p in g]

PAVED = {"asphalt", "concrete", "paved", "concrete:plates", "paving_stones", "sett"}
SURF = {"asphalt": "asphalt", "concrete": "concrete", "paving_stones": "paving stones", "sett": "cobbles", "gravel": "gravel",
        "fine_gravel": "fine gravel", "wood": "wood", "metal": "metal", "stone": "stone", "granite": "granite", "paved": "paved",
        "concrete:plates": "concrete slabs", "unpaved": "unpaved", "grass": "grass", "ground": "dirt", "acrylic": "acrylic"}
def sv(s): return SURF.get(s, s) if s else "unknown"
YN = {"yes": "yes", "no": "no"}

out, seen = [], set()
def add(kind, el, name, lat, lon, score, why, info, g=None, extra=None):
    key = (el["type"], el["id"], kind)
    if key in seen: return
    seen.add(key)
    s = {"id": f"{REGION[:2]}{el['type'][0]}{el['id']}-{kind}", "k": kind, "n": name, "p": [round(lat, 5), round(lon, 5)],
         "s": max(1, min(5, round(score))), "w": why, "i": info, "osm": f"{el['type']}/{el['id']}"}
    if g and len(g) > 1: s["g"] = r5(g)
    if extra: s.update(extra)
    out.append(s)

for el in spots:
    t = el.get("tags", {}); g = geom(el)
    if not g: continue
    c = centroid(g); nm = t.get("name", ""); sport = t.get("sport", ""); hw = t.get("highway", "")
    if hw == "steps" and (t.get("indoor") == "yes" or t.get("conveying") or t.get("level") not in (None, "0")): continue
    sp_ok = re.search(r"skateboard|bmx|pump|roller_skating|^roller$", sport) and "roller_ski" not in sport
    nm_ok = re.search(r"pump ?track|pumpbana|skate ?park|skateboard|skatepool|skateboardpool|kickbike", nm, re.I) and not hw and t.get("amenity") not in ("compressed_air", "bicycle_repair_station", "fuel")
    if sp_ok or nm_ok:
        if t.get("indoor") == "yes" or t.get("access") == "private": continue
        kind = "pump" if re.search(r"bmx|pump|kick", sport + " " + nm, re.I) and not re.search(r"skate", nm, re.I) else "park"
        info = {"Surface": sv(t.get("surface")), "Lit": YN.get(t.get("lit"), "unknown")}
        if t.get("operator"): info["Operator"] = t["operator"]
        add(kind, el, nm or ("Pump track" if kind == "pump" else "Skatepark"), c[0], c[1], 5,
            "Built for riding" + (", lit at night" if t.get("lit") == "yes" else ""), info, g if el["type"] == "way" else None)
        continue
    if hw == "steps":
        L = glen(g)
        try: n = int(t.get("step_count"))
        except: n = None
        tread = L / n if n else None
        info = {"Length": f"{L:.0f} m"}
        if n: info["Steps"] = str(n)
        if tread: info["Depth per step"] = f"~{tread*100:.0f} cm"
        info["Handrail"] = {"yes": "yes", "no": "no", "left": "left side", "right": "right side", "both": "both sides"}.get(t.get("handrail"), "unknown")
        info["Surface"] = sv(t.get("surface"))
        if "yes" in (t.get("ramp"), t.get("ramp:stroller"), t.get("ramp:wheelchair")): info["Ramp alongside"] = "yes"
        if t.get("lit") == "yes": info["Lit"] = "yes"
        why, score, sub = [], 3, "stairs"
        if n and n <= 4: sub = "short"; why.append(f"{n} steps: good for learning to drop and ollie down"); score = 4
        elif n and n <= 10: why.append(f"{n} steps: nice size for stair bashing"); score = 4
        elif n: why.append(f"{n} steps: long set")
        else: why.append("step count not mapped")
        if tread and tread > 2.2: why.append(f"{L:.0f} m long for {n} steps, so likely landings or flat parts")
        elif tread and tread >= 0.6 and n <= 12:
            sub = "long"; why.insert(0, f"long treads (~{tread*100:.0f} cm per step, from the stair length): likely low, deep steps"); score = 5
        elif tread and tread >= 0.55: why.append(f"~{tread*100:.0f} cm per step by length, probably has landings")
        if t.get("surface") in ("asphalt", "concrete", "stone", "granite", "paving_stones"): score += 0.3; why.append(sv(t.get("surface")))
        if t.get("surface") in ("wood", "metal", "gravel"): score -= 1; why.append(f"{sv(t.get('surface'))}: harder to land on")
        if t.get("handrail") in ("yes", "both", "left", "right"): why.append("has a handrail (usually too high to grind, check)")
        if t.get("ramp") == "yes": why.append("ramp alongside, easy to get back up")
        add("steps", el, nm or {"short": "Short stairs", "long": "Long-tread stairs", "stairs": "Stairs"}[sub], c[0], c[1], score, "; ".join(why), info, g, {"sub": sub})
        continue
    if t.get("leisure") == "pitch":
        surf = t.get("surface")
        if surf and surf not in PAVED | {"acrylic"}: continue
        A = area(g)
        add("flat", el, nm or ("Basketball court" if "basket" in sport else "Court"), c[0], c[1], 4 if surf in ("asphalt", "concrete", "acrylic") else 3,
            "Smooth, flat and open: good for powerslides, manuals and flatground" + ("" if surf else " (surface not mapped)"),
            {"Sport": sport.replace(";", ", "), "Surface": sv(surf), "Area": f"{A:.0f} m²" if A else "unknown"}, g if el["type"] == "way" else None, {"sub": "court"})
        continue
    if t.get("amenity") == "parking":
        A = area(g); surf = t.get("surface")
        if A < 1800 or (surf and surf not in PAVED): continue
        if t.get("access") in ("private", "customers") and A < 4000: continue
        info = {"Area": f"{A:.0f} m²", "Surface": sv(surf)}
        if t.get("access"): info["Access"] = t["access"]
        add("flat", el, nm or "Large car park", c[0], c[1], 3 + (1 if A > 5000 else 0) + (0.5 if surf == "asphalt" else 0),
            f"Big open lot ({A:.0f} m²) for powerslides and flatground when it is empty, e.g. evenings and weekends",
            info, g if el["type"] == "way" else None, {"sub": "parking"})
        continue
    if t.get("amenity") == "school":
        A = area(g)
        if el["type"] == "node" or A < 2000: continue
        add("flat", el, nm or "School", c[0], c[1], 3, "Schoolyards often have asphalt, ledges and small sets. Ride when the school is closed.",
            {"Grounds": f"{A:.0f} m²"}, g, {"sub": "schoolyard"})
        continue
    if t.get("place") == "square" or hw == "pedestrian" or t.get("area:highway") == "pedestrian":
        L = glen(g); A = area(g) if (t.get("area") == "yes" or t.get("place") == "square" or t.get("area:highway")) else 0
        surf = t.get("surface")
        if surf and surf not in PAVED: continue
        add("plaza", el, nm or ("Square" if t.get("place") == "square" else "Pedestrian street"), c[0], c[1],
            3.5 if surf in ("asphalt", "concrete", "paving_stones") else 3,
            "Square or pedestrian street: often ledges, benches and low walls" + (", " + sv(surf) if surf else ""),
            {"Surface": sv(surf), "Size": f"{A:.0f} m²" if A else f"{L:.0f} m"}, g if el["type"] == "way" else None)
        continue
    if t.get("amenity") == "bench":
        add("ledge", el, sv(t.get("material")).capitalize() + " bench", c[0], c[1], 3, "Bench in a hard material: might work as a ledge. Check height and edge.",
            {"Material": sv(t.get("material"))}, None, {"sub": "bench"})
        continue
    if t.get("barrier") == "kerb":
        add("ledge", el, "Curb", c[0], c[1], 3, "Mapped curb" + (f" ({t.get('kerb')})" if t.get("kerb") else "") + ": check if it grinds",
            {"Type": t.get("kerb", "unknown")}, g if len(g) > 1 else None, {"sub": "curb"})
        continue
    if t.get("barrier") in ("guard_rail", "handrail"):
        add("rail", el, "Rail", c[0], c[1], 2.5, "Mapped rail: often tall or next to traffic. Check on site.", {"Length": f"{glen(g):.0f} m"}, g)
        continue
print("spots:", collections.Counter(s["k"] for s in out))

# ---------- paved path network ----------
paths = []
for el in base:
    t = el.get("tags", {}); hw = t.get("highway")
    if hw not in ("cycleway", "footway", "path", "pedestrian"): continue
    g = geom(el)
    if len(g) < 2: continue
    surf = t.get("surface"); sm = t.get("smoothness")
    paved = surf in PAVED or (surf is None and hw in ("cycleway", "pedestrian"))
    if surf == "sett": paved = False
    if not paved: continue
    q = 3 if surf in ("asphalt", "concrete") or sm in ("excellent", "good") else 2
    if sm == "intermediate": q = 2
    if sm in ("bad", "very_bad", "horrible"): q = 1
    if surf == "paving_stones": q = min(q, 2)
    paths.append({"g": g, "hw": hw, "q": q, "surf": surf, "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"]})
roads = []
for el in base:
    t = el.get("tags", {})
    if t.get("highway") in ("residential", "living_street") and t.get("surface", "asphalt") in PAVED:
        roads.append({"g": geom(el), "hw": t["highway"], "q": 0, "surf": t.get("surface"), "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"]})
print("paths", len(paths), "roads", len(roads))

# ---------- elevations ----------
def sample_points(g, step=30):
    pts = [g[0]]; acc = 0
    for i in range(len(g) - 1):
        a, b = g[i], g[i + 1]; d = dist(a, b); s = step - acc
        while s < d:
            f = s / d; pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)); s += step
        acc = (acc + d) % step
    pts.append(g[-1]); return pts
def ek(p): return f"{p[0]:.4f},{p[1]:.4f}"
cand = paths + roads
need = set()
for p in cand:
    p["sp"] = sample_points(p["g"])
    for q in p["sp"]:
        if ek(q) not in elev: need.add(ek(q))
need = sorted(need)
print("elevation points to fetch:", len(need), "cached:", len(elev), flush=True)
if need and "--no-fetch" not in sys.argv:
    for i in range(0, len(need), 100):
        chunk = need[i:i + 100]
        url = "https://api.opentopodata.org/v1/eudem25m?locations=" + "|".join(chunk)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "skatemap-local/1.0"}), timeout=60) as r:
                    res = json.load(r)
                for k, rr in zip(chunk, res["results"]): elev[k] = rr["elevation"]
                break
            except Exception as e:
                time.sleep(2 + attempt * 4)
        time.sleep(1.05)
        if i % 2000 == 0: json.dump(elev, open(CACHE, "w")); print("  fetched", i + len(chunk), "/", len(need), flush=True)
    json.dump(elev, open(CACHE, "w"))
def H(q):
    h = elev.get(ek(q))
    if h is not None: return h
    for dx in (-1, 0, 1):  # nearest cached point within ~11 m (older caches used other sample spots)
        for dy in (-1, 0, 1):
            h = elev.get(f"{q[0] + dx * 1e-4:.4f},{q[1] + dy * 1e-4:.4f}")
            if h is not None: return h
    return None

# ---------- hills ----------
hills = []
for p in cand:
    sp = p["sp"]; hs = [H(q) for q in sp]
    if any(h is None for h in hs) or len(sp) < 5: continue
    sm = [sum(hs[max(0, i - 1):i + 2]) / len(hs[max(0, i - 1):i + 2]) for i in range(len(hs))]
    cum = [0]
    for i in range(len(sp) - 1): cum.append(cum[-1] + dist(sp[i], sp[i + 1]))
    best = None
    for i in range(len(sp)):
        for j in range(i + 4, len(sp)):
            L = cum[j] - cum[i]
            if L < 100: continue
            if L > 700: break
            dh = sm[j] - sm[i]; gr = abs(dh) / L
            same = sum(1 for k in range(i, j) if (sm[k + 1] - sm[k]) * dh > 0) / (j - i)
            if 0.03 <= gr <= 0.12 and same >= 0.7 and abs(dh) >= 5:
                sc = L * min(gr, 0.08) * same
                if not best or sc > best[0]: best = (sc, i, j, L, dh, gr)
    if not best: continue
    sc, i, j, L, dh, gr = best
    seg = sp[i:j + 1]; prof = sm[i:j + 1]
    if dh > 0: seg = seg[::-1]; prof = prof[::-1]
    level = "mellow" if gr < 0.06 else ("solid" if gr < 0.09 else "steep")
    path_like = p["hw"] in ("cycleway", "footway", "path", "pedestrian")
    hills.append({"id": f"{REGION[:2]}h{p['id']}", "k": "hill", "n": p["name"] or ("Hill on bike path" if path_like else "Hill on residential street"),
                  "p": [round(seg[0][0], 5), round(seg[0][1], 5)], "g": r5(seg),
                  "s": 5 if (0.04 <= gr <= 0.075 and p["q"] >= 3 and L >= 150 and path_like) else (4 if (0.035 <= gr <= 0.09 and L >= 130) else 3),
                  "w": f"{L:.0f} m downhill, {abs(dh):.0f} m drop ({gr*100:.1f} %): {level}" + (" on smooth asphalt" if p["q"] >= 3 else "") + ("; car street, watch out" if not path_like else "; bike path, no cars" if p["hw"] == "cycleway" else ""),
                  "i": {"Length": f"{L:.0f} m", "Drop": f"{abs(dh):.0f} m", "Grade": f"{gr*100:.1f} %", "Surface": sv(p["surf"]) if p["surf"] else "asphalt (assumed)", "Lit": YN.get(p["lit"], "unknown")},
                  "osm": f"way/{p['id']}", "sub": level, "prof": [round(x - min(prof), 1) for x in prof]})
hills.sort(key=lambda h: -h["s"]); kept = []
for h in hills:
    if all(dist(h["p"], k["p"]) > 60 for k in kept): kept.append(h)
hills = kept
print("hills:", len(hills), collections.Counter(h["s"] for h in hills))

# ---------- street names for generic names ----------
grid = collections.defaultdict(list)
for el in base:
    t = el.get("tags", {})
    if t.get("highway") and t.get("name"):
        for q in geom(el): grid[(int(q[0] * 200), int(q[1] * 100))].append((q, t["name"]))
def street(p, maxd=120):
    best = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for q, nm in grid.get((int(p[0] * 200) + dx, int(p[1] * 100) + dy), []):
                d = dist(p, q)
                if d < maxd and (best is None or d < best[0]): best = (d, nm)
    return best[1] if best else None
GENERIC = {"Short stairs", "Long-tread stairs", "Stairs", "Court", "Basketball court", "Large car park", "Pedestrian street", "Square",
           "Hill on bike path", "Hill on residential street", "Curb", "Rail", "Skatepark", "Pump track"}
for s in out + hills:
    if s["n"] in GENERIC or s["n"].endswith(" bench"):
        st = street(s["p"])
        if st and st != s["n"]: s["n"] = f"{s['n']}, {st}"

# ---------- route graph ----------
nid, nodes, adj, E = {}, [], collections.defaultdict(list), []
def N(q):
    k = (round(q[0], 5), round(q[1], 5))
    if k not in nid:
        nid[k] = len(nodes); h = H(q); nodes.append([k[0], k[1], round(h, 1) if h is not None else None])
    return nid[k]
for p in cand:
    g = p["g"]; pen = {3: 1.0, 2: 1.6, 1: 3.0, 0: 2.4}[p["q"]]
    for i in range(len(g) - 1):
        a, b = N(g[i]), N(g[i + 1])
        if a == b: continue
        L = dist(g[i], g[i + 1]); E.append([a, b, round(L, 1), p["q"]])
        adj[a].append((b, L * pen, L)); adj[b].append((a, L * pen, L))
for _ in range(4):
    for i, n in enumerate(nodes):
        if n[2] is None:
            hs = [nodes[b][2] for b, _, _ in adj[i] if nodes[b][2] is not None]
            if hs: n[2] = round(sum(hs) / len(hs), 1)
ekey = {}
for a, b, L, q in E: ekey[(a, b)] = q; ekey[(b, a)] = q
print("graph:", len(nodes), "nodes", len(E), "edges")
ngrid = collections.defaultdict(list)
for i, n in enumerate(nodes): ngrid[(int(n[0] * 500), int(n[1] * 250))].append(i)
def nearest(p):
    for r in (1, 3, 8):
        best = None
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for i in ngrid.get((int(p[0] * 500) + dx, int(p[1] * 250) + dy), []):
                    d = dist(p, nodes[i])
                    if best is None or d < best[0]: best = (d, i)
        if best: return best[1]
def route(a, b):
    Dd = {a: 0}; prev = {}; pq = [(0, a)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b: break
        if d > Dd.get(u, 1e18): continue
        for v, c, _ in adj[u]:
            nd = d + c
            if nd < Dd.get(v, 1e18): Dd[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    if b not in prev: return None
    path = [b]
    while path[-1] != a: path.append(prev[path[-1]])
    return path[::-1]
top = lambda k, n: sorted([s for s in out if s["k"] == k], key=lambda s: -s["s"])[:n]
anchors = top("park", 30) + top("pump", 20) + top("plaza", 20) + [h for h in hills if h["s"] >= 5][:20] + top("steps", 20)
an_n = [(s, nearest(s["p"])) for s in anchors]
spotpts = [s for s in out if s["k"] in ("steps", "plaza", "ledge", "park", "pump")]
scored = []
for x in range(len(an_n)):
    for y in range(x + 1, len(an_n)):
        (sa, na), (sb, nb) = an_n[x], an_n[y]
        if not (1500 < dist(sa["p"], sb["p"]) < 5000): continue
        pth = route(na, nb)
        if not pth: continue
        L = good = road = climb = 0
        for i in range(len(pth) - 1):
            u, v = nodes[pth[i]], nodes[pth[i + 1]]; l = dist(u, v); q = ekey.get((pth[i], pth[i + 1]), 0)
            L += l; good += l if q >= 3 else 0; road += l if q == 0 else 0
            if u[2] is not None and v[2] is not None: climb += max(0, v[2] - u[2])
        if L < 2000 or L > 9000: continue
        samp = [nodes[n] for n in pth[::4]]
        nsp = sum(1 for s in spotpts if min(dist(s["p"], q) for q in samp) < 60)
        scored.append((good / L * 3 - road / L * 2 + nsp * 0.15, sa, sb, pth, L, climb, good, road, nsp))
scored.sort(key=lambda x: -x[0])
routes, used = [], []
def short(s): return s["n"].split(", ")[-1]
for sc, sa, sb, pth, L, climb, good, road, nsp in scored:
    mid = nodes[pth[len(pth) // 2]]
    if any(dist(mid, u) < 1200 for u in used): continue
    used.append(mid)
    hm = climb / (L / 1000); char = "flat and easy" if hm < 6 else ("a bit hilly" if hm < 12 else "hilly")
    prof = [nodes[n][2] for n in pth]; mn = min([h for h in prof if h is not None] or [0])
    routes.append({"id": f"{REGION[:2]}r{len(routes)}", "k": "route", "n": f"{short(sa)} → {short(sb)}", "p": [nodes[pth[0]][0], nodes[pth[0]][1]],
                   "g": [[nodes[n][0], nodes[n][1]] for n in pth], "prof": [round((h or mn) - mn, 1) for h in prof[::max(1, len(prof) // 80)]],
                   "s": 5 if good / L > 0.75 else (4 if good / L > 0.5 else 3),
                   "w": f"{L/1000:.1f} km, {good/L*100:.0f} % smooth asphalt bike path, {char}" + (f", {nsp} spots along the way" if nsp else "") + (f"; {road:.0f} m on residential streets" if road > 50 else ""),
                   "i": {"Length": f"{L/1000:.1f} km", "Climb": f"~{climb:.0f} m", "Smooth bike path": f"{good/L*100:.0f} %", "Residential street": f"{road:.0f} m", "Spots on the way": str(nsp)}, "osm": ""})
    if len(routes) >= 14: break
print("routes:", len(routes))

surf_layer = {"3": [], "2": [], "1": []}
for p in paths: surf_layer[str(p["q"])].append(r5(p["g"]))
data = {"name": REGION, "bbox": bbox, "surf": surf_layer, "spots": out + hills + routes, "graph": {"n": nodes, "e": E}, "built": time.strftime("%Y-%m-%d")}
os.makedirs(os.path.join(HERE, "web", "regions"), exist_ok=True)
s = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
open(os.path.join(HERE, "web", "regions", REGION + ".json"), "w").write(s)
print("regions/%s.json" % REGION, len(s) // 1024, "KB")
