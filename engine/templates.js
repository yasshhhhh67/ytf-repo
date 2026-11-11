// ytf scene templates. Each template: { draw(p, lt, d, scene), settle(p, d, scene) -> seconds after which the frame
// is static (lets the renderer reuse frames), or null if it animates throughout }.
// p = params (validated against schemas in ytf/templates.py), lt = seconds into the scene, d = scene duration.
'use strict';
(() => {
const B = Y.BRAND, T = Y.TEMPLATES;
const box = () => Y.box;
const cx = () => Y.box.x + Y.box.w / 2;

// optional heading at top of the content box; returns y below it
function heading(title, lt, y0) {
  if (!title) return y0;
  const b = box(); const size = Y.vertical ? 64 : 66;
  const w = Y.wrap(title, b.w, size, 40, 2, 800);
  const h = Y.riseText(w.lines, cx(), y0, w.size, B.ink, Y.seg(lt, 0.05, 0.9));
  return y0 + h + 36;
}

// ---------- 1. title_card ----------
T.title_card = {
  draw(p, lt) {
    const b = box(); let y = b.y + b.h * (Y.vertical ? (p.graphic ? 0.08 : 0.28) : (p.graphic ? 0.1 : 0.26));
    if (p.graphic) { const gs = Y.vertical ? 260 : 280; Y.graphic(p.graphic, cx(), y + gs / 2, gs, { enterPreset: 'zoomIn', k: Y.seg(lt, 0, 0.5) }); y += gs + 40; }
    if (p.kicker) { Y.pill(p.kicker.toUpperCase(), cx(), y, 30, B.accent, '#fff', Y.seg(lt, 0, 0.35)); y += 70; }
    const w = Y.wrap(p.title, b.w * 0.92, Y.vertical ? 104 : 112, 56, 3, 900);
    const h = Y.riseText(w.lines, cx(), y, w.size, B.ink, Y.seg(lt, 0.1, 1.0), 'center', 900, 1.08);
    y += h + 18;
    const k = Y.eo(Y.seg(lt, 0.5, 1.1)); const c = Y.c;
    c.fillStyle = B.accent; Y.rr(cx() - 90 * k, y, 180 * k, 8, 4); c.fill();
    if (p.subtitle) {
      const s = Y.wrap(p.subtitle, b.w * 0.85, Y.vertical ? 44 : 46, 30, 2, 600);
      c.save(); c.globalAlpha = Y.eo(Y.seg(lt, 0.7, 1.2)); Y.text(s.lines, cx(), y + 36, s.size, B.muted, 'center', 600); c.restore();
    }
  },
  settle: () => 1.3,
};

// ---------- 2. kinetic_text: 1-4 short lines revealed in turn, one emphasised word ----------
T.kinetic_text = {
  draw(p, lt, d, scene) {
    const b = box(); const n = p.lines.length; const c = Y.c;
    const size0 = Y.vertical ? 92 : 100;
    let size = size0; for (const l of p.lines) size = Math.min(size, Y.fitSize(l, b.w * 0.94, size0, 52, 900));
    const gs = p.graphic ? (Y.vertical ? 300 : 300) : 0;
    const lh = size * 1.22, total = n * lh + (gs ? gs + 30 : 0); let y = b.y + (b.h - total) / 2;
    if (gs) { Y.shadow(cx(), y + gs * 0.95, gs * 0.6, 0.3); Y.graphic(p.graphic, cx(), y + gs / 2, gs, { enterPreset: 'bounceIn', k: Y.seg(lt, 0, 0.5), idlePreset: 'float', t: lt }); y += gs + 30; }
    const emph = (p.emphasis || '').toLowerCase();
    p.lines.forEach((line, i) => {
      const at = Y.revealAt(scene, i, n, 0.1);
      const k = Y.eo(Y.seg(lt, at, at + 0.45)); if (k <= 0) { y += lh; return; }
      c.font = Y.font(size, 900); const words = line.split(' ');
      const widths = words.map((w) => c.measureText(w + ' ').width); const tw = widths.reduce((a, b2) => a + b2, 0) - c.measureText(' ').width;
      let x = cx() - tw / 2;
      c.save(); c.globalAlpha = k; c.textAlign = 'left'; c.textBaseline = 'alphabetic';
      words.forEach((w, j) => {
        const isE = emph && w.toLowerCase().replace(/[^a-z0-9%$]/g, '') === emph.replace(/[^a-z0-9%$]/g, '');
        if (isE) { const pk = Y.eob(Y.seg(lt, at + 0.25, at + 0.6)); c.save(); c.globalAlpha = k * pk; Y.rr(x - 14, y + size * 0.08, (widths[j] - c.measureText(' ').width) + 28, size * 1.12, 18); c.fillStyle = B.accent; c.fill(); c.restore(); }
        c.fillStyle = isE ? '#fff' : B.ink; c.fillText(w, x, y + size + (1 - k) * 30); x += widths[j];
      });
      c.restore(); y += lh;
    });
  },
  settle: (p, d, s) => (p.graphic ? null : Y.revealAt(s, p.lines.length - 1, p.lines.length, 0.1) + 0.7),
};

// ---------- 3. labeled_diagram: nodes + directed edges, layered layout ----------
function layers(nodes, edges) {
  const ids = nodes.map((n) => n.id), inc = {}; ids.forEach((i) => (inc[i] = []));
  edges.forEach((e) => { if (inc[e.to] && ids.includes(e.from)) inc[e.to].push(e.from); });
  const lvl = {}; const visit = (i, seen = new Set()) => { if (lvl[i] != null) return lvl[i]; if (seen.has(i)) return 0; seen.add(i);
    return (lvl[i] = inc[i].length ? 1 + Math.max(...inc[i].map((j) => visit(j, seen))) : 0); };
  ids.forEach((i) => visit(i));
  const by = []; nodes.forEach((n) => { (by[lvl[n.id]] ||= []).push(n); });
  return by.filter(Boolean);
}
T.labeled_diagram = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y);
    const L = layers(p.nodes, p.edges || []); const pos = {};
    const areaY = top + 10, areaH = b.y + b.h - areaY - 20;
    L.forEach((row, li) => row.forEach((n, ni) => {
      if (Y.vertical) pos[n.id] = { x: b.x + (b.w * (ni + 0.5)) / row.length, y: areaY + (areaH * (li + 0.5)) / L.length };
      else pos[n.id] = { x: b.x + (b.w * (li + 0.5)) / L.length, y: areaY + (areaH * (ni + 0.5)) / row.length };
    }));
    const maxRow = Math.max(...L.map((r) => r.length));
    const nw = Math.min(Y.vertical ? b.w / maxRow - 30 : b.w / L.length - 70, 360), nh = Y.vertical ? 104 : 112;
    const order = p.nodes.map((n) => n.id); const at = (id) => Y.revealAt(scene, order.indexOf(id), order.length, 0.3);
    (p.edges || []).forEach((e) => {
      const a = pos[e.from], z = pos[e.to]; if (!a || !z) return;
      const t0 = Math.max(at(e.from), at(e.to)) + 0.25, k = Y.eio(Y.seg(lt, t0, t0 + 0.5)); if (k <= 0) return;
      const dx = z.x - a.x, dy = z.y - a.y, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len;
      const ox = Y.vertical ? 0 : nw / 2 + 8, oy = Y.vertical ? nh / 2 + 8 : 0;
      const sx = a.x + ux * Math.abs(ux * ox + uy * oy) , sy = a.y + uy * Math.abs(ux * ox + uy * oy);
      const ex = z.x - ux * Math.abs(ux * ox + uy * oy), ey = z.y - uy * Math.abs(ux * ox + uy * oy);
      Y.arrow(sx, sy, ex, ey, 'rgba(160,180,255,0.75)', 5, k, 20);
      if (e.label && k > 0.95) { c.save(); c.globalAlpha = Y.seg(lt, t0 + 0.5, t0 + 0.8); Y.label(e.label, (sx + ex) / 2 + (Y.vertical ? 16 : 0), (sy + ey) / 2 - (Y.vertical ? 0 : 14), B.accent2, 22, Y.vertical ? 'left' : 'center'); c.restore(); }
    });
    p.nodes.forEach((n, i) => {
      const q = pos[n.id]; const t0 = at(n.id), k = Y.eob(Y.seg(lt, t0, t0 + 0.45)); if (Y.seg(lt, t0, t0 + 0.45) <= 0) return;
      c.save(); c.translate(q.x, q.y); c.scale(Y.lerp(0.6, 1, k), Y.lerp(0.6, 1, k)); c.globalAlpha = Y.clamp(k);
      const hi = n.highlight; Y.card(-nw / 2, -nh / 2, nw, nh, { fill: hi ? B.accent : 'rgba(255,255,255,0.08)', line: hi ? B.accent : B.cardLine, r: 26 });
      const s = Y.wrap(n.label, nw - 36, 40, 24, 2, 800); Y.text(s.lines, 0, -(s.lines.length * s.size * 1.15) / 2 - 4, s.size, '#fff', 'center', 800, 1.15);
      c.restore();
    });
  },
  settle: (p, d, s) => Y.revealAt(s, p.nodes.length - 1, p.nodes.length, 0.3) + 1.4,
};

