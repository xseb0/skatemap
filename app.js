(function () {
"use strict";
const REGIONS = ["soder", "vallentuna"];
const KINDS = {
  park:  { l: "Skateparks", one: "Skatepark", c: "--c-park" },
  pump:  { l: "Pump tracks", one: "Pump track / bike park", c: "--c-pump" },
  steps: { l: "Stairs", one: "Stairs", c: "--c-steps" },
  hill:  { l: "Hills", one: "Hill", c: "--c-hill" },
  ledge: { l: "Ledges & curbs", one: "Ledge / curb", c: "--c-ledge" },
  rail:  { l: "Rails", one: "Rail", c: "--c-rail" },
  plaza: { l: "Plazas", one: "Plaza / pedestrian street", c: "--c-plaza" },
  flat:  { l: "Flat ground", one: "Flat ground", c: "--c-flat" },
  route: { l: "Routes", one: "Suggested route", c: "--c-route" },
  mine:  { l: "My spots", one: "My spot", c: "--c-mine" },
};
const SUBC = { long: "--c-long", short: "--c-short" };
const SUBL = { long: "Stairs with long, low steps", short: "Short stairs: jump practice", stairs: "Stairs", parking: "Large car park", court: "Court",
  schoolyard: "Schoolyard", plan: "Planned route", mellow: "Mellow hill", solid: "Solid hill", steep: "Steep hill", bench: "Bench", curb: "Curb" };
const NOTE = { good: "Good spot", ok: "It's okay", meh: "Not for me" };

const $ = (id) => document.getElementById(id);
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dist = (a, b) => { const r = Math.PI / 180, x = (b[1] - a[1]) * r * Math.cos(((a[0] + b[0]) / 2) * r), y = (b[0] - a[0]) * r; return 6371000 * Math.hypot(x, y); };
const fmtD = (m) => (m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
const stars = (n) => "●".repeat(n) + "<i>" + "●".repeat(5 - n) + "</i>";
const bearing = (a, b) => { const r = Math.PI / 180; return ((Math.atan2((b[1] - a[1]) * Math.cos(a[0] * r), b[0] - a[0]) / r) + 360) % 360; };

// ---------- state ----------
let st = {}; try { st = JSON.parse(localStorage.getItem("skatemap") || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem("skatemap", JSON.stringify(st)); } catch (e) {} };
st.on = Object.assign({ park: 1, pump: 1, steps: 1, hill: 1, ledge: 1, rail: 1, plaza: 1, flat: 0, route: 0, mine: 1 }, st.on || {});
st.notes = st.notes || {}; st.mine = st.mine || []; st.min = st.min || 1;
let spots = [], byId = new Map(), me = null, sel = null, mode = null;
const colorOf = (s) => css(SUBC[s.sub] || KINDS[s.k].c);

// ---------- map + layers ----------
const map = L.map("map", { zoomControl: false, maxZoom: 20, minZoom: 5 }).setView(st.view?.c || [59.276, 18.13], st.view?.z || 14);
L.control.zoom({ position: "bottomright" }).addTo(map);
L.control.scale({ position: "bottomleft", imperial: false }).addTo(map);
const BASES = {
  streets: { l: "Streets", sw: "linear-gradient(135deg,#f2efe9 40%,#fff 40% 50%,#aad3df 50%)", layer: () => L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 20, maxNativeZoom: 19, attribution: "© OpenStreetMap contributors" }) },
  bike: { l: "Bike paths", sw: "linear-gradient(135deg,#eee 45%,#7c3aed 45% 52%,#eee 52%)", layer: () => L.tileLayer("https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png", { maxZoom: 20, attribution: "CyclOSM · © OpenStreetMap contributors" }) },
  terrain: { l: "Terrain", sw: "linear-gradient(135deg,#d9e6c8,#c7b48f)", layer: () => L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", { maxZoom: 20, maxNativeZoom: 17, attribution: "OpenTopoMap (CC-BY-SA) · © OpenStreetMap contributors" }) },
  satellite: { l: "Satellite", sw: "linear-gradient(135deg,#2f4a2a,#6b6a4b 60%,#3b4d5c)", layer: () => L.layerGroup([
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { maxZoom: 20, maxNativeZoom: 19, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }),
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}", { maxZoom: 20, maxNativeZoom: 19, opacity: .8 }),
      L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", { maxZoom: 20, maxNativeZoom: 19 }),
    ]) },
};
let baseLayer = null;
function setBase(k) {
  if (!BASES[k]) k = "streets";
  if (baseLayer) map.removeLayer(baseLayer);
  baseLayer = BASES[k].layer().addTo(map); baseLayer.bringToBack?.();
  st.base = k; save();
  $("basegrid").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.k === k));
}
$("basegrid").innerHTML = Object.entries(BASES).map(([k, v]) => `<button data-k="${k}" style="--sw:${v.sw}"><i></i>${v.l}</button>`).join("");
$("basegrid").onclick = (e) => { const b = e.target.closest("button"); if (b) setBase(b.dataset.k); };
map.createPane("sat"); map.getPane("sat").style.zIndex = 250;
const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { pane: "sat", maxZoom: 20, maxNativeZoom: 19, opacity: st.satOp || 0.6, attribution: "Imagery © Esri" });
function setSat(on) { $("satOn").checked = on; if (on) sat.addTo(map); else sat.remove(); st.sat = on; save(); }
$("satOn").onchange = (e) => setSat(e.target.checked);
$("satOp").value = st.satOp || 0.6;
$("satOp").oninput = (e) => { st.satOp = +e.target.value; sat.setOpacity(st.satOp); if (!st.sat) setSat(true); save(); };
setBase(st.base || "streets"); setSat(!!st.sat);
$("bLayers").onclick = () => { $("layers").hidden = !$("layers").hidden; $("bLayers").classList.toggle("on", !$("layers").hidden); };
map.on("click", () => { if (!$("layers").hidden) { $("layers").hidden = true; $("bLayers").classList.remove("on"); } });

