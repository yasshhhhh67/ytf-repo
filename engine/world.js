// ytf "world" scenes: one illustrated cartoon world that stays on screen across consecutive world_shot scenes.
// The storyboard defines the world once (setting + props at world x positions); each world_shot then moves the
// camera and runs a few actions (drive the car to a tower, draw a signal link, show a badge...). State carries
// over from shot to shot, so the video feels like one continuous animation instead of a slideshow.
// World units: x grows right, y grows UP from the ground (y = 0). At zoom 1 the screen is 1080 units wide (Shorts).
// Every frame is still a pure function of t: the state for a shot is rebuilt by replaying earlier shots' actions.
'use strict';
(() => {
const T = Y.TEMPLATES;
const INK = '#0b151c';
const C = {
  yellow: '#f7c948', yellowD: '#d9a21b', teal: '#3fb6a8', tealD: '#23786f', coral: '#ff6b5b', coralD: '#c8473a',
  cream: '#f4f1e8', steel: '#dfe6ea', steelD: '#93a4ae', glass: '#bfe3ea', skin: '#f2c7a5',
  sky0: '#1f3a48', sky1: '#0e1b23', hill: '#16303a', hill2: '#12262f', road: '#27363f', ground: '#15232b',
  tree: '#2b6a61', treeL: '#3d8a7c', dark: '#1a2a33', lit: '#ffd76a',
};
const TONES = { yellow: [C.yellow, INK], red: [C.coral, '#fff'], teal: [C.teal, '#fff'], dark: ['rgba(11,21,28,0.88)', C.yellow] };

// ---------- drawing helpers (world space; shapes are drawn with their base at y = 0 going up = negative canvas y) ----------
const ctx = () => Y.c;
const line = (lw) => { const c = ctx(); c.lineWidth = lw; c.strokeStyle = INK; c.lineJoin = 'round'; c.lineCap = 'round'; };
const fs = (fill, lw = 6) => { const c = ctx(); c.fillStyle = fill; c.fill(); line(lw); c.stroke(); };
const rr = (x, y, w, h, r) => Y.rr(x, y, w, h, r);
const circ = (x, y, r) => { const c = ctx(); c.beginPath(); c.arc(x, y, r, 0, 6.2832); };
// an outlined stroke: thick dark line underneath, coloured line on top
const oline = (pts, col, w = 5, closed = false) => {
  const c = ctx(); const path = () => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]); if (closed) c.closePath(); };
  c.lineJoin = 'round'; c.lineCap = 'round'; path(); c.strokeStyle = INK; c.lineWidth = w + 6; c.stroke(); path(); c.strokeStyle = col; c.lineWidth = w; c.stroke();
};
const arcs = (x, y, n, r0, gap, a0, a1, col, k, t) => {        // broadcast arcs (wifi / tower signal)
  const c = ctx(); c.save(); c.lineCap = 'round';
  for (let i = 0; i < n; i++) {
    const ph = ((t * 1.4 - i * 0.28) % 1 + 1) % 1; const a = k * (0.35 + 0.65 * (1 - ph));
    c.globalAlpha = a; c.strokeStyle = col; c.lineWidth = 7; c.beginPath(); c.arc(x, y, r0 + i * gap, a0, a1); c.stroke();
    c.beginPath(); c.arc(x, y, r0 + i * gap, Math.PI - a1, Math.PI - a0); c.stroke();
  }
  c.restore();
};