// ---------- 4. process_flow: numbered steps with a travelling dot ----------
T.process_flow = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const n = p.steps.length;
    const at = (i) => Y.revealAt(scene, i, n, 0.3);
    const pts = []; let cw, ch;
    if (Y.vertical) { const gap = 26; ch = Math.min(190, (b.y + b.h - top - gap * (n - 1)) / n); cw = b.w;
      const off = (b.y + b.h - top - (n * ch + (n - 1) * gap)) / 2;
      for (let i = 0; i < n; i++) pts.push({ x: b.x, y: top + off + i * (ch + gap) }); }
    else { const gap = 60; cw = (b.w - gap * (n - 1)) / n; ch = Math.min(360, b.y + b.h - top - 40);
      for (let i = 0; i < n; i++) pts.push({ x: b.x + i * (cw + gap), y: top + (b.y + b.h - top - ch) / 2 }); }
    // connector
    const done = p.steps.filter((_, i) => lt > at(i)).length;
    for (let i = 0; i < n - 1; i++) {
      const a = pts[i], z = pts[i + 1]; const k = Y.eio(Y.seg(lt, at(i + 1) - 0.25, at(i + 1) + 0.2)); if (k <= 0) continue;
      if (Y.vertical) Y.arrow(a.x + 70, a.y + ch, a.x + 70, Y.lerp(a.y + ch, z.y, k), B.accent, 5, 1, 0);
      else Y.arrow(a.x + cw + 8, a.y + ch / 2, Y.lerp(a.x + cw + 8, z.x - 8, k), a.y + ch / 2, B.accent, 6, k >= 1 ? 1 : 0.999, 18);
    }
    p.steps.forEach((s, i) => {
      const q = pts[i], k = Y.eo(Y.seg(lt, at(i), at(i) + 0.45)); if (k <= 0) return;
      const active = i === done - 1;
      c.save(); c.globalAlpha = k; c.translate(Y.vertical ? (1 - k) * 60 : 0, Y.vertical ? 0 : (1 - k) * 60);
      Y.card(q.x, q.y, cw, ch, { fill: active ? 'rgba(61,107,255,0.22)' : B.card, line: active ? B.accent : B.cardLine });
      const r = 36; const nx = Y.vertical ? q.x + 70 : q.x + 60, ny = Y.vertical ? q.y + ch / 2 : q.y + 60;
      c.fillStyle = active ? B.accent : 'rgba(255,255,255,0.12)'; c.beginPath(); c.arc(nx, ny, r, 0, 6.283); c.fill();
      c.font = Y.font(34, 900); c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(String(i + 1), nx, ny + 2);
      if (Y.vertical) {
        const tx = q.x + 130, tw = cw - 160;
        const l = Y.wrap(s.label, tw, 44, 28, s.detail ? 1 : 2, 800);
        const dl = s.detail ? Y.wrap(s.detail, tw, 30, 22, 2, 500) : null;
        const hh = l.lines.length * l.size * 1.15 + (dl ? 10 + dl.lines.length * dl.size * 1.2 : 0);
        let ty = q.y + (ch - hh) / 2 - 6; Y.text(l.lines, tx, ty, l.size, '#fff', 'left', 800, 1.15);
        if (dl) Y.text(dl.lines, tx, ty + l.lines.length * l.size * 1.15 + 6, dl.size, B.muted, 'left', 500, 1.2);
      } else {
        const tx = q.x + 30, tw = cw - 60;
        const l = Y.wrap(s.label, tw, 46, 28, 3, 800); const hy = Y.text(l.lines, tx, q.y + 116, l.size, '#fff', 'left', 800, 1.15);
        if (s.detail) { const dl = Y.wrap(s.detail, tw, 30, 22, 4, 500); Y.text(dl.lines, tx, q.y + 130 + hy, dl.size, B.muted, 'left', 500, 1.22); }
      }
      c.restore();
    });
  },
  settle: (p, d, s) => Y.revealAt(s, p.steps.length - 1, p.steps.length, 0.3) + 0.8,
};

