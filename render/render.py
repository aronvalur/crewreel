"""Crewreel render: template + job footage -> finished reel (mp4, 1080x1920, 30 fps).

  python render/render.py <template_dir> <footage_dir> <out.mp4> [--params p.json] [--seconds N]

Pipeline
  1. overlay.js   seeks the HTML template frame by frame -> transparent PNGs + plan.json
                  (plan = which footage layers go underneath each frame)
  0. ingest.py    normalises every upload (HDR tonemap, rotation, EXIF, letterbox, landscape
                  -> action-following 9:16 crop) into 1080x1920 30 fps mezzanine clips
  2. align.py     lines up the after clip with the before clip (fallback: crossfade)
  3. composite    footage layers per plan + overlay -> x264
  4. audio.py     music bed, whooshes on cuts, optional ElevenLabs VO -> loudnorm -> mux
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import align
import audio
import ingest

W, H = 1080, 1920
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def probe_frames(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return int(out or 0)


class Clip:
    """Sequential reader with hold-last-frame. Scales to cover 1080x1920, optional warp + zoom."""

    def __init__(self, path, fps, warp=None, zoom=1.0):
        self.path, self.fps, self.warp, self.zoom = path, fps, warp, zoom
        self.is_image = path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        self.n = 1 if self.is_image else max(1, probe_frames(path))
        self.proc, self.idx, self.cur, self.cache = None, -1, None, {}

    def _open(self):
        if self.proc:
            self.proc.kill()
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={self.fps}"
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", self.path, "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.idx = -1

    def _post(self, f):
        if self.warp is not None:
            f = cv2.warpAffine(f, self.warp, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if self.zoom > 1.0001:
            cw, ch = int(W / self.zoom), int(H / self.zoom)
            x0, y0 = (W - cw) // 2, (H - ch) // 2
            f = cv2.resize(f[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_CUBIC)
        return f

    def frame(self, t):
        i = min(int(round(t * self.fps)), self.n - 1)
        if self.is_image:
            i = 0
        if i in self.cache:
            return self.cache[i]
        if self.proc is None or i < self.idx:
            self._open()
        while self.idx < i:
            b = self.proc.stdout.read(W * H * 3)
            if len(b) < W * H * 3:          # clip shorter than probed: hold last
                self.n = self.idx + 1
                break
            self.idx += 1
            self.cur = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        f = self._post(self.cur)
        self.cache = {i: f}                 # tiny cache: same frame reused by several layers
        return f


def transform(img, zoom=1.0, fx=.5, fy=.5):
    """Ken Burns: zoom >= 1 towards focus point (fx, fy)."""
    if zoom <= 1.0001:
        return img
    cw, ch = W / zoom, H / zoom
    x0 = np.clip(fx * W - cw / 2, 0, W - cw)
    y0 = np.clip(fy * H - ch / 2, 0, H - ch)
    M = np.float32([[zoom, 0, -x0 * zoom], [0, zoom, -y0 * zoom]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR)


def blur(img, px):
    if px <= 0:
        return img
    s = 0.25
    small = cv2.resize(img, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), px * s)
    return cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR)


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


XS = np.arange(W, dtype=np.float32)


def render_layer(L, clips):
    if "color" in L:
        img = np.broadcast_to(hexrgb(L["color"]), (H, W, 3)).astype(np.float32)
    else:
        img = clips[L["src"]].frame(L.get("t", 0)).astype(np.float32)
        img = transform(img, L.get("zoom", 1), L.get("fx", .5), L.get("fy", .5))
        img = blur(img, L.get("blur", 0))
    if L.get("dim"):
        img = img * (1 - L["dim"])
    a = np.full((1, W, 1), float(L.get("alpha", 1)), np.float32)
    if "mask" in L:  # horizontal band [x0, x1] in 0..1; feather = soft edge width in px (default 1.5)
        x0, x1 = L["mask"][0] * W, L["mask"][1] * W
        f = float(L.get("feather", 1.5))
        a = a * (np.clip((XS - x0) / f + .5, 0, 1) * np.clip((x1 - XS) / f + .5, 0, 1))[None, :, None]
    return img, a


def composite(frames_dir, plan, clips, out_path, fps):
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "17", "-pix_fmt", "yuv420p", out_path], stdin=subprocess.PIPE)
    for i, fp in enumerate(plan["frames"]):
        acc = np.zeros((H, W, 3), np.float32)
        for L in fp["layers"]:
            img, a = render_layer(L, clips)
            acc = acc * (1 - a) + img * a
        o = np.asarray(Image.open(f"{frames_dir}/{i:04d}.png").convert("RGBA")).astype(np.float32)
        oa = o[..., 3:] / 255.0
        acc = acc * (1 - oa) + o[..., :3] * oa
        enc.stdin.write(np.clip(acc, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    for c in clips.values():
        if c.proc:
            c.proc.kill()


def first_frame(path):
    c = Clip(path, 30)
    return c.frame(0)


def find_clip(footage, name):
    for ext in (".mp4", ".mov", ".m4v", ".jpg", ".jpeg", ".png"):
        p = os.path.join(footage, name + ext)
        if os.path.exists(p):
            return p
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("footage")
    ap.add_argument("out")
    ap.add_argument("--params", default=None)
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    work = tempfile.mkdtemp(prefix="crewreel-")
    params = json.load(open(args.params)) if args.params else {}

    # 0. ingest: every upload -> clean 1080x1920 SDR mezzanine
    mezz = os.path.join(work, "mezz")
    os.makedirs(mezz, exist_ok=True)
    report = {}
    for f in sorted(os.listdir(args.footage)):
        name, ext = os.path.splitext(f)
        if ext.lower() not in (".mp4", ".mov", ".m4v", ".webm", ".mkv") + ingest.IMAGE_EXT or name in report:
            continue
        out = os.path.join(mezz, name + (".png" if ext.lower() in ingest.IMAGE_EXT else ".mp4"))
        report[name] = ingest.ingest(os.path.join(args.footage, f), out, max_seconds=30)
        r = report[name]
        print(f"ingest {f}: {r['kind']} hdr={r.get('hdr', False)} crop={r['crop']} pan={'yes' if r.get('pan') else 'no'}")
    footage = mezz

    # 2. alignment first: the template needs to know whether a split reveal is possible
    b, a = find_clip(footage, "before"), find_clip(footage, "after")
    al = align.plan_alignment(first_frame(b), first_frame(a)) if b and a else dict(ok=False, zoom=1, score=0)
    params["aligned"] = bool(al["ok"])
    params["activity"] = {k: v.get("activity") for k, v in report.items() if v.get("activity")}
    pfile = os.path.join(work, "params.json")
    json.dump(params, open(pfile, "w"))
    print(f"align: ok={al['ok']} score={al['score']:.2f} zoom={al['zoom']:.3f}")

    # 1. overlay + plan
    cmd = ["node", os.path.join(ROOT, "render/overlay.js"), os.path.join(args.template, "index.html"), work, pfile]
    if args.seconds:
        cmd.append(str(args.seconds))
    subprocess.run(cmd, check=True)
    plan = json.load(open(os.path.join(work, "plan.json")))
    fps = plan["meta"]["fps"]
    print(f"overlay: {len(plan['frames'])} frames in {time.time() - t0:.0f}s")

    # 3. composite
    clips = {}
    for name in plan["meta"]["sources"]:
        p = find_clip(footage, name)
        if not p:
            raise SystemExit(f"missing footage: {name} in {args.footage}")
        warp = al.get(name) if name in ("before", "after") and al["ok"] else None
        zoom = al["zoom"] if name in ("before", "after") and al["ok"] else 1.0
        clips[name] = Clip(p, fps, warp, zoom)
    silent = os.path.join(work, "silent.mp4")
    composite(work, plan, clips, silent, fps)
    print(f"composite done at {time.time() - t0:.0f}s")

    # 4. audio
    wav = os.path.join(work, "mix.wav")
    audio.build_mix(plan["meta"], wav, work)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], check=True)
    print(f"reel -> {args.out} in {time.time() - t0:.0f}s")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("work dir:", work)


if __name__ == "__main__":
    main()
