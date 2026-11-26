// Renders the transparent motion-graphics layer of a template, frame by frame.
// The template is a deterministic HTML composition: it exposes window.seek(t) and,
// after each seek, window.__plan = { layers:[...] } describing which footage the
// compositor should put underneath. No timers or CSS animations are allowed.
//
// usage: node render/overlay.js <template.html> <outDir> [paramsJson] [seconds]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [tpl, outDir, paramsArg = '{}', secondsArg] = process.argv.slice(2);
  fs.mkdirSync(outDir, { recursive: true });
  const params = JSON.parse(fs.existsSync(paramsArg) ? fs.readFileSync(paramsArg, 'utf8') : paramsArg);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.addInitScript(p => { window.PARAMS = p; }, params);
  await page.goto('file://' + path.resolve(tpl));
  await page.evaluate(() => document.fonts.ready);
  const meta = await page.evaluate(() => window.META);
  const fps = meta.fps || 30;
  const total = secondsArg ? Math.min(Number(secondsArg), meta.duration) : meta.duration;
  const n = Math.round(fps * total);
  const plans = [];
  for (let i = 0; i < n; i++) {
    plans.push(await page.evaluate(t => { window.seek(t); return window.__plan; }, i / fps));
    await page.screenshot({ path: `${outDir}/${String(i).padStart(4, '0')}.png`, omitBackground: true });
  }
  fs.writeFileSync(`${outDir}/plan.json`, JSON.stringify({ meta: { ...meta, fps, duration: total }, frames: plans }));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
