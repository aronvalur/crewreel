"""Before/after auto-alignment.

Crews never stand in exactly the same spot twice. The split reveal only looks
'agency' when the after shot lines up with the before shot, so we estimate a
transform that maps the AFTER frame onto the BEFORE frame and warp every after
frame with it.

Strategy: ORB features + RANSAC similarity (robust to the big colour change
between dirty and clean), refined with ECC on edge maps. If neither is
confident we return None and the template falls back to a crossfade.
"""
import cv2
import numpy as np

WORK = 540  # working width for estimation


def _edges(img):
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    g = cv2.createCLAHE(2.0, (8, 8)).apply(g)          # dirt vs clean: equalise contrast
    e = cv2.Canny(cv2.GaussianBlur(g, (5, 5), 0), 30, 90)
    return cv2.GaussianBlur(e, (0, 0), 2).astype(np.float32) / 255.0, g


def _pyramid_ecc(eb, ea, M, levels=(4, 2, 1)):
    """Refine M (maps after->before, cv2.warpAffine convention) with ECC.
    ECC solves the inverse map (before coords -> after coords), so invert around it."""
    M = cv2.invertAffineTransform(M).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 100, 1e-5)
    for lv in levels:
        b = cv2.resize(eb, None, fx=1 / lv, fy=1 / lv, interpolation=cv2.INTER_AREA)
        a = cv2.resize(ea, None, fx=1 / lv, fy=1 / lv, interpolation=cv2.INTER_AREA)
        Ml = M.copy(); Ml[:, 2] /= lv
        try:
            _, Ml = cv2.findTransformECC(b, a, Ml, cv2.MOTION_EUCLIDEAN, crit, None, 3)
            M = Ml.copy(); M[:, 2] *= lv
        except cv2.error:
            pass
    return cv2.invertAffineTransform(M).astype(np.float32)


def _grid_search(b, a):
    """Brute-force rotation x translation search on tiny low-pass luminance, then ECC.
    Robust to the dirty->clean colour change, where feature matching fails."""
    q = 8
    bs = cv2.resize(b, None, fx=1 / q, fy=1 / q, interpolation=cv2.INTER_AREA)
    as_ = cv2.resize(a, None, fx=1 / q, fy=1 / q, interpolation=cv2.INTER_AREA)
    h, w = bs.shape
    m = 8
    bc = bs[m:-m, m:-m].ravel(); bc = (bc - bc.mean()) / (bc.std() + 1e-6)
    best, bestM = -2, np.eye(2, 3, dtype=np.float32)
    r = int(0.12 * w) + 1
    for ang in np.arange(-4, 4.01, 1.0):
        R = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0).astype(np.float32)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                M = R.copy(); M[0, 2] += dx; M[1, 2] += dy
                wa = cv2.warpAffine(as_, M, (w, h))[m:-m, m:-m].ravel()
                c = float(np.dot((wa - wa.mean()) / (wa.std() + 1e-6), bc)) / bc.size
                if c > best:
                    best, bestM = c, M
    bestM[:, 2] *= q
    return _pyramid_ecc(b, a, bestM, levels=(4, 2, 1))


