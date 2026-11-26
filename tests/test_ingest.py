"""Ingest tests: the footage problems real crews will hand us."""
import json, os, subprocess, sys
import numpy as np
import cv2
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import ingest  # noqa: E402


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def textured(h, w):
    """Bright top half, dark-but-detailed bottom half (a shadowed driveway, not a letterbox bar)."""
    n = np.random.default_rng(2).integers(0, 40, (h, w))
    a = np.where(np.arange(h)[:, None] < h // 2, 215, 15) + n
    return a.astype(np.uint8)


def frames_of(path, n=None):
    return list(ingest.decode(path, [], 270, 480, limit=n))


def size_of(path):
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height", "-of", "json", path], capture_output=True, text=True).stdout)
    return s["streams"][0]["width"], s["streams"][0]["height"]


def test_letterboxed_landscape_follows_the_action(tmp_path):
    """16:9 clip with black bars and a bright 'spray' blob moving right -> 9:16 crop follows it."""
    src = tmp_path / "lb.mp4"
    w, h, n = 640, 360, 60
    rng = np.random.default_rng(1)
    tex = cv2.resize(rng.random((24, 64)).astype(np.float32), (w, 270)) * 60 + 90
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                          "-r", "30", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)], stdin=subprocess.PIPE)
    for i in range(n):
        f = np.zeros((h, w), np.float32)
        img = tex.copy()
        x = int(80 + 480 * i / n)
        cv2.circle(img, (x + int(6 * np.sin(i)), 135), 40, 255 if i % 2 else 200, -1)   # flickering spray
        f[45:315] = img
        p.stdin.write(f.astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    out = tmp_path / "o.mp4"
    meta = ingest.ingest(str(src), str(out))
    assert meta["crop"] is not None and meta["crop"][1] >= 45 and meta["crop"][1] + meta["crop"][3] <= 315
    assert size_of(str(out)) == (1080, 1920)
    assert meta["pan"][-1] > meta["pan"][0] + 200          # crop pans right with the action
    fr = frames_of(str(out))
    assert min(f[:6].mean() for f in fr) > 40              # no black bar left at the top


def test_hdr_hlg_is_tonemapped_to_sdr(tmp_path):
    src = tmp_path / "hlg.mp4"
    ff("-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=1", "-c:v", "libx265", "-x265-params", "log-level=error",
       "-pix_fmt", "yuv420p10le", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc",
       str(src))
    assert ingest.probe(str(src))["hdr"]
    out = tmp_path / "o.mp4"
    meta = ingest.ingest(str(src), str(out))
    assert meta["hdr"]
    fr = frames_of(str(out))
    assert fr[0].std() > 30                                # not a washed-out flat grey
    trc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
    assert trc == "bt709"


def test_rotation_metadata_is_applied(tmp_path):
    """Landscape-encoded clip flagged as rotated 90 deg must come out portrait without cropping it to a sliver."""
    raw = tmp_path / "raw.mp4"
    # top half white, bottom half black when upright (portrait 360x640) -> encode rotated as 640x360
    up = textured(640, 360)
    stored = cv2.rotate(up, cv2.ROTATE_90_CLOCKWISE)        # what the sensor wrote
    cv2.imwrite(str(tmp_path / "s.png"), stored)
    ff("-loop", "1", "-i", str(tmp_path / "s.png"), "-t", "1", "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw))
    rot = tmp_path / "rot.mp4"
    ff("-display_rotation", "90", "-i", str(raw), "-c", "copy", str(rot))
    info = ingest.probe(str(rot))
    assert abs(info["rotation"]) == 90 and info["height"] > info["width"]
    out = tmp_path / "o.mp4"
    meta = ingest.ingest(str(rot), str(out))
    assert meta["pan"] is None                             # treated as portrait, not landscape
    f = frames_of(str(out))[0].astype(np.float32).mean(axis=(1, 2))
    assert f[:220].mean() - f[260:].mean() > 120           # upright: bright half on top, dark half kept


def test_photo_exif_orientation(tmp_path):
    from PIL import Image
    up = np.dstack([textured(800, 600)] * 3)                  # upright portrait: bright top, dark bottom
    stored = np.ascontiguousarray(np.rot90(up, 1))            # camera stored it sideways
    im = Image.fromarray(stored)
    exif = im.getexif(); exif[0x0112] = 6                    # 'rotate 90 CW to display'
    src = tmp_path / "p.jpg"
    im.save(src, exif=exif)
    out = tmp_path / "o.png"
    ingest.ingest(str(src), str(out))
    a = cv2.imread(str(out), cv2.IMREAD_GRAYSCALE).astype(np.float32)
    assert a.shape == (1920, 1080)
    assert a[:900].mean() > 180 and a[1020:].mean() < 70
