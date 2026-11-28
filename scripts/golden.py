"""Golden frames of every template's graphics (no footage), for visual regression tests.

  python scripts/golden.py            # (re)write tests/golden/*.png after an intended design change
  python scripts/golden.py --check    # compare (what tests/test_golden.py does)

Graphics are drawn over flat mid-grey at fixed params, so only layout/typography/motion changes show up.
Compared at 270x480 with a tolerance, so Chromium antialiasing differences between machines don't fail it."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "golden")
# moments that carry the design: hook, method plate, reveal text, end card
TIMES = {"driveway": [1.6, 4.5, 8.8, 11.2, 14.5], "house-wash": [1.6, 4.0, 12.5, 19.5], "roof": [1.8, 5.0, 12.0, 17.5], "windows": [1.6, 5.5, 8.5, 10.5, 16.0], "deck": [1.6, 5.5, 8.6, 10.5, 16.0]}
PARAMS = {"business": "Golden Exterior Care", "initials": "G", "area": "Testville", "url": "example.com/quote",
          "accent": "#7FD1FF", "aligned": True}
SIZE = (270, 480)


def shoot(tpl):
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [tpl, params, ts] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.addInitScript(x => { window.PARAMS = x; }, params);
      await p.goto('file://' + tpl);
      await p.evaluate(async () => { await document.fonts.ready; window.relayout && window.relayout();
        document.body.style.background = '#808080'; });
      const out = [];
      for (const t of ts) { await p.evaluate(t => seek(t), t);
        out.push((await p.screenshot({ type: 'png' })).toString('base64')); }
      console.log(JSON.stringify(out)); await b.close();
    })();"""
    arg = json.dumps([f"{ROOT}/templates/{tpl}/index.html", PARAMS, TIMES[tpl]])
    out = subprocess.run(["node", "-e", js, arg], capture_output=True, text=True, check=True, cwd=ROOT).stdout
    import base64, io
    return [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB").resize(SIZE, Image.LANCZOS)
            for b in json.loads(out)]


def path(tpl, t):
    return os.path.join(GOLDEN, f"{tpl}_{t:05.2f}.png")


def diff(a, b):
    """Mean abs difference (0..255) and share of pixels that changed a lot."""
    x, y = np.asarray(a, np.float32), np.asarray(b, np.float32)
    d = np.abs(x - y).max(axis=2)
    return float(d.mean()), float((d > 60).mean())


def main():
    check = "--check" in sys.argv
    os.makedirs(GOLDEN, exist_ok=True)
    bad = []
    for tpl, ts in TIMES.items():
        for t, img in zip(ts, shoot(tpl)):
            p = path(tpl, t)
            if check:
                m, share = diff(img, Image.open(p).convert("RGB"))
                print(f"{tpl} {t:5.2f}s  mean {m:.2f}  changed {share:.3%}")
                if m > 2.0 or share > .01:
                    bad.append(p)
                    img.save(p.replace(".png", ".new.png"))
            else:
                img.save(p)
    if bad:
        sys.exit("visual change in: " + ", ".join(os.path.basename(b) for b in bad))


if __name__ == "__main__":
    main()