// ---------- prop library: w/h = size at scale 1, port = where links attach (x, y up), float = default height ----------
const P = {};
P.tower = { w: 150, h: 560, port: [0, 520], draw(o, t) {
  oline([[-72, 0], [-15, -470]], C.steel, 6); oline([[72, 0], [15, -470]], C.steel, 6);
  const ys = [0, -90, -175, -255, -330, -400, -470];
  for (let i = 0; i < ys.length - 1; i++) {
    const w0 = Y.lerp(72, 15, -ys[i] / 470), w1 = Y.lerp(72, 15, -ys[i + 1] / 470);
    oline([[-w0, ys[i]], [w1, ys[i + 1]]], C.steelD, 3); oline([[w0, ys[i]], [-w1, ys[i + 1]]], C.steelD, 3);
    oline([[-w1, ys[i + 1]], [w1, ys[i + 1]]], C.steel, 4);
  }
  oline([[0, -470], [0, -545]], C.steel, 5);
  const on = Math.max(o.hi, o.active);
  rr(-58, -528, 116, 30, 13); fs(on > 0.01 ? C.yellow : '#c9d3d8', 6);
  if (on > 0.01) { Y.glow(0, -513, 120, C.yellow, 0.35 * on); arcs(0, -513, 2, 74, 30, -0.75, -0.25, C.yellow, on, t); }
  circ(0, -552, 9); fs(on > 0.01 ? C.coral : C.steelD, 4);
} };
P.car = { w: 230, h: 125, port: [0, 125], draw(o) {
  const c = ctx(); c.save(); c.scale(o.dir < 0 ? -1 : 1, 1);
  c.beginPath(); c.moveTo(-62, -74); c.lineTo(-38, -122); c.lineTo(46, -122); c.lineTo(78, -74); c.closePath(); fs(C.yellow, 6);
  c.beginPath(); c.moveTo(-46, -80); c.lineTo(-30, -112); c.lineTo(2, -112); c.lineTo(2, -80); c.closePath(); fs(C.glass, 4);
  c.beginPath(); c.moveTo(12, -80); c.lineTo(12, -112); c.lineTo(40, -112); c.lineTo(62, -80); c.closePath(); fs(C.glass, 4);
  rr(-115, -82, 230, 56, 22); fs(C.yellow, 6);
  rr(-115, -50, 230, 10, 4); c.fillStyle = C.yellowD; c.fill();
  rr(96, -70, 16, 14, 5); fs(C.cream, 3); rr(-113, -70, 12, 14, 4); fs(C.coral, 3);
  for (const wx of [-66, 66]) {
    circ(wx, -24, 24); fs('#2a2f33', 6); circ(wx, -24, 10); fs(C.steelD, 3);
    c.save(); c.translate(wx, -24); c.rotate(o.roll); c.strokeStyle = INK; c.lineWidth = 3; c.beginPath(); c.moveTo(-10, 0); c.lineTo(10, 0); c.moveTo(0, -10); c.lineTo(0, 10); c.stroke(); c.restore();
  }
  c.restore();
} };
const phoneShape = (glow) => {
  rr(-30, -110, 60, 110, 12); fs('#24323a', 6); rr(-22, -100, 44, 84, 6); fs(glow ? '#5fe0a8' : '#3aa486', 3);
  const c = ctx(); c.save(); c.strokeStyle = INK; c.lineWidth = 6; c.lineCap = 'round'; c.beginPath();
  c.moveTo(-9, -72); c.quadraticCurveTo(-12, -48, 9, -38); c.stroke(); c.restore();
  circ(0, -8, 4); ctx().fillStyle = '#93a4ae'; ctx().fill();
};
P.phone = { w: 70, h: 115, port: [0, 60], bubble: true, draw(o) { phoneShape(o.active > 0.5 || o.hi > 0.5); } };
P.house = { w: 230, h: 215, port: [0, 200], draw(o) {
  const c = ctx(); rr(-95, -130, 190, 130, 6); fs(C.cream, 6);
  c.beginPath(); c.moveTo(-118, -126); c.lineTo(0, -212); c.lineTo(118, -126); c.closePath(); fs(C.coral, 6);
  rr(-24, -70, 48, 70, 6); fs(C.tealD, 5); rr(36, -100, 40, 36, 5); fs(o.active > 0.5 ? C.lit : C.glass, 4); rr(-76, -100, 40, 36, 5); fs(C.lit, 4);
} };
P.building = { w: 210, h: 440, port: [0, 440], draw(o, t) {
  rr(-100, -430, 200, 430, 8); fs('#2f4c59', 6); rr(-100, -440, 200, 22, 6); fs('#3e6372', 5);
  const c = ctx(); const r = Y.rng(o.seed + 7);
  for (let row = 0; row < 8; row++) for (let col = 0; col < 3; col++) {
    const lit = r() < 0.55; rr(-76 + col * 56, -400 + row * 48, 36, 30, 4); c.fillStyle = lit ? C.lit : '#1c313b'; c.fill(); line(3); c.stroke();
  }
  void t;
} };
P.tree = { w: 130, h: 215, port: [0, 180], draw() {
  rr(-11, -90, 22, 90, 6); fs('#6b4a35', 5); circ(0, -140, 72); fs(C.treeL, 6); circ(-26, -160, 22); ctx().fillStyle = 'rgba(255,255,255,0.12)'; ctx().fill();
} };
P.server = { w: 150, h: 290, port: [0, 290], draw(o, t) {
  rr(-72, -285, 144, 285, 10); fs('#2a3b45', 6);
  for (let i = 0; i < 5; i++) { rr(-56, -268 + i * 54, 112, 40, 6); fs('#1b2830', 4);
    for (let j = 0; j < 3; j++) { const on = Math.sin(t * 5 + i * 1.7 + j * 2.3 + o.seed) > -0.2; circ(-36 + j * 18, -248 + i * 54, 5); ctx().fillStyle = on ? (j === 2 ? C.yellow : '#5fe0a8') : '#33454f'; ctx().fill(); }
    rr(8, -252 + i * 54, 34, 8, 3); ctx().fillStyle = '#3e5560'; ctx().fill(); }
} };
P.laptop = { w: 190, h: 120, port: [0, 110], draw(o) {
  const c = ctx(); rr(-70, -118, 140, 92, 10); fs('#2a3b45', 6); rr(-58, -108, 116, 72, 5); fs(o.active > 0.5 ? '#5fe0a8' : C.glass, 3);
  c.beginPath(); c.moveTo(-92, -26); c.lineTo(92, -26); c.lineTo(80, 0); c.lineTo(-80, 0); c.closePath(); fs(C.steelD, 6);
} };
P.router = { w: 170, h: 100, port: [0, 90], draw(o, t) {
  oline([[-48, -50], [-60, -118]], C.steelD, 6); oline([[48, -50], [60, -118]], C.steelD, 6);
  rr(-82, -56, 164, 56, 14); fs(C.cream, 6);
  for (let j = 0; j < 4; j++) { circ(-50 + j * 22, -28, 6); ctx().fillStyle = Math.sin(t * 6 + j) > 0 ? '#5fe0a8' : '#9fb4bd'; ctx().fill(); }
  const on = Math.max(o.active, o.hi); if (on > 0.01) arcs(0, -70, 3, 70, 28, -1.0, -0.35, C.teal, on, t);
} };
P.satellite = { w: 240, h: 110, float: 760, port: [0, 55], draw(o, t) {
  const c = ctx(); c.save(); c.translate(0, -55); c.rotate(Math.sin(t * 0.8 + o.seed) * 0.06);
  for (const s of [-1, 1]) { rr(s > 0 ? 42 : -118, -26, 76, 52, 5); fs('#3a6fb0', 5); c.strokeStyle = 'rgba(255,255,255,0.35)'; c.lineWidth = 2; c.beginPath(); c.moveTo(s * 80, -26); c.lineTo(s * 80, 26); c.stroke(); oline([[s * 30, 0], [s * 42, 0]], C.steelD, 5); }
  rr(-32, -32, 64, 64, 10); fs(C.yellow, 6); oline([[0, 32], [0, 52]], C.steelD, 4); circ(0, 56, 9); fs(C.cream, 4);
  c.restore();
} };
P.person = { w: 80, h: 185, port: [0, 170], draw(o, t) {
  const c = ctx(); const sw = o.moving ? Math.sin(o.x / 14) * 12 : 0;
  oline([[-12, -78], [-14 - sw, 0]], '#30424c', 9); oline([[12, -78], [14 + sw, 0]], '#30424c', 9);
  rr(-30, -140, 60, 70, 22); fs(o.hi > 0.5 ? C.yellow : C.teal, 6);
  circ(0, -160, 26); fs(C.skin, 6); circ(-9, -163, 3.5); c.fillStyle = INK; c.fill(); circ(9, -163, 3.5); c.fill();
  void t;
} };
P.cloud = { w: 270, h: 140, float: 700, port: [0, 40], draw(o, t) {
  const c = ctx(); c.save(); c.translate(Math.sin(t * 0.5 + o.seed) * 6, 0);
  c.beginPath(); c.arc(-70, -50, 46, Math.PI * 0.5, Math.PI * 1.5); c.arc(-20, -88, 58, Math.PI, Math.PI * 1.9); c.arc(55, -70, 52, Math.PI * 1.25, Math.PI * 0.5); c.closePath();
  fs(o.hi > 0.5 ? '#fff7d6' : '#e6eef2', 6); c.restore();
} };
P.chip = { w: 170, h: 170, port: [0, 85], draw(o, t) {
  const c = ctx(); for (let i = 0; i < 5; i++) { const p = -48 + i * 24; oline([[p, -150], [p, -170]], C.steelD, 5); oline([[p, -20], [p, 0]], C.steelD, 5); oline([[-70, -48 - 24 * i - 14 + 24], [-88, -48 - 24 * i - 14 + 24]], C.steelD, 5); oline([[70, -48 - 24 * i - 14 + 24], [88, -48 - 24 * i - 14 + 24]], C.steelD, 5); }
  rr(-70, -155, 140, 140, 14); fs('#2a3b45', 6); rr(-40, -125, 80, 80, 8);
  const on = Math.max(o.active, o.hi); fs(on > 0.5 ? C.yellow : C.tealD, 5);
  if (on > 0.5) Y.glow(0, -85, 110, C.yellow, 0.25 + 0.1 * Math.sin(t * 4));
  void c;
} };
P.robot = { w: 160, h: 210, port: [0, 200], draw(o, t) {
  const c = ctx(); rr(-52, -92, 104, 92, 18); fs(C.steel, 6);
  rr(-66, -190, 132, 96, 24); fs(C.cream, 6); oline([[0, -190], [0, -214]], C.steelD, 5); circ(0, -220, 10); fs(C.coral, 4);
  const blink = (t * 0.7 + o.seed) % 3 < 0.12 ? 0.2 : 1; const on = Math.max(o.active, o.hi) > 0.5;
  for (const s of [-1, 1]) { c.save(); c.translate(s * 28, -146); c.scale(1, blink); circ(0, 0, 14); fs(on ? C.yellow : C.teal, 4); c.restore(); }
  rr(-26, -118, 52, 10, 5); c.fillStyle = INK; c.fill(); rr(-30, -64, 60, 34, 8); fs(C.tealD, 4);
} };
P.tunnel = { w: 480, h: 300, port: [-170, 260], draw() {
  const c = ctx(); c.beginPath(); c.moveTo(-240, 0); c.bezierCurveTo(-230, -330, 230, -330, 240, 0); c.closePath(); fs('#33454f', 6);
  c.beginPath(); c.moveTo(-150, 0); c.lineTo(-150, -150); c.quadraticCurveTo(0, -210, 150, -150); c.lineTo(150, 0); c.closePath(); fs('#121c22', 6);
}, front() {                                               // drawn over things inside, so they look shaded
  const c = ctx(); c.save(); c.beginPath(); c.moveTo(-150, 0); c.lineTo(-150, -150); c.quadraticCurveTo(0, -210, 150, -150); c.lineTo(150, 0); c.closePath();
  c.fillStyle = 'rgba(5,10,14,0.45)'; c.fill(); c.restore();
  rr(-160, -12, 22, 12, 3); fs('#55666f', 4); rr(138, -12, 22, 12, 3); fs('#55666f', 4);
} };
P.lamp = { w: 60, h: 260, port: [0, 250], draw(o) {
  oline([[0, 0], [0, -240], [40, -250]], '#55666f', 7); const c = ctx(); rr(28, -256, 36, 14, 6); fs(C.lit, 4);
  if (o.vis > 0) Y.glow(46, -240, 90, C.lit, 0.18); void c;
} };
P.graphic = { w: 170, h: 170, port: [0, 100], draw(o) {          // any Fluent Emoji key, for things the library does not draw
  Y.shadow(0, -4, 120, 0.3); Y.graphic(o.graphic, 0, -85, 170, { k: 1 });
} };
const KINDS = Object.keys(P).filter((k) => k !== 'graphic');
Y.WORLD_KINDS = KINDS;
const spec = (o) => P[o.graphic ? 'graphic' : o.kind] || P.graphic;