const R = L.canvas({ padding: 0.3, tolerance: 8 });
const surfLayer = L.layerGroup(), spotLayer = L.layerGroup().addTo(map), lineLayer = L.layerGroup().addTo(map), hiLayer = L.layerGroup().addTo(map), routeLayer = L.layerGroup().addTo(map);
let surfData = { "1": [], "2": [], "3": [] };
function drawSurf() { surfLayer.clearLayers(); for (const q of ["1", "2", "3"]) if (surfData[q].length) L.polyline(surfData[q], { renderer: R, color: css("--q" + q), weight: q === "3" ? 3.5 : 3, opacity: .9, interactive: false }).addTo(surfLayer); }
function setSurf(on) { $("surfOn").checked = on; if (on) surfLayer.addTo(map); else surfLayer.remove(); st.surf = on; save(); }
$("surfOn").onchange = (e) => setSurf(e.target.checked);

// rating filter
function drawRate() { $("minRate").querySelectorAll("button").forEach((b) => b.classList.toggle("on", +b.dataset.v === st.min)); }
$("minRate").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; st.min = +b.dataset.v; save(); drawRate(); render(); };
drawRate();

// ---------- chips ----------
function drawChips() {
  const c = {}; for (const s of spots) c[s.k] = (c[s.k] || 0) + 1;
  const allOn = Object.keys(KINDS).every((k) => st.on[k] || !c[k]);
  $("chips").innerHTML = `<span class="chip all ${allOn ? "" : "off"}"><button data-all>All</button></span>` +
    Object.entries(KINDS).filter(([k]) => c[k] || k === "mine").map(([k, v]) =>
      `<span class="chip ${st.on[k] ? "" : "off"}" style="--c:var(${v.c})"><button class="tog" data-k="${k}" aria-pressed="${!!st.on[k]}" title="Show or hide ${v.l.toLowerCase()}"><span class="dot"></span>${v.l}<span class="n">${c[k] || 0}</span></button><button class="only" data-only="${k}" title="Show only ${v.l.toLowerCase()}">only</button></span>`).join("");
}
$("chips").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.all !== undefined) { for (const k in KINDS) st.on[k] = 1; }
  else if (b.dataset.only) { for (const k in KINDS) st.on[k] = k === b.dataset.only ? 1 : 0; }
  else { const k = b.dataset.k; st.on[k] = st.on[k] ? 0 : 1; }
  save(); drawChips(); render();
};

// ---------- data ----------
function addSpots(arr) { for (const s of arr) { if (byId.has(s.id) || (s.osm && byId.has("osm:" + s.osm + s.k))) continue; byId.set(s.id, s); if (s.osm) byId.set("osm:" + s.osm + s.k, s); spots.push(s); } }
function mineSpots() { return st.mine.map((m) => Object.assign({ k: "mine", s: 5 }, m)); }
function refreshMine() { spots = spots.filter((s) => s.k !== "mine"); for (const [k, v] of byId) if (v.k === "mine") byId.delete(k); addSpots(mineSpots()); }
const G = { n: [], e: [] };
async function loadRegions() {
  for (const r of REGIONS) {
    try {
      const d = await (await fetch(`regions/${r}.json?v=2026-11-14`)).json();
      addSpots(d.spots);
      for (const q of ["1", "2", "3"]) surfData[q].push(...d.surf[q]);
      const off = G.n.length; G.n.push(...d.graph.n); for (const [a, b, l, q] of d.graph.e) G.e.push([a + off, b + off, l, q]);
      drawChips(); render(); drawSurf();
    } catch (e) { console.warn("region failed", r, e); }
  }
  buildGraph();
}

