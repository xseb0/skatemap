"""Scans all of Madeira for skateable car-free stretches (inlines), for picking spots by hand in madeira.py.

Reads data/madeira/paths1..4.json (Overpass, q_paths*.txt: footways, cycleways, paths, coastline).
For every connected network of smooth paths it reports length, surface mix, distance to the sea,
steepness from the terrain model (Mapterhorn zoom 13, ~8 m per pixel) and sharp turns on steep parts.
Writes data/madeira/scan.json and prints the best candidates.
Run: python3 madeira_scan.py
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "madeira")
os.environ.setdefault("DEM_Z", "13")
sys.path.insert(0, HERE); import dem

SMOOTH = {"asphalt": 3, "concrete": 3, "concrete:plates": 2, "concrete:lanes": 3, "paved": 2, "paving_stones": 2, "tartan": 3, "acrylic": 3}
GOOD_SM = {"excellent", "good"}


def dist(a, b):
    x = (b[1] - a[1]) * math.cos(math.radians(a[0])) * 111320; y = (b[0] - a[0]) * 110540
    return math.hypot(x, y)


def quality(t):
    """3 = smooth, 2 = okay, 0 = not for inlines."""
    s, sm = t.get("surface"), t.get("smoothness")
    if sm in ("bad", "very_bad", "horrible", "very_horrible", "impassable"): return 0
    if t.get("access") == "no" or t.get("foot") == "no": return 0
    q = SMOOTH.get(s, 0)
    if s == "paving_stones": q = 2 if sm in GOOD_SM else 1  # pavers: joints, only "okay" when tagged good
    if q and sm == "excellent": q = 3
    return q


ways, coast, seen = [], [], set()
for f in sorted(glob.glob(os.path.join(D, "paths[0-9].json"))):
    for e in json.load(open(f))["elements"]:
        if e["id"] in seen: continue
        seen.add(e["id"])
        g = [(p["lat"], p["lon"]) for p in e.get("geometry", []) if p]
        if e["tags"].get("natural") == "coastline": coast += g[::3]
        elif e["tags"].get("highway"): ways.append((e, g))

# coast lookup grid (~1 km cells)
CG = {}
for p in coast: CG.setdefault((round(p[0], 2), round(p[1], 2)), []).append(p)
def to_sea(p):
    best = 9e9
    for dy in (-0.01, 0, 0.01):
        for dx in (-0.01, 0, 0.01):
            for q in CG.get((round(p[0] + dy, 2), round(p[1] + dx, 2)), []): best = min(best, dist(p, q))
    return best

# connected networks of usable paths
adj, info = {}, {}
for e, g in ways:
    q = quality(e["tags"])
    if q < 2 or len(g) < 2: continue
    info[e["id"]] = (e, g, q)
    for p in (g[0], g[-1]): adj.setdefault((round(p[0], 6), round(p[1], 6)), []).append(e["id"])
# join ways sharing any node (not just ends)
node_ways = {}
for wid, (e, g, q) in info.items():
    for p in g: node_ways.setdefault((round(p[0], 6), round(p[1], 6)), set()).add(wid)
parent = {w: w for w in info}
def find(w):
    while parent[w] != w: parent[w] = parent[parent[w]]; w = parent[w]
    return w
for ws in node_ways.values():
    ws = list(ws)
    for w in ws[1:]: parent[find(w)] = find(ws[0])
groups = {}
for w in info: groups.setdefault(find(w), []).append(w)


def resample(g, step=15):
    out = [g[0]]
    for a, b in zip(g, g[1:]):
        d = dist(a, b); n = int(d // step)
        for i in range(1, n + 1): t = i * step / d; out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        out.append(b)
    return out


def hill_check(g):
    """Max grade over 60 m, climb, and sharp turns (>60° within 30 m) where the grade is over 7 %."""
    pts = resample(g, 15)
    if len(pts) < 3: return 0, 0, 0
    try: h = [dem.elevation(*p) for p in pts]
    except Exception: return None, None, None
    cum = [0]
    for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + dist(a, b))
    grades = []
    j = 0
    for i in range(len(pts)):
        while j < len(pts) - 1 and cum[j] - cum[i] < 60: j += 1
        if cum[j] - cum[i] >= 40: grades.append((i, abs(h[j] - h[i]) / (cum[j] - cum[i])))
    gmax = max((x[1] for x in grades), default=0)
    climb = sum(max(0, b - a) for a, b in zip(h, h[1:]))
    steep_i = {i for i, gr in grades if gr > 0.07}
    sharp = 0
    for i in range(2, len(pts) - 2):
        if i not in steep_i: continue
        hd = lambda a, b: math.degrees(math.atan2((b[1] - a[1]) * math.cos(math.radians(a[0])), b[0] - a[0]))
        turn = abs((hd(pts[i - 2], pts[i]) - hd(pts[i], pts[i + 2]) + 180) % 360 - 180)
        if turn > 60: sharp += 1
    return round(gmax * 100, 1), round(climb), sharp


cands = []
for root, ws in groups.items():
    segs = [info[w] for w in ws]
    L = sum(sum(dist(a, b) for a, b in zip(g, g[1:])) for _, g, _ in segs)
    if L < 350: continue
    surf, names = {}, {}
    for e, g, q in segs:
        l = sum(dist(a, b) for a, b in zip(g, g[1:]))
        s = e["tags"].get("surface", "?"); surf[s] = surf.get(s, 0) + l
        n = e["tags"].get("name")
        if n: names[n] = names.get(n, 0) + l
    smooth = sum(sum(dist(a, b) for a, b in zip(g, g[1:])) for _, g, q in segs if q == 3)
    allp = [p for _, g, _ in segs for p in g]
    c = (sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp))
    sea = min(to_sea(p) for p in allp[:: max(1, len(allp) // 40)])
    gmax = climb = sharp = 0
    for _, g, _ in segs:
        a, b, s = hill_check(g)
        if a is None: continue
        gmax = max(gmax, a); climb += b; sharp += s
    cands.append({"c": [round(c[0], 5), round(c[1], 5)], "len": round(L), "smooth": round(smooth), "sea": round(sea),
                  "gmax": gmax, "climb": climb, "sharp": sharp, "names": sorted(names, key=lambda k: -names[k])[:3],
                  "surf": {k: round(v) for k, v in sorted(surf.items(), key=lambda x: -x[1])},
                  "ways": ws, "bbox": [min(p[0] for p in allp), min(p[1] for p in allp), max(p[0] for p in allp), max(p[1] for p in allp)]})

cands.sort(key=lambda x: -(x["smooth"] + 0.5 * (x["len"] - x["smooth"])))
json.dump(cands, open(os.path.join(D, "scan.json"), "w"), ensure_ascii=False)
for x in cands[:0]:
    print(f'{x["len"]:5d}m smooth {x["smooth"]:5d} sea {x["sea"]:5d}m grade {x["gmax"]:4}% climb {x["climb"]:4}m sharp {x["sharp"]:2} {x["c"]} {x["names"]} {x["surf"]}')


# ---------- pass 2: flat pieces only (inlines), no levada/vereda/alley paths ----------
SKIP = ("levada", "vereda", "beco", "escad", "caminho", "travessa", "azinhaga", "rampa")
flat_pieces = []
for e, g in ways:
    q = quality(e["tags"]); n = (e["tags"].get("name") or "").lower()
    if q < 2 or len(g) < 2 or any(k in n for k in SKIP): continue
    if e["tags"].get("highway") == "path" and e["tags"].get("surface") not in ("asphalt", "concrete"): continue
    pts = resample(g, 15)
    try: h = [dem.elevation(*p) for p in pts]
    except Exception: continue
    cur = [pts[0]]
    for i in range(1, len(pts)):
        d = dist(pts[i - 1], pts[i]) or 1
        lo, hi = max(0, i - 3), min(len(pts) - 1, i + 2)  # ~75 m window against DEM noise
        span = sum(dist(pts[k], pts[k + 1]) for k in range(lo, hi)) or 1
        if abs(h[hi] - h[lo]) / span <= 0.06: cur.append(pts[i])
        else:
            if len(cur) > 1: flat_pieces.append((e, cur, q))
            cur = [pts[i]]
    if len(cur) > 1: flat_pieces.append((e, cur, q))

nodes2 = {}
for i, (e, g, q) in enumerate(flat_pieces):
    for p in (g[0], g[-1]): nodes2.setdefault((round(p[0], 5), round(p[1], 5)), []).append(i)
par2 = list(range(len(flat_pieces)))
def f2(i):
    while par2[i] != i: par2[i] = par2[par2[i]]; i = par2[i]
    return i
for ids in nodes2.values():
    for j in ids[1:]: par2[f2(j)] = f2(ids[0])
grp2 = {}
for i in range(len(flat_pieces)): grp2.setdefault(f2(i), []).append(i)
flat = []
for ids in grp2.values():
    segs = [flat_pieces[i] for i in ids]
    L = sum(sum(dist(a, b) for a, b in zip(g, g[1:])) for _, g, _ in segs)
    if L < 300: continue
    surf, names, hw = {}, {}, {}
    for e, g, q in segs:
        l = sum(dist(a, b) for a, b in zip(g, g[1:]))
        s = e["tags"].get("surface", "?") + ("/" + e["tags"]["smoothness"] if e["tags"].get("smoothness") else ""); surf[s] = surf.get(s, 0) + l
        hw[e["tags"]["highway"]] = hw.get(e["tags"]["highway"], 0) + l
        if e["tags"].get("name"): names[e["tags"]["name"]] = names.get(e["tags"]["name"], 0) + l
    allp = [p for _, g, _ in segs for p in g]
    c = (sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp))
    sea = min(to_sea(p) for p in allp[:: max(1, len(allp) // 40)])
    smooth = sum(sum(dist(a, b) for a, b in zip(g, g[1:])) for _, g, q in segs if q == 3)
    flat.append({"c": [round(c[0], 5), round(c[1], 5)], "len": round(L), "smooth": round(smooth), "sea": round(sea), "names": sorted(names, key=lambda k: -names[k])[:3],
                 "surf": {k: round(v) for k, v in sorted(surf.items(), key=lambda x: -x[1])}, "hw": {k: round(v) for k, v in hw.items()},
                 "ways": sorted({e["id"] for e, _, _ in segs}), "lines": [[[round(p[0], 5), round(p[1], 5)] for p in g] for _, g, _ in segs]})
flat.sort(key=lambda x: -(x["smooth"] + 0.6 * (x["len"] - x["smooth"])))
json.dump(flat, open(os.path.join(D, "flat.json"), "w"), ensure_ascii=False)
print("\n--- flat (<=6 %) stretches ---")
for x in flat[:50]:
    print(f'{x["len"]:5d}m smooth {x["smooth"]:5d} sea {min(x["sea"], 99999):5d}m {x["c"]} {x["names"]} {x["surf"]} {x["hw"]}')
