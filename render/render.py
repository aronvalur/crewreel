"""Crewreel render: template + job footage -> finished reel (mp4, 1080x1920, 30 fps).

  python render/render.py <template_dir> <footage_dir> <out.mp4> [--params p.json] [--seconds N]

Pipeline
  1. overlay.js   seeks the HTML template frame by frame -> transparent PNGs + plan.json
                  (plan = which footage layers go underneath each frame)
  0. ingest.py    normalises every upload (HDR tonemap, rotation, EXIF, letterbox, landscape
                  -> action-following 9:16 crop) into 1080x1920 30 fps mezzanine clips
  1b. stabilize.py locks before/after to their first frame (tripod look)
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
import focus
import ingest
import stabilize

W, H = 1080, 1920
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def probe_frames(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return int(out or 0)


class Clip:
    """Sequential reader with hold-last-frame. Scales to cover 1080x1920, optional warp + zoom."""

    def __init__(self, path, fps, warp=None, zoom=1.0, speed=1.0, stab=None):
        self.path, self.fps, self.warp, self.zoom, self.speed = path, fps, warp, zoom, speed
        self.stab = stab or None              # per-frame lock to frame 0 (stabilize.track)
        self.is_image = path.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        self.n = 1 if self.is_image else max(1, probe_frames(path))
        self.proc, self.idx, self.cur, self.prev, self.cache = None, -1, None, None, {}

    def _open(self):
        if self.proc:
            self.proc.kill()
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={self.fps}"
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", self.path, "-vf", vf,
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)   # we kill readers early: no 'Broken pipe' spam
        self.idx, self.cur, self.prev = -1, None, None

    def _post(self, f, i=0):
        warp = self.warp
        if self.stab:
            S = self.stab[min(i, len(self.stab) - 1)]
            warp = stabilize.compose(warp, S) if warp is not None else S
        if warp is not None:
            f = cv2.warpAffine(f, warp, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        if self.zoom > 1.0001:
            cw, ch = int(W / self.zoom), int(H / self.zoom)
            x0, y0 = (W - cw) // 2, (H - ch) // 2
            f = cv2.resize(f[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_CUBIC)
        return f

    def _seek(self, i):
        """Advance the sequential reader to source frame i (held at the last frame)."""
        i = min(i, self.n - 1)
        if self.proc is None or i < self.idx - 1:
            self._open()
        while self.idx < i:
            b = self.proc.stdout.read(W * H * 3)
            if len(b) < W * H * 3:          # clip shorter than probed: hold last
                self.n = max(1, self.idx + 1)
                break
            self.idx += 1
            self.prev, self.cur = self.cur, np.frombuffer(b, np.uint8).reshape(H, W, 3)
        if i == self.idx - 1 and self.prev is not None:
            return self.prev
        return self.cur

    def frame(self, t):
        """Frame at template time t. speed < 1 = slow motion with frame blending, used when the
        crew's clip is shorter than the template slot (a slowed clip beats a frozen one)."""
        if self.is_image:
            i, w = 0, 0.0
        else:
            x = max(0.0, t * self.speed * self.fps)
            i, w = int(x), x - int(x)
            if self.speed > .999:
                i, w = int(round(t * self.fps)), 0.0
        key = (i, round(w, 2))
        if key in self.cache:
            return self.cache[key]
        if w > .05 and i + 1 < self.n:
            a = self._seek(i)
            a = a.astype(np.float32) if a is not None else None
            b = self._seek(i + 1).astype(np.float32)
            f = (a * (1 - w) + b * w).astype(np.uint8) if a is not None else b.astype(np.uint8)
        else:
            f = self._seek(i)
        f = self._post(f, i)
        self.cache = {key: f}               # tiny cache: same frame reused by several layers
        return f


def needed_seconds(plan, name):
    """Latest clip time a template asks of source `name` (how long the crew's clip must be)."""
    ts = [L.get("t", 0) for fp in plan["frames"] for L in fp["layers"] if L.get("src") == name]
    return max(ts) if ts else 0.0