// ---------- render markers + list ----------
const zoomMin = () => (map.getZoom() <= 12 ? 5 : map.getZoom() <= 14 ? 4 : 1);
function visible() { const m = Math.max(st.min, zoomMin()); return spots.filter((s) => st.on[s.k] && (s.s >= m || s.k === "mine" || s.k === "park" || s.k === "pump")); }
function render() {
  spotLayer.clearLayers(); lineLayer.clearLayers();
  const vs = visible(), z = map.getZoom();
  const rad = z >= 17 ? 9 : z >= 15 ? 7 : z >= 13 ? 5 : 3.5;
  const ink = css("--panel");
  for (const s of vs) {
    const col = colorOf(s);
    if ((s.k === "route" || s.k === "hill") && s.g && z >= 13) L.polyline(s.g, { renderer: R, color: col, weight: s.k === "route" ? 4 : 5, opacity: s.k === "route" ? .55 : .8 }).on("click", (e) => pick(s, e)).addTo(lineLayer);
    if (s.k === "mine") L.marker(s.p, { icon: L.divIcon({ className: "", html: `<div class="mine-pin"></div>`, iconSize: [16, 16] }), title: s.n }).on("click", (e) => pick(s, e)).addTo(spotLayer);
    else L.circleMarker(s.p, { renderer: R, radius: s.s >= 5 ? rad + 1.5 : rad, color: ink, weight: 2, fillColor: col, fillOpacity: 1 }).on("click", (e) => pick(s, e)).addTo(spotLayer);
  }
  drawList(vs);
}
function drawList(vs) {
  vs = vs || visible();
  const ref = me || [map.getCenter().lat, map.getCenter().lng];
  const b = map.getBounds().pad(0.2);
  let inView = vs.filter((s) => b.contains(s.p));
  inView.forEach((s) => (s._d = dist(ref, s.p)));
  inView.sort((a, c) => a._d - c._d);
  $("sheetTitle").textContent = me ? "Spots near you" : "Spots in view";
  $("sheetSub").textContent = zoomMin() > st.min ? `${inView.length} · top rated, zoom in for all` : `${inView.length}`;
  if (!inView.length) { $("list").innerHTML = `<div class="empty">No spots here with these filters. Turn on more categories, zoom out, or tap the search button on the right to find spots in this area.</div>`; return; }
  $("list").innerHTML = inView.slice(0, 120).map((s) => {
    const n = st.notes[s.id];
    return `<button class="item ${sel && sel.id === s.id ? "sel" : ""}" data-id="${esc(s.id)}" style="--c:${colorOf(s)}"><span class="dot"></span><span style="min-width:0"><div class="t">${esc(s.n)}${n && n.status ? `<span class="tag ${n.status}">${esc(NOTE[n.status])}</span>` : ""}</div><div class="w">${esc(s.w)}</div></span><span class="meta">${fmtD(s._d)}<br><span class="stars">${stars(s.s)}</span></span></button>`;
  }).join("") + (inView.length > 120 ? `<div class="empty">Showing the 120 closest of ${inView.length}.</div>` : "");
}
$("list").onclick = (e) => { const b = e.target.closest(".item"); if (b) open(byId.get(b.dataset.id), true); };
$("sheetBar").onclick = () => { const c = $("sheet").classList.toggle("collapsed"); $("sheetBar").setAttribute("aria-expanded", !c); };
let mvT; map.on("moveend zoomend", () => { clearTimeout(mvT); mvT = setTimeout(() => { st.view = { c: [map.getCenter().lat, map.getCenter().lng], z: map.getZoom() }; save(); render(); }, 200); });

