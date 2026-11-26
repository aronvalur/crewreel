"""Lock a handheld clip to its first frame ("tripod look").

The before/after split only reads as agency work when the two shots stay registered for
the whole reveal. align.py registers frame 0 of after onto frame 0 of before; this module
removes each clip's own handheld drift so that registration holds on every frame.

track(path) -> list of 2x3 float32 matrices S_k (cv2.warpAffine convention) that map
frame k onto frame 0, in full-resolution 1080x1920 coordinates.
"""
import numpy as np
import cv2

import ingest

SW, SH = 270, 480          # tracking resolution (1/4)


def _gray(f):
    g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    return cv2.GaussianBlur(g, (0, 0), 1.2)


def track(path, seconds=None, fps=30):
    frames = [_gray(f) for f in ingest.decode(path, [], SW, SH, fps=fps, limit=seconds)]
    if not frames:
        return []
    ref = frames[0]
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5)
    M = np.eye(2, 3, dtype=np.float32)       # ECC: maps ref coords -> frame k coords
    params = [(0.0, 0.0, 0.0)]
    for g in frames[1:]:
        try:
            _, M = cv2.findTransformECC(ref, g, M.copy(), cv2.MOTION_EUCLIDEAN, crit, None, 5)
        except cv2.error:
            pass                              # keep the previous estimate (spray / occlusion)
        params.append((float(np.arctan2(M[1, 0], M[0, 0])), float(M[0, 2]), float(M[1, 2])))
    p = np.array(params)
    # light temporal smoothing removes estimation jitter without letting drift back in
    k = np.array([1, 2, 3, 2, 1], np.float32); k /= k.sum()
    pad = np.pad(p, ((2, 2), (0, 0)), mode="edge")
    p = np.stack([np.convolve(pad[:, i], k, "valid") for i in range(3)], 1)
    out = []
    s = W_SCALE = 1080 / SW
    for th, tx, ty in p:
        F = np.float32([[np.cos(th), -np.sin(th), tx * s], [np.sin(th), np.cos(th), ty * s]])  # ref -> k
        out.append(cv2.invertAffineTransform(F).astype(np.float32))                             # k -> ref
    return out


def compose(A, B):
    """A after B, both 2x3 (warpAffine convention)."""
    return (np.vstack([A, [0, 0, 1]]) @ np.vstack([B, [0, 0, 1]]))[:2].astype(np.float32)
