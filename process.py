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
def load_all(names):
    """Merges Overpass answers (main area + any extra strips like spots2.json), without duplicates."""
    out_, ids = [], set()
    for nm in names:
        fp = os.path.join(D, nm)
        if not os.path.exists(fp): continue
        for e in json.load(open(fp))["elements"]:
            if (e["type"], e["id"]) in ids: continue
            ids.add((e["type"], e["id"])); out_.append(e)
    return out_
spots = load_all(["spots.json", "extra.json", "spots2.json", "extra2.json"])
base = load_all(["base.json", "base2.json"])
_bbs = [[float(x) for x in open(os.path.join(D, q)).read().split('"skateboard|roller|bmx|pump"](')[1].split(")")[0].split(",")]
        for q in ("q_spots.txt", "q2_spots.txt") if os.path.exists(os.path.join(D, q))]
bbox = [min(b[0] for b in _bbs), min(b[1] for b in _bbs), max(b[2] for b in _bbs), max(b[3] for b in _bbs)]
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
BAD = {"gravel", "fine_gravel", "compacted", "dirt", "ground", "earth", "grass", "sand", "unpaved", "mud", "pebblestone", "woodchips",
       "wood", "sett", "cobblestone", "unhewn_cobblestone", "grass_paver", "rock", "stepping_stones"}
BAD_SMOOTH = {"bad", "very_bad", "horrible", "very_horrible", "impassable"}
def bad(t): return t.get("surface") in BAD or t.get("smoothness") in BAD_SMOOTH
def surf_cat(s):
    if s in ("asphalt",): return "asphalt"
    if s in ("concrete", "concrete:plates", "concrete:lanes"): return "concrete"
    if s in ("acrylic", "tartan", "rubber"): return "court surface"
    if s in ("paving_stones", "stone", "granite"): return "paving stones"
    if s in ("paved",): return "paved"
    return "unknown"
# which ways meet at each node (for checking what surrounds a stair set)
NODE = collections.defaultdict(list)
for el in base:
    t = el.get("tags", {})
    if el["type"] != "way" or not t.get("highway") or t.get("highway") == "steps": continue
    for p in el.get("geometry", []) or []:
        if p: NODE[(round(p["lat"], 6), round(p["lon"], 6))].append(t)
