"""Where to look and where to write.

Two questions every template asks of the crew's footage, answered from the first frames of the
before/after pair in *render space* (after alignment warp + crop zoom, i.e. what the viewer sees):

change_points(before, after)  -> the spots where the clean-up is most visible. Detail push-ins go
                                 there instead of to hard-coded coordinates, so a close-up always
                                 lands on a transformation, never on a bush or a blank wall.
busy_profile(img)             -> how much visual detail (edges, texture contrast) each horizontal
                                 band holds. Text goes over the calm bands (sky, lawn, plain
                                 siding), not over windows, doors and rooflines.
"""
import cv2
import numpy as np

SW, SH = 270, 480          # analysis size (1080x1920 / 4)
BINS = 24


def to_render_space(img, M=None, zoom=1.0, size=(1080, 1920)):
    """Apply the same warp + centred crop zoom the compositor applies to a clip."""
    W, H = size
    if img.shape[1] != W or img.shape[0] != H:
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    if M is not None:
        img = cv2.warpAffine(img, np.asarray(M, np.float32), (W, H), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT)
    if zoom > 1.0001:
        cw, ch = int(W / zoom), int(H / zoom)
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        img = cv2.resize(img[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_AREA)
    return img


def _small(img):
    return cv2.resize(img, (SW, SH), interpolation=cv2.INTER_AREA)


def change_map(before, after):
    """Perceptual before->after difference, low-passed so it follows surfaces, not pixels.
    Lightness change counts most (grime -> clean is mostly a lightness lift), colour too (green algae)."""
    lb = cv2.cvtColor(_small(before), cv2.COLOR_RGB2LAB).astype(np.float32)
    la = cv2.cvtColor(_small(after), cv2.COLOR_RGB2LAB).astype(np.float32)
    lb = cv2.GaussianBlur(lb, (0, 0), 5)
    la = cv2.GaussianBlur(la, (0, 0), 5)
    d = np.sqrt(1.0 * (la[..., 0] - lb[..., 0]) ** 2 + .6 * (la[..., 1] - lb[..., 1]) ** 2
                + .6 * (la[..., 2] - lb[..., 2]) ** 2)
    d = np.maximum(d - np.percentile(d, 30), 0)        # ignore global exposure/white-balance shifts
    return d


def change_points(before, after, n=2, zoom=1.6, min_dist=.3):
    """Up to n focus points (fx, fy in 0..1) where the clean-up is most visible in a push-in of `zoom`.

    Each point is the centre of the zoomed view with the most change inside it. Views stay inside the
    frame and clear of the UI safe zones (top 300 / bottom 520 px) where possible. Returns
    [dict(fx, fy, score)] (score = mean change in the view, 0..~60) — may be empty if nothing changed."""
    d = change_map(before, after)
    vw, vh = int(SW / zoom), int(SH / zoom)
    win = cv2.boxFilter(d, -1, (vw, vh), normalize=True, borderType=cv2.BORDER_CONSTANT)
    # centre-weighted: among views that contain the change, prefer the one centred on it
    cen = cv2.GaussianBlur(d, (0, 0), sigmaX=vw / 5, sigmaY=vh / 5, borderType=cv2.BORDER_CONSTANT)
    cen = cen / (cen.max() + 1e-6)
    # valid centres: view inside the frame, and the view's middle out of the UI zones
    ys, xs = np.mgrid[0:SH, 0:SW]
    lo_y = max(vh / 2, 300 / 1920 * SH + vh * .15)
    hi_y = min(SH - vh / 2, SH - 520 / 1920 * SH - vh * .15)
    valid = (xs >= vw / 2) & (xs <= SW - vw / 2) & (ys >= min(lo_y, SH / 2)) & (ys <= max(hi_y, SH / 2))
    score = np.where(valid, win * (.5 + .5 * cen), -1)
    pts = []
    for _ in range(n):
        y, x = np.unravel_index(int(np.argmax(score)), score.shape)
        s = float(score[y, x])
        if s <= 0.5 or (pts and s < .35 * pts[0]["score"]):
            break
        pts.append(dict(fx=round(float(x) / SW, 3), fy=round(float(y) / SH, 3), score=round(s, 2)))
        # suppress everything too close to this point (distance in frame-width units)
        dist = np.hypot((xs - x) / SW, (ys - y) / SW)
        score = np.where(dist < min_dist, -1, score)
    return pts


def busy_profile(img):
    """Visual detail per horizontal band (BINS floats, top->bottom, sum 1).
    Edges on contrast-equalised luminance + local texture contrast. Flat frames -> flat profile."""
    g = cv2.cvtColor(_small(img), cv2.COLOR_RGB2GRAY)
    g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
    e = cv2.Canny(cv2.GaussianBlur(g, (3, 3), 0), 40, 120).astype(np.float32) / 255
    gf = g.astype(np.float32)
    mu = cv2.GaussianBlur(gf, (0, 0), 4)
    var = np.sqrt(np.maximum(cv2.GaussianBlur(gf * gf, (0, 0), 4) - mu * mu, 0)) / 64
    # distinct objects (a dark window on pale siding, a door, a roofline against sky) read as subject
    # even when their insides are flat
    big = cv2.GaussianBlur(gf, (0, 0), 6)
    dist = np.abs(big - np.median(gf)) / 64
    m = cv2.GaussianBlur(e, (0, 0), 3) + .5 * var + .8 * dist
    rows = m.sum(1)
    prof = rows.reshape(BINS, -1).sum(1)
    tot = float(prof.sum())
    if tot < 1e-6:
        return [1 / BINS] * BINS
    return [round(float(p / tot), 4) for p in prof]
