"""Pipeline tests. Run: pytest -q   (needs ffmpeg, node + playwright, numpy, opencv)"""
import json, os, subprocess, sys
import numpy as np
import cv2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import align  # noqa: E402
import audio  # noqa: E402


def synthetic_pair(dx=40, dy=-30, ang=1.5):
    rng = np.random.default_rng(0)
    small = rng.random((60, 34)).astype(np.float32)
    base = cv2.resize(small, (1080 * 2, 1920 * 2), interpolation=cv2.INTER_CUBIC)
    base = (np.dstack([base] * 3) * 200 + 30).astype(np.uint8)
    cx, cy = 1080, 1920
    crop = lambda M: cv2.warpAffine(base, M, (1080, 1920))
    Mb = np.float32([[1, 0, -cx / 2], [0, 1, -cy / 2]])
    R = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    R[0, 2] += -cx / 2 + dx
    R[1, 2] += -cy / 2 + dy
    before = crop(Mb)
    after = (crop(R.astype(np.float32)) * .8 + 40).astype(np.uint8)  # 'cleaner' = brighter, lower contrast
    return before, after


def test_align_recovers_offset():
    b, a = synthetic_pair()
    M, score = align.estimate(b, a)
    assert M is not None, score
    warped = cv2.warpAffine(a, M, (1080, 1920))
    g = lambda x: cv2.cvtColor(x, cv2.COLOR_RGB2GRAY)[200:-200, 200:-200].astype(np.float32)
    assert np.corrcoef(g(warped).ravel(), g(b).ravel())[0, 1] > .95


def test_align_rejects_unrelated_frames():
    b, _ = synthetic_pair()
    noise = np.random.default_rng(5).integers(0, 255, b.shape, dtype=np.uint8)
    M, _ = align.estimate(b, noise)
    assert M is None


def test_meet_halfway_composes_to_full_transform():
    M = np.float32([[np.cos(.03), -np.sin(.03), 50], [np.sin(.03), np.cos(.03), -20]])
    Mb, Ma = align.meet_halfway(M)
    full = lambda A: np.vstack([A, [0, 0, 1]])
    np.testing.assert_allclose(np.linalg.inv(full(Mb)) @ full(Ma), full(M), atol=1e-3)


def test_audio_mix_without_vo(tmp_path):
    out = audio.build_mix({"duration": 4, "cuts": [1, 2], "impacts": [2]}, str(tmp_path / "m.wav"), str(tmp_path))
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                             capture_output=True, text=True).stdout)
    assert abs(d - 4) < .05


@pytest.mark.parametrize("tpl,n", [("driveway", 3), ("house-wash", 5)])
def test_template_plan_is_deterministic(tmp_path, tpl, n):
    """Seeking the same t twice must give the same plan; sources must be declared."""
    js = f"""
    const {{ chromium }} = require('playwright');
    (async () => {{
      const b = await chromium.launch(); const p = await b.newPage({{ viewport: {{ width: 1080, height: 1920 }} }});
      await p.goto('file://{ROOT}/templates/{tpl}/index.html');
      const r = await p.evaluate(() => {{
        const out = []; for (const t of [0, 4, 9.5, 10.5, 13, 16, 19.9, 4]) {{ seek(t); out.push(JSON.stringify(window.__plan)); }}
        return {{ plans: out, meta: window.META }};
      }});
      console.log(JSON.stringify(r)); await b.close();
    }})();"""
    f = tmp_path / "t.js"
    f.write_text(js)
    r = json.loads(subprocess.run(["node", str(f)], capture_output=True, text=True, check=True, cwd=ROOT).stdout)
    assert r["plans"][1] == r["plans"][-1]
    assert len(r["meta"]["sources"]) == n
    for p in r["plans"]:
        for L in json.loads(p)["layers"]:
            assert "color" in L or L["src"] in r["meta"]["sources"]


@pytest.mark.slow
def test_render_two_seconds(tmp_path):
    foot = tmp_path / "foot"
    subprocess.run([sys.executable, f"{ROOT}/scripts/gen_placeholder.py", "pavers", str(foot)], check=True)
    out = tmp_path / "r.mp4"
    subprocess.run([sys.executable, f"{ROOT}/render/render.py", f"{ROOT}/templates/driveway", str(foot), str(out),
                    "--seconds", "2"], check=True)
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(out)],
                                     capture_output=True, text=True).stdout)
    v = [s for s in info["streams"] if s["codec_type"] == "video"][0]
    assert (v["width"], v["height"]) == (1080, 1920)
    assert int(v["nb_frames"]) == 60
    assert any(s["codec_type"] == "audio" for s in info["streams"])
