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
  await page.evaluate(async () => { await document.fonts.ready; if (window.relayout) window.relayout(); });
  const meta = await page.evaluate(() => window.META);
  const fps = meta.fps || 30;
  const total = secondsArg ? Math.min(Number(secondsArg), meta.duration) : meta.duration;
  const n = Math.round(fps * total);
  // Fast transparent capture straight from CDP (Playwright's screenshot is ~25 % slower).
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  const plans = [];
  let prevSig = null, prevOv = -1, shots = 0;
  for (let i = 0; i < n; i++) {
    // The overlay is a pure function of the DOM, so if the DOM didn't change the pixels didn't either:
    // about half of a reel's frames are held text. Skip those screenshots and point at the last PNG.
    const { plan, sig } = await page.evaluate(t => { window.seek(t); return { plan: window.__plan, sig: document.body.outerHTML }; }, i / fps);
    if (sig !== prevSig) {
      const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', optimizeForSpeed: true });
      fs.writeFileSync(`${outDir}/${String(i).padStart(4, '0')}.png`, Buffer.from(data, 'base64'));
      prevSig = sig; prevOv = i; shots++;
    }
    plans.push({ ...plan, ov: prevOv });
  }
  console.error(`overlay: ${shots}/${n} frames captured, ${n - shots} reused`);
  fs.writeFileSync(`${outDir}/plan.json`, JSON.stringify({ meta: { ...meta, fps, duration: total }, frames: plans }));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
