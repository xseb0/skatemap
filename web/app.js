(function () {
"use strict";
const REGIONS = ["soder", "vallentuna"];
const KINDS = {
  park:  { l: "Skateparks", one: "Skatepark", c: "--c-park" },
  pump:  { l: "Pump & BMX", one: "Pump track / BMX track", c: "--c-pump" },
  rink:  { l: "Ice rinks", one: "Outdoor ice rink (winter)", c: "--c-rink" },
  steps: { l: "Stairs", one: "Stairs", c: "--c-steps" },
  longsteps: { l: "Long-tread stairs", one: "Stairs with long, low steps", c: "--c-long" },
  hill:  { l: "Hills", one: "Hill", c: "--c-hill" },
  ledge: { l: "Ledges & curbs", one: "Ledge / curb", c: "--c-ledge" },
  rail:  { l: "Rails", one: "Rail", c: "--c-rail" },
  plaza: { l: "Plazas", one: "Plaza / pedestrian street", c: "--c-plaza" },
  flat:  { l: "Flat ground", one: "Flat ground", c: "--c-flat" },
  route: { l: "Routes", one: "Suggested route", c: "--c-route" },
  mine:  { l: "My spots", one: "My spot", c: "--c-mine" },
};
const SUBC = { long: "--c-long", short: "--c-short" };
const SUBL = { smoothplaza: "Big smooth plaza", long: "Stairs with long, low steps", short: "Short stairs: jump practice", stairs: "Stairs", parking: "Large car park", court: "Court",
  schoolyard: "Schoolyard", plan: "Planned route", mellow: "Mellow hill", solid: "Solid hill", steep: "Steep hill", "very steep": "Very steep hill", bench: "Bench", curb: "Curb" };
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
const save = () => { try { localStorage.setItem("skatemap", JSON.stringify(st)); } catch (e) {} syncHash(); };
st.on = Object.assign({ park: 1, pump: 1, rink: 1, steps: 1, longsteps: 1, hill: 1, ledge: 1, rail: 1, plaza: 1, flat: 0, route: 0, mine: 1 }, st.on || {});
const FDEF = { nMin: 0, nMax: 99, stepType: "any", rail: false, pavedEnds: false, hasCount: false,
  flatType: { court: true, parking: true, schoolyard: true }, surf: { asphalt: true, concrete: true, "court surface": true, "paving stones": true, paved: true, unknown: true },
  hillLv: { gentle: true, mellow: true, solid: true, steep: true, "very steep": true }, carFree: false, bigPlaza: false, noDirt: false, hub: "any" };
st.f = Object.assign(JSON.parse(JSON.stringify(FDEF)), st.f || {});
st.f.hillLv = Object.assign({}, FDEF.hillLv, st.f.hillLv);
if (st.f.stepType === "long") st.f.stepType = "any";
st.notes = st.notes || {}; st.mine = st.mine || []; st.min = st.min || 1;

// ---------- shareable links: the address holds the view, categories, filters, map style and selection ----------
// Short form, only what differs from the defaults, e.g. #m=59.2803,18.1358,18&c=h&h=g&s=soh153273974
const CAT = { park: "p", pump: "b", rink: "i", steps: "s", longsteps: "l", hill: "h", ledge: "e", rail: "r", plaza: "z", flat: "f", route: "o", mine: "m" };
const ONDEF = { park: 1, pump: 1, rink: 1, steps: 1, longsteps: 1, hill: 1, ledge: 1, rail: 1, plaza: 1, flat: 0, route: 0, mine: 1 };
const FLAG = { rail: "r", pavedEnds: "e", hasCount: "c", carFree: "f", bigPlaza: "p", noDirt: "d" };
const SURF = { asphalt: "a", concrete: "c", "court surface": "k", "paving stones": "p", paved: "v", unknown: "x" };
const HLV = { gentle: "g", mellow: "m", solid: "s", steep: "t", "very steep": "v" };
const FLT = { court: "c", parking: "p", schoolyard: "s" };
const BASEC = { bike: "c", terrain: "t", satellite: "s" };
const inv = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [v, k]));
const LINK = {};
(() => {
  const raw = location.hash.slice(1); if (!raw.includes("=")) return;
  for (const part of raw.split("&")) { const i = part.indexOf("="); if (i > 0) LINK[part.slice(0, i)] = decodeURIComponent(part.slice(i + 1)); }
  const view = LINK.m || LINK.v;
  if (view) { const [la, lo, z] = view.split(",").map(Number); if (isFinite(la) && isFinite(lo)) st.view = { c: [la, lo], z: isFinite(z) ? z : 15 }; }
  if (LINK.c !== undefined) { const ic = inv(CAT); for (const k of Object.keys(st.on)) st.on[k] = 0; for (const ch of LINK.c) if (ic[ch]) st.on[ic[ch]] = 1; }
  else if (LINK.on !== undefined) { const on = new Set(LINK.on.split(".")); for (const k of Object.keys(st.on)) st.on[k] = on.has(k) ? 1 : 0; }
  else Object.assign(st.on, ONDEF);
  st.min = +(LINK.r || LINK.min) || 1;
  const F = JSON.parse(JSON.stringify(FDEF));
  if (LINK.n) { const [a, z] = LINK.n.split("-").map(Number); F.nMin = a || 0; F.nMax = isFinite(z) ? z : 99; }
  if (LINK.t) F.stepType = LINK.t === "s" ? "short" : LINK.t === "n" ? "stairs" : "any";
  const iflag = inv(FLAG); for (const ch of LINK.q || "") if (iflag[ch]) F[iflag[ch]] = true;
  for (const [key, map_, g] of [["u", SURF, "surf"], ["h", HLV, "hillLv"], ["y", FLT, "flatType"]]) { const im = inv(map_); for (const ch of LINK[key] || "") if (im[ch]) F[g][im[ch]] = false; }
  if (LINK.k) F.hub = LINK.k === "b" ? "Bagarmossen" : LINK.k === "k" ? "Kärrtorp" : "any";
  st.f = F;
  st.base = inv(BASEC)[LINK.b] || LINK.b || "streets"; st.sat = !!LINK.o; if (LINK.o) st.satOp = Math.min(1, (+LINK.o || 6) / 10); st.surf = LINK.w === "1";
})();
let lastHash = location.hash, hashT;
function linkHash() {
  const c = map.getCenter(), parts = [`m=${c.lat.toFixed(4)},${c.lng.toFixed(4)},${map.getZoom()}`], F = st.f;
  if (Object.keys(CAT).some((k) => !!st.on[k] !== !!ONDEF[k])) parts.push(`c=${Object.keys(CAT).filter((k) => st.on[k]).map((k) => CAT[k]).join("")}`);
  if (st.min > 1) parts.push(`r=${st.min}`);
  if (F.nMin !== 0 || F.nMax !== 99) parts.push(`n=${F.nMin}-${F.nMax}`);
  if (F.stepType !== "any") parts.push(`t=${F.stepType === "short" ? "s" : "n"}`);
  const q = Object.keys(FLAG).filter((k) => F[k]).map((k) => FLAG[k]).join(""); if (q) parts.push(`q=${q}`);
  for (const [key, map_, g] of [["u", SURF, "surf"], ["h", HLV, "hillLv"], ["y", FLT, "flatType"]]) { const off = Object.keys(map_).filter((k) => !F[g][k]).map((k) => map_[k]).join(""); if (off) parts.push(`${key}=${off}`); }
  if (F.hub !== "any") parts.push(`k=${F.hub === "Bagarmossen" ? "b" : "k"}`);
  if (st.base && st.base !== "streets") parts.push(`b=${BASEC[st.base] || st.base}`);
  if (st.sat) parts.push(`o=${Math.round((st.satOp || 0.6) * 10)}`);
  if (st.surf) parts.push("w=1");
  if (sel && sel.id === "plan" && sel.ends) parts.push(`p=${sel.ends.flat().map((x) => x.toFixed(4)).join(",")}`);
  else if (sel && sel.id !== "plan") parts.push(`s=${encodeURIComponent(sel.id)}`);
  return "#" + parts.join("&");
}
function syncHash() { clearTimeout(hashT); hashT = setTimeout(() => { try { lastHash = linkHash(); history.replaceState(null, "", lastHash); } catch (e) {} }, 250); }
window.addEventListener("hashchange", () => { if (location.hash !== lastHash) location.reload(); });  // a pasted link opens as that link
async function shareLink(title) {
  const url = location.href.split("#")[0] + linkHash();
  try { if (navigator.share && matchMedia("(pointer:coarse)").matches) { await navigator.share({ title: title || "Skate Map", url }); return "Shared"; } } catch (e) { if (e.name === "AbortError") return ""; }
  try { await navigator.clipboard.writeText(url); return "Link copied"; } catch (e) { prompt("Copy this link", url); return ""; }
}
let spots = [], byId = new Map(), me = null, sel = null, mode = null;
const colorOf = (s) => css(SUBC[s.sub] || KINDS[s.k].c);

