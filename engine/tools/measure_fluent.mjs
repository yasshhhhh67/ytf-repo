// Measure how visible each installed illustration is on the dark channel background.
// Writes tools/assets/fluent_dark.json: keys whose average brightness is too low to read on navy.
//   node engine/tools/measure_fluent.mjs /srv/ytf/data/assets/fluent tools/assets/fluent_dark.json
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [dir, out] = process.argv.slice(2);
const keys = fs.readdirSync(dir).filter((f) => f.endsWith('.svg')).map((f) => f.slice(0, -4));
const browser = await chromium.launch({ args: ['--disable-gpu'] });
const page = await browser.newPage();
const results = {};
for (const k of keys) {
  const svg = fs.readFileSync(path.join(dir, k + '.svg'), 'utf8');
  results[k] = await page.evaluate(async (src) => {
    const im = new Image(); im.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(src)));
    await im.decode();
    const cv = document.createElement('canvas'); cv.width = cv.height = 96; const c = cv.getContext('2d');
    c.drawImage(im, 0, 0, 96, 96); const d = c.getImageData(0, 0, 96, 96).data;
    let sum = 0, n = 0;
    for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 128) { sum += (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255; n++; }
    return n ? +(sum / n).toFixed(3) : 0;
  }, svg);
}
await browser.close();
const dark = Object.entries(results).filter(([, l]) => l < 0.3).sort((a, b) => a[1] - b[1]);
fs.writeFileSync(out, JSON.stringify({ threshold: 0.3, dark: Object.fromEntries(dark) }, null, 1));
console.log(`${keys.length} measured, ${dark.length} too dark:`, dark.map(([k, l]) => `${k}=${l}`).join(' '));
