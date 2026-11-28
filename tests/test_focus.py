"""Focus + calm-zone: close-ups land on the clean-up, text sits off the subject."""
import json, os, subprocess, sys
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import focus  # noqa: E402

W, H = 1080, 1920


def wall(seed=0):
    r = np.random.default_rng(seed)
    img = np.full((H, W, 3), 150, np.float32) + r.normal(0, 6, (H, W, 1))
    img[(np.arange(H) % 60) < 4] *= .6                      # board joints
    return np.clip(img, 0, 255).astype(np.uint8)


def test_change_points_find_the_cleaned_patch():
    b = wall()
    a = b.copy()
    a[1000:1300, 650:950] = np.clip(a[1000:1300, 650:950].astype(int) + 70, 0, 255)   # cleaned patch
    pts = focus.change_points(b, a)
    assert pts, "a clear clean-up must yield a focus point"
    fx, fy = pts[0]["fx"], pts[0]["fy"]
    assert abs(fx * W - 800) < 160 and abs(fy * H - 1150) < 260


def test_change_points_empty_when_nothing_changed():
    b = wall()
    assert focus.change_points(b, b.copy()) == []


def test_change_points_ignore_global_exposure_shift():
    b = wall()
    a = np.clip(b.astype(int) + 25, 0, 255).astype(np.uint8)       # phone exposed brighter, nothing cleaned
    a[300:600, 100:400] = np.clip(a[300:600, 100:400].astype(int) + 60, 0, 255)
    pts = focus.change_points(b, a, n=1)
    assert pts and pts[0]["fy"] < .45                        # the patch, not the whole frame


def test_busy_profile_peaks_on_a_window_and_is_flat_on_a_plain_wall():
    plain = focus.busy_profile(wall())
    assert max(plain) / min(plain) < 1.5
    img = wall()
    img[350:750, 300:780] = (60, 75, 90)                     # dark window with frame
    img[540:560, 300:780] = 235
    p = np.array(focus.busy_profile(img))
    top = p[4:9].mean()                                      # rows ~320-720
    low = p[13:17].mean()                                    # rows ~1040-1360
    assert top > 1.4 * low


def test_to_render_space_matches_size_and_zoom():
    img = wall()
    out = focus.to_render_space(img, np.eye(2, 3, dtype=np.float32), 1.2)
    assert out.shape == img.shape


def layout(tpl, params):
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [tpl, params] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.addInitScript(x => { window.PARAMS = x; }, params);
      await p.goto('file://' + tpl);
      await p.evaluate(async () => { await document.fonts.ready; window.relayout && window.relayout(); });
      const r = await p.evaluate(() => {
        seek(1.5); const hook = document.getElementById('hook').getBoundingClientRect();
        const plans = [14.2, 15.0, 16.2].map(t => { seek(t); return window.__plan.layers; });
        return { zone: window.HOOK_ZONE, hookTop: hook.top, plans };
      });
      console.log(JSON.stringify(r)); await b.close();
    })();"""
    arg = json.dumps([f"{ROOT}/templates/{tpl}/index.html", params])
    out = subprocess.run(["node", "-e", js, arg], capture_output=True, text=True, check=True, cwd=ROOT).stdout
    return json.loads(out)


def band(lo, hi, n=24):
    p = np.full(n, .5)
    p[lo:hi] = 2.0
    return list(p / p.sum())


@pytest.mark.parametrize("tpl", ["driveway", "house-wash", "roof", "windows"])
def test_hook_moves_off_a_busy_top(tpl):
    r = layout(tpl, {"busy": {"before": band(3, 9), "after": band(3, 9)}})
    assert r["zone"] == 1 and r["hookTop"] > 1920 * .5
    r = layout(tpl, {"busy": {"before": band(12, 18), "after": band(12, 18)}})
    assert r["zone"] == 0 and r["hookTop"] < 1920 * .3
    assert layout(tpl, {})["zone"] == 0                      # no data: designed default


def test_house_wash_close_ups_follow_focus():
    f = [{"fx": .7, "fy": .6, "score": 9}, {"fx": .3, "fy": .4, "score": 7}]
    plans = layout("house-wash", {"aligned": True, "focus": f})["plans"]
    first, mid, second = plans
    # close-up 1: before + after wiping in, both aimed at focus point 1
    assert [l["src"] for l in mid] == ["before", "after"] and "mask" in mid[1]
    assert all(abs(l["fx"] - .7) < 1e-6 and abs(l["fy"] - .6) < 1e-6 for l in mid)
    assert second[-1]["fx"] == .3 and second[-1]["fy"] == .4
    # no focus data -> designed fallback, single after layer
    plans = layout("house-wash", {"aligned": True})["plans"]
    assert len(plans[1]) == 1 and plans[1][0]["src"] == "after"


def roof_plans(params, ts):
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [tpl, params, ts] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.addInitScript(x => { window.PARAMS = x; }, params);
      await p.goto('file://' + tpl);
      const r = await p.evaluate(ts => ts.map(t => { seek(t); return window.__plan.layers; }), ts);
      console.log(JSON.stringify(r)); await b.close();
    })();"""
    arg = json.dumps([f"{ROOT}/templates/roof/index.html", params, ts])
    return json.loads(subprocess.run(["node", "-e", js, arg], capture_output=True, text=True, check=True,
                                     cwd=ROOT).stdout)


def test_roof_rinse_wipes_ridge_to_gutter():
    a, b, c = roof_plans({"aligned": True}, [8.9, 9.6, 12.0])
    assert a[1]["vmask"][1] < b[1]["vmask"][1]              # wipe edge moves down the roof
    assert "vmask" not in c[1] and c[1]["src"] == "after"   # settled on the clean roof
    (cf,) = roof_plans({"aligned": False}, [9.6])
    assert "vmask" not in cf[1] and 0 < cf[1]["alpha"] < 1  # no alignment: crossfade, never a broken wipe


def test_roof_close_up_follows_focus():
    (p,) = roof_plans({"aligned": True, "focus": [{"fx": .25, "fy": .55, "score": 9}]}, [13.6])
    assert [l["src"] for l in p] == ["before", "after"]
    assert all(l["fx"] == .25 and l["fy"] == .55 for l in p)


def test_vertical_mask_in_compositor():
    import render as R
    class C:
        def frame(self, t): return np.full((R.H, R.W, 3), 200, np.uint8)
    img, a = R.render_layer({"src": "x", "vmask": [-1, .5], "feather": 2}, {"x": C()})
    col = a[:, 0, 0]
    assert col[100] == 1 and col[-100] == 0 and abs(col[R.H // 2]) - .5 < .3