// ---------- map + layers ----------
const map = L.map("map", { zoomControl: false, maxZoom: 20, minZoom: 5 }).setView(st.view?.c || [59.276, 18.13], st.view?.z || 14);
L.control.zoom({ position: "bottomright" }).addTo(map);
map.attributionControl.addAttribution('Elevation <a href="https://mapterhorn.com/attribution" target="_blank" rel="noopener">© Mapterhorn</a>');
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
map.createPane("sat"); map.getPane("sat").style.zIndex = 250; map.getPane("sat").style.pointerEvents = "none";
const sat = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { pane: "sat", maxZoom: 20, maxNativeZoom: 19, opacity: st.satOp || 0.6, attribution: "Imagery © Esri" });
function setSat(on) { $("satOn").checked = on; if (on) sat.addTo(map); else sat.remove(); st.sat = on; save(); }
$("satOn").onchange = (e) => setSat(e.target.checked);
$("satOp").value = st.satOp || 0.6;
$("satOp").oninput = (e) => { st.satOp = +e.target.value; sat.setOpacity(st.satOp); if (!st.sat) setSat(true); save(); };
setBase(st.base || "streets"); setSat(!!st.sat);
$("bLayers").onclick = () => { $("layers").hidden = !$("layers").hidden; $("bLayers").classList.toggle("on", !$("layers").hidden); if (!$("layers").hidden) $("filters").hidden = true; };
map.on("click", () => { if (!$("layers").hidden) { $("layers").hidden = true; $("bLayers").classList.remove("on"); } if (!$("filters").hidden) $("filters").hidden = true; });

