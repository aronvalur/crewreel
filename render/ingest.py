"""Ingest: turn whatever the crew uploaded into a clean 1080x1920 SDR mezzanine clip.

Real phone footage breaks naive pipelines in predictable ways. This module fixes them
once, up front, so templates and the compositor only ever see well-behaved clips:

  * HDR (iPhone HLG / Dolby Vision, Android PQ)  -> tone-mapped to SDR BT.709
    (without this, HDR clips come out flat and grey)
  * rotation metadata                            -> applied (ffmpeg autorotate)
  * photos with EXIF orientation                 -> transposed upright
  * letterbox / pillarbox bars (screen recordings, re-exports) -> cropped off
  * landscape clips                              -> 9:16 crop that follows the action
                                                    (motion + detail saliency, smoothed
                                                    into a slow, steady virtual pan)
  * any fps / resolution                         -> 30 fps, 1080x1920, yuv420p

usage: python render/ingest.py <in> <out.mp4|out.png>   (prints the info JSON)
"""
import json, os, subprocess, sys
import numpy as np
import cv2

W, H, FPS = 1080, 1920, 30
HDR_TRC = {"smpte2084", "arib-std-b67"}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic")


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_format",
                        "-of", "json", path], capture_output=True, text=True)
    info = json.loads(r.stdout or "{}")
    s = (info.get("streams") or [{}])[0]
    rot = 0
    for sd in s.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    if not rot and "rotate" in (s.get("tags") or {}):
        rot = -int(s["tags"]["rotate"])
    w, h = int(s.get("width", 0)), int(s.get("height", 0))
    if abs(rot) % 180 == 90:
        w, h = h, w                                    # display size after autorotate
    dur = float(s.get("duration") or info.get("format", {}).get("duration") or 0)
    return dict(width=w, height=h, rotation=rot, duration=dur,
                trc=s.get("color_transfer", ""), hdr=s.get("color_transfer", "") in HDR_TRC,
                pix_fmt=s.get("pix_fmt", ""))


def tonemap_vf(hdr):
    if not hdr:
        return []
    return ["zscale=t=linear:npl=100", "format=gbrpf32le", "zscale=p=bt709",
            "tonemap=hable:desat=0", "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p"]


