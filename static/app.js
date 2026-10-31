"use strict";
// All user-supplied text is inserted with textContent (never innerHTML), so names and interests cannot inject markup.
const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
async function api(url, opts) {
  const r = await fetch(url, opts);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || "Request failed");
  return d;
}
let msgTimer;
function say(text) {
  const m = $("#msg");
  m.textContent = text || "";
  clearTimeout(msgTimer);
  if (text) msgTimer = setTimeout(() => (m.textContent = ""), 5000);
}
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { say(e.message); } };

const S = {
  nodes: [], byId: {}, edges: [], comms: [], stats: {},
  sel: null, dst: null, focus: null, method: "bfs",
  walk: null, path: null, alpha: 1, hover: null,
  view: { x: 0, y: 0, k: 1 },
};
let timer = null, loadSeq = 0, recSeq = 0;
const cv = $("#cv"), ctx = cv.getContext("2d");
let W = 0, H = 0, dpr = 1;

function resize() {
  const r = cv.getBoundingClientRect();
  dpr = window.devicePixelRatio || 1;
  W = r.width; H = r.height;
  cv.width = W * dpr; cv.height = H * dpr;
}
window.addEventListener("resize", resize);

const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const colorOf = (n) => {
  const c = S.comms[n.community];
  return !c || c.size === 1 ? "#8b93a5" : `hsl(${(n.community * 47) % 360} 65% 52%)`;
};
const radius = (n) => 6 + Math.min(n.degree, 10) * 0.8;
const toWorld = (sx, sy) => ({ x: (sx - W / 2 - S.view.x) / S.view.k, y: (sy - H / 2 - S.view.y) / S.view.k });

// ------------------------------------------------------------- data
const load = guard(async () => {
  const seq = ++loadSeq;
  const g = await api(`/api/graph?threshold=${$("#th").value}&method=${S.method}`);
  if (seq !== loadSeq) return;
  const old = S.byId;
  S.nodes = g.nodes.map((n) => {
    const o = old[n.id];
    n.x = o ? o.x : (Math.random() - 0.5) * 400;
    n.y = o ? o.y : (Math.random() - 0.5) * 400;
    n.vx = n.vy = 0;
    return n;
  });
  S.byId = Object.fromEntries(S.nodes.map((n) => [n.id, n]));
  S.edges = g.edges.map((e) => ({ a: S.byId[e.source], b: S.byId[e.target], w: e.weight, bridge: e.is_bridge }));
  S.comms = g.communities;
  S.stats = g.stats;
  if (!S.byId[S.sel]) S.sel = null;
  if (!S.byId[S.dst]) S.dst = null;
  stopWalk();
  S.path = null;
  S.alpha = 1;
  renderStats(); renderComms(); renderDst(); renderDetail();
});

function renderStats() {
  const s = S.stats, box = $("#stats");
  box.replaceChildren();
  [["Students", s.students], ["Connections", s.connections], ["Communities", s.communities],
   ["Independent", s.independent], ["Modularity", s.modularity], ["Bridge students", s.bridge_students]]
    .forEach(([k, v]) => { const d = el("div", "stat"); d.append(el("b", "", v), el("span", "", k)); box.append(d); });
}

function renderComms() {
  const box = $("#comms");
  box.replaceChildren();
  S.comms.filter((c) => c.size > 1).forEach((c) => {
    const d = el("div", "comm" + (S.focus === c.id ? " on" : ""));
    const head = el("div");
    const dot = el("span", "dot");
    dot.style.background = `hsl(${(c.id * 47) % 360} 65% 52%)`;
    head.append(dot, el("strong", "", `${c.label} (${c.size})`));
    d.append(head, el("div", "small", `Hub: ${S.byId[c.hub] ? S.byId[c.hub].name : "-"} · avg similarity ${c.avg_similarity}`));
    c.top_interests.forEach((i) => d.append(el("span", "tag", i.name)));
    d.addEventListener("click", () => { S.focus = S.focus === c.id ? null : c.id; renderComms(); });
    box.append(d);
  });
  const lone = S.comms.filter((c) => c.size === 1).length;
  if (lone) box.append(el("p", "small", `${lone} independent student${lone > 1 ? "s" : ""} (no similar peers at this threshold).`));
  if (!S.comms.length) box.append(el("p", "muted", "No students yet."));
}

