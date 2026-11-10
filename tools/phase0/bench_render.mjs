// Phase 0 benchmark B1-lite: Canvas2D frame capture in headless Chromium -> ffmpeg (libx264), single-threaded.
// Usage: node bench_render.mjs <W> <H> <seconds> <fps> <preset> <out.mp4> [jpegQ=0.9]
// Draws a representative explainer scene (gradient bg, dot grid, rising text, node diagram, travelling dot, counter).
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const [W, H, SECS, FPS, PRESET, OUT, Q = '0.9'] = process.argv.slice(2);
const w = +W, h = +H, n = Math.round(+SECS * +FPS);

const PAGE = `<!doctype html><html><body style="margin:0;background:#000">
<canvas id="cv" width="${w}" height="${h}"></canvas><script>
const cv = document.getElementById('cv'), c = cv.getContext('2d');
const W = ${w}, H = ${h}, S = Math.min(W, H) / 1080;
const ease = (x) => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
const nodes = [[0.2,0.35],[0.5,0.25],[0.8,0.35],[0.35,0.6],[0.65,0.6],[0.5,0.82]];
const edges = [[0,1],[1,2],[0,3],[1,3],[1,4],[2,4],[3,5],[4,5]];
window.frame = (t, q) => {
  const g = c.createLinearGradient(0, 0, W, H); g.addColorStop(0, '#0b1020'); g.addColorStop(1, '#131c3a');
  c.fillStyle = g; c.fillRect(0, 0, W, H);
  c.fillStyle = 'rgba(120,150,255,0.10)';
  for (let y = 0; y < H; y += 36*S) for (let x = (t*20)%(36*S); x < W; x += 36*S) { c.beginPath(); c.arc(x, y, 2*S, 0, 6.283); c.fill(); }
  const a = ease(t / 0.8);
  c.globalAlpha = a; c.fillStyle = '#fff'; c.font = '800 ' + Math.round(84*S) + 'px Inter, sans-serif'; c.textAlign = 'center';
  c.fillText('How a GPU thinks', W/2, H*0.12 + (1-a)*40*S);
  c.font = '600 ' + Math.round(38*S) + 'px Inter, sans-serif'; c.fillStyle = '#8fa8ff';
  c.fillText('thousands of cores, one simple sum each', W/2, H*0.12 + 70*S); c.globalAlpha = 1;
  c.lineWidth = 6*S;
  edges.forEach(([i,j], k) => { const p = ease((t - 0.5 - k*0.15) / 0.5); if (p <= 0) return;
    const [x1,y1] = nodes[i], [x2,y2] = nodes[j]; c.strokeStyle = 'rgba(143,168,255,0.6)'; c.beginPath();
    c.moveTo(x1*W, y1*H); c.lineTo((x1+(x2-x1)*p)*W, (y1+(y2-y1)*p)*H); c.stroke(); });
  nodes.forEach(([x,y], k) => { const p = ease((t - 0.3 - k*0.12) / 0.4); if (p <= 0) return;
    c.fillStyle = k === Math.floor(t*2)%6 ? '#2f5bff' : '#e8ecff'; c.beginPath(); c.arc(x*W, y*H, 46*S*p, 0, 6.283); c.fill();
    c.fillStyle = '#0b1020'; c.font = '700 ' + Math.round(30*S) + 'px Inter, sans-serif'; c.fillText('L'+k, x*W, y*H + 10*S); });
  const e = edges[Math.floor(t*1.5) % edges.length], f = (t*1.5) % 1, [x1,y1] = nodes[e[0]], [x2,y2] = nodes[e[1]];
  c.fillStyle = '#18b46b'; c.beginPath(); c.arc((x1+(x2-x1)*f)*W, (y1+(y2-y1)*f)*H, 14*S, 0, 6.283); c.fill();
  c.fillStyle = '#fff'; c.font = '800 ' + Math.round(120*S) + 'px Inter, sans-serif';
  c.fillText(Math.round(ease(t/6) * 100e9).toLocaleString('en-US'), W/2, H*0.95);
  return cv.toDataURL('image/jpeg', q);
};
window.ready = true;
</script></body></html>`;

const t0 = Date.now();
const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-dev-shm-usage', '--disable-background-timer-throttling', '--renderer-process-limit=1'] });
const page = await browser.newPage({ viewport: { width: Math.min(w, 1280), height: Math.min(h, 1280) } });
await page.setContent(PAGE); await page.waitForFunction('window.ready === true');
await page.evaluate(() => document.fonts.ready);
const boot = (Date.now() - t0) / 1000;

const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', FPS, '-i', '-', '-c:v', 'libx264', '-preset', PRESET,
  '-crf', '20', '-threads', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
let ffPeak = 0; const probe = setInterval(() => { try { const s = fs.readFileSync(`/proc/${ff.pid}/status`, 'utf8');
  const m = s.match(/VmHWM:\s+(\d+)/); if (m) ffPeak = Math.max(ffPeak, +m[1] / 1024); } catch {} }, 500);

const t1 = Date.now();
for (let i = 0; i < n; i++) {
  const d = await page.evaluate(([t, q]) => window.frame(t, q), [i / +FPS, +Q]);
  const b = Buffer.from(d.slice(d.indexOf(',') + 1), 'base64');
  if (!ff.stdin.write(b)) await new Promise((r) => ff.stdin.once('drain', r));
}
const capture = (Date.now() - t1) / 1000;
ff.stdin.end(); await new Promise((r) => ff.on('close', r)); clearInterval(probe);
const total = (Date.now() - t1) / 1000;

// peak RSS of all chromium processes (sampled at end; VmHWM per process)
let chromePeak = 0;
for (const pid of fs.readdirSync('/proc').filter((p) => /^\d+$/.test(p))) {
  try { const cmd = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8'); if (!/chrom/i.test(cmd)) continue;
    const m = fs.readFileSync(`/proc/${pid}/status`, 'utf8').match(/VmHWM:\s+(\d+)/); if (m) chromePeak += +m[1] / 1024; } catch {}
}
await browser.close();
console.log(JSON.stringify({ size: `${w}x${h}`, frames: n, fps_target: +FPS, preset: PRESET, boot_s: +boot.toFixed(1),
  capture_s: +capture.toFixed(1), total_s: +total.toFixed(1), effective_fps: +(n / total).toFixed(2),
  realtime_factor: +(total / +SECS).toFixed(1), chrome_peak_rss_mb_sum: Math.round(chromePeak), ffmpeg_peak_rss_mb: Math.round(ffPeak),
  out_mb: +(fs.statSync(OUT).size / 1048576).toFixed(2) }));