// ---------- 5. comparison_split ----------
T.comparison_split = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y);
    const vH = p.verdict ? 120 : 0; const gap = 36; const sides = [p.left, p.right]; const cols = [B.accent2, B.accent];
    // size cards to their content, then centre them in the free area
    const ptSize = Y.vertical ? 36 : 40, maxPts = Math.max(p.left.points.length, p.right.points.length);
    const want = 40 + 56 * 1.3 + maxPts * (ptSize * 1.2 * 2 + 10) + 30;
    const free = { y: top, h: b.y + b.h - top - vH };
    const cardH = Math.min(Y.vertical ? (free.h - gap) / 2 : free.h, want);
    const used = Y.vertical ? cardH * 2 + gap : cardH;
    const area = { y: free.y + (free.h - used) / 2, h: used };
    const rects = Y.vertical
      ? [{ x: b.x, y: area.y, w: b.w, h: (area.h - gap) / 2 }, { x: b.x, y: area.y + (area.h + gap) / 2, w: b.w, h: (area.h - gap) / 2 }]
      : [{ x: b.x, y: area.y, w: (b.w - gap) / 2, h: area.h }, { x: b.x + (b.w + gap) / 2, y: area.y, w: (b.w - gap) / 2, h: area.h }];
    const nPts = sides.reduce((a, s) => a + s.points.length, 0) + 2; let idx = 0;
    sides.forEach((s, si) => {
      const r = rects[si]; const t0 = Y.revealAt(scene, idx++, nPts, 0.2); const k = Y.eo(Y.seg(lt, t0, t0 + 0.45)); if (k <= 0) { idx += s.points.length; return; }
      c.save(); c.globalAlpha = k;
      Y.card(r.x, r.y, r.w, r.h, { fill: 'rgba(255,255,255,0.05)', line: cols[si] });
      const hs = Y.fitSize(s.heading, r.w - 80, 56, 32, 900); Y.text([s.heading], r.x + 40, r.y + 24, hs, cols[si], 'left', 900);
      let y = r.y + 40 + hs * 1.3;
      const ps = Math.min(...s.points.map((pt) => Y.wrap(pt, r.w - 120, ptSize, 24, 2, 600).size));
      s.points.forEach((pt) => {
        const tp = Y.revealAt(scene, idx++, nPts, 0.2); const kp = Y.eo(Y.seg(lt, tp, tp + 0.4));
        if (kp > 0) { c.save(); c.globalAlpha = k * kp;
          c.fillStyle = cols[si]; c.beginPath(); c.arc(r.x + 52, y + ps * 0.62, 8, 0, 6.283); c.fill();
          const w = Y.wrap(pt, r.w - 120, ps, ps, 2, 600); Y.text(w.lines, r.x + 80, y, ps, B.ink, 'left', 600, 1.2); c.restore(); }
        y += ps * 1.2 * 2 + 10;
      });
      c.restore();
    });
    if (p.verdict) { const tv = Y.revealAt(scene, nPts - 1, nPts, 0.2) + 0.2; const s = Y.fitSize(p.verdict, b.w - 120, 40, 26, 800);
      Y.pill(p.verdict, cx(), b.y + b.h - vH / 2 + 10, s, B.accent, '#fff', Y.seg(lt, tv, tv + 0.4)); }
  },
  settle: (p, d, s) => { const n = p.left.points.length + p.right.points.length + 2; return Y.revealAt(s, n - 1, n, 0.2) + 1.0; },
};

// ---------- 6. big_number: animated counter ----------
T.big_number = {
  draw(p, lt) {
    const b = box(); const c = Y.c; const k = Y.eio(Y.seg(lt, 0.2, 1.6));
    const dec = p.decimals ?? (Number.isInteger(p.value) ? 0 : 1);
    const txt = (p.prefix || '') + Y.fmtNum(p.value * k, dec) + (p.suffix ? ' ' + p.suffix : '');
    const final = (p.prefix || '') + Y.fmtNum(p.value, dec) + (p.suffix ? ' ' + p.suffix : '');
    const size = Y.fitSize(final, b.w * 0.95, Y.vertical ? 170 : 190, 70, 900);
    const y = b.y + b.h * (p.graphic ? 0.5 : 0.36);
    if (p.graphic) { const gs = Y.vertical ? 230 : 240; Y.graphic(p.graphic, cx(), y - size * 0.6 - gs / 2 - 10, gs, { enterPreset: 'bounceIn', k: Y.seg(lt, 0, 0.5) }); }
    Y.glow(cx(), y, size * 2.2, B.accent, 0.3 * Y.seg(lt, 0, 0.6));
    c.save(); c.globalAlpha = Y.seg(lt, 0, 0.3); c.font = Y.font(size, 900); c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(txt, cx(), y); c.restore();
    const l = Y.wrap(p.label, b.w * 0.9, Y.vertical ? 50 : 54, 30, 2, 700);
    c.save(); c.globalAlpha = Y.eo(Y.seg(lt, 0.9, 1.4)); Y.text(l.lines, cx(), y + size * 0.62, l.size, B.accent2, 'center', 700); c.restore();
    if (p.context) { const x = Y.wrap(p.context, b.w * 0.85, 36, 24, 3, 500);
      c.save(); c.globalAlpha = Y.eo(Y.seg(lt, 1.4, 1.9)); Y.text(x.lines, cx(), y + size * 0.62 + l.lines.length * l.size * 1.2 + 30, x.size, B.muted, 'center', 500, 1.25); c.restore(); }
  },
  settle: () => 2.0,
};

