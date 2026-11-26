"""The split reveal must stay registered for the whole reveal, not only on frame 0.

Registration = align.py (frame 0 of after onto frame 0 of before, tested in test_pipeline)
+ stabilize.py (every frame of each clip locked onto its own frame 0, tested here)."""
import os, subprocess, sys
import numpy as np
import cv2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import render, stabilize  # noqa: E402


def shift_px(a, b):
    """Shift between two frames of the same take (px), phase correlation on a central crop."""
    g = lambda x: cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (540, 960),
                             interpolation=cv2.INTER_AREA)[200:-200, 120:-120].astype(np.float32)
    win = cv2.createHanningWindow((300, 560), cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(g(a), g(b), win)
    return 2 * float(np.hypot(dx, dy))


@pytest.mark.slow
def test_handheld_takes_are_locked_to_frame_zero(tmp_path):
    foot = tmp_path / "f"
    subprocess.run([sys.executable, f"{ROOT}/scripts/gen_placeholder.py", "pavers", str(foot)], check=True,
                   capture_output=True)
    ts = np.arange(.25, 4, .25)
    for name in ("before", "after"):
        p = str(foot / f"{name}.mp4")
        S = stabilize.track(p, 4)
        assert len(S) >= 110
        locked, loose = render.Clip(p, 30, stab=S), render.Clip(p, 30)
        f0 = locked.frame(0)
        worst_locked = max(shift_px(f0, locked.frame(t)) for t in ts)
        worst_loose = max(shift_px(loose.frame(0), loose.frame(t)) for t in ts)
        print(f"{name}: drift {worst_loose:.1f}px -> {worst_locked:.1f}px")
        assert worst_loose > 8                     # the take really is handheld
        assert worst_locked < 2.0                  # ... and now holds like a tripod


def test_compose_order():
    A = np.float32([[1, 0, 10], [0, 1, 0]])
    B = np.float32([[0, -1, 0], [1, 0, 0]])        # 90 deg
    p = np.array([1, 0, 1], np.float32)
    np.testing.assert_allclose(stabilize.compose(A, B) @ p, A @ np.r_[B @ p, 1])
