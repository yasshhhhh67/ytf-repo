// ytf scene engine core: canvas setup, brand, easing, text fitting, backgrounds, scene playback.
// Every frame is a pure function of t (seeded randomness only), so frames can be rendered in any order.
'use strict';

const Y = (window.Y = {});
Y.TEMPLATES = {};
Y.reports = [];             // layout problems found while drawing (text overflow etc.); read by `render.mjs check`

Y.BRAND = {
  bg0: '#070b18', bg1: '#101a36', ink: '#f4f6ff', muted: '#9aa6c8', faint: 'rgba(154,166,200,0.18)',
  accent: '#3d6bff', accent2: '#22d3ee', good: '#22c55e', bad: '#f43f5e', warn: '#ffd84d',
  card: 'rgba(255,255,255,0.06)', cardLine: 'rgba(255,255,255,0.14)',
  sans: 'Inter', mono: 'JetBrains Mono',
};

// ---------- math & easing ----------
Y.clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
Y.lerp = (a, b, k) => a + (b - a) * k;
Y.seg = (t, a, b) => Y.clamp((t - a) / (b - a));                 // 0..1 progress of t inside [a, b]
Y.eo = (k) => 1 - Math.pow(1 - Y.clamp(k), 3);                   // ease out cubic
Y.eio = (k) => { k = Y.clamp(k); return k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; };
Y.eob = (k) => { k = Y.clamp(k); const c = 1.70158; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); };
Y.rng = (seed) => { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); };
Y.hash = (str) => { let h = 2166136261; for (const ch of String(str)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return h >>> 0; };
Y.fmtNum = (v, decimals = 0) => Number(v).toLocaleString('en-US', { maximumFractionDigits: decimals, minimumFractionDigits: decimals });

// ---------- canvas ----------
Y.init = (W, H) => {
  const cv = document.getElementById('cv');
  cv.width = W; cv.height = H;
  Y.W = W; Y.H = H; Y.S = Math.min(W, H) / 1080; Y.vertical = H > W;
  Y.c = cv.getContext('2d');
  // content box: Shorts keep clear of YouTube UI (top 220 px) and the caption band (y >= 1230)
  Y.box = Y.vertical ? { x: 70, y: 230, w: W - 140, h: 980 } : { x: 110, y: 90, w: W - 220, h: H - 180 };
};

Y.font = (size, weight = 800, family = Y.BRAND.sans) => `${weight} ${Math.round(size)}px "${family}"`;

// Fit one line: shrink from `size` down to `min`. Reports overflow if it still does not fit.
Y.fitSize = (text, maxW, size, min, weight = 800, family) => {
  const c = Y.c; let s = size;
  for (; s >= min; s -= 2) { c.font = Y.font(s, weight, family); if (c.measureText(text).width <= maxW) return s; }
  c.font = Y.font(min, weight, family);
  if (c.measureText(text).width > maxW) Y.reports.push({ kind: 'overflow', text: String(text).slice(0, 60), need: Math.round(c.measureText(text).width), max: Math.round(maxW) });
  return min;
};

// Wrap into at most maxLines lines, shrinking font as needed. Returns {lines, size}.
Y.wrap = (text, maxW, size, min, maxLines = 3, weight = 800, family) => {
  const c = Y.c; const words = String(text).split(/\s+/).filter(Boolean);
  for (let s = size; s >= min; s -= 2) {
    c.font = Y.font(s, weight, family);
    const lines = []; let cur = '';
    for (const w of words) {
      const t = cur ? cur + ' ' + w : w;
      if (c.measureText(t).width <= maxW || !cur) cur = t; else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    const widest = Math.max(...lines.map((l) => c.measureText(l).width));
    if (lines.length <= maxLines && widest <= maxW) return { lines, size: s };
  }
  Y.reports.push({ kind: 'overflow', text: String(text).slice(0, 60), maxLines, max: Math.round(maxW) });
  c.font = Y.font(min, weight, family);
  return { lines: [String(text)], size: min };
};

// Draw text block. align: 'left' | 'center' | 'right'. Returns total height.
Y.text = (lines, x, y, size, color, align = 'center', weight = 800, lh = 1.18, family) => {
  const c = Y.c; c.font = Y.font(size, weight, family); c.fillStyle = color; c.textAlign = align; c.textBaseline = 'alphabetic';
  lines.forEach((l, i) => c.fillText(l, x, y + size + i * size * lh));
  return lines.length * size * lh;
};

// Rising text: each line rises from a mask with ease-out, staggered.
Y.riseText = (lines, x, y, size, color, k, align = 'center', weight = 800, lh = 1.18) => {
  const c = Y.c; c.font = Y.font(size, weight); c.textAlign = align; c.textBaseline = 'alphabetic';
  lines.forEach((l, i) => {
    const p = Y.eo(Y.seg(k, i * 0.12, i * 0.12 + 0.6));
    if (p <= 0) return;
    const ly = y + size + i * size * lh;
    c.save(); c.beginPath(); c.rect(0, ly - size * 1.05, Y.W, size * 1.35); c.clip();
    c.globalAlpha = p; c.fillStyle = color; c.fillText(l, x, ly + (1 - p) * size * 0.9);
    c.restore();
  });
  return lines.length * size * lh;
};

Y.rr = (x, y, w, h, r) => { const c = Y.c; r = Math.max(0, Math.min(r, w / 2, h / 2)); c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); };

Y.card = (x, y, w, h, opts = {}) => {
  const c = Y.c; const r = (opts.r ?? 28) * Y.S;
  c.save(); c.globalAlpha *= opts.alpha ?? 1;
  Y.rr(x, y, w, h, r); c.fillStyle = opts.fill || Y.BRAND.card; c.fill();
  c.lineWidth = (opts.lw ?? 2) * Y.S; c.strokeStyle = opts.line || Y.BRAND.cardLine; c.stroke();
  c.restore();
};

Y.pill = (text, cx, cy, size, fill, color = '#fff', k = 1) => {
  const c = Y.c; c.font = Y.font(size, 800); const w = c.measureText(text).width + size * 1.1, h = size * 1.55;
  c.save(); c.globalAlpha *= Y.clamp(k); c.translate(cx, cy); c.scale(Y.lerp(0.7, 1, Y.eob(k)), Y.lerp(0.7, 1, Y.eob(k)));
  Y.rr(-w / 2, -h / 2, w, h, h / 2); c.fillStyle = fill; c.fill();
  c.fillStyle = color; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(text, 0, size * 0.04);
  c.restore();
};

Y.glow = (x, y, r, color, a = 0.35) => {
  const c = Y.c; const g = c.createRadialGradient(x, y, 0, x, y, r);
  g.addColorStop(0, color); g.addColorStop(1, 'rgba(0,0,0,0)');
  c.save(); c.globalAlpha = a; c.fillStyle = g; c.fillRect(x - r, y - r, r * 2, r * 2); c.restore();
};

Y.arrow = (x1, y1, x2, y2, color, lw, k = 1, head = 16) => {
  const c = Y.c; const x = Y.lerp(x1, x2, k), y = Y.lerp(y1, y2, k);
  c.save(); c.strokeStyle = color; c.fillStyle = color; c.lineWidth = lw; c.lineCap = 'round';
  c.beginPath(); c.moveTo(x1, y1); c.lineTo(x, y); c.stroke();
  if (k > 0.98) { const a = Math.atan2(y2 - y1, x2 - x1), h = head * Y.S;
    c.beginPath(); c.moveTo(x2, y2); c.lineTo(x2 - h * Math.cos(a - 0.45), y2 - h * Math.sin(a - 0.45)); c.lineTo(x2 - h * Math.cos(a + 0.45), y2 - h * Math.sin(a + 0.45)); c.closePath(); c.fill(); }
  c.restore();
};

// Channel style "Blueprint": deep navy, faint engineering grid, one electric-blue accent. Static (no drift), so
// held frames can be reused by the renderer. Same on every video: variety comes from the diagrams, not the colours.
Y.background = () => {
  const c = Y.c, W = Y.W, H = Y.H;
  if (!Y._bg || Y._bg.w !== W || Y._bg.h !== H) {
    const off = document.createElement('canvas'); off.width = W; off.height = H; const o = off.getContext('2d');
    const g = o.createLinearGradient(0, 0, W * 0.35, H); g.addColorStop(0, '#0d1838'); g.addColorStop(1, '#050914');
    o.fillStyle = g; o.fillRect(0, 0, W, H);
    const minor = 30 * Y.S, major = minor * 4;
    o.lineWidth = 1; o.strokeStyle = 'rgba(120,150,255,0.055)';
    for (let x = 0; x <= W; x += minor) { o.beginPath(); o.moveTo(x + 0.5, 0); o.lineTo(x + 0.5, H); o.stroke(); }
    for (let y = 0; y <= H; y += minor) { o.beginPath(); o.moveTo(0, y + 0.5); o.lineTo(W, y + 0.5); o.stroke(); }
    o.strokeStyle = 'rgba(120,150,255,0.11)';
    for (let x = 0; x <= W; x += major) { o.beginPath(); o.moveTo(x + 0.5, 0); o.lineTo(x + 0.5, H); o.stroke(); }
    for (let y = 0; y <= H; y += major) { o.beginPath(); o.moveTo(0, y + 0.5); o.lineTo(W, y + 0.5); o.stroke(); }
    const glow = (x, y, r, col, a) => { const gg = o.createRadialGradient(x, y, 0, x, y, r); gg.addColorStop(0, col); gg.addColorStop(1, 'rgba(0,0,0,0)'); o.globalAlpha = a; o.fillStyle = gg; o.fillRect(x - r, y - r, r * 2, r * 2); o.globalAlpha = 1; };
    glow(W * 0.85, H * 0.1, Math.max(W, H) * 0.5, Y.BRAND.accent, 0.20);
    glow(W * 0.08, H * 0.95, Math.max(W, H) * 0.45, Y.BRAND.accent2, 0.08);
    const v = o.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.78);
    v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.5)'); o.fillStyle = v; o.fillRect(0, 0, W, H);
    Y._bg = { w: W, h: H, cv: off };
  }
  c.drawImage(Y._bg.cv, 0, 0);
};

