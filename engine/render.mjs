// ytf renderer: drives engine/page.html in headless Chromium and pipes frames to ffmpeg.
//   node render.mjs <job_dir> check [step]                 -> JSON {duration, reports}
//   node render.mjs <job_dir> sheet <out.jpg> [step] [cols]  contact sheet with timestamps
//   node render.mjs <job_dir> frames <out_dir> <t1,t2,...>   full-size JPEG stills
//   node render.mjs <job_dir> video <out.mp4> <f0> <f1>      frames [f0, f1) -> silent H.264 chunk
//   node render.mjs <job_dir> thumb <out.jpg>                still from job_dir/thumb.json
// The page can only load files from this server; every other request is blocked.
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ENGINE = path.dirname(fileURLToPath(import.meta.url));
const [JOB, MODE, ...REST] = process.argv.slice(2);
const FONTS = { '/fonts/inter/': '/usr/share/fonts/opentype/inter/', '/fonts/jbm/': '/usr/share/fonts/truetype/jetbrains-mono/' };
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.otf': 'font/otf', '.ttf': 'font/ttf', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml' };
const X264_THREADS = process.env.X264_THREADS || '1';
const PRESET = process.env.X264_PRESET || 'veryfast';

function resolve(url) {
  const u = decodeURIComponent(url.split('?')[0]);
  for (const [pre, dir] of Object.entries(FONTS)) if (u.startsWith(pre)) return path.join(dir, path.basename(u));
  if (u.startsWith('/job/')) { const f = path.join(path.resolve(JOB), u.slice(5)); return f.startsWith(path.resolve(JOB)) ? f : null; }
  const f = path.join(ENGINE, u === '/' ? 'page.html' : u); return f.startsWith(ENGINE) ? f : null;
}
const server = http.createServer((req, res) => {
  const f = resolve(req.url);
  if (!f || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
  fs.createReadStream(f).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ args: ['--disable-gpu', '--disable-dev-shm-usage', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--renderer-process-limit=1', '--no-first-run'] });
const page = await browser.newPage({ viewport: { width: 1280, height: 1280 } });
await page.route('**/*', (route) => (route.request().url().startsWith(BASE) ? route.continue() : route.abort()));
const pageErrors = []; page.on('pageerror', (e) => pageErrors.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') pageErrors.push(m.text()); });
await page.goto(`${BASE}/page.html${MODE === 'thumb' ? '?thumb=1' : ''}`);
const st = await page.waitForFunction('window.OP && (window.OP.ready || window.OP.bootError)', null, { timeout: 120000 }).then(() => page.evaluate('OP.bootError || null'));
const done = async (code = 0) => { await browser.close(); server.close(); process.exit(code); };
if (st) { console.error('BOOT ERROR: ' + st + '\n' + pageErrors.join('\n')); await done(2); }
const jpg = (d) => Buffer.from(d.slice(d.indexOf(',') + 1), 'base64');

if (MODE === 'check') {
  const step = +(REST[0] || 0.25);
  const reports = await page.evaluate((s) => OP.check(s), step);
  console.log(JSON.stringify({ duration: await page.evaluate('OP.duration()'), reports, pageErrors }));
} else if (MODE === 'thumb') {
  fs.writeFileSync(REST[0], jpg(await page.evaluate('OP.still(0.92)'))); console.log(REST[0]);
} else if (MODE === 'frames') {
  fs.mkdirSync(REST[0], { recursive: true });
  for (const t of REST[1].split(',').map(Number)) fs.writeFileSync(path.join(REST[0], `t${t.toFixed(2)}.jpg`), jpg(await page.evaluate(([x]) => OP.frame(x, 0.92), [t])));
  console.log(REST[0]);
} else if (MODE === 'sheet') {
  const [out, step = '1', cols = '8'] = REST; const dur = await page.evaluate('OP.duration()');
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ytf-sheet-')); let n = 0;
  for (let t = +step / 2; t < dur; t += +step) fs.writeFileSync(path.join(tmp, `f${String(n++).padStart(4, '0')}.jpg`), jpg(await page.evaluate(([x]) => OP.frame(x, 0.8), [t])));
  const W = await page.evaluate('Y.W'), H = await page.evaluate('Y.H'); const tw = W > H ? 384 : 216, th = Math.round(tw * H / W);
  const r = spawnSync('ffmpeg', ['-v', 'error', '-y', '-framerate', '1', '-i', path.join(tmp, 'f%04d.jpg'), '-vf',
    `scale=${tw}:${th},drawtext=fontfile=/usr/share/fonts/opentype/inter/Inter-Bold.otf:text='%{eif\\:n*${step}+${+step / 2}\\:d}s':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=${cols}x${Math.ceil(n / +cols)}:padding=4:color=black`,
    '-frames:v', '1', '-q:v', '3', out]);
  fs.rmSync(tmp, { recursive: true, force: true });
  if (r.status) { console.error(String(r.stderr)); await done(1); } console.log(`${out} (${n} frames)`);
} else if (MODE === 'video') {
  const [out, f0s, f1s] = REST; const fps = await page.evaluate('fetch("/job/timeline.json").then(r=>r.json()).then(t=>t.fps)');
  const f0 = +f0s, f1 = +f1s;
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-c:v', 'libx264', '-preset', PRESET, '-crf', '17',
    '-g', String(Math.round(fps / 2)), '-bf', '2', '-flags', '+cgop', '-pix_fmt', 'yuv420p', '-threads', X264_THREADS, '-r', String(fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  let lastKey = null, lastBuf = null, reused = 0; const t0 = Date.now();
  for (let f = f0; f < f1; f++) {
    const t = f / fps; const key = await page.evaluate(([x]) => OP.frameKey(x), [t]);
    let buf;
    if (key !== null && key === lastKey && lastBuf) { buf = lastBuf; reused++; }
    else { buf = jpg(await page.evaluate(([x]) => OP.frame(x, 0.93), [t])); lastBuf = buf; }
    lastKey = key;
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); const code = await new Promise((r) => ff.on('close', r));
  console.log(JSON.stringify({ out, frames: f1 - f0, reused, seconds: +((Date.now() - t0) / 1000).toFixed(1), ffmpeg: code, pageErrors }));
  if (code) await done(1);
} else { console.error('unknown mode ' + MODE); await done(1); }
await done(0);