// ---------- world state ----------
const clone = (st) => ({ props: Object.fromEntries(Object.entries(st.props).map(([k, v]) => [k, { ...v, badge: v.badge && { ...v.badge } }])),
  links: st.links.map((l) => ({ ...l })), order: st.order });
function initState(w) {
  const props = {}; const order = [];
  (w.props || []).forEach((p, i) => {
    const sp = P[p.graphic ? 'graphic' : p.kind] || P.graphic;
    props[p.id] = { id: p.id, kind: p.kind, graphic: p.graphic, x: p.x, y: p.y ?? sp.float ?? 0, s: p.scale || 1, label: p.label || '', labelK: 1,
      vis: p.hidden ? 0 : 1, on: p.on || null, hi: 0, active: 0, range: 0, rangeR: 0, badge: null, pulse: 0, moving: 0, dir: 1, roll: 0, seed: i * 3.1 };
    order.push(p.id);
  });
  return { props, links: [], order };
}
const DUR = { move: 1.8, show: 0.5, hide: 0.45, link: 0.9, unlink: 0.45, range: 0.8, range_off: 0.45, badge: 0.45, highlight: 0.45, pulse: 1.3, activate: 0.4, deactivate: 0.4, attach: 0.6, label: 0.4 };
const targetX = (st, to) => (typeof to === 'number' ? to : st.props[to] ? st.props[to].x : null);
function apply(st, a, k) {
  const p = st.props[a.target]; const e = Y.eio(k);
  switch (a.do) {
    case 'show': if (p) p.vis = Y.lerp(p.vis, 1, k); break;
    case 'hide': if (p) p.vis = Y.lerp(p.vis, 0, k); break;
    case 'move': { if (!p) break; const tx = targetX(st, a.to); if (tx == null) break;
      const from = p.x; p.x = Y.lerp(from, tx, e); if (tx !== from) p.dir = tx > from ? 1 : -1; p.moving = k > 0 && k < 1 ? 1 : 0; p.roll = p.x / 24; break; }
    case 'attach': if (p && k > 0) p.on = a.to; break;
    case 'link': { const key = a.target + '>' + a.to; let l = st.links.find((x) => x.key === key);
      if (!l) { l = { key, from: a.target, to: a.to, style: a.style || 'signal', k: 0, alpha: 1 }; st.links.push(l); }
      l.k = Math.max(l.k, Y.eo(k)); l.alpha = 1; l.style = a.style || l.style; break; }
    case 'unlink': st.links.forEach((l) => { if ((l.from === a.target && (!a.to || l.to === a.to)) || (l.to === a.target && !a.to)) l.alpha = Math.min(l.alpha, 1 - k); });
      if (k >= 1) st.links = st.links.filter((l) => l.alpha > 0); break;
    case 'range': if (p) { p.range = Y.lerp(p.range, 1, Y.eo(k)); p.rangeR = a.r || p.rangeR || 380; } break;
    case 'range_off': if (p) p.range = Y.lerp(p.range, 0, k); break;
    case 'badge': if (p) { if (!a.text && !a.icon) { if (p.badge) p.badge.k = 1 - k; if (k >= 1) p.badge = null; } else if (k > 0) p.badge = { text: a.text || '', icon: a.icon || '', tone: a.tone || 'yellow', k: Y.clamp(k) }; } break;
    case 'highlight': for (const q of Object.values(st.props)) q.hi = Y.lerp(q.hi, q.id === a.target ? 1 : 0, k); break;
    case 'activate': if (p) p.active = Y.lerp(p.active, 1, k); break;
    case 'deactivate': if (p) p.active = Y.lerp(p.active, 0, k); break;
    case 'pulse': if (p) p.pulse = k > 0 && k < 1 ? k : 0; break;
    case 'label': if (p) { if (k > 0) { p.label = a.text || ''; p.labelK = Y.eo(k); } } break;
    default: break;
  }
}

