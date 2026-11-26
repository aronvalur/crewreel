"""Template layout behaviour: text must stay off the action and get out of the way."""
import json, os, subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINS = 24


def run(tpl, params, t_list):
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [tpl, params, ts] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
      await p.addInitScript(x => { window.PARAMS = x; }, params);
      await p.goto('file://' + tpl);
      const r = await p.evaluate(ts => {
        const el = document.getElementById('plate');
        const out = ts.map(t => { seek(t); const r = el.getBoundingClientRect();
          return { t, op: +getComputedStyle(el).opacity, disp: getComputedStyle(el).display, top: r.top, bottom: r.bottom }; });
        return { zone: window.PLATE_ZONE, frames: out };
      }, ts);
      console.log(JSON.stringify(r)); await b.close();
    })();"""
    arg = json.dumps([f"{ROOT}/templates/{tpl}/index.html", params, t_list])
    out = subprocess.run(["node", "-e", js, arg], capture_output=True, text=True, check=True, cwd=ROOT).stdout
    return json.loads(out)


def profile(center, width=.12):
    import numpy as np
    y = (np.arange(BINS) + .5) / BINS
    p = np.exp(-.5 * ((y - center) / width) ** 2)
    return list(p / p.sum())


def act(names, prof):
    return {"activity": {n: {"profile": prof} for n in names}}


@pytest.mark.parametrize("tpl,names", [("driveway", ["action1"]), ("house-wash", ["action1", "action2", "action3"])])
def test_plate_moves_low_when_action_is_up_top(tpl, names):
    r = run(tpl, act(names, profile(.25, .07)), [4.0])
    assert r["zone"] == 1
    assert r["frames"][0]["top"] > 1920 * .55       # plate now sits in the lower part of the frame


@pytest.mark.parametrize("tpl,names", [("driveway", ["action1"]), ("house-wash", ["action1", "action2", "action3"])])
def test_plate_stays_high_when_action_is_low_or_unknown(tpl, names):
    r = run(tpl, act(names, profile(.66)), [4.0])
    assert r["zone"] == 0 and r["frames"][0]["bottom"] < 1920 * .45
    assert run(tpl, {}, [4.0])["zone"] == 0


def test_plate_leaves_after_reading_time():
    r = run("driveway", {}, [4.5, 7.8])
    a, b = r["frames"]
    assert a["op"] > .95                     # readable early in the action segment
    assert b["op"] < .05                     # gone before the reveal so the action breathes