// ---------- 7. bar_chart: horizontal bars ----------
T.bar_chart = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const n = p.bars.length;
    const max = Math.max(...p.bars.map((x) => x.value)) || 1;
    const labW = Y.vertical ? 300 : 420, valW = Y.vertical ? 190 : 260;
    const foot = p.source ? 60 : 10; const rowH = Math.min(Y.vertical ? 130 : 120, (b.y + b.h - top - foot) / n);
    const off = (b.y + b.h - top - foot - n * rowH) / 2;
    const ls = Math.min(...p.bars.map((x) => Y.fitSize(x.label, labW - 20, 40, 24, 700)));
    p.bars.forEach((bar, i) => {
      const t0 = Y.revealAt(scene, i, n, 0.3); const k = Y.eio(Y.seg(lt, t0, t0 + 0.8)); if (Y.seg(lt, t0 - 0.1, t0) <= 0 && k <= 0) return;
      const y = top + off + i * rowH; const bh = rowH * 0.56;
      c.save(); c.globalAlpha = Y.seg(lt, t0 - 0.1, t0 + 0.2);
      Y.text([bar.label], b.x + labW - 20, y + (rowH - ls) / 2 - 6, ls, B.ink, 'right', 700);
      const fw = (b.w - labW - valW) * (bar.value / max) * k;
      Y.rr(b.x + labW, y + (rowH - bh) / 2, Math.max(fw, bh * 0.2), bh, bh / 2); c.fillStyle = bar.highlight ? B.accent : 'rgba(150,170,230,0.45)'; c.fill();
      const v = Y.fmtNum(bar.value * k, Number.isInteger(bar.value) ? 0 : 1) + (p.unit ? ' ' + p.unit : '');
      c.font = Y.font(38, 800); c.fillStyle = bar.highlight ? '#fff' : B.muted; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(v, b.x + labW + Math.max(fw, bh * 0.2) + 18, y + rowH / 2);
      c.restore();
    });
    if (p.source) { c.save(); c.globalAlpha = Y.seg(lt, 1, 1.5); Y.label('Source: ' + p.source, b.x, b.y + b.h - 10, B.muted, 20); c.restore(); }
  },
  settle: (p, d, s) => Y.revealAt(s, p.bars.length - 1, p.bars.length, 0.3) + 1.0,
};

// ---------- 8. recap_list: checklist ----------
T.recap_list = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const n = p.items.length;
    const rowH = Math.min(Y.vertical ? 170 : 150, (b.y + b.h - top) / n);
    const off = (b.y + b.h - top - n * rowH) / 2;
    const size = Math.min(...p.items.map((it) => Y.wrap(it, b.w - 140, Y.vertical ? 44 : 48, 28, 2, 700).size));
    p.items.forEach((it, i) => {
      const t0 = Y.revealAt(scene, i, n, 0.35); const k = Y.eo(Y.seg(lt, t0, t0 + 0.45)); if (k <= 0) return;
      const y = top + off + i * rowH; c.save(); c.globalAlpha = k; c.translate((1 - k) * 50, 0);
      const ck = Y.eob(Y.seg(lt, t0 + 0.15, t0 + 0.5)); c.fillStyle = B.good; c.beginPath(); c.arc(b.x + 36, y + rowH / 2 - 8, 30 * ck, 0, 6.283); c.fill();
      if (ck > 0.6) { c.strokeStyle = '#fff'; c.lineWidth = 7; c.lineCap = 'round'; c.beginPath(); c.moveTo(b.x + 22, y + rowH / 2 - 8); c.lineTo(b.x + 32, y + rowH / 2 + 3); c.lineTo(b.x + 52, y + rowH / 2 - 20); c.stroke(); }
      const w = Y.wrap(it, b.w - 140, size, size, 2, 700); Y.text(w.lines, b.x + 100, y + rowH / 2 - (w.lines.length * size * 1.18) / 2 - 10, size, B.ink, 'left', 700);
      c.restore();
    });
  },
  settle: (p, d, s) => Y.revealAt(s, p.items.length - 1, p.items.length, 0.35) + 0.8,
};

// ---------- 9. end_card ----------
T.end_card = {
  draw(p, lt) {
    const b = box(); const c = Y.c;
    let y0 = Y.vertical ? b.y + b.h * (p.graphic ? 0.12 : 0.3) : b.y + 40;   // long-form: keep the lower area free for YouTube end-screen elements
    if (p.graphic && Y.vertical) { const gs = 300; Y.graphic(p.graphic, cx(), y0 + gs / 2, gs, { enterPreset: 'bounceIn', k: Y.seg(lt, 0, 0.5), idlePreset: 'float', t: lt }); y0 += gs + 40; }
    const w = Y.wrap(p.line, b.w * 0.9, Y.vertical ? 84 : 76, 44, 3, 900);
    const h = Y.riseText(w.lines, cx(), y0, w.size, '#fff', Y.seg(lt, 0.1, 0.9), 'center', 900, 1.1);
    if (p.next) { const s = Y.wrap(p.next, b.w * 0.85, 42, 28, 2, 600); c.save(); c.globalAlpha = Y.eo(Y.seg(lt, 0.6, 1.1)); Y.text(s.lines, cx(), y0 + h + 24, s.size, B.accent2, 'center', 600); c.restore(); }
    if (!Y.vertical) { c.save(); c.globalAlpha = 0.5 * Y.seg(lt, 1, 1.5); c.setLineDash([14, 12]); c.strokeStyle = B.cardLine; c.lineWidth = 3;
      Y.rr(b.x + 80, b.y + b.h * 0.42, b.w * 0.42, b.h * 0.5, 24); c.stroke(); Y.rr(b.x + b.w * 0.55, b.y + b.h * 0.42, b.w * 0.37, b.h * 0.5, 24); c.stroke(); c.restore(); }
  },
  settle: () => 1.6,
};