// ---------- shots: every world_shot of one world, in order (state carries over even if other scenes cut in) ----------
let RUNS = null;
function prep() {
  if (RUNS) return; RUNS = new Map(); const TL = Y.TL; const byWorld = {};
  TL.scenes.forEach((s, i) => {
    if (s.template !== 'world_shot') return;
    const wi = s.world ?? 0; const w = (TL.worlds || [])[wi] || TL.world;
    const run = (byWorld[wi] = byWorld[wi] || { wi, world: w, shots: [] });
    run.shots.push(i); RUNS.set(i, run);
  });
  for (const r of new Set(RUNS.values())) {                 // state at the start of each shot, and its camera
    let st = initState(r.world || { props: [] }); r.start = {}; r.end = {}; r.cam = {};
    for (const i of r.shots) { r.start[i] = clone(st); for (const a of actionsOf(TL.scenes[i])) apply(st, a, 1); r.end[i] = clone(st); }
    for (const i of r.shots) r.cam[i] = frame(TL.scenes[i].params, r.end[i], r.start[i]);
  }
}
function actionsOf(s) {
  const acts = s.params.actions || []; const d = s.end - s.start; const n = acts.length; const cues = s.cues || {};
  const step = n ? Math.min(1.1, Math.max(0.35, (d - 1.2) / n)) : 0;
  let prev = -Infinity;                                     // an action without a cue word follows the one before it
  return acts.map((a, j) => {
    const at = Math.min(Math.max(0.1, d - 0.3), cues[j] != null ? cues[j] : Math.max(0.45 + j * step, prev + 0.4)); prev = at;
    return { ...a, at, dur: Math.min(DUR[a.do] || 0.5, Math.max(0.3, d - at)) };
  });
}

// ---------- camera ----------
const layout = () => (Y.vertical
  ? { ax: Y.W / 2, ay: 1330, top: 520, availW: Y.W, road: 96 }
  : { ax: Y.W / 2, ay: 850, top: 330, availW: Y.W, road: 84 });
const bbox = (st, ids) => {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const id of ids) { const p = st.props[id]; if (!p) continue; const sp = spec(p); const q = pos(st, p);
    x0 = Math.min(x0, q.x - sp.w * p.s / 2); x1 = Math.max(x1, q.x + sp.w * p.s / 2); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y + sp.h * p.s + (p.badge || p.label ? 120 : 30));
    if (p.range > 0.5) { const r = p.rangeR * p.s; x0 = Math.min(x0, q.x - r * 0.55); x1 = Math.max(x1, q.x + r * 0.55); } }
  return x0 === Infinity ? null : { x0, x1, y0, y1 };
};
function frame(params, stEnd, stStart) {
  const L = layout(); const vis = (st) => st.order.filter((id) => st.props[id].vis > 0.5);
  const ids = (params.focus && params.focus.length ? params.focus : [...new Set([...vis(stEnd), ...vis(stStart)])]);
  const b = bbox(stEnd, ids) || { x0: -400, x1: 400, y0: 0, y1: 500 };
  const hAvail = L.ay - L.top; const floor = Math.max(0, b.y0 - 60);
  let z = Math.min((L.availW - 150) / Math.max(200, b.x1 - b.x0), hAvail / Math.max(150, b.y1 - floor));
  z = params.zoom ? Y.clamp(params.zoom, 0.45, 2.2) : Y.clamp(z, 0.45, 1.6);     // auto framing never zooms in too far
  return { x: (b.x0 + b.x1) / 2, y: floor, z };
}
const lerpCam = (a, b, k) => ({ x: Y.lerp(a.x, b.x, k), y: Y.lerp(a.y, b.y, k), z: Math.exp(Y.lerp(Math.log(a.z), Math.log(b.z), k)) });

// position of a prop (attached props ride above their host)
function pos(st, p) {
  if (p.on && st.props[p.on]) { const h = st.props[p.on]; const hs = spec(h); return { x: h.x + (h.kind === 'car' ? 0 : 0), y: h.y + hs.h * h.s + 70 }; }
  return { x: p.x, y: p.y };
}