def end_ok(pt):
    ts = NODE.get((round(pt[0], 6), round(pt[1], 6)), [])
    if not ts: return None  # nothing mapped there
    if any(not bad(t) and (t.get("surface") in PAVED or t.get("highway") not in ("footway", "path", "track", "bridleway")) for t in ts): return True
    if all(bad(t) for t in ts): return False  # only gravel, dirt etc. here
    return None

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
    # outdoor ice rinks (ice in winter, flat ground the rest of the year)
    ice = t.get("leisure") == "ice_rink" or (t.get("leisure") == "pitch" and re.search(r"ice_hockey|ice_skating|ice-skating|bandy", sport))
    if ice:
        if t.get("indoor") == "yes" or t.get("building") in ("sports_hall", "sports_centre") or t.get("leisure") == "sports_hall" or t.get("surface") in ("grass", "artificial_turf", "gravel", "dirt", "sand"): continue
        roofed = t.get("building") not in (None, "no")
        add("rink", el, nm or ("Covered ice rink" if roofed else "Outdoor ice rink"), c[0], c[1], 5 if roofed else 4,
            ("Rink with a roof: ice in winter, and often a dry, smooth surface with boards the rest of the year. " if roofed else "Ice rink in winter. The rest of the year it is usually a flat open surface, often with boards. ") + "Check what it is out of season.",
            {"Surface": sv(t.get("surface")), "Seasonal": t.get("seasonal", "unknown"), "Sports": sport.replace(";", ", ") or "skating"},
            g if el["type"] == "way" else None, {"f": {"su": surf_cat(t.get("surface"))}})
        continue
    bmx_track = t.get("leisure") == "track" and (re.search(r"bmx", sport + " " + nm, re.I) or re.search(r"skateboard|roller", sport))
    sp_ok = re.search(r"skateboard|bmx|pump|roller_skating|^roller$", sport) and "roller_ski" not in sport
    nm_ok = re.search(r"pump ?track|pumpbana|skate ?park|skateboard|skatepool|skateboardpool|kickbike|\bbmx\b", nm, re.I) and not hw and t.get("amenity") not in ("compressed_air", "bicycle_repair_station", "fuel") and not t.get("shop")
    if sp_ok or nm_ok or bmx_track:
        if t.get("access") == "private" or t.get("shop") or (t.get("opening_hours") and not t.get("leisure")): continue
        indoor = t.get("indoor") == "yes" or (t.get("building") not in (None, "no", "roof"))
        kind = "pump" if re.search(r"bmx|pump|kick", sport + " " + nm, re.I) and not re.search(r"skate", nm, re.I) else "park"
        info = {"Surface": sv(t.get("surface")), "Lit": YN.get(t.get("lit"), "unknown")}
        if indoor: info["Indoor"] = "yes"
        if t.get("operator"): info["Operator"] = t["operator"]
        dirt = t.get("surface") in ("ground", "earth", "dirt", "compacted", "gravel")
        if bmx_track and kind == "park": kind = "pump"
        add(kind, el, nm or ("BMX track" if bmx_track else "Pump track" if kind == "pump" else "Skatepark"), c[0], c[1], 5,
            "Built for riding" + (" (indoors)" if indoor else "") + (", dirt surface: BMX bikes, not skateboards" if dirt else "") + (", lit at night" if t.get("lit") == "yes" else ""),
            info, g if el["type"] == "way" else None, {"f": {"indoor": indoor, "dirt": dirt}})
        continue
    if hw == "steps":
        if bad(t) or t.get("surface") == "metal": continue
        ends = [end_ok(g[0]), end_ok(g[-1])]
        if False in ends: continue  # gravel or dirt at the top or bottom: can't roll in or land
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
        if None in ends: why.append("ground at one end not mapped, check it")
        else: why.append("paved at both ends")
        rail = t.get("handrail") in ("yes", "both", "left", "right")
        add("steps", el, nm or {"short": "Short stairs", "long": "Long-tread stairs", "stairs": "Stairs"}[sub], c[0], c[1], score, "; ".join(why), info, g,
            {"sub": sub, "f": {"n": n, "tr": round(tread * 100) if tread else None, "rail": rail, "su": surf_cat(t.get("surface")), "ends": None not in ends}})
        continue
    if t.get("leisure") == "pitch":
        surf = t.get("surface")
        if surf and surf not in PAVED | {"acrylic", "tartan", "rubber"} or bad(t): continue
        A = area(g)
        add("flat", el, nm or ("Basketball court" if "basket" in sport else "Court"), c[0], c[1], 4 if surf in ("asphalt", "concrete", "acrylic") else 3,
            "Smooth, flat and open: good for powerslides, manuals and flatground" + ("" if surf else " (surface not mapped)"),
            {"Sport": sport.replace(";", ", "), "Surface": sv(surf), "Area": f"{A:.0f} m²" if A else "unknown"}, g if el["type"] == "way" else None, {"sub": "court", "f": {"su": surf_cat(surf), "sport": sport}})
        continue
    if t.get("amenity") == "parking":
        A = area(g); surf = t.get("surface")
        if A < 1800 or (surf and surf not in PAVED) or bad(t): continue
        if t.get("access") in ("private", "customers") and A < 4000: continue
        info = {"Area": f"{A:.0f} m²", "Surface": sv(surf)}
        if t.get("access"): info["Access"] = t["access"]
        add("flat", el, nm or "Large car park", c[0], c[1], 3 + (1 if A > 5000 else 0) + (0.5 if surf == "asphalt" else 0),
            f"Big open lot ({A:.0f} m²) for powerslides and flatground when it is empty, e.g. evenings and weekends",
            info, g if el["type"] == "way" else None, {"sub": "parking", "f": {"su": surf_cat(surf)}})
        continue
    if t.get("amenity") == "school":
        A = area(g)
        if el["type"] == "node" or A < 2000: continue
        add("flat", el, nm or "School", c[0], c[1], 3, "Schoolyards often have asphalt, ledges and small sets. Ride when the school is closed.",
            {"Grounds": f"{A:.0f} m²"}, g, {"sub": "schoolyard", "f": {"su": "unknown"}})
        continue
    if t.get("place") == "square" or hw == "pedestrian" or t.get("area:highway") == "pedestrian":
        L = glen(g); A = area(g) if (t.get("area") == "yes" or t.get("place") == "square" or t.get("area:highway")) else 0
        surf = t.get("surface")
        if (surf and surf not in PAVED) or bad(t): continue
        smooth = surf in ("asphalt", "concrete")
        big = A >= 800
        sc = 5 if (smooth and big) else 4 if (smooth and A >= 250) or surf == "paving_stones" and big else 3
        add("plaza", el, nm or ("Square" if t.get("place") == "square" else "Pedestrian street"), c[0], c[1], sc,
            (f"Big open {sv(surf)} plaza ({A:.0f} m²): smooth ground for flatground, manuals and powerslides" if smooth and big else
             "Square or pedestrian street: often ledges, benches and low walls" + (", " + sv(surf) if surf else "")),
            {"Surface": sv(surf), "Size": f"{A:.0f} m²" if A else f"{L:.0f} m"}, g if el["type"] == "way" else None, {"sub": "smoothplaza" if (smooth and big) else None, "f": {"su": surf_cat(surf), "area": round(A)}})
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
if os.path.exists(os.path.join(D, "curated.json")):
    out += json.load(open(os.path.join(D, "curated.json")))
