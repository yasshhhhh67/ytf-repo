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

// Static background (no drift, so held frames can be reused by the renderer).
Y.background = (accent) => {
  const c = Y.c, W = Y.W, H = Y.H;
  const g = c.createLinearGradient(0, 0, W * 0.4, H); g.addColorStop(0, Y.BRAND.bg1); g.addColorStop(1, Y.BRAND.bg0);
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  if (!Y._grid || Y._grid.w !== W) {
    const off = document.createElement('canvas'); off.width = W; off.height = H; const o = off.getContext('2d');
    o.fillStyle = 'rgba(140,160,255,0.09)'; const step = 44 * Y.S;
    for (let y = step / 2; y < H; y += step) for (let x = step / 2; x < W; x += step) { o.beginPath(); o.arc(x, y, 1.8 * Y.S, 0, 6.283); o.fill(); }
    Y._grid = { w: W, cv: off };
  }
  c.drawImage(Y._grid.cv, 0, 0);
  Y.glow(W * 0.85, H * 0.12, Math.max(W, H) * 0.45, accent || Y.BRAND.accent, 0.22);
  Y.glow(W * 0.1, H * 0.92, Math.max(W, H) * 0.4, Y.BRAND.accent2, 0.10);
  const v = c.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.max(W, H) * 0.75);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.45)'); c.fillStyle = v; c.fillRect(0, 0, W, H);
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
