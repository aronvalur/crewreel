"""Generate placeholder job footage for testing templates (NOT for customer reels).

Creates procedural 'before', 'after' and 'action' clips for two surfaces:
  pavers  (driveway)   and   siding (house wash)
The 'after' clip is deliberately shot from a slightly different camera position
(shift + rotation) so the auto-align step has something real to fix.

usage: python scripts/gen_placeholder.py <surface> <outdir>
"""
import os, subprocess, sys
import numpy as np
import cv2

W, H, FPS = 540, 960, 30          # generated at half res, upscaled by ffmpeg
rng = np.random.default_rng(7)


def noise(h, w, scale, seed):
    r = np.random.default_rng(seed)
    small = r.random((max(2, h // scale), max(2, w // scale))).astype(np.float32)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)


def base_surface(kind, h=H * 2, w=W * 2):
    """Large canvas (2x frame) so the 'camera' can drift over it."""
    grain = noise(h, w, 2, 1) * .5 + noise(h, w, 9, 2) * .3 + noise(h, w, 40, 3) * .2
    if kind == "pavers":
        img = np.dstack([grain * 60 + 150, grain * 58 + 146, grain * 55 + 138])
        # herringbone-ish paver joints
        jy = (np.arange(h) % 70) < 4
        jx = ((np.arange(w)[None, :] + (np.arange(h)[:, None] // 70) * 70) % 140) < 4
        joints = jy[:, None] | jx
        img[joints] *= .55
        # grass edge on the left, house wall at top
        img[:, : w // 8] = np.dstack([grain * 40 + 40, grain * 70 + 90, grain * 30 + 35])[:, : w // 8]
        img[: h // 6] = np.dstack([grain * 30 + 200, grain * 30 + 196, grain * 30 + 188])[: h // 6]
    else:  # siding
        img = np.dstack([grain * 25 + 222, grain * 25 + 222, grain * 25 + 216])
        boards = (np.arange(h) % 46)
        shade = np.clip(boards / 46.0, 0, 1)[:, None, None] * .18 + .82
        img *= shade
        img[(boards < 3)] *= .6
        # a window
        y0, x0 = int(h * .35), int(w * .38)
        img[y0:y0 + 300, x0:x0 + 240] = [70, 85, 100]
        img[y0 + 145:y0 + 155, x0:x0 + 240] = 235
        img[y0:y0 + 300, x0 + 115:x0 + 125] = 235
        # sky strip
        img[: h // 10] = np.dstack([grain * 10 + 150, grain * 10 + 190, grain * 10 + 235])[: h // 10]
    return img.astype(np.float32)


def dirt_mask(kind, h=H * 2, w=W * 2):
    m = noise(h, w, 30, 11) * .6 + noise(h, w, 6, 12) * .4
    m = np.clip((m - .25) * 1.8, 0, 1)
    if kind == "siding":   # algae heavier near the bottom and under boards
        m *= np.linspace(.5, 1.0, h)[:, None]
    return m


def dirty(img, kind, m):
    tint = np.array([70, 75, 60], np.float32) if kind == "pavers" else np.array([95, 120, 70], np.float32)
    k = (m * (.75 if kind == "pavers" else .6))[..., None]
    out = img * (1 - k) + tint * k
    out[: img.shape[0] // (6 if kind == "pavers" else 10)] = img[: img.shape[0] // (6 if kind == "pavers" else 10)]
    return out


def cam(canvas, t, dx=0, dy=0, rot=0.0, ph=0.0):
    """Handheld camera: slow drift + micro shake, crop W x H from the 2x canvas.
    ph = phase offset, so separate takes (before vs after) wobble independently like real handheld."""
    h, w = canvas.shape[:2]
    cx = w / 2 + dx + 6 * np.sin(t * 1.3 + ph) + 2 * np.sin(t * 7.1 + 2 * ph)
    cy = h / 2 + dy + 5 * np.cos(t * 1.1 + 1.7 * ph) + 2 * np.cos(t * 6.3 + ph)
    M = cv2.getRotationMatrix2D((cx, cy), rot + .25 * np.sin(t * .9 + ph), 1.0)
    M[0, 2] += W / 2 - cx
    M[1, 2] += H / 2 - cy
    return cv2.warpAffine(canvas, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def write(path, frames):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-vf", "scale=1080:1920:flags=lanczos,noise=alls=6:allf=t",
                          "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()


def main(kind, out):
    os.makedirs(out, exist_ok=True)
    clean = base_surface(kind)
    m = dirt_mask(kind)
    dirty_img = dirty(clean, kind, m)
    n = FPS * 5
    write(f"{out}/before.mp4", (cam(dirty_img, i / FPS) for i in range(n)))
    # after: tripod-less re-shoot, ~3% offset and 1.5 deg rotation
    write(f"{out}/after.mp4", (cam(clean * 1.03, i / FPS, dx=28, dy=-22, rot=1.5, ph=2.1) for i in range(n)))
    # action: a cleaned band sweeping across (surface cleaner / soft wash wand)
    hh, ww = clean.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    clips = 1 if kind == "pavers" else 3
    for c in range(clips):
        frames = []
        for i in range(n if clips == 1 else FPS * 2):
            t = i / FPS
            if kind == "pavers":   # left-to-right swath
                front = ww * (.15 + .7 * t / 5)
                k = np.clip((front - xx) / 40, 0, 1) * (np.abs(yy - hh / 2) < hh * .3)
            else:                   # top-down rinse, each clip a different band
                front = hh * (.1 + .8 * (t / 2))
                band = (np.abs(xx - ww * (.3 + .2 * c)) < ww * .22)
                k = np.clip((front - yy) / 60, 0, 1) * band
            k = cv2.GaussianBlur(k.astype(np.float32), (0, 0), 6)[..., None]
            frames.append(cam(dirty_img * (1 - k) + clean * k, t, dx=-30 * c, dy=20 * c))
        write(f"{out}/action{c + 1}.mp4", frames)
    print("placeholder footage ->", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