if os.path.exists(os.path.join(D, "city.json")):  # Stockholm city's own lists (ice rinks, skateparks)
    s_, w_, n_, e_ = bbox
    for c in json.load(open(os.path.join(D, "city.json"))):
        if not (s_ - .01 < c["p"][0] < n_ + .01 and w_ - .02 < c["p"][1] < e_ + .02): continue
        twin = next((o for o in out if o["k"] in ("park", "pump", "rink") and dist(o["p"], c["p"]) < 150 and (o["k"] == c["k"] or {o["k"], c["k"]} <= {"park", "pump"})), None)
        if twin:
            twin.setdefault("url", c.get("url"))
            if twin["n"] in ("Skatepark", "Pump track", "BMX track", "Outdoor ice rink") or twin["n"].startswith(("Skatepark, ", "Pump track, ", "Outdoor ice rink")): twin["n"] = c["n"]
            continue
        out.append(c)
# Trucks & Fins (trucksandfins.com) skatepark directory for Sweden: names, positions and features, linked back to the source
TF = os.path.join(HERE, "data", "trucksandfins_se.json")
if os.path.exists(TF):
    s_, w_, n_, e_ = bbox; FEAT = {"bowl": "bowl", "concrete": "concrete park", "diy": "DIY", "indoor": "indoor / sheltered", "pump": "pump track", "street": "street spot"}
    for t in json.load(open(TF)):
        p_ = [round(t["lat"], 6), round(t["lon"], 6)]
        if not (s_ - .01 < p_[0] < n_ + .01 and w_ - .02 < p_[1] < e_ + .02) or "rip" in t["tags"]: continue
        kind = "pump" if ("pump" in t["tags"] or re.search(r"pump|bmx", t["n"], re.I)) else "park"
        twin = next((o for o in out if o["k"] in ("park", "pump") and dist(o["p"], p_) < 150), None)
        feats = ", ".join(FEAT[x] for x in t["tags"] if x in FEAT)
        if twin:
            twin["tf"] = t["url"]
            if feats: twin.setdefault("i", {})["Features"] = feats
            if twin["n"] in ("Skatepark", "Pump track") or twin["n"].startswith(("Skatepark, ", "Pump track, ")): twin["n"] = t["n"]
            continue
        out.append({"id": "tf-" + t["url"].rstrip("/").split("/")[-1], "k": kind, "n": t["n"], "p": p_, "s": 5,
                    "w": ("Street spot" if "street" in t["tags"] else "DIY spot" if "diy" in t["tags"] else "Built for riding") + (f" ({feats})" if feats else "") + ". Listed on Trucks & Fins.",
                    "i": {"Features": feats or "not listed", "Source": "trucksandfins.com"}, "osm": "", "tf": t["url"], "f": {"indoor": "indoor" in t["tags"]}})
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
    if sm in BAD_SMOOTH: continue
    if surf == "paving_stones": q = min(q, 2)
    paths.append({"g": g, "hw": hw, "q": q, "surf": surf, "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"]})