const R = L.canvas({ padding: 0.3, tolerance: 8 });
map.createPane("hi"); map.getPane("hi").style.zIndex = 450; map.getPane("hi").style.pointerEvents = "none";  // never block taps on the spots below
const RH = L.canvas({ padding: 0.3, pane: "hi" });  // selected spot/route is drawn on its own layer above everything
function darken(c, f = 0.62) {
  const m = c.match(/^#([0-9a-f]{6})$/i); if (!m) return c;
  const n = parseInt(m[1], 16); return `rgb(${Math.round((n >> 16) * f)},${Math.round(((n >> 8) & 255) * f)},${Math.round((n & 255) * f)})`;
}
const surfLayer = L.layerGroup(), spotLayer = L.layerGroup().addTo(map), lineLayer = L.layerGroup().addTo(map), hiLayer = L.layerGroup().addTo(map), routeLayer = L.layerGroup().addTo(map);
let surfData = { "1": [], "2": [], "3": [] };
function drawSurf() { surfLayer.clearLayers(); for (const q of ["1", "2", "3"]) if (surfData[q].length) L.polyline(surfData[q], { renderer: R, color: css("--q" + q), weight: q === "3" ? 3.5 : 3, opacity: .9, interactive: false }).addTo(surfLayer); }
function setSurf(on) { $("surfOn").checked = on; if (on) surfLayer.addTo(map); else surfLayer.remove(); st.surf = on; save(); }
$("surfOn").onchange = (e) => setSurf(e.target.checked);

// rating filter
function drawRate() { $("minRate").querySelectorAll("button").forEach((b) => b.classList.toggle("on", +b.dataset.v === st.min)); }
$("minRate").onclick = (e) => { const b = e.target.closest("button"); if (!b) return; e.stopPropagation(); st.min = +b.dataset.v; save(); drawRate(); drawChips(); render(); };
drawRate();

// ---------- chips ----------
function drawChips() {
  const c = {}; for (const s of spots) c[s.k] = (c[s.k] || 0) + 1;
  const allOn = Object.keys(KINDS).every((k) => st.on[k] || !c[k]);
  const nf = activeFilters();
  $("chips").innerHTML = `<span class="chip filt ${nf ? "act" : ""}"><button data-filters><svg viewBox="0 0 24 24" width="15" height="15" style="stroke:currentColor;fill:none;stroke-width:2.2"><path d="M3 5h18M6 12h12M10 19h4"/></svg>Filters${nf ? ` <span class="n">${nf}</span>` : ""}</button></span><span class="chip all ${allOn ? "" : "off"}"><button data-all>All</button></span>` +
    Object.entries(KINDS).filter(([k]) => c[k] || k === "mine").map(([k, v]) =>
      `<span class="chip ${st.on[k] ? "" : "off"}" style="--c:var(${v.c})"><button class="tog" data-k="${k}" aria-pressed="${!!st.on[k]}" title="Show or hide ${v.l.toLowerCase()}"><span class="dot"></span>${v.l}<span class="n">${c[k] || 0}</span></button><button class="only" data-only="${k}" title="Show only ${v.l.toLowerCase()}">only</button></span>`).join("");
}
$("chips").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  if (b.dataset.filters !== undefined) { toggleFilters(); return; }
  if (b.dataset.all !== undefined) { for (const k in KINDS) st.on[k] = 1; }
  else if (b.dataset.only) { for (const k in KINDS) st.on[k] = k === b.dataset.only ? 1 : 0; }
  else { const k = b.dataset.k; st.on[k] = st.on[k] ? 0 : 1; }
  save(); drawChips(); drawCtx(); render();
};

