#!/usr/bin/env python3
"""Converts Stockholm city's open map feeds (motionera.stockholm, EPSG:3011) into curated spots for a region.
Usage: python3 sthlm_city.py <ice.json> <skate.json> <region>   → data/<region>/city.json"""
import json, math, sys, os
def sweref1800_to_wgs84(x_east, y_north):
    # Lantmäteriet Gauss-Krüger inverse, SWEREF 99 18 00: lon0 18, k 1, FE 150000, FN 0, GRS80
    a = 6378137.0; f = 1 / 298.257222101; lon0 = math.radians(18.0); k0 = 1.0; FN = 0.0; FE = 150000.0
    e2 = f * (2 - f); n = f / (2 - f); a_roof = a / (1 + n) * (1 + n * n / 4 + n ** 4 / 64)
    d1 = n / 2 - 2 * n * n / 3 + 37 * n ** 3 / 96 - n ** 4 / 360
    d2 = n * n / 48 + n ** 3 / 15 - 437 * n ** 4 / 1440
    d3 = 17 * n ** 3 / 480 - 37 * n ** 4 / 840
    d4 = 4397 * n ** 4 / 161280
    As = e2 + e2 ** 2 + e2 ** 3 + e2 ** 4
    Bs = -(7 * e2 ** 2 + 17 * e2 ** 3 + 30 * e2 ** 4) / 6
    Cs = (224 * e2 ** 3 + 889 * e2 ** 4) / 120
    Ds = -(4279 * e2 ** 4) / 1260
    xi = (y_north - FN) / (k0 * a_roof); eta = (x_east - FE) / (k0 * a_roof)
    xp = xi - d1 * math.sin(2 * xi) * math.cosh(2 * eta) - d2 * math.sin(4 * xi) * math.cosh(4 * eta) - d3 * math.sin(6 * xi) * math.cosh(6 * eta) - d4 * math.sin(8 * xi) * math.cosh(8 * eta)
    ep = eta - d1 * math.cos(2 * xi) * math.sinh(2 * eta) - d2 * math.cos(4 * xi) * math.sinh(4 * eta) - d3 * math.cos(6 * xi) * math.sinh(6 * eta) - d4 * math.cos(8 * xi) * math.sinh(8 * eta)
    phi_star = math.asin(math.sin(xp) / math.cosh(ep)); dl = math.atan(math.sinh(ep) / math.cos(xp))
    s = math.sin(phi_star) ** 2
    lat = phi_star + math.sin(phi_star) * math.cos(phi_star) * (As + Bs * s + Cs * s * s + Ds * s ** 3)
    return math.degrees(lat), math.degrees(lon0 + dl)
ice, skate, region = sys.argv[1:4]
out = []
for f in json.load(open(ice))["features"]:
    x, y = f["geometry"]["coordinates"][:2]; la, lo = sweref1800_to_wgs84(x, y); p = f["properties"]
    out.append({"id": f"city-ice-{f['id']}", "k": "rink", "n": p["name"], "p": [round(la, 6), round(lo, 6)], "s": 4,
                "w": "Skating ice in winter (Stockholm city list). The rest of the year it is usually a court or open plaza: check the surface in Street View.",
                "i": {"Where": p.get("adress", ""), "Source": "motionera.stockholm"}, "osm": "", "url": f"https://motionera.stockholm/hitta-skridskois/skridskois/{p['furl']}", "f": {"su": "unknown", "city": True}})
for f in json.load(open(skate))["features"]:
    x, y = f["geometry"]["coordinates"][:2]; la, lo = sweref1800_to_wgs84(x, y); p = f["properties"]
    nm = p["name"]; low = nm.lower()
    if "parkour" in low and "skate" not in low: continue
    kind = "pump" if ("pump" in low or "bmx" in low) else "park"
    out.append({"id": f"city-skate-{f['id']}", "k": kind, "n": nm, "p": [round(la, 6), round(lo, 6)], "s": 5,
                "w": "Built for riding (Stockholm city list)", "i": {"Where": p.get("adress", ""), "Source": "motionera.stockholm"}, "osm": "",
                "url": f"https://motionera.stockholm/hitta-skatepark-och-parkourpark/skatepark/{p['furl']}", "f": {"city": True}})
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", region, "city.json"), "w"), ensure_ascii=False)
print(len(out), "city spots", [o["n"] for o in out if "Skarpn" in o["n"] or "Fogde" in o.get("i", {}).get("Where", "")])