roads = []
for el in base:
    t = el.get("tags", {})
    hw = t.get("highway")
    if hw in ("residential", "living_street", "unclassified") and t.get("surface", "asphalt") in PAVED and not bad(t) and t.get("surface") != "sett":
        roads.append({"g": geom(el), "hw": hw, "q": 0, "surf": t.get("surface"), "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"]})
    elif hw in ("service", "track") and t.get("surface") in ("asphalt", "concrete", "paved") and not bad(t) and t.get("service") not in ("driveway", "parking_aisle", "drive-through") and t.get("access") not in ("private", "no"):
        roads.append({"g": geom(el), "hw": hw, "q": 2, "surf": t.get("surface"), "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"]})
    elif hw == "service" and not t.get("surface") and t.get("service") not in ("driveway", "parking_aisle", "drive-through") and t.get("access") not in ("private", "no"):
        # lanes in housing areas are nearly always asphalt but often lack a surface tag
        roads.append({"g": geom(el), "hw": hw, "q": 2, "surf": None, "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"], "unk": True})
unknown_paths = []  # footpaths with no surface tag: only used to find hills, flagged so they can be filtered out
for el in base:
    t = el.get("tags", {})
    if t.get("highway") in ("footway", "path") and not t.get("surface") and not bad(t) and t.get("access") not in ("private", "no"):
        g = geom(el)
        if len(g) >= 2: unknown_paths.append({"g": g, "hw": t["highway"], "q": 1, "surf": None, "lit": t.get("lit"), "name": t.get("name", ""), "id": el["id"], "unk": True})
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
BRIDGE = {el["id"] for el in base if el.get("tags", {}).get("bridge") not in (None, "no") or el.get("tags", {}).get("tunnel") not in (None, "no") or el.get("tags", {}).get("layer", "0") not in ("0",)}
# join pieces of the same named street/path end to end, so a long hill split into several OSM ways is seen as one
def chain_named(items):
    groups = collections.defaultdict(list)
    for it in items:
        if it["name"]: groups[(it["name"], it["hw"])].append(it)
    joined = []
    for key, its in groups.items():
        if len(its) < 2: continue
        segs = [list(it["g"]) for it in its]
        while segs:
            line = segs.pop(0); grew = True
            while grew:
                grew = False
                for i, s in enumerate(segs):
                    k = lambda p: (round(p[0], 6), round(p[1], 6))
                    if k(s[0]) == k(line[-1]): line += s[1:]
                    elif k(s[-1]) == k(line[-1]): line += s[::-1][1:]
                    elif k(s[-1]) == k(line[0]): line = s[:-1] + line
                    elif k(s[0]) == k(line[0]): line = s[::-1][:-1] + line
                    else: continue
                    segs.pop(i); grew = True; break
            if len(line) > max(len(it["g"]) for it in its) - 1 and glen(line) > 150:
                base_it = its[0]
                joined.append(dict(base_it, g=line, id=f"{base_it['id']}j{len(joined)}", joined=True))
    return joined