// ---------- background: night sky, stars, parallax hills / skyline, trees, road ----------
function drawBackdrop(w, cam, L, gt) {
  const c = Y.c, W = Y.W, H = Y.H;
  const g = c.createLinearGradient(0, 0, 0, L.ay); g.addColorStop(0, C.sky1); g.addColorStop(1, C.sky0); c.fillStyle = g; c.fillRect(0, 0, W, H);
  const r = Y.rng(11);
  for (let i = 0; i < 70; i++) { const sx = ((r() * W * 1.6 - cam.x * 0.06) % (W * 1.6) + W * 1.6) % (W * 1.6) - W * 0.3, sy = r() * L.ay * 0.8; const tw = 0.35 + 0.35 * Math.sin(gt * 1.3 + i * 2.1);
    c.globalAlpha = tw; c.fillStyle = '#d8ecf0'; c.beginPath(); c.arc(sx, sy, 1.2 + r() * 2.2, 0, 6.283); c.fill(); }
  c.globalAlpha = 1;
  Y.glow(W * 0.78, L.ay * 0.25, W * 0.5, C.teal, 0.10);
  if (w.setting === 'indoor') {
    c.fillStyle = '#1b2c35'; c.fillRect(0, 0, W, L.ay); c.fillStyle = 'rgba(255,255,255,0.03)';
    for (let x = -((cam.x * cam.z * 0.5) % 160); x < W; x += 160) c.fillRect(x, 0, 6, L.ay);
    return;
  }
  // far layer: hills (road) or skyline (city), parallax 0.35
  const par = 0.35, z = cam.z * 0.6 + 0.4; c.save(); c.translate(L.ax, L.ay); c.scale(z, z); c.translate(-cam.x * par, 0);
  const x0 = cam.x * par - (L.ax / z) - 400, x1 = cam.x * par + (L.ax / z) + 400;
  if (w.setting === 'city') {
    const rr2 = (i) => Y.rng(1000 + i)();
    for (let i = Math.floor(x0 / 120); i < x1 / 120; i++) { const h = 180 + rr2(i) * 320; c.fillStyle = i % 2 ? C.hill : C.hill2; c.fillRect(i * 120, -h, 112, h);
      c.fillStyle = 'rgba(255,215,106,0.25)'; for (let j = 0; j < h / 50 - 1; j++) if (Y.rng(i * 31 + j)() < 0.35) c.fillRect(i * 120 + 22 + (j % 2) * 40, -h + 24 + j * 46, 22, 18); }
  } else {
    c.fillStyle = C.hill; c.beginPath(); c.moveTo(x0, 0);
    for (let x = x0; x <= x1; x += 40) c.lineTo(x, -120 - 70 * Math.sin(x / 310) - 40 * Math.sin(x / 120 + 1));
    c.lineTo(x1, 0); c.closePath(); c.fill();
  }
  c.restore();
}
function drawTrees(w, cam, L, avoid) {                     // mid layer: trees along the road, parallax 0.85
  if (w.setting === 'indoor' || w.trees === false) return;
  const c = Y.c, par = 0.85; c.save(); c.translate(L.ax, L.ay); c.scale(cam.z, cam.z); c.translate(-cam.x * par, -cam.y * cam.z * 0);
  const x0 = cam.x * par - L.ax / cam.z - 200, x1 = cam.x * par + L.ax / cam.z + 200;
  for (let i = Math.floor(x0 / 170); i < x1 / 170; i++) {
    const rr2 = Y.rng(500 + i); const x = i * 170 + rr2() * 60; const s = 0.55 + rr2() * 0.3;
    if (avoid.some((a) => Math.abs(a - x / par) < 110)) continue;
    c.save(); c.translate(x, -4); c.scale(s, s); c.globalAlpha = 0.9;
    rr(-9, -80, 18, 80, 5); c.fillStyle = '#20343b'; c.fill(); circ(0, -128, 64); c.fillStyle = i % 3 ? C.tree : '#255c55'; c.fill(); c.restore();
  }
  c.restore();
}
function drawGround(w, cam, L) {
  const c = Y.c, W = Y.W, H = Y.H; const top = L.ay - cam.y * 0 ;
  if (w.setting === 'indoor') { c.fillStyle = '#2a3a43'; c.fillRect(0, top, W, H - top); c.fillStyle = INK; c.fillRect(0, top - 4, W, 8); return; }
  const rh = L.road * cam.z;
  c.fillStyle = C.ground; c.fillRect(0, top, W, H - top);
  c.fillStyle = '#31444e'; c.fillRect(0, top - 6, W, 10);                                  // curb
  c.fillStyle = C.road; c.fillRect(0, top + 4, W, rh);
  c.fillStyle = INK; c.fillRect(0, top + 4 + rh, W, 6);
  const dash = 70 * cam.z, gap = 50 * cam.z, off = ((-(cam.x * cam.z) % (dash + gap)) + (dash + gap)) % (dash + gap);
  c.fillStyle = 'rgba(244,241,232,0.55)'; for (let x = off - (dash + gap); x < W; x += dash + gap) c.fillRect(x, top + 4 + rh / 2 - 3 * cam.z, dash, 6 * cam.z);
}

// ---------- links between props ----------
function portOf(st, id) { const p = st.props[id]; if (!p) return null; const sp = spec(p); const q = pos(st, p); return { x: q.x + sp.port[0] * p.s * (p.dir < 0 && p.kind === 'car' ? -1 : 1), y: q.y + sp.port[1] * p.s }; }
function drawLink(st, l, gt, z) {
  const a = portOf(st, l.from), b = portOf(st, l.to); if (!a || !b || l.k <= 0 || l.alpha <= 0) return;
  const c = Y.c; const mx = (a.x + b.x) / 2, my = Math.max(a.y, b.y) + Math.abs(a.x - b.x) * 0.18 + 40;
  const col = { signal: C.cream, data: C.yellow, weak: C.coral, wire: C.steelD }[l.style] || C.cream;
  const N = 40, pts = []; for (let i = 0; i <= N; i++) { const u = i / N; pts.push([(1 - u) * (1 - u) * a.x + 2 * u * (1 - u) * mx + u * u * b.x, -((1 - u) * (1 - u) * a.y + 2 * u * (1 - u) * my + u * u * b.y)]); }
  const upto = Math.max(1, Math.round(N * l.k));
  c.save(); c.globalAlpha = l.alpha; c.lineCap = 'round'; c.lineJoin = 'round';
  c.setLineDash(l.style === 'wire' ? [] : [2, 16 / Math.max(0.6, z) * 1.2]); c.lineDashOffset = -gt * 40;
  c.beginPath(); pts.slice(0, upto + 1).forEach((p, i) => (i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])));
  c.strokeStyle = INK; c.lineWidth = 12 / Math.max(0.7, z); c.stroke(); c.strokeStyle = col; c.lineWidth = 6 / Math.max(0.7, z); c.stroke();
  c.setLineDash([]);
  if (l.k >= 1 && l.style !== 'wire') {                    // packets travelling along the link
    for (let j = 0; j < 2; j++) { const u = ((gt * 0.55 + j * 0.5) % 1); const p = pts[Math.round(u * N)]; circ(p[0], p[1], 9 / Math.max(0.7, z)); fs(l.style === 'weak' ? C.coral : C.yellow, 4); }
  }
  for (const p of [pts[0], pts[upto]]) { circ(p[0], p[1], 8 / Math.max(0.7, z)); fs(col, 4); }
  c.restore();
}