def clip_speed(available_s, needed_s, floor=.5):
    """Playback speed so a short clip fills its slot; never slower than `floor` (0.5x still looks
    like intentional slow motion; slower turns into a slideshow - then we hold the last frame)."""
    if needed_s <= 0 or available_s >= needed_s:
        return 1.0
    return max(floor, available_s / needed_s)


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
    ov_idx, ov = None, None
    for i, fp in enumerate(plan["frames"]):
        acc = np.zeros((H, W, 3), np.float32)
        for L in fp["layers"]:
            img, a = render_layer(L, clips)
            acc = acc * (1 - a) + img * a
        j = fp.get("ov", i)
        if j != ov_idx:                     # overlay changed: decode once, premultiply, cache
            o = np.asarray(Image.open(f"{frames_dir}/{j:04d}.png").convert("RGBA")).astype(np.float32)
            oa = o[..., 3:] / 255.0
            ys = np.where(oa[..., 0].max(axis=1) > 0)[0]
            # only blend the rows that actually carry graphics
            ov = (ys[0], ys[-1] + 1, o[ys[0]:ys[-1] + 1, :, :3] * oa[ys[0]:ys[-1] + 1],
                  1 - oa[ys[0]:ys[-1] + 1]) if len(ys) else None
            ov_idx = j
        if ov is not None:
            y0, y1, rgb, inv = ov
            acc[y0:y1] = acc[y0:y1] * inv + rgb
        enc.stdin.write(np.clip(acc, 0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    enc.wait()
    for c in clips.values():
        if c.proc:
            c.proc.kill()


def first_frame(path):
    c = Clip(path, 30)
    return c.frame(0)


def template_meta(html, pfile):
    """window.META of a template (with these params), without rendering any frames."""
    js = ("const { chromium } = require('playwright');(async () => {const [h, p] = process.argv.slice(-2);"
          "const b = await chromium.launch(); const pg = await b.newPage();"
          "await pg.addInitScript(x => { window.PARAMS = x; }, JSON.parse(require('fs').readFileSync(p, 'utf8')));"
          "await pg.goto('file://' + h); console.log(JSON.stringify(await pg.evaluate(() => window.META)));"
          "await b.close(); })();")
    out = subprocess.run(["node", "-e", js, os.path.abspath(html), pfile], capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


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
    ap.add_argument("--vo-take", default=None, help="one VO recording holding every template line, split on pauses")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
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
        for wmsg in r["warnings"]:
            print(f"  ! {name}: {wmsg['message']}")
    footage = mezz

    # 2. alignment first: the template needs to know whether a split reveal is possible
    b, a = find_clip(footage, "before"), find_clip(footage, "after")
    al = align.plan_alignment(first_frame(b), first_frame(a)) if b and a else dict(ok=False, zoom=1, score=0)
    params["aligned"] = bool(al["ok"])
    # where the clean-up shows most (detail push-ins) and which bands are calm enough for text
    params["busy"] = {}
    for name, path in (("before", b), ("after", a)):
        if path:
            fr = focus.to_render_space(first_frame(path), al.get(name) if al["ok"] else None,
                                       al["zoom"] if al["ok"] else 1.0)
            params["busy"][name] = focus.busy_profile(fr)
            if name == "before":
                fb = fr
    if al["ok"]:
        params["focus"] = focus.change_points(fb, fr)
        print("focus:", ", ".join(f"({p['fx']:.2f},{p['fy']:.2f}) {p['score']:.0f}" for p in params["focus"]) or "none")
    params["activity"] = {k: v.get("activity") for k, v in report.items() if v.get("activity")}
    pfile = os.path.join(work, "params.json")
    json.dump(params, open(pfile, "w"))
    print(f"align: ok={al['ok']} score={al['score']:.2f} zoom={al['zoom']:.3f}")

    # VO take: split per line and time every word BEFORE drawing, so captions can follow the voice
    vo_clips = None
    if args.vo_take:
        meta0 = template_meta(os.path.join(args.template, "index.html"), pfile)
        try:
            timing, vo_clips = audio.take_timing(args.vo_take, meta0.get("vo", []))
            params["voTiming"] = timing
            json.dump(params, open(pfile, "w"))
            print(f"vo: {len(timing)} lines timed from {os.path.basename(args.vo_take)}")
        except ValueError as e:
            print("vo: skipped,", e)

    # 1. overlay + plan
    cmd = ["node", os.path.join(ROOT, "render/overlay.js"), os.path.join(args.template, "index.html"), work, pfile]
    if args.seconds:
        cmd.append(str(args.seconds))
    subprocess.run(cmd, check=True)
    plan = json.load(open(os.path.join(work, "plan.json")))
    fps = plan["meta"]["fps"]
    print(f"overlay: {len(plan['frames'])} frames in {time.time() - t0:.0f}s")

    # 3. composite
    # tripod lock: remove each clip's handheld drift so the split stays registered on every frame.
    # before and after must share one crop zoom, or the registration breaks.
    stabs, pair_zoom = {}, al["zoom"] if al["ok"] else 1.0
    ident = np.eye(2, 3, dtype=np.float32)
    for name in ("before", "after"):
        p = find_clip(footage, name)
        if p and name in plan["meta"]["sources"] and report.get(name, {}).get("kind") == "video":
            stabs[name] = stabilize.track(p, seconds=needed_seconds(plan, name) + .5, fps=fps)
            A = al.get(name) if al["ok"] and al.get(name) is not None else ident
            pair_zoom = max([pair_zoom] + [align.crop_zoom_for(stabilize.compose(A, S), W, H) for S in stabs[name][::5]])
    if stabs:
        print(f"stabilise: {', '.join(stabs)} locked, shared zoom {pair_zoom:.3f}")
    clips = {}
    for name in plan["meta"]["sources"]:
        p = find_clip(footage, name)
        if not p:
            raise SystemExit(f"missing footage: {name} in {args.footage}")
        warp = al.get(name) if name in ("before", "after") and al["ok"] else None
        zoom = al["zoom"] if name in ("before", "after") and al["ok"] else 1.0
        stab = stabs.get(name)
        if name in stabs:
            zoom = pair_zoom
        speed = 1.0
        if name in report and report[name]["kind"] == "video":
            have = report[name]["frames"] / fps
            speed = clip_speed(have, needed_seconds(plan, name))
            if have < needed_seconds(plan, name) * .5:
                report[name]["warnings"].append(dict(code="too_short", message=(
                    f"This clip is {have:.0f} s; this reel needs about {needed_seconds(plan, name):.0f} s. "
                    "Keep filming a little longer next time.")))
            if speed < 1:
                print(f"{name}: clip is {have:.1f}s, slot needs {needed_seconds(plan, name):.1f}s -> {speed:.2f}x slow motion")
        clips[name] = Clip(p, fps, warp, zoom, speed, stab)
    silent = os.path.join(work, "silent.mp4")
    composite(work, plan, clips, silent, fps)
    print(f"composite done at {time.time() - t0:.0f}s")

    # 4. audio
    wav = os.path.join(work, "mix.wav")
    audio.build_mix(plan["meta"], wav, work, vo_clips=vo_clips)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", wav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", args.out], check=True)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk != "activity"} for k, v in report.items()},
              open(os.path.splitext(args.out)[0] + ".footage.json", "w"), indent=1)
    print(f"reel -> {args.out} in {time.time() - t0:.0f}s")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print("work dir:", work)


if __name__ == "__main__":
    main()