hill_extra = chain_named([c for c in cand if c["id"] not in BRIDGE])
print("joined named lines:", len(hill_extra))
USE_DEM = "--eudem" not in sys.argv  # default: Mapterhorn ~1.2 m terrain tiles; --eudem = old 25 m API data
if USE_DEM:
    sys.path.insert(0, HERE); import dem
    _hm = {}
    def H(q):
        k = (round(q[0], 5), round(q[1], 5))
        if k not in _hm:
            try: _hm[k] = dem.elevation(*k)
            except Exception as ex: print("  dem tile failed", k, ex); _hm[k] = None
        return _hm[k]
    for p in cand + hill_extra + unknown_paths: p["sp"] = sample_points(p["g"], 10)
    _tiles = {dem.tile_of(q[0], q[1])[:2] for p in cand + hill_extra + unknown_paths for q in p["sp"]}
    print("terrain tiles needed:", len(_tiles), "cached:", sum(1 for t in _tiles if os.path.exists(os.path.join(dem.CACHE, f"{dem.Z}_{t[0]}_{t[1]}.png"))), flush=True)
else:
    need = set()
    for p in cand + hill_extra + unknown_paths:
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
        json.dump(elev, open(CACHE, "w"))
    def H(q):
        h = elev.get(ek(q))
        if h is not None: return h
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                h = elev.get(f"{q[0] + dx * 1e-4:.4f},{q[1] + dy * 1e-4:.4f}")
                if h is not None: return h
        return None

