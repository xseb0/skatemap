"""Finds flat, smooth, quiet-looking car roads on Madeira for inline skating (picked by hand afterwards in madeira.py).

Reads data/madeira/roads1..4.json (Overpass, q_roads1..4.txt: secondary, tertiary, unclassified, service, track
and roads named "Antiga"/"Velha") and the coastline from paths1..4.json.
Keeps road pieces that are at most 5 % steep over 100 m (terrain model, Mapterhorn zoom 13), skips tunnels,
private roads, driveways and unpaved surfaces, joins touching pieces and lists stretches of 800 m or more
with a rough traffic class. Writes data/madeira/roads_flat.json.
Run: python3 madeira_roads.py
"""
import glob, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data", "madeira")
os.environ.setdefault("DEM_Z", "13")
sys.path.insert(0, HERE); import dem

BAD = {"gravel", "fine_gravel", "dirt", "ground", "unpaved", "compacted", "grass", "sett", "cobblestone", "unhewn_cobblestone", "rock", "pebblestone", "earth", "mud", "sand"}
TRAFFIC = {"secondary": 3, "tertiary": 2, "unclassified": 1, "residential": 1, "service": 0, "track": 0, "living_street": 0}


def dist(a, b):
    x = (b[1] - a[1]) * math.cos(math.radians(a[0])) * 111320; y = (b[0] - a[0]) * 110540
    return math.hypot(x, y)


coast, ways, seen = [], [], set()
for f in sorted(glob.glob(os.path.join(D, "paths[0-9].json"))):
    for e in json.load(open(f))["elements"]:
        if e["tags"].get("natural") == "coastline": coast += [(p["lat"], p["lon"]) for p in e["geometry"][::3] if p]
for f in sorted(glob.glob(os.path.join(D, "roads[0-9].json"))):
    for e in json.load(open(f))["elements"]:
        if e["id"] in seen: continue
        seen.add(e["id"]); t = e["tags"]
        if t.get("tunnel") or t.get("access") in ("private", "no") or t.get("motor_vehicle") == "no" and t.get("foot") == "no": continue
        if t.get("surface") in BAD or t.get("smoothness") in ("bad", "very_bad", "horrible", "very_horrible", "impassable"): continue
        if t.get("service") in ("driveway", "parking_aisle", "drive-through"): continue
        if t.get("highway") == "track" and t.get("surface") not in ("asphalt", "concrete", "paved"): continue
        if t.get("highway") in ("motorway", "trunk", "primary", "footway", "path", "steps"): continue
        ways.append(e)
CG = {}
for p in coast: CG.setdefault((round(p[0], 2), round(p[1], 2)), []).append(p)
def to_sea(p):
    best = 9e9
    for dy in (-0.01, 0, 0.01):
        for dx in (-0.01, 0, 0.01):
            for q in CG.get((round(p[0] + dy, 2), round(p[1] + dx, 2)), []): best = min(best, dist(p, q))
    return best


def resample(g, step=20):
    out = [g[0]]
    for a, b in zip(g, g[1:]):
        d = dist(a, b); n = int(d // step)
        for i in range(1, n + 1): out.append((a[0] + (b[0] - a[0]) * i * step / d, a[1] + (b[1] - a[1]) * i * step / d))
        out.append(b)
    return out


pieces = []
for e in ways:
    g = [(p["lat"], p["lon"]) for p in e["geometry"] if p]
    if len(g) < 2: continue
    pts = resample(g)
    try: h = [dem.elevation(*p) for p in pts]
    except Exception: continue
    cum = [0]
    for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + dist(a, b))
    ok = []
    for i in range(len(pts)):
        lo, hi = i, i
        while lo > 0 and cum[i] - cum[lo] < 50: lo -= 1
        while hi < len(pts) - 1 and cum[hi] - cum[i] < 50: hi += 1
        span = cum[hi] - cum[lo]
        ok.append(span < 30 or abs(h[hi] - h[lo]) / span <= float(os.environ.get("MAXG", 0.05)))
    cur = []
    for p, k in zip(pts, ok):
        if k: cur.append(p)
        else:
            if len(cur) > 1: pieces.append((e, cur))
            cur = []
    if len(cur) > 1: pieces.append((e, cur))

ends = {}
for i, (e, g) in enumerate(pieces):
    for p in (g[0], g[-1]): ends.setdefault((round(p[0], 5), round(p[1], 5)), []).append(i)
par = list(range(len(pieces)))
def find(i):
    while par[i] != i: par[i] = par[par[i]]; i = par[i]
    return i
for ids in ends.values():
    for j in ids[1:]: par[find(j)] = find(ids[0])
groups = {}
for i in range(len(pieces)): groups.setdefault(find(i), []).append(i)

out = []
for ids in groups.values():
    segs = [pieces[i] for i in ids]
    L = sum(sum(dist(a, b) for a, b in zip(g, g[1:])) for _, g in segs)
    if L < int(os.environ.get("MINL", 800)): continue
    cls, names, surf = {}, {}, {}
    for e, g in segs:
        l = sum(dist(a, b) for a, b in zip(g, g[1:])); t = e["tags"]
        cls[t["highway"]] = cls.get(t["highway"], 0) + l
        surf[t.get("surface", "?") + ("/" + t["smoothness"] if t.get("smoothness") else "")] = surf.get(t.get("surface", "?"), 0) + l
        n = t.get("name") or t.get("ref")
        if n: names[n] = names.get(n, 0) + l
    allp = [p for _, g in segs for p in g]
    c = (sum(p[0] for p in allp) / len(allp), sum(p[1] for p in allp) / len(allp))
    traffic = sum(TRAFFIC.get(k, 1) * v for k, v in cls.items()) / L
    if any("antiga" in n.lower() or "velha" in n.lower() for n in names): traffic -= 1
    elev = dem.elevation(*c)
    out.append({"c": [round(c[0], 5), round(c[1], 5)], "len": round(L), "traffic": round(traffic, 1), "sea": round(min(to_sea(p) for p in allp[:: max(1, len(allp) // 30)])),
                "elev": round(elev), "names": sorted(names, key=lambda k: -names[k])[:4], "cls": {k: round(v) for k, v in cls.items()},
                "surf": {k: round(v) for k, v in sorted(surf.items(), key=lambda x: -x[1])[:3]}, "ways": sorted({e["id"] for e, _ in segs}),
                "lines": [[[round(p[0], 5), round(p[1], 5)] for p in g] for _, g in segs]})
out.sort(key=lambda x: -x["len"] / (1 + x["traffic"]))
json.dump(out, open(os.path.join(D, "roads_flat.json"), "w"), ensure_ascii=False)
for x in out[:60]:
    print(f'{x["len"]:5d}m traffic {x["traffic"]:4} sea {min(x["sea"], 99999):5d}m elev {x["elev"]:5d} {x["c"]} {x["names"]} {x["cls"]} {x["surf"]}')