// ---------- 10. parallel_grid: few big cores working in sequence vs many small cores at once ----------
T.parallel_grid = {
  draw(p, lt, d) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const gap = 40;
    const panels = Y.vertical
      ? [{ x: b.x, y: top, w: b.w, h: (b.y + b.h - top - gap) / 2 }, { x: b.x, y: top + (b.y + b.h - top + gap) / 2, w: b.w, h: (b.y + b.h - top - gap) / 2 }]
      : [{ x: b.x, y: top, w: (b.w - gap) / 2, h: b.y + b.h - top }, { x: b.x + (b.w + gap) / 2, y: top, w: (b.w - gap) / 2, h: b.y + b.h - top }];
    const tasks = p.tasks || 256; const run = Math.max(1, d - 1.2);
    [[p.left_label, p.left_cores, B.accent2], [p.right_label, p.right_cores, B.accent]].forEach(([label, n, col], pi) => {
      const r = panels[pi]; const k0 = Y.eo(Y.seg(lt, pi * 0.25, pi * 0.25 + 0.5)); if (k0 <= 0) return;
      c.save(); c.globalAlpha = k0; Y.card(r.x, r.y, r.w, r.h, { fill: 'rgba(255,255,255,0.04)', line: col });
      const ls = Y.fitSize(label, r.w - 60, 44, 28, 900); Y.text([label], r.x + 30, r.y + 18, ls, col, 'left', 900);
      const cols = Math.ceil(Math.sqrt(n * (r.w / (r.h - 150)))); const rows = Math.ceil(n / cols);
      const gw = r.w - 60, gh = r.h - 150; const cell = Math.min(gw / cols, gh / rows); const ox = r.x + 30 + (gw - cell * cols) / 2, oy = r.y + 90;
      const throughput = n;                                        // tasks finished per "tick"
      const ticks = (Y.clamp((lt - 0.8) / run) * tasks * (pi === 0 ? 0.08 : 1));
      const done = Math.min(tasks, Math.floor(ticks)); const active = Math.floor(ticks * 6) % Math.max(1, n);
      for (let i = 0; i < n; i++) {
        const x = ox + (i % cols) * cell, y = oy + Math.floor(i / cols) * cell;
        const on = pi === 0 ? i === active % n && done < tasks : done < tasks && lt > 0.8;
        const flick = pi === 1 ? 0.55 + 0.45 * Math.sin(lt * 9 + i * 1.7) : 1;
        c.fillStyle = on ? col : 'rgba(255,255,255,0.10)'; c.globalAlpha = k0 * (on ? flick : 1);
        Y.rr(x + cell * 0.08, y + cell * 0.08, cell * 0.84, cell * 0.84, Math.min(10, cell * 0.2)); c.fill();
      }
      c.globalAlpha = k0; const bx = r.x + 30, by = r.y + r.h - 46, bw = r.w - 60;
      Y.rr(bx, by, bw, 18, 9); c.fillStyle = 'rgba(255,255,255,0.1)'; c.fill();
      Y.rr(bx, by, Math.max(18, bw * done / tasks), 18, 9); c.fillStyle = col; c.fill();
      Y.label(`${done}/${tasks} ${p.task_label || 'tasks'}`, bx + bw, by - 12, B.muted, 22, 'right');
      c.restore(); void throughput;
    });
  },
  settle: () => null,
};

// ---------- 11. matrix_multiply: A x B = C, one output cell at a time ----------
T.matrix_multiply = {
  draw(p, lt, d) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y);
    const A = p.a, Bm = p.b; const m = A.length, k = A[0].length, n = Bm[0].length;
    const C = A.map((row) => Bm[0].map((_, j) => row.reduce((s, v, t) => s + v * Bm[t][j], 0)));
    const cellsW = k + n + n + 2.4; const cell = Math.min((b.w - 40) / cellsW, (b.y + b.h - top - (p.caption ? 140 : 40)) / Math.max(m, k), Y.vertical ? 120 : 130);
    const totalW = cell * cellsW; let x = cx() - totalW / 2;
    const blockH = Math.max(m, k) * cell + 110; const y = top + Math.max(30, (b.y + b.h - top - (p.caption ? 90 : 0) - blockH) / 2);
    const steps = m * n; const per = Math.max(0.5, (d - 1.5) / steps); const s = Y.clamp((lt - 0.8) / per, 0, steps); const cur = Math.min(steps - 1, Math.floor(s));
    const ci = Math.floor(cur / n), cj = cur % n; const showAll = lt > 0.8 + per * steps;
    const drawM = (M, x0, kind) => M.forEach((row, i) => row.forEach((v, j) => {
      const hi = !showAll && ((kind === 'A' && i === ci) || (kind === 'B' && j === cj) || (kind === 'C' && i === ci && j === cj));
      const filled = kind !== 'C' || i * n + j < s || showAll;
      c.fillStyle = hi ? (kind === 'C' ? B.good : B.accent) : 'rgba(255,255,255,0.07)';
      Y.rr(x0 + j * cell + 4, y + i * cell + 4, cell - 8, cell - 8, 12); c.fill();
      if (filled) { c.font = Y.font(cell * 0.38, 800); c.fillStyle = '#fff'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(String(kind === 'C' ? C[i][j] : v), x0 + j * cell + cell / 2, y + i * cell + cell / 2 + 2); }
    }));
    c.save(); c.globalAlpha = Y.seg(lt, 0, 0.5);
    drawM(A, x, 'A'); x += k * cell; c.font = Y.font(cell * 0.5, 900); c.fillStyle = B.muted; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('×', x + cell * 0.6, y + (m * cell) / 2);
    x += cell * 1.2; drawM(Bm, x, 'B'); x += n * cell; c.fillStyle = B.muted; c.fillText('=', x + cell * 0.6, y + (m * cell) / 2); x += cell * 1.2; drawM(C, x, 'C');
    c.restore();
    if (!showAll && lt > 0.8) {
      const terms = A[ci].map((v, t) => `${v}×${Bm[t][cj]}`).join(' + ') + ` = ${C[ci][cj]}`;
      const fs = Y.fitSize(terms, b.w * 0.95, Y.vertical ? 48 : 54, 26, 700, B.mono);
      c.font = Y.font(fs, 700, B.mono); c.fillStyle = B.accent2; c.textAlign = 'center'; c.textBaseline = 'alphabetic'; c.fillText(terms, cx(), y + Math.max(m, k) * cell + 90);
    }
    if (p.caption) { const w = Y.wrap(p.caption, b.w * 0.9, 38, 24, 2, 600); c.save(); c.globalAlpha = Y.seg(lt, 0.5, 1); Y.text(w.lines, cx(), b.y + b.h - w.lines.length * w.size * 1.2 - 10, w.size, B.muted, 'center', 600); c.restore(); }
  },
  settle: () => null,
};


