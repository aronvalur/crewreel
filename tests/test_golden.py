"""Visual regression: every template's graphics at its key moments must match tests/golden/.
After an intended design change: python scripts/golden.py  (then look at the new PNGs before committing)."""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_graphics_match_golden_frames():
    r = subprocess.run([sys.executable, f"{ROOT}/scripts/golden.py", "--check"], capture_output=True, text=True,
                       cwd=ROOT)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-800:]
