#!/usr/bin/env python3
"""High-resolution ground elevation from Mapterhorn terrain tiles (terrarium-encoded WebP, 512 px).
At zoom 15 one pixel is about 1.2 m in Stockholm. Tiles are cached in data/dem_tiles/.
WebP is decoded with macOS `sips` to PNG, and the PNG is read here with zlib (no extra packages)."""
import math, os, struct, subprocess, urllib.request, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "dem_tiles")
Z = int(os.environ.get("DEM_Z", 15))  # Madeira only has zoom 13 (~8 m per pixel)
_tiles = {}

def _png_rgb(path):
    data = open(path, "rb").read(); pos = 8; idat = b""; w = h = 0
    while pos < len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8]); chunk = data[pos + 8:pos + 8 + ln]; pos += 12 + ln
        if typ == b"IHDR": w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10]); bpp = {2: 3, 6: 4}[ctype]
        elif typ == b"IDAT": idat += chunk
    raw = zlib.decompress(idat); stride = w * bpp; out = bytearray(h * stride); prev = bytearray(stride); i = 0
    for r in range(h):
        f = raw[i]; line = bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        if f == 1:
            for x in range(bpp, stride): line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride): line[x] = (line[x] + ((line[x - bpp] if x >= bpp else 0) + prev[x]) // 2) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0; b = prev[x]; c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out[r * stride:(r + 1) * stride] = line; prev = line
    return w, h, bpp, out

def _tile(x, y):
    key = (x, y)
    if key in _tiles: return _tiles[key]
    os.makedirs(CACHE, exist_ok=True)
    png = os.path.join(CACHE, f"{Z}_{x}_{y}.png")
    if not os.path.exists(png):
        webp = png[:-4] + ".webp"
        req = urllib.request.Request(f"https://tiles.mapterhorn.com/{Z}/{x}/{y}.webp", headers={"User-Agent": "skatemap-local/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r: open(webp, "wb").write(r.read())
        subprocess.run(["sips", "-s", "format", "png", webp, "--out", png], check=True, capture_output=True)
        os.remove(webp)
    _tiles[key] = _png_rgb(png)
    return _tiles[key]

def tile_of(lat, lon):
    n = 2 ** Z; fx = (lon + 180) / 360 * n; fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(fx), int(fy), fx, fy

def elevation(lat, lon):
    x, y, fx, fy = tile_of(lat, lon)
    w, h, bpp, px = _tile(x, y)
    px_x = min(w - 1, int((fx - x) * w)); px_y = min(h - 1, int((fy - y) * h)); i = (px_y * w + px_x) * bpp
    r, g, b = px[i], px[i + 1], px[i + 2]
    return r * 256 + g + b / 256 - 32768

if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        la, lo = map(float, a.split(",")); print(a, round(elevation(la, lo), 2))