// =================== graphic templates (Fluent Emoji preset + motion presets) ===================
const fitPill = (txt, x, y, maxW, k, fill = B.accent) => {
  const fs = Y.fitSize(txt, maxW - 40, 34, 22, 800); Y.c.font = Y.font(fs, 800);
  const w = Y.c.measureText(txt).width + fs * 1.1; const b = box();
  x = Y.clamp(x, b.x + w / 2, b.x + b.w - w / 2); Y.pill(txt, x, y, fs, fill, '#fff', k); return x;
};
const labelUnder = (txt, x, y, maxW, size, color = B.ink, k = 1) => {
  const w = Y.wrap(txt, maxW, size, 22, 2, 800); Y.c.save(); Y.c.globalAlpha *= Y.clamp(k); Y.text(w.lines, x, y, w.size, color, 'center', 800, 1.12); Y.c.restore();
  return w.lines.length * w.size * 1.12;
};

// ---------- hero_graphic: one big illustration with 0-3 callouts ----------
T.hero_graphic = {
  draw(p, lt) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y);
    const capH = p.caption ? 120 : 0, area = { y: top, h: b.y + b.h - top - capH }, n = (p.callouts || []).length;
    const size = Math.min(area.h * 0.8, Y.vertical ? 400 : 460);
    const gx = Y.vertical || !n ? cx() : b.x + b.w * 0.33, gy = area.y + area.h / 2;
    Y.shadow(gx, gy + size * 0.48, size * 0.65, 0.35 * Y.seg(lt, 0.1, 0.5));
    Y.graphic(p.graphic, gx, gy, size, { enterPreset: 'bounceIn', k: Y.seg(lt, 0.05, 0.65), idlePreset: p.motion || 'float', t: lt });
    (p.callouts || []).forEach((txt, i) => {
      const t0 = 0.6 + i * 0.45, k = Y.eo(Y.seg(lt, t0, t0 + 0.4)); if (k <= 0) return;
      let px, py;
      if (Y.vertical) { const pos = [[-0.5, -0.42], [0.5, 0.02], [-0.5, 0.46]][i]; px = gx + pos[0] * size; py = gy + pos[1] * size; }
      else { px = b.x + b.w * 0.74; py = area.y + area.h * (n === 1 ? 0.5 : 0.22 + (i * 0.56) / (n - 1)); }
      c.save(); c.globalAlpha = k; c.strokeStyle = 'rgba(160,180,255,0.55)'; c.lineWidth = 3; c.setLineDash([8, 8]);
      c.beginPath(); c.moveTo(gx + (px > gx ? 1 : -1) * size * 0.32, gy + (py - gy) * 0.4); c.lineTo(px, py); c.stroke(); c.setLineDash([]); c.restore();
      fitPill(txt, px, py, Y.vertical ? 330 : 560, k);
    });
    if (p.caption) labelUnder(p.caption, cx(), b.y + b.h - capH + 10, b.w * 0.9, Y.vertical ? 40 : 44, B.muted, Y.seg(lt, 0.6, 1.1));
  },
  settle: (p) => (p.motion && p.motion !== 'none' ? null : 0.6 + (p.callouts || []).length * 0.45 + 0.5),
};

// ---------- versus_graphics: two illustrations compared ----------
T.versus_graphics = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const sides = [p.left, p.right];
    const area = { y: top, h: b.y + b.h - top }; const gap = Y.vertical ? 70 : 120;
    const rects = Y.vertical
      ? [{ x: b.x, y: area.y, w: b.w, h: (area.h - gap) / 2 }, { x: b.x, y: area.y + (area.h + gap) / 2, w: b.w, h: (area.h - gap) / 2 }]
      : [{ x: b.x, y: area.y, w: (b.w - gap) / 2, h: area.h }, { x: b.x + (b.w + gap) / 2, y: area.y, w: (b.w - gap) / 2, h: area.h }];
    sides.forEach((sd, i) => {
      const r = rects[i], t0 = Y.revealAt(scene, i, 2, 0.15, 0.9), k = Y.seg(lt, t0, t0 + 0.55); if (k <= 0) return;
      const win = p.winner === (i ? 'right' : 'left'), lose = p.winner && p.winner !== 'none' && !win;
      const done = Y.seg(lt, t0 + 1.2, t0 + 1.6);
      c.save(); c.globalAlpha = Y.clamp(k * 2) * (lose ? Y.lerp(1, 0.55, done) : 1);
      Y.card(r.x, r.y, r.w, r.h, { fill: win && done ? 'rgba(61,107,255,0.16)' : B.card, line: win && done ? B.accent : B.cardLine });
      const gs = Y.vertical ? Math.min(r.h * 0.78, 260) : Math.min(r.w * 0.55, r.h * 0.5);
      const gx = Y.vertical ? r.x + 40 + gs / 2 : r.x + r.w / 2, gy = Y.vertical ? r.y + r.h / 2 : r.y + r.h * 0.38;
      Y.graphic(sd.graphic, gx, gy, gs, { enterPreset: i ? 'slideInRight' : 'slideInLeft', k, idlePreset: sd.motion || 'float', t: lt, seed: i });
      const tx = Y.vertical ? r.x + 80 + gs : r.x + 30, tw = Y.vertical ? r.w - gs - 110 : r.w - 60;
      const ls = Y.wrap(sd.label, tw, Y.vertical ? 50 : 58, 30, 2, 900);
      const ly = Y.vertical ? r.y + r.h / 2 - (ls.lines.length * ls.size * 1.1 + (sd.sub ? 50 : 0)) / 2 - 8 : r.y + r.h * 0.7;
      const hh = Y.text(ls.lines, Y.vertical ? tx : r.x + r.w / 2, ly, ls.size, i ? B.accent : B.accent2, Y.vertical ? 'left' : 'center', 900, 1.1);
      if (sd.sub) { const sw = Y.wrap(sd.sub, tw, 34, 22, 2, 600); Y.text(sw.lines, Y.vertical ? tx : r.x + r.w / 2, ly + hh + 4, sw.size, B.muted, Y.vertical ? 'left' : 'center', 600, 1.2); }
      if (win && done > 0) { Y.pill('✓', r.x + r.w - 46, r.y + 46, 36, B.good, '#fff', done); }
      c.restore();
    });
    const vk = Y.eob(Y.seg(lt, 0.5, 0.9));
    if (vk > 0) { const vx = Y.vertical ? cx() : b.x + b.w / 2, vy = Y.vertical ? area.y + area.h / 2 : area.y + area.h * 0.38;
      c.save(); c.translate(vx, vy); c.scale(vk, vk); c.fillStyle = B.warn; c.beginPath(); c.arc(0, 0, 46, 0, 6.283); c.fill();
      c.font = Y.font(40, 900); c.fillStyle = '#0b1020'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('VS', 0, 3); c.restore(); }
  },
  settle: (p) => ((p.left.motion && p.left.motion !== 'none') || (p.right.motion && p.right.motion !== 'none') ? null : 2.4),
};