// ---------- spot card with Street View ----------
function svUrl(s, embed) {
  const g = s.g && s.g.length > 1 ? s.g : null;
  let p = s.p, h = 0;
  if (g && s.k === "steps") { p = g[g.length - 1]; h = bearing(g[g.length - 1], g[0]); }
  else if (g && s.k === "hill") { p = g[0]; h = bearing(g[0], g[Math.min(3, g.length - 1)]); }
  else if (g && s.k === "route") { p = g[0]; h = bearing(g[0], g[Math.min(5, g.length - 1)]); }
  const base = `https://www.google.com/maps?layer=c&cbll=${p[0]},${p[1]}&cbp=12,${h.toFixed(0)},0,0,5`;
  return embed ? base + "&output=svembed" : base;
}
function profSVG(p, col) {
  if (!p || p.length < 2) return "";
  const W = 320, H = 70, mx = Math.max(...p, 1), pts = p.map((v, i) => `${((i / (p.length - 1)) * W).toFixed(1)},${(H - 4 - (v / mx) * (H - 16)).toFixed(1)}`);
  return `<svg class="prof" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Elevation profile, ${mx.toFixed(0)} m difference"><polygon points="0,${H} ${pts.join(" ")} ${W},${H}" fill="${col}" fill-opacity=".18"/><polyline points="${pts.join(" ")}" fill="none" stroke="${col}" stroke-width="2"/><text x="4" y="12" font-size="10" fill="${css("--muted")}" font-family="JetBrains Mono, monospace">${mx.toFixed(0)} m elevation difference</text></svg>`;
}
function open(s, fly) {
  if (!s) return;
  sel = s; hiLayer.clearLayers(); $("layers").hidden = true; $("bLayers").classList.remove("on");
  const col = colorOf(s);
  if (s.g) L.polyline(s.g, { renderer: R, color: col, weight: 9, opacity: .9 }).addTo(hiLayer);
  L.circleMarker(s.p, { renderer: R, radius: 13, color: col, weight: 3, fill: false }).addTo(hiLayer);
  const narrow = innerWidth <= 760;
  if (fly || narrow) {
    if (s.g && s.g.length > 2 && s.k !== "steps") map.fitBounds(L.latLngBounds(s.g), { paddingTopLeft: narrow ? [20, 20] : [400, 40], paddingBottomRight: narrow ? [20, innerHeight * 0.6] : [420, 40], maxZoom: 18 });
    else { const z = Math.max(map.getZoom(), 17); const pt = map.project(s.p, z); map.setView(map.unproject(narrow ? pt.add([0, innerHeight * 0.28]) : pt.add([200, 0]), z), z); }
  }
  const n = st.notes[s.id] || {};
  const [la, lo] = s.p;
  $("card").innerHTML = `<button class="x" aria-label="Close">×</button>
    <div class="sv"><div class="svmsg">Loading Street View…<br>If it stays empty there is no Street View here.</div><iframe src="${svUrl(s, true)}" loading="lazy" allowfullscreen referrerpolicy="no-referrer-when-downgrade" title="Street View"></iframe></div>
    <div class="body">
      <div><div class="kind" style="--c:${col}">${esc(SUBL[s.sub] || KINDS[s.k].one)}</div><h2>${esc(s.n)}</h2>
        <div class="stars" style="margin-top:4px">${stars(s.s)} <span class="small">${s.k === "mine" ? "your spot" : "estimated from map data"}</span></div></div>
      <div class="why">${esc(s.w)}</div>
      ${s.prof ? profSVG(s.prof, col) : ""}
      ${s.i ? `<dl>${Object.entries(s.i).map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
      <div class="links">
        <a href="${svUrl(s)}" target="_blank" rel="noopener">Open Street View</a>
        <a href="https://www.google.com/maps/dir/?api=1&destination=${la},${lo}&travelmode=walking" target="_blank" rel="noopener">Directions</a>
        <a href="https://www.google.com/maps/search/?api=1&query=${la},${lo}" target="_blank" rel="noopener">Google Maps</a>
        ${s.osm ? `<a href="https://www.openstreetmap.org/${s.osm}" target="_blank" rel="noopener">OpenStreetMap</a>` : ""}
      </div>
      ${s.id === "plan" ? "" : `<div class="notes">
        <div class="small">Been here? Save what you thought.</div>
        <div class="row">${Object.entries(NOTE).map(([k, v]) => `<button class="btn ${n.status === k ? "on" : ""}" data-st="${k}">${v}</button>`).join("")}</div>
        <textarea id="nText" placeholder="E.g. 6 steps, low rail on the left, gravel at the landing">${esc(n.text || "")}</textarea>
        <div class="row"><button class="btn primary" id="nSave">Save note</button>${s.k === "mine" ? `<button class="btn" id="nDel">Delete spot</button>` : ""}<span class="small" id="nMsg"></span></div>
      </div>`}
    </div>`;
  $("card").hidden = false; $("card").scrollTop = 0; document.body.classList.add("card-open");
  $("card").querySelector(".x").onclick = closeCard;
  $("card").querySelectorAll("[data-st]").forEach((b) => (b.onclick = () => { const v = b.dataset.st; setNote(s, { status: n.status === v ? null : v }); }));
  const ns = $("nSave"); if (ns) ns.onclick = () => { setNote(s, { text: $("nText").value.trim() }); $("nMsg").textContent = "Saved"; };
  const nd = $("nDel"); if (nd) nd.onclick = () => { st.mine = st.mine.filter((m) => m.id !== s.id); save(); refreshMine(); closeCard(); drawChips(); render(); };
  document.querySelectorAll(".item.sel").forEach((x) => x.classList.remove("sel"));
  const li = document.querySelector(`.item[data-id="${CSS.escape(s.id)}"]`); if (li) li.classList.add("sel");
}
function setNote(s, patch) {
  st.notes[s.id] = Object.assign({}, st.notes[s.id] || {}, patch, { t: Date.now() }); save();
  const keepText = $("nText") ? $("nText").value : null;
  open(s); if (keepText !== null && $("nText")) $("nText").value = keepText; drawList();
}
function closeCard() { document.body.classList.remove("card-open"); $("card").hidden = true; $("card").innerHTML = ""; hiLayer.clearLayers(); sel = null; drawList(); }

// ---------- my location ----------
let watchId = null, meDot = null, meAcc = null, follow = false;
$("bLocate").onclick = () => {
  if (!navigator.geolocation) { hint("This browser cannot share your location", 3000); return; }
  if (watchId !== null) { follow = !follow; $("bLocate").classList.toggle("follow", follow); if (me) map.setView(me, Math.max(map.getZoom(), 16)); return; }
  hint("Finding you…");
  follow = true; $("bLocate").classList.add("follow");
  watchId = navigator.geolocation.watchPosition((pos) => {
    const first = !me; me = [pos.coords.latitude, pos.coords.longitude];
    if (!meDot) { meAcc = L.circle(me, { radius: pos.coords.accuracy, color: css("--me"), weight: 1, fillOpacity: .12, interactive: false }).addTo(map); meDot = L.marker(me, { icon: L.divIcon({ className: "", html: '<div class="me-dot"></div>', iconSize: [18, 18] }), zIndexOffset: 2000, interactive: false }).addTo(map); }
    else { meDot.setLatLng(me); meAcc.setLatLng(me).setRadius(pos.coords.accuracy); }
    if (first) { hideHint(); map.setView(me, Math.max(map.getZoom(), 16)); }
    else if (follow) map.panTo(me);
    drawList();
  }, (err) => { hint(err.code === 1 ? "Location is blocked. Allow it in the browser's site settings." : "Could not find your location", 4000); watchId = null; follow = false; $("bLocate").classList.remove("follow"); },
  { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
};
map.on("dragstart", () => { if (follow) { follow = false; $("bLocate").classList.remove("follow"); } });

// ---------- hint + modes ----------
let hintT;
function hint(t, ms) { $("hintText").textContent = t; $("hint").hidden = false; $("hintX").hidden = !mode; clearTimeout(hintT); if (ms) hintT = setTimeout(hideHint, ms); }
function hideHint() { $("hint").hidden = true; }
function setMode(m, t) { mode = m; ["bRoute", "bAdd"].forEach((id) => $(id).classList.toggle("on", (id === "bRoute" && m === "route") || (id === "bAdd" && m === "add"))); map.getContainer().style.cursor = m ? "crosshair" : ""; if (m) hint(t); else hideHint(); }
$("hintX").onclick = () => { setMode(null); routeA = null; };
$("bAdd").onclick = () => setMode(mode === "add" ? null : "add", "Tap where the spot is");
let routeA = null;
$("bRoute").onclick = () => { routeA = null; routeLayer.clearLayers(); setMode(mode === "route" ? null : "route", me ? "Tap your destination (starts from you)" : "Tap the start point"); if (me && mode === "route") routeA = me; };
map.on("click", (e) => tap([e.latlng.lat, e.latlng.lng]));
function tap(ll) {
  const p = [+ll[0].toFixed(6), +ll[1].toFixed(6)];
  if (mode === "add") { setMode(null); addForm(p); return; }
  if (mode === "route") {
    if (!routeA) { routeA = p; routeLayer.clearLayers(); L.circleMarker(p, { radius: 8, color: css("--c-route"), fillOpacity: 1 }).addTo(routeLayer); hint("Now tap the destination"); return; }
    const r = plan(routeA, p); setMode(null); routeA = null;
    if (!r) { hint("No smooth path found between those points. Routes work inside Söder and Vallentuna–Täby.", 4500); return; }
    showRoute(r);
  }
}
function pick(s, e) { L.DomEvent.stop(e); if (mode) tap([e.latlng.lat, e.latlng.lng]); else open(s); }
function addForm(p) {
  sel = null; hiLayer.clearLayers(); L.circleMarker(p, { radius: 9, color: css("--accent"), fillOpacity: .6 }).addTo(hiLayer);
  $("card").innerHTML = `<button class="x" aria-label="Close" style="background:var(--hover);color:var(--ink)">×</button><div class="body" style="padding-top:18px">
    <h2>New spot</h2>
    <label class="small" for="eName">Name</label><input type="text" id="eName" placeholder="E.g. Low stairs by the library">
    <label class="small" for="eType">What is here?</label>
    <select id="eType">${["Stairs", "Stairs with long, low steps", "Low rail", "Grindable curb", "Ledge / bench", "Hill", "Powerslide spot", "Jump / drop", "Bank / transition", "Manual pad", "Other"].map((x) => `<option>${x}</option>`).join("")}</select>
    <label class="small" for="eText">Notes</label><textarea id="eText" placeholder="Height, number of steps, surface, when it's empty"></textarea>
    <div class="row" style="justify-content:flex-start"><button class="btn primary" id="eSave">Save spot</button></div></div>`;
  $("card").hidden = false; document.body.classList.add("card-open"); $("card").querySelector(".x").onclick = closeCard; $("eName").focus();
  $("eSave").onclick = () => {
    const type = $("eType").value, note = $("eText").value.trim();
    const m = { id: "m" + Date.now(), n: $("eName").value.trim() || type, sub: "", p, w: type + (note ? ": " + note : ""), t: Date.now() };
    st.mine.push(m); st.on.mine = 1; save(); refreshMine(); drawChips(); render(); open(byId.get(m.id));
  };
}

// ---------- route planner ----------
let adj = null, ngrid = null;
function buildGraph() {
  adj = Array.from({ length: G.n.length }, () => []);
  for (const [a, b, l, q] of G.e) { const c = l * (q >= 3 ? 1 : q === 2 ? 1.6 : q === 1 ? 3 : 2.4); adj[a].push([b, c, q]); adj[b].push([a, c, q]); }
  ngrid = new Map();
  G.n.forEach((n, i) => { const k = Math.floor(n[0] * 500) + ":" + Math.floor(n[1] * 250); (ngrid.get(k) || ngrid.set(k, []).get(k)).push(i); });
}
function nearestNode(p) {
  if (!ngrid) return -1;
  for (const r of [1, 3, 8]) {
    let bi = -1, bd = 1e18; const gx = Math.floor(p[0] * 500), gy = Math.floor(p[1] * 250);
    for (let dx = -r; dx <= r; dx++) for (let dy = -r; dy <= r; dy++) for (const i of ngrid.get(gx + dx + ":" + (gy + dy)) || []) { const d = dist(p, G.n[i]); if (d < bd) { bd = d; bi = i; } }
    if (bi >= 0) return bd < 800 ? bi : -1;
  }
  return -1;
}
function plan(A, B) {
  const a = nearestNode(A), b = nearestNode(B); if (a < 0 || b < 0) return null;
  const NN = G.n.length, D = new Float64Array(NN).fill(Infinity), P = new Int32Array(NN).fill(-1), Q = new Int8Array(NN).fill(-1), h = [];
  const push = (x) => { h.push(x); let i = h.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (h[p][0] <= h[i][0]) break; [h[p], h[i]] = [h[i], h[p]]; i = p; } };
  const pop = () => { const t = h[0], l = h.pop(); if (h.length) { h[0] = l; let i = 0; for (;;) { let m = i; const L1 = 2 * i + 1, R1 = L1 + 1; if (L1 < h.length && h[L1][0] < h[m][0]) m = L1; if (R1 < h.length && h[R1][0] < h[m][0]) m = R1; if (m === i) break; [h[m], h[i]] = [h[i], h[m]]; i = m; } } return t; };
  D[a] = 0; push([0, a]);
  while (h.length) { const [d, u] = pop(); if (u === b) break; if (d > D[u]) continue; for (const [v, c, q] of adj[u]) { const nd = d + c; if (nd < D[v]) { D[v] = nd; P[v] = u; Q[v] = q; push([nd, v]); } } }
  if (a !== b && P[b] < 0) return null;
  const path = [b], qs = []; while (path[path.length - 1] !== a) { const x = path[path.length - 1]; qs.push(Q[x]); path.push(P[x]); }
  path.reverse(); qs.reverse();
  let L = 0, good = 0, road = 0, up = 0, down = 0;
  for (let i = 0; i < path.length - 1; i++) { const u = G.n[path[i]], v = G.n[path[i + 1]], l = dist(u, v); L += l; if (qs[i] >= 3) good += l; if (qs[i] === 0) road += l; if (u[2] != null && v[2] != null) { const dh = v[2] - u[2]; if (dh > 0) up += dh; else down -= dh; } }
  return { path, L, good, road, up, down };
}
function showRoute(r) {
  routeLayer.clearLayers();
  const g = r.path.map((i) => [G.n[i][0], G.n[i][1]]);
  L.polyline(g, { renderer: R, color: css("--c-route"), weight: 6, opacity: .9 }).addTo(routeLayer);
  L.circleMarker(g[0], { radius: 8, color: css("--c-route"), fillOpacity: 1 }).addTo(routeLayer);
  L.circleMarker(g[g.length - 1], { radius: 8, color: css("--accent"), fillOpacity: 1 }).addTo(routeLayer);
  const hs = r.path.map((i) => G.n[i][2]).filter((x) => x != null), mn = Math.min(...hs), step = Math.max(1, Math.floor(hs.length / 80));
  const s = { id: "plan", k: "route", sub: "plan", n: "Your route", p: g[0], g, s: r.good / r.L > .75 ? 5 : r.good / r.L > .5 ? 4 : 3,
    w: `${fmtD(r.L)}, ${Math.round((r.good / r.L) * 100)} % smooth asphalt bike path${r.road > 50 ? `, ${fmtD(r.road)} on residential streets` : ""}.`,
    prof: hs.filter((_, i) => i % step === 0).map((x) => x - mn),
    i: { Length: fmtD(r.L), Uphill: `${Math.round(r.up)} m`, Downhill: `${Math.round(r.down)} m`, "Smooth bike path": `${Math.round((r.good / r.L) * 100)} %`, "Residential street": fmtD(r.road) } };
  open(s, true);
}

// ---------- search: spots + places (Nominatim) ----------
let qT, qAbort, qSel = -1;
$("q").addEventListener("input", () => { $("qClear").hidden = !$("q").value; clearTimeout(qT); qT = setTimeout(search, 300); });
$("q").addEventListener("keydown", (e) => {
  const btns = [...$("results").querySelectorAll("button")]; if (!btns.length) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); qSel = (qSel + (e.key === "ArrowDown" ? 1 : -1) + btns.length) % btns.length; btns.forEach((b, i) => b.classList.toggle("act", i === qSel)); }
  if (e.key === "Enter") { e.preventDefault(); (btns[qSel] || btns[0]).click(); }
  if (e.key === "Escape") { $("results").hidden = true; }
});
$("qClear").onclick = () => { $("q").value = ""; $("qClear").hidden = true; $("results").hidden = true; $("q").focus(); };
async function search() {
  const q = $("q").value.trim(); qSel = -1;
  if (q.length < 2) { $("results").hidden = true; return; }
  const ql = q.toLowerCase();
  const sp = spots.filter((s) => s.n.toLowerCase().includes(ql) || (KINDS[s.k].l.toLowerCase().includes(ql))).slice(0, 6);
  let html = sp.length ? `<div class="head">Spots</div>` + sp.map((s) => `<button data-id="${esc(s.id)}"><span class="dot" style="--c:${colorOf(s)}"></span><span>${esc(s.n)}<small>${esc(SUBL[s.sub] || KINDS[s.k].one)}</small></span></button>`).join("") : "";
  $("results").innerHTML = html + `<div class="head">Places</div><div class="empty">Searching…</div>`; $("results").hidden = false;
  try {
    qAbort?.abort(); qAbort = new AbortController();
    const c = map.getCenter();
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=se&accept-language=en&viewbox=${c.lng - .4},${c.lat + .2},${c.lng + .4},${c.lat - .2}&q=${encodeURIComponent(q)}`;
    const res = await (await fetch(url, { signal: qAbort.signal })).json();
    html += `<div class="head">Places</div>` + (res.length ? res.map((r) => `<button data-lat="${r.lat}" data-lon="${r.lon}" data-bb="${(r.boundingbox || []).join(",")}"><span class="dot" style="--c:var(--muted)"></span><span>${esc(r.name || r.display_name.split(",")[0])}<small>${esc(r.display_name.split(",").slice(1, 4).join(","))}</small></span></button>`).join("") : `<div class="empty">No places found</div>`);
    $("results").innerHTML = html;
  } catch (e) { if (e.name !== "AbortError") $("results").innerHTML = html + `<div class="head">Places</div><div class="empty">Place search is not reachable right now</div>`; }
}
$("results").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  $("results").hidden = true; $("q").blur();
  if (b.dataset.id) { open(byId.get(b.dataset.id), true); return; }
  const bb = b.dataset.bb.split(",").map(Number);
  if (bb.length === 4 && bb[0] !== bb[1]) map.fitBounds([[bb[0], bb[2]], [bb[1], bb[3]]], { maxZoom: 17 }); else map.setView([+b.dataset.lat, +b.dataset.lon], 17);
};
document.addEventListener("click", (e) => { if (!e.target.closest(".top")) $("results").hidden = true; });