# ---------- hills ----------
hills = []
for p in hill_extra + cand + unknown_paths:
    if p["id"] in BRIDGE: continue
    sp = p["sp"]; hs = [H(q) for q in sp]
    if any(h is None for h in hs) or len(sp) < 5: continue
    sm = [sum(hs[max(0, i - 1):i + 2]) / len(hs[max(0, i - 1):i + 2]) for i in range(len(hs))]
    cum = [0]
    for i in range(len(sp) - 1): cum.append(cum[-1] + dist(sp[i], sp[i + 1]))
    dn = [0]; up = [0]  # running counts of falling / rising steps, so "how steady is the slope" is O(1)
    for k in range(len(sm) - 1): dn.append(dn[-1] + (sm[k + 1] < sm[k])); up.append(up[-1] + (sm[k + 1] > sm[k]))
    MINL = 50 if USE_DEM else 100; MINDH = 3 if USE_DEM else 5; MAXG = 0.18 if USE_DEM else 0.12
    best = None
    for i in range(len(sp)):
        for j in range(i + 4, len(sp)):
            L = cum[j] - cum[i]
            if L < MINL: continue
            if L > 1500: break
            dh = sm[j] - sm[i]; gr = abs(dh) / L
            same = ((dn[j] - dn[i]) if dh < 0 else (up[j] - up[i])) / (j - i)
            if 0.03 <= gr <= MAXG and same >= 0.7 and abs(dh) >= MINDH:
                sc = L * min(gr, 0.09) * same
                if not best or sc > best[0]: best = (sc, i, j, L, dh, gr)
    if not best: continue
    sc, i, j, L, dh, gr = best
    seg = sp[i:j + 1]; prof = sm[i:j + 1]
    if dh > 0: seg = seg[::-1]; prof = prof[::-1]
    level = "gentle" if gr < 0.04 else "mellow" if gr < 0.06 else "solid" if gr < 0.09 else "steep" if gr < 0.13 else "very steep"
    path_like = p["hw"] in ("cycleway", "footway", "path", "pedestrian", "service", "track")
    hills.append({"id": f"{REGION[:2]}h{p['id']}", "k": "hill", "n": p["name"] or {"cycleway": "Hill on bike path", "footway": "Hill on footpath", "path": "Hill on footpath", "pedestrian": "Hill on footpath", "service": "Hill on quiet road", "track": "Hill on quiet road"}.get(p["hw"], "Hill on street"),
                  "p": [round(seg[0][0], 5), round(seg[0][1], 5)], "g": r5(seg),
                  "s": 5 if ((0.04 <= gr <= 0.10 and L >= 120) or (gr >= 0.03 and L >= 300)) and (p["q"] >= 3 or p["surf"] == "asphalt") else (4 if (0.035 <= gr <= 0.13 and L >= 70) or (gr >= 0.03 and L >= 200) else 3),
                  "w": f"{L:.0f} m downhill, {abs(dh):.0f} m drop ({gr*100:.1f} %): {level}" + (" on smooth asphalt" if (p["q"] >= 3 or p["surf"] == "asphalt") else "") + {"cycleway": "; bike path, no cars", "service": "; quiet service road", "track": "; quiet paved track", "unclassified": "; minor road, some cars", "residential": "; residential street, watch for cars", "living_street": "; residential street, watch for cars"}.get(p["hw"], ""),
                  "f": {"lv": level, "cf": p["hw"] in ("cycleway", "footway", "path", "pedestrian", "service", "track"), "su": "unknown" if p.get("unk") else surf_cat(p["surf"] or "asphalt")},
                  "i": {"Length": f"{L:.0f} m", "Drop": f"{abs(dh):.0f} m", "Grade": f"{gr*100:.1f} %", "Surface": sv(p["surf"]) if p["surf"] else ("not mapped, check it" if p.get("unk") else "asphalt (assumed)"), "Lit": YN.get(p["lit"], "unknown")},
                  "osm": f"way/{p['id']}", "sub": level, "prof": [round(x - min(prof), 1) for x in prof[::max(1, len(prof) // 80)]]})
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
           "Hill on bike path", "Hill on footpath", "Hill on quiet road", "Hill on street", "Curb", "Rail", "Skatepark", "Pump track"}
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
# connected components, so routes never start on a tiny isolated piece of path
comp = [-1] * len(nodes); csize = []
for s0 in range(len(nodes)):
    if comp[s0] >= 0: continue
    cid = len(csize); stack = [s0]; comp[s0] = cid; n_ = 0
    while stack:
        u = stack.pop(); n_ += 1
        for v, _, _ in adj[u]:
            if comp[v] < 0: comp[v] = cid; stack.append(v)
    csize.append(n_)
BIG = 2000  # nodes; the main network
ngrid = collections.defaultdict(list)
for i, n in enumerate(nodes):
    if csize[comp[i]] >= BIG: ngrid[(int(n[0] * 500), int(n[1] * 250))].append(i)
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
def short(s):
    n = s["n"].split(", ")[-1]
    if n in GENERIC: n = street(s["p"], 250) or n.lower()
    return n
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
HUBS = json.load(open(os.path.join(D, "hubs.json"))) if os.path.exists(os.path.join(D, "hubs.json")) else {"hubs": [], "places": []}
def stats(pth):
    L = good = road = climb = 0
    for i in range(len(pth) - 1):
        u, v = nodes[pth[i]], nodes[pth[i + 1]]; l = dist(u, v); q = ekey.get((pth[i], pth[i + 1]), 0)
        L += l; good += l if q >= 3 else 0; road += l if q == 0 else 0
        if u[2] is not None and v[2] is not None: climb += max(0, v[2] - u[2])
    return L, good, road, climb
def route_avoid(a, b, avoid):
    Dd = {a: 0}; prev = {}; pq = [(0, a)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == b: break
        if d > Dd.get(u, 1e18): continue
        for v, c, _ in adj[u]:
            nd = d + c * (5 if (u, v) in avoid else 1)
            if nd < Dd.get(v, 1e18): Dd[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    if b not in prev: return None
    path = [b]
    while path[-1] != a: path.append(prev[path[-1]])
    return path[::-1]
dests = [a for a in anchors if not (a.get("f") or {}).get("dirt")] + [{"n": n, "p": [la, lo], "k": "place"} for n, la, lo in HUBS["places"]] + [h for h in hills if h["s"] >= 4][:150]
for hub, hla, hlo in HUBS["hubs"]:
    hn = nearest([hla, hlo]); cands = []
    for d in dests:
        cd = dist([hla, hlo], d["p"])
        if not (600 < cd < 3500): continue
        dn = nearest(d["p"])
        out_p = route(hn, dn)
        if not out_p: continue
        used_e = {(out_p[i], out_p[i + 1]) for i in range(len(out_p) - 1)} | {(out_p[i + 1], out_p[i]) for i in range(len(out_p) - 1)}
        back = route_avoid(dn, hn, used_e)
        if not back: continue
        loop = out_p + back[1:]
        L, good, road, climb = stats(loop)
        if L < 2500 or L > 12000: continue
        back_e = {(back[i], back[i + 1]) for i in range(len(back) - 1)}
        overlap = sum(dist(nodes[a], nodes[b]) for a, b in back_e if (a, b) in used_e) / max(1, stats(back)[0])
        samp = [nodes[n] for n in loop[::4]]
        nsp = sum(1 for s in spotpts if min(dist(s["p"], q) for q in samp) < 60)
        bonus = 2 if d.get("k") == "place" else (0.6 if d.get("k") in ("park", "pump") else 0)
        cands.append((good / L * 3 - road / L * 2 - overlap * 1.5 + min(nsp, 20) * 0.06 + bonus - abs(L / 1000 - 6) * 0.12, d, loop, L, climb, good, road, nsp, overlap, len(out_p)))
    print("hub", hub, "loop candidates", len(cands))
    cands.sort(key=lambda x: -x[0]); mids = []; kept_n = 0
    for sc, d, loop, L, climb, good, road, nsp, overlap, turn in cands:
        mid = nodes[loop[turn - 1]]
        if any(dist(mid, e) < 800 for e in mids): continue
        mids.append(mid); kept_n += 1
        hm = climb / (L / 1000); char = "flat and easy" if hm < 6 else ("a bit hilly" if hm < 12 else "hilly")
        prof = [nodes[n][2] for n in loop]; mn = min([x for x in prof if x is not None] or [0])
        routes.append({"id": f"{REGION[:2]}r{len(routes)}", "k": "route", "n": f"{hub} loop via {short(d)}", "p": [nodes[loop[0]][0], nodes[loop[0]][1]],
                       "g": [[nodes[n][0], nodes[n][1]] for n in loop], "prof": [round((x or mn) - mn, 1) for x in prof[::max(1, len(prof) // 80)]],
                       "s": 5 if good / L > 0.7 and overlap < 0.35 else (4 if good / L > 0.45 else 3), "f": {"hub": hub, "loop": True},
                       "w": f"Round trip from {hub}: {L/1000:.1f} km, {good/L*100:.0f} % smooth asphalt bike path, {char}" + (", different way back" if overlap < 0.3 else ", partly the same way back") + (f", {nsp} spots on the way" if nsp else "") + (f"; {road:.0f} m on streets" if road > 50 else ""),
                       "i": {"Length": f"{L/1000:.1f} km", "Climb": f"~{climb:.0f} m", "Smooth bike path": f"{good/L*100:.0f} %", "Same way back": f"{overlap*100:.0f} %", "Streets": f"{road:.0f} m", "Spots on the way": str(nsp)}, "osm": ""})
        if kept_n >= 10: break
print("routes:", len(routes))

surf_layer = {"3": [], "2": [], "1": []}
for p in paths: surf_layer[str(p["q"])].append(r5(p["g"]))
data = {"name": REGION, "bbox": bbox, "surf": surf_layer, "spots": out + hills + routes, "graph": {"n": nodes, "e": E}, "built": time.strftime("%Y-%m-%d")}
os.makedirs(os.path.join(HERE, "web", "regions"), exist_ok=True)
s = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
open(os.path.join(HERE, "web", "regions", REGION + ".json"), "w").write(s)
print("regions/%s.json" % REGION, len(s) // 1024, "KB")