// ---------- crowd: many small copies of one illustration (optionally vs one big one) ----------
T.crowd = {
  draw(p, lt) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y);
    const area = { x: b.x, y: top, w: b.w, h: b.y + b.h - top };
    let crowdR = { ...area };
    if (p.contrast) {
      const cs = Y.vertical ? Math.min(220, area.h * 0.3) : Math.min(area.h * 0.55, 380);
      const cr = Y.vertical ? { x: area.x, y: area.y, w: area.w, h: cs + 70 } : { x: area.x, y: area.y, w: area.w * 0.32, h: area.h };
      crowdR = Y.vertical ? { x: area.x, y: area.y + cr.h + 30, w: area.w, h: area.h - cr.h - 30 } : { x: area.x + area.w * 0.38, y: area.y, w: area.w * 0.62, h: area.h };
      const k = Y.seg(lt, 0.05, 0.6);
      Y.graphic(p.contrast.graphic, cr.x + cr.w / 2, cr.y + cs / 2, cs, { enterPreset: 'bounceIn', k, idlePreset: 'float', t: lt });
      labelUnder(p.contrast.label, cr.x + cr.w / 2, cr.y + cs + 4, cr.w * 0.95, Y.vertical ? 40 : 46, B.accent2, k);
    }
    const n = p.count, labH = 70; const gh = crowdR.h - labH;
    const cols = Math.max(1, Math.round(Math.sqrt(n * crowdR.w / gh))), rows = Math.ceil(n / cols);
    const cell = Math.min(crowdR.w / cols, gh / rows); const ox = crowdR.x + (crowdR.w - cell * cols) / 2, oy = crowdR.y + (gh - cell * rows) / 2;
    const appear = p.contrast ? 0.7 : 0.15;
    for (let i = 0; i < n; i++) {
      const t0 = appear + (i / n) * 0.8, k = Y.seg(lt, t0, t0 + 0.3); if (k <= 0) continue;
      Y.graphic(p.graphic, ox + (i % cols + 0.5) * cell, oy + (Math.floor(i / cols) + 0.5) * cell, cell * 0.86,
        { enterPreset: 'popIn', k, idlePreset: 'bob', t: lt, seed: i });
    }
    labelUnder(p.label, crowdR.x + crowdR.w / 2, crowdR.y + gh + 8, crowdR.w * 0.95, Y.vertical ? 40 : 46, B.accent, Y.seg(lt, appear + 0.8, appear + 1.2));
  },
  settle: () => null,
};

// ---------- graphic_steps: 2-4 steps, each an illustration + label ----------
T.graphic_steps = {
  draw(p, lt, d, scene) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const n = p.steps.length;
    p.steps.forEach((st, i) => {
      const t0 = Y.revealAt(scene, i, n, 0.25), k = Y.seg(lt, t0, t0 + 0.5); if (k <= 0) return;
      if (Y.vertical) {
        const rowH = (b.y + b.h - top) / n, y = top + i * rowH + rowH / 2, gs = Math.min(rowH * 0.8, 190);
        Y.graphic(st.graphic, b.x + gs / 2 + 10, y, gs, { enterPreset: 'bounceIn', k, idlePreset: 'none', t: lt });
        c.save(); c.globalAlpha = Y.eo(k); const w = Y.wrap(st.label, b.w - gs - 60, 48, 28, 2, 800);
        Y.text(w.lines, b.x + gs + 40, y - (w.lines.length * w.size * 1.12) / 2 - 8, w.size, B.ink, 'left', 800, 1.12); c.restore();
        if (i < n - 1 && Y.seg(lt, t0 + 0.4, t0 + 0.7) > 0) Y.arrow(b.x + gs / 2 + 10, y + gs / 2 + 4, b.x + gs / 2 + 10, y + rowH - gs / 2 - 6, B.accent, 5, Y.eio(Y.seg(lt, t0 + 0.4, t0 + 0.7)), 16);
      } else {
        const colW = b.w / n, x = b.x + colW * (i + 0.5), gs = Math.min(colW * 0.6, 300), gy = top + (b.y + b.h - top) * 0.42;
        Y.graphic(st.graphic, x, gy, gs, { enterPreset: 'bounceIn', k, idlePreset: 'none', t: lt });
        labelUnder(st.label, x, gy + gs / 2 + 20, colW * 0.9, 46, B.ink, Y.eo(k));
        if (i < n - 1 && Y.seg(lt, t0 + 0.4, t0 + 0.7) > 0) Y.arrow(x + gs / 2 + 10, gy, x + colW - gs / 2 - 10, gy, B.accent, 6, Y.eio(Y.seg(lt, t0 + 0.4, t0 + 0.7)), 20);
      }
    });
  },
  settle: (p, d, s) => Y.revealAt(s, p.steps.length - 1, p.steps.length, 0.25) + 1.0,
};

