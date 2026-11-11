// ytf page runtime: loads /job/timeline.json, draws frame t, exposes window.OP for the renderer.
'use strict';
(async () => {
  const OP = (window.OP = { ready: false });
  try {
    const qs = new URLSearchParams(location.search);
    await document.fonts.load('900 40px "Inter"'); await document.fonts.load('800 40px "Inter"');
    await document.fonts.load('700 40px "Inter"'); await document.fonts.load('600 40px "Inter"');
    await document.fonts.load('500 40px "Inter"'); await document.fonts.load('700 40px "JetBrains Mono"');

    if (qs.get('thumb')) {                                 // still-image mode for thumbnails
      const job = await (await fetch('/job/thumb.json')).json();
      Y.init(job.width, job.height); await Y.loadGraphics(Y.graphicKeys(job.params));
      OP.still = (q = 0.92) => { Y.reports = []; Y.background(); Y.TEMPLATES.thumb.draw(job.params, 0, 0, {}); return Y.c.canvas.toDataURL('image/jpeg', q); };
      OP.ready = true; return;
    }

    const TL = await (await fetch('/job/timeline.json')).json();
    Y.init(TL.width, TL.height);
    // Shorts: templates draw in a smaller virtual box that is scaled up ~1.34x, so everything reads well on a phone.
    const VS = Y.vertical ? 940 / 700 : 1;
    if (Y.vertical) Y.box = { x: 0, y: 0, w: 700, h: 760 };
    const scenes = TL.scenes, caps = TL.captions || [];
    await Y.loadGraphics(Y.graphicKeys(scenes.map((s) => s.params)));
    const bootReports = Y.reports.slice();
    // The first scene is fully formed from frame 0 (the hook must read instantly, no fade-in).
    const localT = (i, t) => t - scenes[i].start + (i === 0 ? 5 : 0);
    const missing = scenes.filter((s) => !Y.TEMPLATES[s.template]).map((s) => s.template);
    if (missing.length) throw new Error('unknown templates: ' + [...new Set(missing)].join(', '));

    const layer = () => { const cv = document.createElement('canvas'); cv.width = TL.width; cv.height = TL.height; return cv.getContext('2d'); };
    const main = Y.c, L1 = layer(), L2 = layer(); const TR = 0.35;

    const sceneAt = (t) => { let i = scenes.findIndex((s) => t >= s.start && t < s.end); if (i < 0) i = t < scenes[0].start ? 0 : scenes.length - 1; return i; };
    const drawScene = (ctx, s, lt) => {
      ctx.clearRect(0, 0, TL.width, TL.height); Y.c = ctx; ctx.save();
      if (Y.vertical) { ctx.translate(70, 230); ctx.scale(VS, VS); }
      try { Y.TEMPLATES[s.template].draw(s.params, lt, s.end - s.start, s); }
      catch (e) { Y.reports.push({ kind: 'error', scene: s.id, msg: String(e && e.message || e) }); }
      ctx.restore(); Y.c = main;
    };
    const capAt = (t) => caps.findIndex((g) => t >= g.s && t < g.e);

    function drawCaption(t) {
      const gi = capAt(t); if (gi < 0) return;
      const g = caps[gi], c = main; const k = Y.eob(Y.seg(t, g.s, g.s + 0.12));
      const words = g.text.toUpperCase().split(' '); const hi = (g.hi || '').toUpperCase();
      let size = 84; c.font = Y.font(size, 900);
      while (c.measureText(g.text.toUpperCase()).width > TL.width - 120 && size > 48) { size -= 4; c.font = Y.font(size, 900); }
      const sp = c.measureText(' ').width; const ws = words.map((w) => c.measureText(w).width); const tw = ws.reduce((a, b) => a + b, 0) + sp * (words.length - 1);
      c.save(); c.translate(TL.width / 2, 1395); c.scale(Y.lerp(0.85, 1, k), Y.lerp(0.85, 1, k)); c.globalAlpha = Y.clamp(k * 1.5);
      let x = -tw / 2; c.textAlign = 'left'; c.textBaseline = 'middle'; c.lineJoin = 'round';
      words.forEach((w, i) => { c.lineWidth = 14; c.strokeStyle = 'rgba(0,0,0,0.85)'; c.strokeText(w, x, 0);
        c.fillStyle = w.replace(/[^A-Z0-9%$]/g, '') === hi.replace(/[^A-Z0-9%$]/g, '') && hi ? Y.BRAND.warn : '#fff'; c.fillText(w, x, 0); x += ws[i] + sp; });
      c.restore();
    }

    OP.draw = (t) => {
      const i = sceneAt(t), s = scenes[i], lt = localT(i, t);
      Y.background();
      drawScene(L1, s, lt);
      const k = i > 0 && lt < TR ? Y.eo(lt / TR) : 1;
      if (k < 1) { const p = scenes[i - 1]; drawScene(L2, p, p.end - p.start); main.save(); main.globalAlpha = 1 - k; main.drawImage(L2.canvas, 0, 0); main.restore(); }
      main.save(); main.globalAlpha = k; main.translate(0, (1 - k) * 36 * Y.S); main.drawImage(L1.canvas, 0, 0); main.restore();
      if (TL.format === 'short' && s.template !== 'kinetic_text') drawCaption(t);   // the words are already on screen
    };
    // null = frame animates; otherwise a key that stays equal while the picture is unchanged
    OP.frameKey = (t) => {
      const i = sceneAt(t), s = scenes[i], lt = localT(i, t); const tm = Y.TEMPLATES[s.template];
      const st = tm.settle ? tm.settle(s.params, s.end - s.start, s) : null;
      if (st == null || lt < Math.max(st, TR + 0.05)) return null;
      if (TL.format !== 'short' || s.template === 'kinetic_text') return 's' + i;
      const gi = capAt(t); if (gi >= 0 && t < caps[gi].s + 0.13) return null;
      return 's' + i + ':c' + gi;
    };
    OP.frame = (t, q = 0.92) => { OP.draw(t); return main.canvas.toDataURL('image/jpeg', q); };
    OP.duration = () => TL.duration;
    OP.check = (step = 0.25) => {
      const found = [];
      for (let t = 0; t < TL.duration; t += step) { Y.reports = []; OP.draw(t); for (const r of Y.reports) found.push({ t: +t.toFixed(2), scene: scenes[sceneAt(t)].id, ...r }); }
      found.push(...bootReports.map((r) => ({ t: 0, scene: '-', ...r })));
      const seen = new Set(); return found.filter((r) => { const key = r.scene + r.kind + r.text; if (seen.has(key)) return false; seen.add(key); return true; });
    };
    OP.ready = true;
  } catch (e) { OP.bootError = String(e && e.stack || e); }
})();