// ---------- screen-space overlays ----------
const up = (s) => String(s || '').toUpperCase();
function popScale(k) { return Y.lerp(0.55, 1, Y.eob(k)); }
function titleBlock(text, hi, y, k, maxW, instant) {
  const c = Y.c; const words = up(text).split(/\s+/).filter(Boolean); const hiN = up(hi).replace(/[^A-Z0-9%$]/g, '');
  const w = Y.wrap(up(text), maxW, Y.vertical ? 104 : 92, 56, 2, 900); let i0 = 0; const lh = w.size * 1.06;
  w.lines.forEach((ln, li) => {
    const ws = ln.split(' '); c.font = Y.font(w.size, 900); const sp = c.measureText(' ').width; const wd = ws.map((x) => c.measureText(x).width);
    let x = Y.W / 2 - (wd.reduce((a, b) => a + b, 0) + sp * (ws.length - 1)) / 2;
    ws.forEach((word, j) => {
      const kk = instant ? 1 : Y.seg(k, (i0 + j) * 0.07, (i0 + j) * 0.07 + 0.45); if (kk <= 0) { x += wd[j] + sp; return; }
      const isH = hiN && word.replace(/[^A-Z0-9%$]/g, '') === hiN; const s = popScale(kk); const yy = y + li * lh + w.size;
      c.save(); c.translate(x + wd[j] / 2, yy - w.size * 0.35); c.scale(s, s); c.globalAlpha *= Y.clamp(kk * 2);
      c.textAlign = 'center'; c.textBaseline = 'alphabetic'; c.lineJoin = 'round';
      c.lineWidth = 16; c.strokeStyle = INK; c.strokeText(word, 0, w.size * 0.35); c.fillStyle = isH ? C.yellow : '#fff'; c.fillText(word, 0, w.size * 0.35);
      c.restore(); x += wd[j] + sp;
    });
    i0 += ws.length;
  });
  void words; return w.lines.length * lh + 10;
}
function pill(text, x, y, size, tone, k, maxW) {
  const c = Y.c; const [bg, fg] = TONES[tone] || TONES.yellow; const t = up(text);
  const s0 = Y.fitSize(t, maxW - size * 1.4, size, 26, 900); c.font = Y.font(s0, 900);
  const w = c.measureText(t).width + s0 * 1.4, h = s0 * 1.6; const s = popScale(k);
  c.save(); c.translate(x, y); c.scale(s, s); c.globalAlpha *= Y.clamp(k * 2);
  Y.rr(-w / 2, -h / 2, w, h, h / 2); c.fillStyle = bg; c.fill(); c.lineWidth = 6; c.strokeStyle = tone === 'dark' ? C.yellow : INK; c.stroke();
  c.fillStyle = fg; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(t, 0, s0 * 0.05); c.restore();
  return h;
}
function chapterBadge(ch, k) {
  const c = Y.c; const x = Y.vertical ? 70 : 90, y = Y.vertical ? 250 : 60; const s = 92;
  c.save(); c.globalAlpha *= Y.clamp(k * 2); c.translate(x + s / 2, y + s / 2); const sc = popScale(k); c.scale(sc, sc);
  Y.rr(-s / 2, -s / 2, s, s, 22); c.fillStyle = C.teal; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  Y.rr(-s / 2 + 10, -s / 2 + 8, s - 20, 12, 6); c.fillStyle = 'rgba(255,255,255,0.25)'; c.fill();
  c.font = Y.font(64, 900); c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(String(ch.n), 0, 4); c.restore();
  const tk = Y.eo(Y.seg(k, 0.25, 1)); if (tk <= 0) return y + s;
  c.save(); c.globalAlpha *= tk; c.translate((1 - tk) * -30, 0);
  const tw = Y.W - (x + s + 26) - 60; const ts = Y.fitSize(up(ch.title), tw, 66, 36, 900);
  c.font = Y.font(ts, 900); c.textAlign = 'left'; c.textBaseline = 'alphabetic'; c.lineJoin = 'round'; c.lineWidth = 12; c.strokeStyle = INK;
  const ty = ch.sub ? y + ts * 0.95 : y + s / 2 + ts * 0.36; c.strokeText(up(ch.title), x + s + 26, ty); c.fillStyle = '#fff'; c.fillText(up(ch.title), x + s + 26, ty);
  if (ch.sub) { const ss = Y.fitSize(up(ch.sub), tw, 30, 20, 800); c.font = Y.font(ss, 800); c.fillStyle = C.yellow; c.fillText(up(ch.sub), x + s + 28, ty + ss + 14); }
  c.restore(); return y + s;
}
const ICONS = {
  bars0: (k) => bars(0, k), bars1: (k) => bars(1, k), bars2: (k) => bars(2, k), bars3: (k) => bars(3, k), bars4: (k) => bars(4, k),
  check: () => { const c = Y.c; c.strokeStyle = '#2fbf71'; c.lineWidth = 10; c.lineCap = 'round'; c.beginPath(); c.moveTo(-18, 2); c.lineTo(-5, 15); c.lineTo(20, -14); c.stroke(); },
  cross: () => { const c = Y.c; c.strokeStyle = C.coral; c.lineWidth = 10; c.lineCap = 'round'; c.beginPath(); c.moveTo(-15, -15); c.lineTo(15, 15); c.moveTo(15, -15); c.lineTo(-15, 15); c.stroke(); },
  question: () => { const c = Y.c; c.font = Y.font(46, 900); c.fillStyle = C.coral; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('?', 0, 3); },
  warn: () => { const c = Y.c; c.font = Y.font(46, 900); c.fillStyle = C.yellowD; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('!', 0, 3); },
  clock: (k, gt) => { const c = Y.c; c.strokeStyle = INK; c.lineWidth = 5; circ(0, 0, 20); c.stroke(); c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos(gt * 3) * 14, Math.sin(gt * 3) * 14); c.stroke(); },
  bolt: () => { const c = Y.c; c.beginPath(); c.moveTo(6, -24); c.lineTo(-14, 4); c.lineTo(0, 4); c.lineTo(-6, 24); c.lineTo(14, -6); c.lineTo(0, -6); c.closePath(); c.fillStyle = C.yellowD; c.fill(); },
};
function bars(n, k) { const c = Y.c; for (let i = 0; i < 4; i++) { const h = 10 + i * 9; Y.rr(-24 + i * 13, 18 - h, 9, h, 3); c.fillStyle = i < n ? (n <= 1 ? C.coral : '#2fbf71') : 'rgba(11,21,28,0.25)'; c.fill(); } void k; }
function badge(b, x, y, gt) {
  const c = Y.c; const [bg, fg] = TONES[b.tone] || TONES.yellow; const k = b.k; const s = popScale(k);
  c.save(); c.translate(x, y); c.scale(s, s); c.globalAlpha *= Y.clamp(k * 2);
  let w = 0, h = 72; c.font = Y.font(38, 900); const tw = b.text ? c.measureText(up(b.text)).width : 0;
  w = (b.icon ? 64 : 0) + (b.text ? tw + 36 : 0) + (b.icon && !b.text ? 8 : 0);
  const bgc = b.icon && !b.text ? C.cream : bg;
  Y.rr(-w / 2, -h / 2, w, h, 18); c.fillStyle = bgc; c.fill(); c.lineWidth = 6; c.strokeStyle = INK; c.stroke();
  c.beginPath(); c.moveTo(-12, h / 2 - 1); c.lineTo(0, h / 2 + 14); c.lineTo(12, h / 2 - 1); c.closePath(); c.fillStyle = bgc; c.fill(); c.stroke();
  let x0 = -w / 2;
  if (b.icon && ICONS[b.icon]) { c.save(); c.translate(x0 + 36, 0); ICONS[b.icon](k, gt); c.restore(); x0 += 64; }
  if (b.text) { c.fillStyle = b.icon ? INK : fg; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(up(b.text), x0 + (b.icon ? 2 : 18), 2); }
  c.restore();
}