// Small mono label (e.g. "STEP 2", "SOURCE: ...")
Y.label = (text, x, y, color = Y.BRAND.muted, size = 24, align = 'left') => {
  const c = Y.c; c.font = Y.font(size * Y.S, 700, Y.BRAND.mono); c.fillStyle = color; c.textAlign = align; c.textBaseline = 'alphabetic';
  const t = String(text).toUpperCase(); let out = '';
  for (const ch of t) out += ch + ' ';
  c.fillText(out.trim(), x, y);
};

// Reveal time for item i: uses resolved cue times (seconds into scene) or an even stagger.
Y.revealAt = (scene, i, n, start = 0.25, spread = null) => {
  const cues = scene.cues || {};
  if (cues[i] != null) return cues[i];
  const d = scene.end - scene.start; const span = spread ?? Math.min(d * 0.55, 0.9 * n);
  return start + (n <= 1 ? 0 : (span * i) / (n - 1));
};

// ---------- graphics preset: Microsoft Fluent Emoji (MIT), loaded from /assets/fluent/<key>.svg ----------
Y.G = {};
Y.loadGraphics = async (keys) => {
  await Promise.all([...new Set(keys)].map((k) => new Promise((res) => {
    const im = new Image(); im.onload = () => { Y.G[k] = im; res(); };
    im.onerror = () => { Y.reports.push({ kind: 'missing-graphic', text: k }); res(); };
    im.src = `/assets/fluent/${k}.svg`;
  })));
};
// keys of every "graphic" field anywhere in an object
Y.graphicKeys = (o, out = []) => {
  if (Array.isArray(o)) o.forEach((x) => Y.graphicKeys(x, out));
  else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) { if ((k === 'graphic' || k === 'packet') && typeof v === 'string') out.push(v); else Y.graphicKeys(v, out); }
  return out;
};

