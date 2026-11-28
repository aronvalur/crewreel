"""End card: footage drawn inside the proof card (compositor `box` layers) and the card's layout."""
import json, os, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import render  # noqa: E402

W, H = render.W, render.H


def test_box_alpha_is_a_rounded_rect():
    a = render.box_alpha([100, 300, 880, 560], radius=44)[..., 0]
    assert a[580, 540] == 1 and a[100, 540] == 0 and a[580, 50] == 0     # inside / above / left
    assert a[302, 102] == 0                                               # corner cut by the radius
    assert a[300 + 44, 100 + 1] == 1                                      # straight edge below the corner


def test_into_box_frames_the_focus_point():
    """A marker at the focus point must land in the middle of the box, filling it (cover, no bars)."""
    img = np.zeros((H, W, 3), np.float32)
    img[1150:1250, 500:600] = 255                                         # marker around (550, 1200)
    box = [96, 316, 888, 560]
    out = render.into_box(img, box, zoom=1.0, fx=550 / W, fy=1200 / H)
    ys, xs = np.where(out[..., 0] > 128)
    cy, cx = ys.mean(), xs.mean()
    assert abs(cx - (box[0] + box[2] / 2)) < 30 and abs(cy - (box[1] + box[3] / 2)) < 30
    assert out[:box[1] - 2].max() == 0 and out[box[1] + box[3] + 2:].max() == 0   # nothing outside the box


def test_end_card_layout_fits_safe_zones_and_long_names():
    """Proof card, name and CTA sit between the top 300 px and bottom 520 px UI zones; long names shrink."""
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [tpl, params] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.addInitScript(x => { window.PARAMS = x; }, params);
      await p.goto('file://' + tpl);
      await p.evaluate(async () => { await document.fonts.ready; });
      const r = await p.evaluate(() => {
        seek(META.duration - .1);
        const box = s => document.querySelector('#end ' + s).getBoundingClientRect();
        const biz = document.querySelector('#end .biz');
        const kinds = window.__plan.layers.map(L => L.box ? (L.src || 'shadow') : 'bg');
        return { proof: box('.proof'), id: box('.id'), cta: box('.cta'), url: box('.url'), over: biz.scrollWidth - biz.clientWidth,
                 lines: Math.round(biz.scrollHeight / parseFloat(getComputedStyle(biz).fontSize) / 1.02), kinds };
      });
      console.log(JSON.stringify(r)); await b.close();
    })();"""
    params = {"business": "Northern Lights Pressure Washing & Soft Wash Co", "area": "Greater Reykjavík",
              "url": "example.com/quote", "aligned": True}
    for tpl in ("driveway", "house-wash", "roof", "windows"):
        arg = json.dumps([f"{ROOT}/templates/{tpl}/index.html", params])
        r = json.loads(subprocess.run(["node", "-e", js, arg], capture_output=True, text=True, check=True,
                                      cwd=ROOT).stdout)
        assert r["proof"]["top"] >= 300 and r["url"]["bottom"] <= H - 520, (tpl, r)
        assert r["cta"]["height"] > 100 and r["id"]["bottom"] < r["cta"]["top"] - 16, (tpl, r)
        assert r["lines"] <= 2, (tpl, r)
        assert r["over"] <= 1, f"{tpl}: business name overflows ({r['over']} px)"
        assert r["kinds"] == ["bg", "shadow", "before", "after"], r["kinds"]