function renderDst() {
  const sel = $("#dst");
  sel.replaceChildren();
  [...S.nodes].sort((a, b) => a.name.localeCompare(b.name)).forEach((n) => {
    const o = el("option", "", n.name); o.value = n.id; sel.append(o);
  });
  if (S.dst != null) sel.value = S.dst;
  S.dst = sel.value ? Number(sel.value) : null;
}

const renderDetail = guard(async () => {
  const box = $("#detail");
  box.replaceChildren();
  const n = S.byId[S.sel];
  if (!n) { box.append(el("p", "muted", "Select a student to see details and suggestions.")); return; }
  box.append(el("h2", "", n.name),
    el("div", "small", `${n.department} · year ${n.year} · ${n.degree} connections · clustering ${n.clustering}${n.is_bridge ? " · bridge student" : ""}`));
  const tags = el("div");
  n.interests.forEach((i) => tags.append(el("span", "tag", i)));
  const del = el("button", "", "Delete student");
  del.addEventListener("click", guard(async () => {
    if (!confirm(`Delete ${n.name}?`)) return;
    await api(`/api/students/${n.id}`, { method: "DELETE" });
    S.sel = null;
    await load();
  }));
  const row = el("div", "row"); row.append(del);
  box.append(tags, row);
  const seq = ++recSeq;
  const rec = await api(`/api/recommend/${n.id}?threshold=${$("#th").value}`);
  if (seq !== recSeq || S.sel !== n.id) return;
  box.append(el("h2", "", "Suggested connections"));
  if (!rec.recommendations.length) box.append(el("p", "muted", "No suggestions."));
  rec.recommendations.forEach((r) => {
    const d = el("div", "rec");
    d.append(el("strong", "", r.name),
      el("div", "small", `${Math.round(r.similarity * 100)}% similar · ${r.hops == null ? "not connected" : r.hops + " hops"}${r.mutual.length ? " · mutual: " + r.mutual.join(", ") : ""}`));
    r.shared.forEach((i) => d.append(el("span", "tag", i)));
    d.addEventListener("click", () => select(r.id));
    box.append(d);
  });
});

function select(id) { S.sel = id; S.path = null; stopWalk(); renderDetail(); }

// ---------------------------------------------------------- walk / path
function stopWalk() { clearInterval(timer); timer = null; S.walk = null; }
const startWalk = guard(async () => {
  if (S.sel == null) return say("Select a student first.");
  const d = await api(`/api/traverse?start=${S.sel}&algo=${S.method}&threshold=${$("#th").value}`);
  stopWalk(); S.path = null;
  S.walk = { steps: d.steps, shown: 0 };
  timer = setInterval(() => {
    S.walk.shown++;
    if (S.walk.shown >= S.walk.steps.length) { clearInterval(timer); timer = null; }
  }, 140);
  say(`${S.method.toUpperCase()} reached ${d.reached} students, up to ${d.max_level} steps away.`);
});
const findPath = guard(async () => {
  if (S.sel == null) return say("Select a student first.");
  const dst = Number($("#dst").value);
  S.dst = dst;
  const d = await api(`/api/path?src=${S.sel}&dst=${dst}&threshold=${$("#th").value}`);
  stopWalk();
  if (!d.path) { S.path = null; return say("No connection between them at this threshold."); }
  S.path = d.path;
  say(`${d.hops} hop${d.hops === 1 ? "" : "s"}: ${d.path.map((i) => S.byId[i].name).join(" → ")}`);
});