def decode(path, vf, w, h, fps=FPS, limit=None):
    """Yield RGB frames (h, w, 3) uint8 after the ffmpeg filter chain vf."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", path]
    if limit:
        cmd += ["-t", str(limit)]
    cmd += ["-vf", ",".join(vf + [f"fps={fps}", f"scale={w}:{h}:flags=bicubic", "format=rgb24"]),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    finally:
        p.kill()
        p.wait()


def detect_bars(frames, thresh=22):
    """Find the active picture box across sample frames. Returns (x0, y0, x1, y1) in px.

    A bar is a row/column that is near-black in EVERY sample frame and has no texture.
    Deep shadows are dark too, but they carry grain/detail; real bars are flat."""
    st = np.stack([f.max(axis=2) for f in frames]).astype(np.float32)
    acc = st.max(axis=0)
    tex = np.abs(cv2.Laplacian(st.mean(axis=0), cv2.CV_32F))
    flat_rows = np.percentile(tex, 90, axis=1) < 4
    flat_cols = np.percentile(tex, 90, axis=0) < 4
    rows = np.where((np.percentile(acc, 90, axis=1) > thresh) | ~flat_rows)[0]
    cols = np.where((np.percentile(acc, 90, axis=0) > thresh) | ~flat_cols)[0]
    h, w = acc.shape
    if len(rows) < h * .3 or len(cols) < w * .3:
        return 0, 0, w, h
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    # only crop real bars (>2 % of the side); shave a further 1 % inside a detected bar
    # because bar edges are soft (scaling / compression) and leave a dark hairline
    ix, iy = int(np.ceil(w * .01)), int(np.ceil(h * .01))
    y0 = y0 + iy if y0 > h * .02 else 0
    y1 = y1 - iy if h - y1 > h * .02 else h
    x0 = x0 + ix if x0 > w * .02 else 0
    x1 = x1 - ix if w - x1 > w * .02 else w
    return x0 // 2 * 2, y0 // 2 * 2, x1 // 2 * 2, y1 // 2 * 2


def saliency_track(frames, crop_w, fps=FPS, smooth_s=1.2, max_speed=.12):
    """Horizontal crop centre per frame for a crop of width crop_w.

    Saliency = motion (frame difference: the spray, the swath being cleaned) + a little
    texture (edges). Centres are smoothed hard and speed-limited so the result reads as a
    calm operator pan, never a jittery auto-reframe. max_speed is in frame widths / second.
    """
    w = frames[0].shape[1]
    small = [cv2.cvtColor(cv2.resize(f, (w // 4, f.shape[0] // 4), interpolation=cv2.INTER_AREA),
                          cv2.COLOR_RGB2GRAY).astype(np.float32) for f in frames]
    xs = np.arange(w // 4, dtype=np.float32)
    cw = crop_w / 4
    raw = []
    prev = small[0]
    for g in small:
        motion = cv2.GaussianBlur(np.abs(g - prev), (0, 0), 3)
        edges = cv2.GaussianBlur(np.abs(cv2.Laplacian(g, cv2.CV_32F)), (0, 0), 3)
        prev = g
        col = motion.sum(0) * 1.0 + edges.sum(0) * .15
        # best window = max of the box-filtered column energy
        k = max(1, int(cw))
        box = np.convolve(col, np.ones(k), "valid")
        raw.append(float(np.argmax(box) + k / 2) if box.max() > 0 else w / 8)
    raw = np.array(raw) * 4
    raw[0] = raw[1] if len(raw) > 1 else raw[0]      # frame 0 has no motion
    # robust smoothing: median then gaussian
    r = max(1, int(fps * .4))
    med = np.array([np.median(raw[max(0, i - r): i + r + 1]) for i in range(len(raw))])
    sig = smooth_s * fps
    k = np.exp(-.5 * (np.arange(-3 * sig, 3 * sig + 1) / sig) ** 2)
    pad = np.pad(med, len(k) // 2, mode="edge")
    sm = np.convolve(pad, k / k.sum(), "valid")[: len(med)]
    # speed limit
    vmax = max_speed * w / fps
    out = [sm[0]]
    for x in sm[1:]:
        out.append(out[-1] + np.clip(x - out[-1], -vmax, vmax))
    half = crop_w / 2
    return np.clip(np.array(out), half, w - half)


def encode(frames, out, fps=FPS):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "fast",
                          "-crf", "14", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
                          "-color_trc", "bt709", out], stdin=subprocess.PIPE)
    n = 0
    for f in frames:
        p.stdin.write(np.ascontiguousarray(f).tobytes())
        n += 1
    p.stdin.close()
    p.wait()
    return n


def ingest_image(src, out):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    a = np.asarray(im)
    x0, y0, x1, y1 = detect_bars([a])
    a = a[y0:y1, x0:x1]
    h, w = a.shape[:2]
    s = max(W / w, H / h)
    a = cv2.resize(a, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    # stills: centre on detail (no motion to follow)
    cx = saliency_track([a, a], W)[0] if a.shape[1] > W + 2 else a.shape[1] / 2
    ox = int(np.clip(cx - W / 2, 0, a.shape[1] - W))
    oy = (a.shape[0] - H) // 2
    Image.fromarray(np.ascontiguousarray(a[oy:oy + H, ox:ox + W])).save(out)
    return dict(kind="image", src_size=[w, h], crop=[int(x0), int(y0), int(x1), int(y1)], pan=None,
                src_px=round(min(w / W, h / H), 3))


def ingest_video(src, out, max_seconds=None):
    info = probe(src)
    vf = tonemap_vf(info["hdr"])
    # pass 1 (low res): bars + saliency
    pw = 360
    ph = max(2, int(round(pw * info["height"] / max(1, info["width"]) / 2)) * 2)
    lo = list(decode(src, vf, pw, ph, fps=10, limit=max_seconds))
    if not lo:
        raise ValueError(f"no frames decoded from {src}")
    step = max(1, len(lo) // 12)
    bx0, by0, bx1, by1 = detect_bars(lo[::step])
    sx = info["width"] / pw
    sy = info["height"] / ph
    cx0, cy0 = int(bx0 * sx) // 2 * 2, int(by0 * sy) // 2 * 2
    cw, ch = int((bx1 - bx0) * sx) // 2 * 2, int((by1 - by0) * sy) // 2 * 2
    cropped = (cx0, cy0, cw, ch) != (0, 0, info["width"] // 2 * 2, info["height"] // 2 * 2)
    pre = vf + ([f"crop={cw}:{ch}:{cx0}:{cy0}"] if cropped else [])
    aspect = cw / max(1, ch)
    # source pixels per output pixel after the crop (below ~0.55 the reel looks visibly soft)
    src_px = ch / H if aspect > W / H * 1.03 else min(cw / W, ch / H)
    meta = dict(kind="video", hdr=info["hdr"], trc=info["trc"], rotation=info["rotation"], src_px=round(src_px, 3),
                src_size=[info["width"], info["height"]], crop=[cx0, cy0, cw, ch] if cropped else None,
                duration=info["duration"])
    if aspect <= W / H * 1.03:
        # portrait (or close): plain cover-scale
        frames = decode(src, pre + [f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}"],
                        W, H, limit=max_seconds)
        meta["pan"] = None
        meta["frames"] = encode(frames, out)
        return meta
    # landscape: scale to full height, follow the action horizontally
    sw = int(round(H * aspect / 2)) * 2
    lo_c = [f[by0:by1, bx0:bx1] for f in lo]
    track_lo = saliency_track(lo_c, W / sw * lo_c[0].shape[1], fps=10)
    t_lo = np.arange(len(track_lo)) / 10
    scale = sw / lo_c[0].shape[1]

    def gen():
        for i, f in enumerate(decode(src, pre, sw, H, limit=max_seconds)):
            cx = float(np.interp(i / FPS, t_lo, track_lo)) * scale
            x = int(np.clip(round(cx - W / 2), 0, sw - W))
            yield f[:, x:x + W]

    meta["pan"] = [round(float(x * scale), 1) for x in track_lo[::5]]
    meta["frames"] = encode(gen(), out)
    return meta


BINS = 24


def activity_profile(mezz, fps=10):
    """Where the action is in the finished 9:16 frame: motion energy per horizontal band.

    Returns BINS floats (top->bottom, sum 1) plus the motion centroid (x, y in 0..1).
    Templates use it to keep text off the subject (the nozzle, the spray, the swath).
    Low-motion clips fall back to a flat profile (=no preference)."""
    fr = [cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).astype(np.float32) for f in decode(mezz, [], 135, 240, fps=fps)]
    if len(fr) < 3:
        return None
    e = np.zeros((240, 135), np.float32)
    for a, b in zip(fr, fr[1:]):
        e += cv2.GaussianBlur(np.abs(b - a), (0, 0), 2)
    e = np.maximum(e - np.percentile(e, 50), 0)           # ignore sensor noise / gentle handheld drift
    tot = float(e.sum())
    if tot < 1e-3:
        return dict(profile=[1 / BINS] * BINS, cx=.5, cy=.5, strength=0.0)
    rows = e.sum(1)
    prof = rows.reshape(BINS, -1).sum(1) / tot
    ys, xs = np.mgrid[0:240, 0:135]
    return dict(profile=[round(float(p), 4) for p in prof],
                cx=round(float((e * xs).sum() / tot / 135), 3), cy=round(float((e * ys).sum() / tot / 240), 3),
                strength=round(float(tot / len(fr) / (240 * 135)), 3))


def quality_warnings(meta, sample):
    """Plain-English re-shoot hints for the crew. sample: a few RGB frames of the source."""
    w = []
    if meta.get("src_px") is not None and meta["src_px"] < .55:
        w.append(dict(code="low_res", message="This clip is low resolution and will look soft. "
                      "Film in 1080p or 4K and hold the phone upright."))
    luma = float(np.mean([cv2.cvtColor(f, cv2.COLOR_RGB2GRAY).mean() for f in sample]))
    if luma < 45:
        w.append(dict(code="too_dark", message="This clip is very dark. Film in daylight or turn on more light."))
    elif luma > 225:
        w.append(dict(code="overexposed", message="This clip is washed out. Tap the surface on screen to set exposure."))
    if meta.get("pan") is not None:
        w.append(dict(code="landscape", message="Filmed sideways: we cropped it to vertical and followed the action. "
                      "Hold the phone upright next time to keep the whole shot."))
    return w


def ingest(src, out, max_seconds=None):
    if src.lower().endswith(IMAGE_EXT):
        meta = ingest_image(src, out)
        sample = [cv2.cvtColor(cv2.imread(out), cv2.COLOR_BGR2RGB)]
    else:
        meta = ingest_video(src, out, max_seconds)
        meta["activity"] = activity_profile(out)
        sample = list(decode(out, [], 135, 240, fps=2))[:8]
    meta["warnings"] = quality_warnings(meta, sample)
    return meta


if __name__ == "__main__":
    print(json.dumps(ingest(sys.argv[1], sys.argv[2]), indent=1))