def estimate(before_rgb, after_rgb):
    """Returns (M 2x3 float32 in full-res coords, score) or (None, score)."""
    h, w = before_rgb.shape[:2]
    s = WORK / w
    b = cv2.resize(before_rgb, (WORK, int(h * s)), interpolation=cv2.INTER_AREA)
    a = cv2.resize(after_rgb, (WORK, int(h * s)), interpolation=cv2.INTER_AREA)
    eb, gb = _edges(b)
    ea, ga = _edges(a)

    cands = [np.eye(2, 3, dtype=np.float32)]
    orb = cv2.ORB_create(3000)
    kb, db = orb.detectAndCompute(gb, None)
    ka, da = orb.detectAndCompute(ga, None)
    if db is not None and da is not None and len(kb) > 20 and len(ka) > 20:
        matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(da, db)
        if len(matches) >= 12:
            src = np.float32([ka[m.queryIdx].pt for m in matches])
            dst = np.float32([kb[m.trainIdx].pt for m in matches])
            est, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3)
            if est is not None and inl is not None and inl.sum() >= 12:
                cands.append(est.astype(np.float32))

    def corr(M):
        valid = cv2.warpAffine(np.ones_like(ea), M, (eb.shape[1], eb.shape[0])) > .5
        out = 0.0
        for x, y in ((ea, eb), (la, lb)):
            warped = cv2.warpAffine(x, M, (eb.shape[1], eb.shape[0]))
            out += float(np.corrcoef(warped[valid], y[valid])[0, 1]) / 2
        return out

    # coarse structure (lawn edge, walls, roofline) survives the dirty->clean change
    blur = lambda g, k: cv2.GaussianBlur(g.astype(np.float32) / 255, (0, 0), k)
    Mb = np.eye(2, 3, dtype=np.float32)
    for k in (16, 8, 4):
        Mb = _pyramid_ecc(blur(gb, k), blur(ga, k), Mb, levels=(4, 2))
    cands.append(Mb)
    cands.append(_grid_search(blur(gb, 6), blur(ga, 6)))
    lb, la = blur(gb, 6), blur(ga, 6)

    base = corr(cands[0])
    best, score = cands[0], base
    for M0 in cands:
        M = _pyramid_ecc(eb, ea, M0.copy())
        for m in (M0, M):
            sc_ = corr(m)
            if sc_ > score:
                best, score = m, sc_
    M = best
    # sanity: reject wild transforms (>12% shift, >8 deg, >10% scale)
    sc = np.hypot(M[0, 0], M[1, 0])
    ang = np.degrees(np.arctan2(M[1, 0], M[0, 0]))
    shift = np.hypot(M[0, 2], M[1, 2]) / WORK
    if score < base + 0.03 or abs(ang) > 8 or abs(sc - 1) > .1 or shift > .12:
        return None, score
    Mf = M.copy()
    Mf[:, 2] /= s
    # zoom in slightly so warped borders never show
    return Mf, score


def crop_zoom_for(M, w, h):
    """Smallest centred zoom (>=1) that hides the empty borders created by warping with M."""
    s = 0.25
    mask = cv2.warpAffine(np.ones((int(h * s), int(w * s)), np.uint8),
                          np.float32([[M[0, 0], M[0, 1], M[0, 2] * s], [M[1, 0], M[1, 1], M[1, 2] * s]]),
                          (int(w * s), int(h * s)))
    hh, ww = mask.shape
    for z in np.arange(1.0, 1.3, 0.005):
        cw, ch = int(ww / z), int(hh / z)
        x0, y0 = (ww - cw) // 2, (hh - ch) // 2
        if mask[y0:y0 + ch, x0:x0 + cw].min() > 0:
            return float(z) + 0.005
    return 1.3


def meet_halfway(M):
    """Split after->before transform M into (Mb, Ma) so BOTH clips move half-way.
    Halves the zoom needed to hide borders compared with warping only the after clip."""
    th = np.arctan2(M[1, 0], M[0, 0]) / 2
    sc = np.sqrt(np.hypot(M[0, 0], M[1, 0]))
    Rh = sc * np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], np.float32)
    th_ = np.linalg.solve(Rh + np.eye(2), M[:, 2])
    Ah = np.c_[Rh, th_].astype(np.float32)           # after -> midpoint
    Bh = cv2.invertAffineTransform(Ah).astype(np.float32)  # before -> midpoint
    return Bh, Ah


def plan_alignment(before_rgb, after_rgb):
    """-> dict(before=M|None, after=M|None, zoom=float, score=float, ok=bool)"""
    h, w = before_rgb.shape[:2]
    M, score = estimate(before_rgb, after_rgb)
    if M is None:
        return dict(before=None, after=None, zoom=1.0, score=score, ok=False)
    Mb, Ma = meet_halfway(M)
    z = max(crop_zoom_for(Mb, w, h), crop_zoom_for(Ma, w, h))
    return dict(before=Mb, after=Ma, zoom=z, score=score, ok=True)