// ---------- the template ----------
const toScreen = (cam, L, x, y) => ({ x: L.ax + (x - cam.x) * cam.z, y: L.ay - (y - cam.y) * cam.z });
function overlayOf(run, i) { const { ch, from } = chapterAt(run, i); return { p: Y.TL.scenes[i].params, cues: Y.TL.scenes[i].cues || {}, ch, chFrom: from }; }
// Draw one shot's overlay at shot time lt with opacity alpha. hide.x = lay it out but don't draw it; still.x = fully shown.
function drawOverlay(o, lt, alpha, { hide, still }) {
  const c = Y.c; let y = Y.vertical ? 250 : 60;
  const part = (hidden, fn) => { c.save(); c.globalAlpha *= hidden ? 0 : alpha; const r = fn(); c.restore(); return r; };
  if (o.ch) y = part(hide.ch, () => chapterBadge(o.ch, still.ch ? 1 : Y.seg(lt, 0.05, 0.75))) + (o.ch.sub ? 50 : 30);
  if (o.p.title) y += part(hide.title, () => titleBlock(o.p.title, o.p.highlight, y, still.title ? 1 : Y.seg(lt, 0, 1.2), Y.W - 120, !!still.title)) + 20;
  if (o.p.callout) {
    const at = o.cues.callout != null ? o.cues.callout : 0.5; const k = still.callout ? 1 : Y.seg(lt, at, at + 0.45);
    if (k > 0) part(hide.callout, () => pill(o.p.callout.text, Y.W / 2, y + 40, Y.vertical ? 44 : 40, o.p.callout.tone || 'yellow', k, Y.W - 140));
  }
}
function chapterAt(run, i) { let ch = null, from = null; for (const j of run.shots) { if (j > i) break; const p = Y.TL.scenes[j].params; if (p.chapter) { ch = p.chapter; from = j; } } return { ch, from }; }