// -------------------------------------------------------------- layout
function tick() {
  const N = S.nodes, a = S.alpha;
  for (let i = 0; i < N.length; i++) {
    for (let j = i + 1; j < N.length; j++) {
      let dx = N[j].x - N[i].x, dy = N[j].y - N[i].y;
      const d2 = dx * dx + dy * dy + 0.01;
      if (d2 > 120000) continue;
      const f = (2600 / d2) * a, d = Math.sqrt(d2);
      dx = (dx / d) * f; dy = (dy / d) * f;
      N[i].vx -= dx; N[i].vy -= dy; N[j].vx += dx; N[j].vy += dy;
    }
  }
  for (const e of S.edges) {
    const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
    const f = (d - 70) * 0.03 * (0.5 + e.w) * a, fx = (dx / d) * f, fy = (dy / d) * f;
    e.a.vx += fx; e.a.vy += fy; e.b.vx -= fx; e.b.vy -= fy;
  }
  for (const n of N) {
    if (n.fixed) { n.vx = n.vy = 0; continue; }
    n.vx = (n.vx - n.x * 0.012 * a) * 0.82;
    n.vy = (n.vy - n.y * 0.012 * a) * 0.82;
    n.x += n.vx; n.y += n.vy;
  }
  S.alpha *= 0.985;
}

// ---------------------------------------------------------------- draw
function draw() {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const v = S.view;
  ctx.setTransform(dpr * v.k, 0, 0, dpr * v.k, dpr * (W / 2 + v.x), dpr * (H / 2 + v.y));
  const ink = cssVar("--ink"), accent = cssVar("--accent"), warn = cssVar("--warn"), line = cssVar("--line");
  const inFocus = (n) => S.focus == null || n.community === S.focus;
  const shown = S.walk ? new Map(S.walk.steps.slice(0, S.walk.shown).map((s, i) => [s.node, i + 1])) : null;
  const walkEdge = new Set();
  if (S.walk) S.walk.steps.slice(0, S.walk.shown).forEach((s) => s.from != null && walkEdge.add(s.from + "-" + s.node));
  const pathEdge = new Set();
  if (S.path) for (let i = 0; i + 1 < S.path.length; i++) pathEdge.add(S.path[i] + "-" + S.path[i + 1]).add(S.path[i + 1] + "-" + S.path[i]);

  for (const e of S.edges) {
    const hot = pathEdge.has(e.a.id + "-" + e.b.id) || walkEdge.has(e.a.id + "-" + e.b.id) || walkEdge.has(e.b.id + "-" + e.a.id);
    ctx.globalAlpha = hot ? 1 : inFocus(e.a) && inFocus(e.b) ? 0.55 : 0.08;
    ctx.strokeStyle = hot ? accent : e.bridge ? warn : line;
    ctx.lineWidth = (hot ? 3 : 0.6 + e.w * 2) / v.k * Math.max(v.k, 1);
    ctx.setLineDash(e.bridge && !hot ? [5, 4] : []);
    ctx.beginPath(); ctx.moveTo(e.a.x, e.a.y); ctx.lineTo(e.b.x, e.b.y); ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.font = `${12 / Math.sqrt(v.k)}px system-ui, sans-serif`;
  ctx.textAlign = "center";
  for (const n of S.nodes) {
    const r = radius(n), onPath = S.path && S.path.includes(n.id);
    ctx.globalAlpha = inFocus(n) ? 1 : 0.15;
    ctx.fillStyle = colorOf(n);
    ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 6.2832); ctx.fill();
    if (n.is_bridge) { ctx.strokeStyle = warn; ctx.lineWidth = 2; ctx.stroke(); }
    if (n.id === S.sel || n.id === S.dst || onPath || (shown && shown.has(n.id))) {
      ctx.strokeStyle = n.id === S.sel ? ink : accent; ctx.lineWidth = n.id === S.sel ? 3 : 2;
      ctx.beginPath(); ctx.arc(n.x, n.y, r + 3, 0, 6.2832); ctx.stroke();
    }
    ctx.fillStyle = ink;
    if (shown && shown.has(n.id)) { ctx.fillStyle = "#fff"; ctx.fillText(shown.get(n.id), n.x, n.y + 4); ctx.fillStyle = ink; }
    else if (v.k > 1.5 || n.id === S.sel || n.id === S.hover || onPath) ctx.fillText(n.name, n.x, n.y - r - 5);
  }
  ctx.globalAlpha = 1;
}
function frame() {
  if (S.alpha > 0.02) tick();
  draw();
  requestAnimationFrame(frame);
}