// ---------- live scan (Overpass) for any area ----------
$("bScan").onclick = scan;
async function scan() {
  if (map.getZoom() < 14) { hint("Zoom in a bit more to search this area", 3000); return; }
  const b = map.getBounds(), bb = `${b.getSouth().toFixed(5)},${b.getWest().toFixed(5)},${b.getNorth().toFixed(5)},${b.getEast().toFixed(5)}`;
  const q = `[out:json][timeout:60];(nwr["sport"~"skateboard|roller|bmx|pump"](${bb});nwr["name"~"[Pp]ump ?track|[Pp]umpbana|[Ss]kate"](${bb});way["highway"="steps"](${bb});nwr["leisure"="pitch"]["sport"~"basketball|multi|tennis|hockey|futsal|streetball"](${bb});way["amenity"="parking"](${bb});nwr["place"="square"](${bb});way["highway"="pedestrian"](${bb});node["amenity"="bench"]["material"~"concrete|stone|granite|metal|steel"](${bb});nwr["barrier"="kerb"](${bb});way["barrier"~"guard_rail|handrail"](${bb}););out tags geom;`;
  hint("Searching this area for spots. This can take up to a minute…"); $("bScan").classList.add("on");
  let data = null;
  const EPS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter", "https://overpass.kumi.systems/api/interpreter"];
  for (let round = 0; round < 2 && !data; round++) {
    const acs = EPS.map(() => new AbortController()), to = setTimeout(() => acs.forEach((a) => a.abort()), 90000);
    try {
      data = await Promise.any(EPS.map(async (ep, i) => {
        const r = await fetch(ep, { method: "POST", body: "data=" + encodeURIComponent(q), signal: acs[i].signal });
        if (!r.ok) throw new Error(r.status);
        const j = await r.json(); if (!j.elements) throw new Error("bad"); return j;
      }));
    } catch (e) { if (round === 0) { hint("Map data servers are busy, trying again…"); await new Promise((r) => setTimeout(r, 5000)); } }
    clearTimeout(to); acs.forEach((a) => a.abort());
  }
  $("bScan").classList.remove("on");
  if (!data) { hint("The map data server is busy. Try again in a minute.", 4000); return; }
  const before = spots.length; addSpots(liveSpots(data.elements)); drawChips(); render();
  hint(spots.length - before ? `Found ${spots.length - before} new spots here` : "No new spots found here", 3000);
}
function liveSpots(els) {
  const out = [], PAVED = new Set(["asphalt", "concrete", "paved", "concrete:plates", "paving_stones"]);
  const g = (el) => el.type === "node" ? [[el.lat, el.lon]] : (el.geometry || []).filter(Boolean).map((p) => [p.lat, p.lon]);
  const glen = (a) => a.reduce((s, p, i) => (i ? s + dist(a[i - 1], p) : 0), 0);
  const area = (a) => { if (a.length < 3) return 0; const k = Math.cos(a[0][0] * Math.PI / 180); let s = 0; for (let i = 0; i < a.length; i++) { const [y1, x1] = a[i], [y2, x2] = a[(i + 1) % a.length]; s += x1 * k * 111320 * y2 * 110574 - x2 * k * 111320 * y1 * 110574; } return Math.abs(s) / 2; };
  const cen = (a) => [a.reduce((s, p) => s + p[0], 0) / a.length, a.reduce((s, p) => s + p[1], 0) / a.length];
  const add = (el, k, n, s, w, i, gg, extra) => out.push(Object.assign({ id: `live-${el.type[0]}${el.id}-${k}`, k, n, p: cen(gg).map((x) => +x.toFixed(6)), s: Math.max(1, Math.min(5, Math.round(s))), w, i, osm: `${el.type}/${el.id}`, g: gg.length > 1 ? gg : undefined }, extra || {}));
  for (const el of els) {
    const t = el.tags || {}, gg = g(el); if (!gg.length) continue;
    const nm = t.name || "", sport = t.sport || "", surf = t.surface;
    const spOk = /skateboard|bmx|pump|roller_skating|^roller$/.test(sport) && !/roller_ski/.test(sport);
    const nmOk = /pump ?track|pumpbana|skate ?park|skateboard|skatepool|kickbike/i.test(nm) && !t.highway && !/compressed_air|bicycle_repair_station|fuel/.test(t.amenity || "");
    if (spOk || nmOk) {
      if (t.indoor === "yes" || t.access === "private") continue;
      const k = /bmx|pump|kick/i.test(sport + " " + nm) && !/skate/i.test(nm) ? "pump" : "park";
      add(el, k, nm || (k === "pump" ? "Pump track" : "Skatepark"), 5, "Built for riding" + (t.lit === "yes" ? ", lit at night" : ""), { Surface: surf || "unknown", Lit: t.lit || "unknown" }, gg); continue;
    }
    if (t.highway === "steps") {
      if (t.indoor === "yes" || t.conveying) continue;
      const L = glen(gg), n = parseInt(t.step_count) || null, tread = n ? L / n : null;
      let sub = "stairs", s = 3; const why = [];
      if (n && n <= 4) { sub = "short"; s = 4; why.push(`${n} steps: good for learning to drop`); } else if (n && n <= 10) { s = 4; why.push(`${n} steps: nice size for stair bashing`); } else if (n) why.push(`${n} steps: long set`); else why.push("step count not mapped");
      if (tread && tread >= .6 && tread <= 2.2 && n <= 12) { sub = "long"; s = 5; why.unshift(`long treads (~${Math.round(tread * 100)} cm per step): likely low, deep steps`); }
      if (/yes|both|left|right/.test(t.handrail || "")) why.push("has a handrail (usually too high to grind, check)");
      add(el, "steps", nm || { short: "Short stairs", long: "Long-tread stairs", stairs: "Stairs" }[sub], s, why.join("; "), Object.assign({ Length: `${Math.round(L)} m`, Handrail: t.handrail || "unknown", Surface: surf || "unknown" }, n ? { Steps: String(n) } : {}), gg, { sub }); continue;
    }
    if (t.leisure === "pitch") { if (surf && !PAVED.has(surf) && surf !== "acrylic") continue; add(el, "flat", nm || "Court", surf ? 4 : 3, "Smooth, flat and open: good for powerslides, manuals and flatground", { Sport: sport, Surface: surf || "unknown" }, gg, { sub: "court" }); continue; }
    if (t.amenity === "parking") { const A = area(gg); if (A < 1800 || (surf && !PAVED.has(surf)) || /underground|multi-storey|rooftop/.test(t.parking || "")) continue; add(el, "flat", nm || "Large car park", 3 + (A > 5000 ? 1 : 0), `Big open lot (${Math.round(A)} m²) for powerslides when it is empty`, { Area: `${Math.round(A)} m²`, Surface: surf || "unknown" }, gg, { sub: "parking" }); continue; }
    if (t.place === "square" || t.highway === "pedestrian") { if (surf && !PAVED.has(surf)) continue; add(el, "plaza", nm || "Square", 3, "Square or pedestrian street: often ledges, benches and low walls", { Surface: surf || "unknown" }, gg); continue; }
    if (t.amenity === "bench") { add(el, "ledge", (t.material || "Hard") + " bench", 3, "Bench in a hard material: might work as a ledge", { Material: t.material }, gg, { sub: "bench" }); continue; }
    if (t.barrier === "kerb") { add(el, "ledge", "Curb", 3, "Mapped curb: check if it grinds", { Type: t.kerb || "unknown" }, gg, { sub: "curb" }); continue; }
    if (/guard_rail|handrail/.test(t.barrier || "")) { add(el, "rail", "Rail", 2.5, "Mapped rail: often tall or next to traffic", { Length: `${Math.round(glen(gg))} m` }, gg); }
  }
  return out;
}