// ---------- graphic_flow: illustrations connected by a line, a packet travels along it ----------
T.graphic_flow = {
  draw(p, lt) {
    const b = box(); const c = Y.c; const top = heading(p.title, lt, b.y); const n = p.nodes.length;
    const pts = p.nodes.map((_, i) => Y.vertical
      ? { x: cx(), y: top + ((b.y + b.h - top) * (i + 0.5)) / n }
      : { x: b.x + (b.w * (i + 0.5)) / n, y: top + (b.y + b.h - top) * 0.42 });
    const gs = Y.vertical ? Math.min((b.y + b.h - top) / n * 0.62, 190) : Math.min(b.w / n * 0.5, 260);
    const lk = Y.eio(Y.seg(lt, 0.3, 0.3 + 0.3 * n));
    c.save(); c.strokeStyle = 'rgba(120,150,255,0.45)'; c.lineWidth = 8; c.lineCap = 'round'; c.setLineDash([2, 18]);
    c.beginPath(); c.moveTo(pts[0].x, pts[0].y);
    const last = pts[n - 1]; c.lineTo(Y.lerp(pts[0].x, last.x, lk), Y.lerp(pts[0].y, last.y, lk)); c.stroke(); c.restore();
    p.nodes.forEach((nd, i) => {
      const k = Y.seg(lt, 0.1 + i * 0.3, 0.5 + i * 0.3); if (k <= 0) return;
      Y.graphic(nd.graphic, pts[i].x, pts[i].y, gs, { enterPreset: 'zoomIn', k, idlePreset: 'none', t: lt });
      if (Y.vertical) { c.save(); c.globalAlpha = Y.eo(k); const w = Y.wrap(nd.label, 260, 40, 24, 2, 800); Y.text(w.lines, pts[i].x + gs / 2 + 26, pts[i].y - (w.lines.length * w.size * 1.12) / 2 - 6, w.size, B.ink, 'left', 800, 1.12); c.restore(); }
      else labelUnder(nd.label, pts[i].x, pts[i].y + gs / 2 + 16, b.w / n * 0.9, 44, B.ink, Y.eo(k));
    });
    if (p.packet && lt > 0.3 + 0.3 * n) {
      const u = ((lt - 0.3 - 0.3 * n) * 0.45) % 1, seg = u * (n - 1), j = Math.min(n - 2, Math.floor(seg)), f = Y.eio(seg - j);
      Y.graphic(p.packet, Y.lerp(pts[j].x, pts[j + 1].x, f), Y.lerp(pts[j].y, pts[j + 1].y, f), gs * 0.42, { k: 1, idlePreset: 'pulse', t: lt });
    }
  },
  settle: (p) => (p.packet ? null : 0.6 + 0.3 * p.nodes.length),
};

// ---------- thumbnail (still) ----------
T.thumb = {
  draw(p) {
    const c = Y.c, W = Y.W, H = Y.H;
    Y.glow(W * 0.72, H * 0.5, Math.max(W, H) * 0.5, B.accent, 0.55);
    if (p.graphic) { const gs = Math.min(W, H) * (Y.vertical ? 0.62 : 0.6); const gx = Y.vertical ? W / 2 : W * 0.77, gy = Y.vertical ? H * 0.66 : H * 0.52;
      Y.shadow(gx, gy + gs * 0.47, gs * 0.6, 0.45); Y.graphic(p.graphic, gx, gy, gs); }
    else {
    // stylised chip motif on the right
    const s = Math.min(W, H) * 0.42, x0 = Y.vertical ? W / 2 - s / 2 : W * 0.66 - s / 2, y0 = Y.vertical ? H * 0.58 : H / 2 - s / 2;
    c.save(); c.strokeStyle = B.accent2; c.lineWidth = 6 * Y.S;
    for (let i = 0; i < 6; i++) { const o = (i + 0.5) * s / 6; [[x0 + o, y0 - s * 0.12, x0 + o, y0], [x0 + o, y0 + s, x0 + o, y0 + s * 1.12], [x0 - s * 0.12, y0 + o, x0, y0 + o], [x0 + s, y0 + o, x0 + s * 1.12, y0 + o]].forEach(([a, b2, c2, d2]) => { c.beginPath(); c.moveTo(a, b2); c.lineTo(c2, d2); c.stroke(); }); }
    Y.rr(x0, y0, s, s, 26 * Y.S); c.fillStyle = '#0d1430'; c.fill(); c.stroke();
    const g = 5; for (let i = 0; i < g; i++) for (let j = 0; j < g; j++) { c.fillStyle = (i * 7 + j * 3) % 4 ? 'rgba(61,107,255,0.55)' : B.accent2; Y.rr(x0 + s * 0.12 + i * s * 0.155, y0 + s * 0.12 + j * s * 0.155, s * 0.12, s * 0.12, 6 * Y.S); c.fill(); }
    c.restore();
    }
    const tx = Y.vertical ? W / 2 : W * 0.06, tw = Y.vertical ? W * 0.88 : W * 0.52, align = Y.vertical ? 'center' : 'left';
    const w = Y.wrap(p.text, tw, Y.vertical ? 150 : 128, 60, 3, 900);
    const ty = Y.vertical ? H * 0.14 : H / 2 - (w.lines.length * w.size * 1.05) / 2 - 20;
    c.save(); c.shadowColor = 'rgba(0,0,0,0.6)'; c.shadowBlur = 24 * Y.S;
    w.lines.forEach((l, i) => { c.font = Y.font(w.size, 900); c.textAlign = align; c.textBaseline = 'alphabetic'; c.fillStyle = i === w.lines.length - 1 ? B.warn : '#fff'; c.fillText(l, tx, ty + w.size + i * w.size * 1.05); });
    c.restore();
    if (p.tag) Y.pill(p.tag.toUpperCase(), Y.vertical ? W / 2 : tx + 120 * Y.S, Y.vertical ? H * 0.09 : ty - 30 * Y.S, 34 * Y.S, B.accent);
  },
  settle: () => 0,
};
})();