// --------------------------------------------------------- interaction
function hit(sx, sy) {
  const p = toWorld(sx, sy);
  let best = null, bd = Infinity;
  for (const n of S.nodes) {
    const d = Math.hypot(n.x - p.x, n.y - p.y);
    if (d <= radius(n) + 3 / S.view.k && d < bd) { best = n; bd = d; }
  }
  return best;
}
let drag = null;
const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
cv.addEventListener("pointerdown", (e) => {
  const [x, y] = pos(e), n = hit(x, y);
  drag = { n, x, y, moved: false, vx: S.view.x, vy: S.view.y };
  if (n) n.fixed = true;
  cv.setPointerCapture(e.pointerId);
});
cv.addEventListener("pointermove", (e) => {
  const [x, y] = pos(e);
  if (!drag) { const h = hit(x, y); S.hover = h ? h.id : null; cv.style.cursor = h ? "pointer" : "grab"; return; }
  if (Math.hypot(x - drag.x, y - drag.y) > 3) drag.moved = true;
  if (drag.n && drag.moved) { const p = toWorld(x, y); drag.n.x = p.x; drag.n.y = p.y; S.alpha = Math.max(S.alpha, 0.1); }
  else if (!drag.n) { S.view.x = drag.vx + x - drag.x; S.view.y = drag.vy + y - drag.y; }
});
cv.addEventListener("pointerup", (e) => {
  if (!drag) return;
  const { n, moved } = drag;
  if (n) n.fixed = false;
  if (n && !moved) {
    if (e.shiftKey && S.sel != null && n.id !== S.sel) { S.dst = n.id; $("#dst").value = n.id; findPath(); }
    else select(n.id);
  } else if (!n && !moved) { S.focus = null; renderComms(); }
  drag = null;
});
cv.addEventListener("dblclick", (e) => { const [x, y] = pos(e), n = hit(x, y); if (n) { select(n.id); startWalk(); } });
cv.addEventListener("wheel", (e) => {
  e.preventDefault();
  const [x, y] = pos(e), before = toWorld(x, y);
  S.view.k = Math.min(5, Math.max(0.3, S.view.k * (e.deltaY < 0 ? 1.12 : 1 / 1.12)));
  S.view.x = x - W / 2 - before.x * S.view.k;
  S.view.y = y - H / 2 - before.y * S.view.k;
}, { passive: false });
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { stopWalk(); S.path = null; S.focus = null; S.sel = null; renderComms(); renderDetail(); say(""); }
});

// ------------------------------------------------------------ controls
const th = $("#th");
th.value = document.body.dataset.threshold || "0.3";
$("#thv").textContent = th.value;
let thTimer;
th.addEventListener("input", () => { $("#thv").textContent = th.value; clearTimeout(thTimer); thTimer = setTimeout(load, 150); });
function setMethod(m) { S.method = m; $("#m-bfs").classList.toggle("on", m === "bfs"); $("#m-dfs").classList.toggle("on", m === "dfs"); }
$("#m-bfs").addEventListener("click", () => setMethod("bfs"));
$("#m-dfs").addEventListener("click", () => setMethod("dfs"));
$("#walk").addEventListener("click", startWalk);
$("#path").addEventListener("click", findPath);
$("#add").addEventListener("click", guard(async () => {
  const body = { name: $("#f-name").value, department: $("#f-dept").value, year: $("#f-year").value, interests: $("#f-int").value };
  const s = await api("/api/students", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  ["#f-name", "#f-dept", "#f-int"].forEach((i) => ($(i).value = ""));
  S.sel = s.id;
  await load();
  say(`Added ${s.name}.`);
}));
$("#imp").addEventListener("change", guard(async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const r = await api("/api/import", { method: "POST", body: fd });
  e.target.value = "";
  S.byId = {}; S.sel = null;
  await load();
  say(`Imported ${r.imported} students${r.skipped ? `, skipped ${r.skipped} invalid rows` : ""}.`);
}));
$("#reset").addEventListener("click", guard(async () => {
  if (!confirm("Replace all students with the sample data?")) return;
  await api("/api/reset", { method: "POST" });
  S.byId = {}; S.sel = null;
  await load();
}));

resize();
load();
requestAnimationFrame(frame);