// ---------- backup ----------
$("bExport").onclick = async () => {
  const txt = JSON.stringify({ mine: st.mine, notes: st.notes });
  try { await navigator.clipboard.writeText(txt); $("ioMsg").textContent = `Copied ${st.mine.length} spots and ${Object.keys(st.notes).length} notes. Paste it on the other device.`; }
  catch (e) { $("ioMsg").textContent = "Could not copy. Your browser blocked the clipboard."; }
};
$("bImport").onclick = async () => {
  try {
    const d = JSON.parse(await navigator.clipboard.readText());
    const have = new Set(st.mine.map((m) => m.id)); for (const m of d.mine || []) if (!have.has(m.id)) st.mine.push(m);
    Object.assign(st.notes, d.notes || {}); save(); refreshMine(); drawChips(); render();
    $("ioMsg").textContent = "Backup added.";
  } catch (e) { $("ioMsg").textContent = "Copy a backup first, then press Paste backup."; }
};

document.addEventListener("keydown", (e) => { if (e.key === "Escape") { if (mode) setMode(null); else if (!$("card").hidden) closeCard(); } });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { drawSurf(); render(); });

// ---------- start ----------
addSpots(mineSpots()); drawChips(); render(); setSurf(!!st.surf);
loadRegions();
})();