// Motion presets (named after the Animate.css set). enter(preset, k) with k = 0..1 entrance progress;
// idle(preset, t) runs continuously. Both return {dx, dy, s, r, a}.
Y.enter = (preset, k) => {
  k = Y.clamp(k); const e = Y.eo(k);
  switch (preset) {
    case 'bounceIn': return { dx: 0, dy: 0, s: Y.lerp(0.3, 1, Y.eob(k)), r: 0, a: Y.clamp(k * 3) };
    case 'zoomIn': return { dx: 0, dy: 0, s: Y.lerp(0.5, 1, e), r: 0, a: e };
    case 'fadeInUp': return { dx: 0, dy: (1 - e) * 80, s: 1, r: 0, a: e };
    case 'slideInLeft': return { dx: -(1 - e) * 300, dy: 0, s: 1, r: 0, a: e };
    case 'slideInRight': return { dx: (1 - e) * 300, dy: 0, s: 1, r: 0, a: e };
    case 'rotateIn': return { dx: 0, dy: 0, s: Y.lerp(0.6, 1, e), r: (1 - e) * -0.8, a: e };
    default: return { dx: 0, dy: 0, s: Y.lerp(0.6, 1, Y.eob(k)), r: 0, a: Y.clamp(k * 2) };        // popIn
  }
};
Y.idle = (preset, t, seed = 0) => {
  const ph = seed * 1.7;
  switch (preset) {
    case 'float': return { dx: 0, dy: Math.sin(t * 1.6 + ph) * 12, s: 1, r: 0, a: 1 };
    case 'pulse': return { dx: 0, dy: 0, s: 1 + Math.sin(t * 4 + ph) * 0.05, r: 0, a: 1 };
    case 'wiggle': return { dx: 0, dy: 0, s: 1, r: Math.sin(t * 6 + ph) * 0.08, a: 1 };
    case 'spin': return { dx: 0, dy: 0, s: 1, r: t * 1.2, a: 1 };
    case 'bob': return { dx: 0, dy: -Math.abs(Math.sin(t * 5 + ph)) * 14, s: 1, r: 0, a: 1 };
    case 'headShake': return { dx: Math.sin(t * 14 + ph) * 6 * Math.max(0, Math.sin(t * 0.9 + ph)), dy: 0, s: 1, r: 0, a: 1 };
    default: return { dx: 0, dy: 0, s: 1, r: 0, a: 1 };
  }
};
// Draw graphic `key` centred at (x, y), `size` px wide, with optional entrance + idle motion.
Y._sprites = {};
Y.sprite = (key) => {                                      // rasterise each SVG once (768 px), then scale the bitmap
  if (Y._sprites[key]) return Y._sprites[key];
  const im = Y.G[key]; if (!im) return null;
  const cv = document.createElement('canvas'); cv.width = cv.height = 768; cv.getContext('2d').drawImage(im, 0, 0, 768, 768);
  return (Y._sprites[key] = cv);
};
Y.graphic = (key, x, y, size, { enterPreset = 'popIn', k = 1, idlePreset = 'none', t = 0, seed = 0, alpha = 1 } = {}) => {
  const im = Y.sprite(key); if (!im) { Y.reports.push({ kind: 'missing-graphic', text: key }); return; }
  const e = Y.enter(enterPreset, k), i = Y.idle(idlePreset, t, seed); const c = Y.c;
  if (e.a <= 0) return;
  c.save(); c.globalAlpha *= alpha * e.a * i.a; c.translate(x + e.dx + i.dx, y + e.dy + i.dy); c.rotate(e.r + i.r);
  const s = size * e.s * i.s; c.drawImage(im, -s / 2, -s / 2, s, s); c.restore();
};
// Soft shadow ellipse under a graphic, gives illustrations weight on the dark background.
Y.shadow = (x, y, w, a = 0.35) => { const c = Y.c; c.save(); c.globalAlpha *= a; c.fillStyle = '#000'; c.beginPath(); c.ellipse(x, y, w / 2, w / 9, 0, 0, 6.283); c.fill(); c.restore(); };