T.world_shot = {
  fullBleed: true,
  draw(p, lt, d, scene) {
    prep(); const TL = Y.TL; const i = scene._i; const run = RUNS.get(i); const c = Y.c; const L = layout();
    const gt = scene.start + lt; const w = run.world || { props: [] };
    // state now: start-of-shot state + this shot's actions so far
    const st = clone(run.start[i]); for (const a of actionsOf(scene)) apply(st, a, Y.seg(lt, a.at, a.at + a.dur));
    // camera: glide from the previous shot's framing (or a slight establishing push on the first shot)
    const pos0 = run.shots.indexOf(i); const target = run.cam[i];
    const live = frame(p, st, st); const tgt = p.focus && p.focus.length ? lerpCam(target, live, 0.5) : target;
    const glide = pos0 > 0 && run.shots[pos0 - 1] === i - 1;         // straight on from the previous shot
    const prev = glide ? run.cam[i - 1] : { x: target.x - 120, y: target.y, z: target.z * 0.9 };
    let cam = i === 0 ? tgt : lerpCam(prev, tgt, Y.eio(Y.seg(lt, 0, glide ? 1.1 : 1.6)));
    cam = { ...cam, x: cam.x + Math.sin(gt * 0.35) * 10 / cam.z, z: cam.z * (1 + 0.012 * Math.sin(gt * 0.27)) };

    drawBackdrop(w, cam, L, gt);
    drawTrees(w, cam, L, st.order.map((id) => st.props[id].x));
    drawGround(w, cam, L);
    // world layer
    c.save(); c.translate(L.ax, L.ay); c.scale(cam.z, cam.z); c.translate(-cam.x, cam.y);
    const ordered = st.order.map((id) => st.props[id]).sort((a, b) => (a.on ? 1 : 0) - (b.on ? 1 : 0) || (a.kind === 'tunnel' ? -1 : 0) - (b.kind === 'tunnel' ? -1 : 0));
    for (const o of ordered) if (o.range > 0.01 && o.vis > 0.01) {         // coverage circles behind everything
      const q = portOf(st, o.id); const r = o.rangeR * o.s * Y.eo(o.range);
      c.save(); c.globalAlpha = o.vis * Math.min(1, o.range * 1.5); circ(q.x, -q.y, r); c.fillStyle = 'rgba(63,182,168,0.10)'; c.fill();
      c.setLineDash([14, 14]); c.lineDashOffset = -gt * 12; c.lineWidth = 4 / cam.z * 1.4; c.strokeStyle = 'rgba(160,230,220,0.7)'; c.stroke(); c.restore();
    }
    for (const o of ordered) {
      if (o.vis <= 0.001) continue; const sp = spec(o); const q = pos(st, o);
      c.save(); c.translate(q.x, -q.y);
      if (o.hi > 0.01) Y.glow(0, -sp.h * o.s * 0.5, Math.max(sp.w, sp.h) * o.s * 0.85, C.yellow, 0.28 * o.hi);
      const pk = Y.eob(Y.clamp(o.vis)); const bob = o.moving && o.kind === 'car' ? Math.sin(gt * 22) * 1.5 : 0;
      c.scale(o.s * pk * (1 + 0.04 * o.hi), o.s * pk * (1 + 0.04 * o.hi)); c.translate(0, bob); c.globalAlpha = Y.clamp(o.vis * 2);
      if (!o.on) Y.shadow(0, 2, sp.w * 0.9, 0.25);
      if (o.on && (sp.bubble || o.graphic)) {                                 // attached props sit in a bubble with a pointer
        const R = 78; c.translate(0, 0); c.beginPath(); c.moveTo(-16, -6); c.lineTo(0, 22); c.lineTo(16, -6); c.closePath(); fs(C.teal, 5);
        circ(0, -R + 2, R); fs('#173a3c', 6); c.lineWidth = 5; c.strokeStyle = C.teal; circ(0, -R + 2, R - 9); c.stroke();
        c.save(); c.translate(0, -R + 2 + (sp.h * 0.72) / 2); c.scale(0.72, 0.72); sp.draw(o, gt); c.restore();
      } else sp.draw(o, gt);
      c.restore();
    }
    for (const l of st.links) drawLink(st, l, gt, cam.z);
    for (const o of ordered) if (o.vis > 0.01 && spec(o).front) { const q = pos(st, o); c.save(); c.translate(q.x, -q.y); c.scale(o.s, o.s); c.globalAlpha = Y.clamp(o.vis * 2); spec(o).front(o, gt); c.restore(); }
    for (const o of ordered) if (o.pulse > 0) { const q = portOf(st, o.id); c.save(); c.globalAlpha = 1 - o.pulse; c.lineWidth = 8 / cam.z; c.strokeStyle = C.yellow; circ(q.x, -q.y, 40 + o.pulse * 160); c.stroke(); c.restore(); }
    c.restore();

    // labels + badges above props, constant on-screen size
    for (const o of ordered) {
      if (o.vis < 0.3 || (!o.label && !o.badge)) continue; const sp = spec(o); const q = pos(st, o);
      const top = toScreen(cam, L, q.x, q.y + sp.h * o.s + (o.on ? 150 : 0)); let y = top.y - 34;
      if (top.x < 40 || top.x > Y.W - 40) continue;                         // prop is off screen
      if (o.label) { c.save(); c.globalAlpha = Y.clamp(o.vis) * o.labelK; c.font = Y.font(40, 900); c.textAlign = 'center'; c.textBaseline = 'alphabetic'; c.lineJoin = 'round';
        c.lineWidth = 12; c.strokeStyle = INK; c.strokeText(up(o.label), top.x, y); c.fillStyle = o.hi > 0.5 ? C.yellow : C.cream; c.fillText(up(o.label), top.x, y); c.restore(); y -= 70; }
      if (o.badge && o.badge.k > 0) badge(o.badge, Y.clamp(top.x, 120, Y.W - 120), y - 10, gt);
    }

    // chapter badge, title, callout. On a cut from the previous shot of this world, the parts that change hand over
    // cleanly: the old ones slide up and fade out first, then the new ones pop in. Parts that stay the same don't move.
    const co = overlayOf(run, i); const prevI = i > 0 && Y.worldContinues(TL.scenes[i - 1], scene) ? i - 1 : null;
    const po = prevI != null ? overlayOf(run, prevI) : null;
    const same = {
      ch: !!(po && co.ch && po.chFrom === co.chFrom),
      title: !!(po && co.p.title && po.p.title === co.p.title),
      callout: !!(po && co.p.callout && po.p.callout && po.p.callout.text === co.p.callout.text),
    };
    const out = po ? 1 - Y.seg(lt, 0, 0.25) : 0;
    if (out > 0) {
      c.save(); if (!same.ch) c.translate(0, -(1 - Y.eo(out)) * 36);    // slide up only when the whole top block leaves
      drawOverlay(po, 99, out, { hide: same, still: { ch: true, title: true, callout: true } });
      c.restore();
    }
    const changed = po && ((po.ch && !same.ch) || (po.p.title && !same.title) || (po.p.callout && !same.callout));
    drawOverlay(co, lt - (changed ? 0.22 : 0), 1, { hide: {}, still: i === 0 ? { ch: true, title: true, callout: false } : same });
  },
  settle: () => null,
};

// a world_shot does not dip-transition into the next world_shot of the same world: the camera glides instead
Y.worldContinues = (a, b) => a && b && a.template === 'world_shot' && b.template === 'world_shot' && (a.world ?? 0) === (b.world ?? 0);
})();