// ---------- filter panel ----------
function activeFilters() {
  let n = 0; const F = st.f;
  for (const k of ["nMin", "nMax", "stepType", "rail", "pavedEnds", "hasCount", "carFree", "bigPlaza", "noDirt", "hub"]) if (JSON.stringify(F[k]) !== JSON.stringify(FDEF[k])) n++;
  for (const g of ["flatType", "surf", "hillLv"]) if (Object.values(F[g]).some((v) => !v)) n++;
  if (st.min > 1) n++;
  return n;
}
function toggleFilters(force) {
  const show = force ?? $("filters").hidden;
  $("filters").hidden = !show; if (show) { $("layers").hidden = true; $("bLayers").classList.remove("on"); drawFilters(); }
}
const LABELS = { surf: { asphalt: "Asphalt", concrete: "Concrete", "court surface": "Court surface", "paving stones": "Paving stones", paved: "Paved (type unknown)", unknown: "Not mapped" },
  hillLv: { gentle: "Gentle 2.5–4 %", mellow: "Mellow 4–6 %", solid: "Solid 6–9 %", steep: "Steep 9–13 %", "very steep": "Very steep 13 %+" }, flatType: { court: "Courts", parking: "Car parks", schoolyard: "Schoolyards" } };
function drawFilters() {
  const F = st.f, c = {}; for (const s of spots) c[s.k] = (c[s.k] || 0) + 1;
  $("fCats").innerHTML = Object.entries(KINDS).filter(([k]) => c[k] || k === "mine").map(([k, v]) =>
    `<div class="fcat" style="--c:var(${v.c})"><label><input type="checkbox" data-cat="${k}" ${st.on[k] ? "checked" : ""}><span class="dot"></span>${v.l}<span class="n">${c[k] || 0}</span></label><button class="only" data-only="${k}">only</button></div>`).join("");
  $("nMin").value = F.nMin; $("nMax").value = F.nMax;
  for (const id of ["hasCount", "rail", "pavedEnds", "carFree", "bigPlaza", "noDirt"]) $(id).checked = !!F[id];
  for (const g of ["surf", "hillLv", "flatType"]) $(g).innerHTML = Object.entries(LABELS[g]).map(([k, l]) => `<button data-g="${g}" data-k="${k}" class="${F[g][k] ? "on" : ""}">${l}</button>`).join("");
  $("stepType").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === F.stepType));
  $("hub").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.v === F.hub));
  $("nPreset").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.r === `${F.nMin},${F.nMax}`));
  drawRate();
}
function applyF() { save(); drawFilters(); drawChips(); drawCtx(); render(); }
function fClick(e) {
  const b = e.target.closest("button"); if (!b) return; const F = st.f;
  if (b.id === "fReset") { st.f = JSON.parse(JSON.stringify(FDEF)); st.min = 1; for (const k in KINDS) st.on[k] = 1; st.on.flat = 0; st.on.route = 0; }
  else if (b.dataset.only) { for (const k in KINDS) st.on[k] = k === b.dataset.only ? 1 : 0; }
  else if (b.dataset.g) F[b.dataset.g][b.dataset.k] = !F[b.dataset.g][b.dataset.k];
  else if (b.dataset.r) { const [a, z] = b.dataset.r.split(",").map(Number); F.nMin = a; F.nMax = z; }
  else if ((b.parentElement.dataset.seg || b.parentElement.id) === "stepType") { F.stepType = b.dataset.v; }
  else if ((b.parentElement.dataset.seg || b.parentElement.id) === "hub") { F.hub = b.dataset.v; if (F.hub !== "any") st.on.route = 1; }
  else if (b.dataset.openfilters !== undefined) { toggleFilters(true); return; }
  else return;
  applyF();
}
function fChange(e) {
  const t = e.target, F = st.f, key = t.dataset.fid || t.id;
  if (t.dataset.cat) st.on[t.dataset.cat] = t.checked ? 1 : 0;
  else if (key === "nMin" || key === "nMax") { F[key] = Math.max(0, Math.min(99, parseInt(t.value) || (key === "nMin" ? 0 : 99))); }
  else if (t.type === "checkbox") F[key] = t.checked;
  applyF();
}
$("filters").addEventListener("click", fClick); $("filters").addEventListener("change", fChange);
$("ctx").addEventListener("click", fClick); $("ctx").addEventListener("change", fChange);
// quick filters for the category you are looking at (shown when only one category is on)
function drawCtx() {
  const on = Object.keys(KINDS).filter((k) => st.on[k]);
  const k = on.length === 1 ? on[0] : null, F = st.f;
  const tg = (g) => Object.entries(LABELS[g]).map(([kk, l]) => `<button data-g="${g}" data-k="${kk}" class="${F[g][kk] ? "on" : ""}">${l}</button>`).join("");
  const ck = (id, l) => `<label class="ck"><input type="checkbox" data-fid="${id}" ${F[id] ? "checked" : ""}> ${l}</label>`;
  const seg = (id, opts) => `<div class="seg" data-seg="${id}">${opts.map(([v, l]) => `<button data-v="${v}" class="${F[id] === v ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const rng = `<div class="tgs">${[["1,4", "1–4 steps"], ["5,10", "5–10"], ["11,20", "11–20"], ["21,99", "21+"], ["0,99", "Any"]].map(([r, l]) => `<button data-r="${r}" class="${`${F.nMin},${F.nMax}` === r ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const body = {
    steps: rng + seg("stepType", [["any", "Any"], ["short", "Short sets"], ["stairs", "Normal"]]) + ck("rail", "Has a handrail") + ck("pavedEnds", "Paved at both ends"),
    longsteps: rng + ck("rail", "Has a handrail") + ck("pavedEnds", "Paved at both ends"),
    hill: `<div class="tgs">${tg("hillLv")}</div>` + ck("carFree", "No car traffic"),
    flat: `<div class="tgs">${tg("flatType")}</div><div class="tgs">${tg("surf")}</div>`,
    plaza: ck("bigPlaza", "Only big smooth plazas") + `<div class="tgs">${tg("surf")}</div>`,
    route: seg("hub", [["any", "All"], ["Bagarmossen", "Loops from Bagis"], ["Kärrtorp", "Loops from Kärrtorp"]]),
    pump: ck("noDirt", "Hide dirt BMX tracks"),
  }[k];
  if (!k || !body) { $("ctx").hidden = true; return; }
  $("ctx").innerHTML = `<div class="ctxh"><span>${KINDS[k].l}</span><button data-openfilters>All filters</button></div>${body}`;
  $("ctx").hidden = false;
}

// ---------- data ----------
function addSpots(arr) { for (const s of arr) { if (s.k === "steps" && s.sub === "long") s.k = "longsteps"; if (byId.has(s.id) || (s.osm && byId.has("osm:" + s.osm + s.k))) continue; byId.set(s.id, s); if (s.osm) byId.set("osm:" + s.osm + s.k, s); spots.push(s); } }
function mineSpots() { return st.mine.map((m) => Object.assign({ k: "mine", s: 5 }, m)); }
function refreshMine() { spots = spots.filter((s) => s.k !== "mine"); for (const [k, v] of byId) if (v.k === "mine") byId.delete(k); addSpots(mineSpots()); }
const G = { n: [], e: [] };
async function loadRegions() {
  for (const r of REGIONS) {
    try {
      const d = await (await fetch(`regions/${r}.json?v=2026-11-14h`)).json();
      addSpots(d.spots);
      for (const q of ["1", "2", "3"]) surfData[q].push(...d.surf[q]);
      const off = G.n.length; G.n.push(...d.graph.n); for (const [a, b, l, q] of d.graph.e) G.e.push([a + off, b + off, l, q]);
      drawChips(); render(); drawSurf();
    } catch (e) { console.warn("region failed", r, e); }
  }
  buildGraph();
  if (LINK.s && byId.get(LINK.s)) open(byId.get(LINK.s));
  else if (LINK.p) { const n = LINK.p.split(",").map(Number); if (n.length === 4) { const A = [n[0], n[1]], B = [n[2], n[3]], r = plan(A, B); if (r) showRoute(r, A, B); } }
  if (LINK.m || LINK.v) { const [la, lo, z] = (LINK.m || LINK.v).split(",").map(Number); map.setView([la, lo], z); }  // keep the shared view, even after opening the spot
}

// ---------- render markers + list ----------
const zoomMin = () => (map.getZoom() <= 12 ? 5 : map.getZoom() <= 14 ? 4 : 1);
function passes(s) {
  const F = st.f, f = s.f || {};
  if (s.k === "steps" || s.k === "longsteps") {
    if (F.hasCount && f.n == null) return false;
    if (f.n != null && (f.n < F.nMin || f.n > F.nMax)) return false;
    if (s.k === "steps" && F.stepType !== "any" && F.stepType !== "long" && (s.sub || "stairs") !== F.stepType) return false;
    if (F.rail && !f.rail) return false;
    if (F.pavedEnds && !f.ends) return false;
    if (f.su && !F.surf[f.su]) return false;
  }
  if (s.k === "flat") { if (!F.flatType[s.sub]) return false; if (f.su && !F.surf[f.su]) return false; }
  if (s.k === "plaza") { if (F.bigPlaza && s.sub !== "smoothplaza") return false; if (f.su && !F.surf[f.su]) return false; }
  if (s.k === "rink" && f.su && !F.surf[f.su]) return false;
  if (s.k === "hill") { if (f.lv && !F.hillLv[f.lv]) return false; if (F.carFree && !f.cf) return false; if (f.su && !F.surf[f.su]) return false; }
  if (s.k === "pump" && F.noDirt && f.dirt) return false;
  if (s.k === "route" && F.hub !== "any" && f.hub !== F.hub) return false;
  return true;
}
const THIN = new Set(["steps", "hill", "flat", "plaza"]);  // only the big categories are thinned out when zoomed out
function visible() { return spots.filter((s) => st.on[s.k] && passes(s) && (s.k === "mine" || s.s >= st.min)); }
function render() {
  spotLayer.clearLayers(); lineLayer.clearLayers();
  const vs = visible(), z = map.getZoom();
  const rad = z >= 17 ? 9 : z >= 15 ? 7 : z >= 14 ? 5 : z >= 13 ? 4 : 3;
  const ink = css("--panel");
  for (const s of vs) {
    const col = colorOf(s);
    const focus = sel && (sel.k === "route" || sel.k === "hill") && sel.id !== s.id;
    if ((s.k === "route" || s.k === "hill") && s.g && z >= 13) L.polyline(s.g, { renderer: R, color: col, weight: s.k === "route" ? 4 : 5, opacity: focus ? 0.12 : s.k === "route" ? .55 : .8 }).on("click", (e) => pick(s, e)).addTo(lineLayer);
    if (s.k === "hill" && s.g && z >= 15 && !focus) arrows(s.g, col, z, lineLayer, R);
    if (s.k === "mine") L.marker(s.p, { icon: L.divIcon({ className: "", html: `<div class="mine-pin"></div>`, iconSize: [16, 16] }), title: s.n }).on("click", (e) => pick(s, e)).addTo(spotLayer);
    else L.circleMarker(s.p, { renderer: R, radius: s.s >= 5 ? rad + 1.5 : rad, color: ink, weight: z >= 14 ? 2 : 1, fillColor: col, fillOpacity: 1 }).on("click", (e) => pick(s, e)).addTo(spotLayer);
  }
  drawList(vs);
}
// downhill chevrons along a hill (its geometry starts at the top)
function arrows(g, col, z, layer, rend, every0) {
  const pts = g.map((p) => map.latLngToLayerPoint(p)), every = every0 || (z >= 17 ? 55 : 70), size = z >= 17 ? 3.5 : 3;
  const dk = darken(col);
  let acc = every / 2;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1], d = a.distanceTo(b); if (!d) continue;
    const ux = (b.x - a.x) / d, uy = (b.y - a.y) / d;
    while (acc <= d) {
      const c = L.point(a.x + ux * acc, a.y + uy * acc), tip = L.point(c.x + ux * size, c.y + uy * size);
      const l1 = L.point(c.x - ux * size - uy * size, c.y - uy * size + ux * size), l2 = L.point(c.x - ux * size + uy * size, c.y - uy * size - ux * size);
      L.polyline([map.layerPointToLatLng(l1), map.layerPointToLatLng(tip), map.layerPointToLatLng(l2)], { renderer: rend, color: dk, weight: 1.5, opacity: .9, interactive: false, lineCap: "round", lineJoin: "round" }).addTo(layer);
      acc += every;
    }
    acc -= d;
  }
}
function drawList(vs) {
  vs = vs || visible();
  const ref = me || [map.getCenter().lat, map.getCenter().lng];
  const b = map.getBounds().pad(0.2);
  let inView = vs.filter((s) => b.contains(s.p));
  inView.forEach((s) => (s._d = dist(ref, s.p)));
  inView.sort((a, c) => a._d - c._d);
  $("sheetTitle").textContent = $("sheet").classList.contains("collapsed") ? "List" : (me ? "Spots near you" : "Spots in view");
  $("sheetSub").textContent = `${inView.length}`;
  if (!inView.length) { $("list").innerHTML = `<div class="empty">No spots here with these filters. Turn on more categories, zoom out, or tap the search button on the right to find spots in this area.</div>`; return; }
  $("list").innerHTML = inView.slice(0, 120).map((s) => {
    const n = st.notes[s.id];
    return `<button class="item ${sel && sel.id === s.id ? "sel" : ""}" data-id="${esc(s.id)}" style="--c:${colorOf(s)}"><span class="dot"></span><span style="min-width:0"><div class="t">${esc(s.n)}${n && n.status ? `<span class="tag ${n.status}">${esc(NOTE[n.status])}</span>` : ""}</div><div class="w">${esc(s.w)}</div></span><span class="meta">${fmtD(s._d)}<br><span class="stars">${stars(s.s)}</span></span></button>`;
  }).join("") + (inView.length > 120 ? `<div class="empty">Showing the 120 closest of ${inView.length}.</div>` : "");
}
$("list").onclick = (e) => { const b = e.target.closest(".item"); if (b) open(byId.get(b.dataset.id), true); };
$("sheetBar").onclick = () => { const c = $("sheet").classList.toggle("collapsed"); $("sheetBar").setAttribute("aria-expanded", !c); $("sheetTitle").textContent = c ? "List" : (me ? "Spots near you" : "Spots in view"); drawList(); };
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
  if (s.g) {
    L.polyline(s.g, { renderer: RH, color: css("--panel"), weight: 11, opacity: .95, interactive: false }).addTo(hiLayer);
    L.polyline(s.g, { renderer: RH, color: col, weight: 6, opacity: 1, interactive: false }).addTo(hiLayer);
    if (s.k === "route" || s.k === "hill") arrows(s.g, col, Math.max(map.getZoom(), 15), hiLayer, RH, s.k === "route" ? 90 : 50);
  }
  L.circleMarker(s.p, { renderer: RH, radius: 13, color: col, weight: 3, fill: false, interactive: false }).addTo(hiLayer);
  const narrow = innerWidth <= 760;
  if (fly || narrow) {
    if (s.g && s.g.length > 2 && s.k !== "steps") map.fitBounds(L.latLngBounds(s.g), { paddingTopLeft: narrow ? [20, 20] : [430, 40], paddingBottomRight: narrow ? [20, innerHeight * 0.6] : [490, 40], maxZoom: 18 });
    else { const z = Math.max(map.getZoom(), 17); const pt = map.project(s.p, z); map.setView(map.unproject(narrow ? pt.add([0, innerHeight * 0.28]) : pt.add([30, 0]), z), z); }
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
        <button class="btn primary" id="cShare">Share link</button>
        <a href="${svUrl(s)}" target="_blank" rel="noopener">Open Street View</a>
        <a href="https://www.google.com/maps/dir/?api=1&destination=${la},${lo}&travelmode=walking" target="_blank" rel="noopener">Directions</a>
        <a href="https://www.google.com/maps/search/?api=1&query=${la},${lo}" target="_blank" rel="noopener">Google Maps</a>
        ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">City page</a>` : ""}
        ${s.tf ? `<a href="${esc(s.tf)}" target="_blank" rel="noopener">Trucks &amp; Fins</a>` : ""}
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
  if (s.k === "route" || s.k === "hill") render();
  $("card").querySelector(".x").onclick = closeCard;
  $("cShare").onclick = async () => { const m = await shareLink(s.n); if (m) hint(m, 2000); };
  syncHash();
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
function closeCard() { setTimeout(syncHash); const was = sel; if (was && was.id === "plan") routeLayer.clearLayers(); document.body.classList.remove("card-open"); $("card").hidden = true; $("card").innerHTML = ""; hiLayer.clearLayers(); sel = null; if (was && (was.k === "route" || was.k === "hill")) render(); else drawList(); }

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
  if (!mode && !$("card").hidden) { closeCard(); return; }  // tapping empty map deselects
  if (mode === "add") { setMode(null); addForm(p); return; }
  if (mode === "route") {
    if (!routeA) { routeA = p; routeLayer.clearLayers(); L.circleMarker(p, { radius: 8, color: css("--c-route"), fillOpacity: 1 }).addTo(routeLayer); hint("Now tap the destination"); return; }
    const A = routeA, r = plan(routeA, p); setMode(null); routeA = null;
    if (!r) { hint("No smooth path found between those points. Routes work inside Söder and Vallentuna–Täby.", 4500); return; }
    showRoute(r, A, p);
  }
}
function pick(s, e) { L.DomEvent.stop(e); if (mode) tap([e.latlng.lat, e.latlng.lng]); else if (sel && sel.id === s.id) closeCard(); else open(s); }
function addForm(p) {
  sel = null; hiLayer.clearLayers(); L.circleMarker(p, { radius: 9, color: css("--accent"), fillOpacity: .6 }).addTo(hiLayer);
  $("card").innerHTML = `<button class="x" aria-label="Close" style="background:var(--hover);color:var(--ink)">×</button><div class="body" style="padding-top:18px">
    <h2>New spot</h2>
    <label class="small" for="eName">Name</label><input type="text" id="eName" placeholder="E.g. Low stairs by the library">
    <label class="small" for="eType">What is here?</label>
    <select id="eType">${["Stairs", "Stairs with long, low steps", "Ice rink in winter", "Smooth plaza", "Low rail", "Grindable curb", "Ledge / bench", "Hill", "Powerslide spot", "Jump / drop", "Bank / transition", "Manual pad", "Other"].map((x) => `<option>${x}</option>`).join("")}</select>
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
function showRoute(r, A, B) {
  routeLayer.clearLayers();
  const g = r.path.map((i) => [G.n[i][0], G.n[i][1]]);
  L.polyline(g, { renderer: R, color: css("--c-route"), weight: 6, opacity: .9 }).addTo(routeLayer);
  L.circleMarker(g[0], { radius: 8, color: css("--c-route"), fillOpacity: 1 }).addTo(routeLayer);
  L.circleMarker(g[g.length - 1], { radius: 8, color: css("--accent"), fillOpacity: 1 }).addTo(routeLayer);
  const hs = r.path.map((i) => G.n[i][2]).filter((x) => x != null), mn = Math.min(...hs), step = Math.max(1, Math.floor(hs.length / 80));
  const s = { id: "plan", ends: A && B ? [A, B] : null, k: "route", sub: "plan", n: "Your route", p: g[0], g, s: r.good / r.L > .75 ? 5 : r.good / r.L > .5 ? 4 : 3,
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
  const BAD = /^(gravel|fine_gravel|compacted|dirt|ground|earth|grass|sand|unpaved|mud|pebblestone|woodchips|wood|sett|cobblestone|unhewn_cobblestone|grass_paver|rock)$/;
  const scat = (s) => s === "asphalt" ? "asphalt" : /^concrete/.test(s || "") ? "concrete" : /acrylic|tartan|rubber/.test(s || "") ? "court surface" : /paving_stones|stone|granite/.test(s || "") ? "paving stones" : s === "paved" ? "paved" : "unknown";
  for (const el of els) {
    const t = el.tags || {}, gg = g(el); if (!gg.length) continue;
    const nm = t.name || "", sport = t.sport || "", surf = t.surface;
    if (BAD.test(surf || "") && !/bmx/i.test(sport + nm) || /bad|horrible|impassable/.test(t.smoothness || "")) continue;
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
      add(el, "steps", nm || { short: "Short stairs", long: "Long-tread stairs", stairs: "Stairs" }[sub], s, why.join("; "), Object.assign({ Length: `${Math.round(L)} m`, Handrail: t.handrail || "unknown", Surface: surf || "unknown" }, n ? { Steps: String(n) } : {}), gg, { sub, f: { n, tr: tread ? Math.round(tread * 100) : null, rail: /yes|both|left|right/.test(t.handrail || ""), su: scat(surf), ends: false } }); continue;
    }
    if (t.leisure === "pitch") { if (surf && !PAVED.has(surf) && surf !== "acrylic") continue; add(el, "flat", nm || "Court", surf ? 4 : 3, "Smooth, flat and open: good for powerslides, manuals and flatground", { Sport: sport, Surface: surf || "unknown" }, gg, { sub: "court", f: { su: scat(surf) } }); continue; }
    if (t.amenity === "parking") { const A = area(gg); if (A < 1800 || (surf && !PAVED.has(surf)) || /underground|multi-storey|rooftop/.test(t.parking || "")) continue; add(el, "flat", nm || "Large car park", 3 + (A > 5000 ? 1 : 0), `Big open lot (${Math.round(A)} m²) for powerslides when it is empty`, { Area: `${Math.round(A)} m²`, Surface: surf || "unknown" }, gg, { sub: "parking", f: { su: scat(surf) } }); continue; }
    if (t.place === "square" || t.highway === "pedestrian") { if (surf && !PAVED.has(surf)) continue; add(el, "plaza", nm || "Square", 3, "Square or pedestrian street: often ledges, benches and low walls", { Surface: surf || "unknown" }, gg, { f: { su: scat(surf) } }); continue; }
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

$("bShareView").onclick = async (e) => { e.stopPropagation(); const m = await shareLink(); if (m) hint(m, 2000); };
// Done buttons on the panels, and keep touches on panels from moving the map
document.querySelectorAll("[data-close]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); $(b.dataset.close).hidden = true; if (b.dataset.close === "layers") $("bLayers").classList.remove("on"); }));
for (const el of document.querySelectorAll(".top, .fab, .pop, .sheet, .card, .hint")) { L.DomEvent.disableClickPropagation(el); L.DomEvent.disableScrollPropagation(el); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { if (mode) setMode(null); else if (!$("filters").hidden) $("filters").hidden = true; else if (!$("layers").hidden) { $("layers").hidden = true; $("bLayers").classList.remove("on"); } else if (!$("card").hidden) closeCard(); } });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { drawSurf(); render(); });

// ---------- start ----------
addSpots(mineSpots()); drawChips(); drawCtx(); render(); setSurf(!!st.surf);
loadRegions();
})();
