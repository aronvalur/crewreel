"""Render worker: picks queued jobs from the job store and turns them into reels.

  python worker/worker.py            # run forever, polling every 2 s
  python worker/worker.py --once     # render at most one job, then exit (tests, cron)

Job store layout (shared with web/lib/store.ts):
  $CREWREEL_DATA/profile.json
  $CREWREEL_DATA/jobs/<id>/job.json, in/<slot>.<ext>  ->  reel.mp4, poster.jpg, render.log
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.abspath(os.environ.get("CREWREEL_DATA", os.path.join(ROOT, "data")))
TEMPLATES = {"driveway", "house-wash", "roof"}
POSTER_AT = {"driveway": 11.6, "house-wash": 10.6, "roof": 9.5}   # split at 50 % / sweep mid-wall / rinse mid-roof

# render.py prints these as it moves through the pipeline -> what the contractor sees
STAGES = [("align:", "Drawing graphics"), ("overlay:", "Steadying shots"),
          ("stabilise:", "Composing frames"), ("composite done", "Mixing sound")]


def now():
    return datetime.now(timezone.utc).isoformat()


def jobs_dir():
    return os.path.join(DATA, "jobs")


def read(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write(path, data):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def claim_next():
    """Oldest queued job, claimed with an O_EXCL lock so two workers never take the same one."""
    try:
        ids = os.listdir(jobs_dir())
    except OSError:
        return None
    queued = []
    for i in ids:
        j = read(os.path.join(jobs_dir(), i, "job.json"))
        if j and j.get("status") == "queued":
            queued.append(j)
    for j in sorted(queued, key=lambda j: j["createdAt"]):
        lock = os.path.join(jobs_dir(), j["id"], ".lock")
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL))
        except FileExistsError:
            continue
        return j
    return None


def build_params(job):
    prof = read(os.path.join(DATA, "profile.json"), {}) or {}
    business = prof.get("business") or "Your Business"
    p = {
        "business": business,
        "initials": "".join(w[0] for w in business.split()[:2]).upper() or "C",
        "area": prof.get("area", ""),
        "url": prof.get("url") or "your-site.com/quote",
        "accent": prof.get("accent") or "#7FD1FF",
        "cta": prof.get("cta") or "Free quote in 60 seconds",
    }
    for k in ("hook", "method", "result"):
        if job.get("params", {}).get(k):
            p[k] = job["params"][k]
    return p


def render(job):
    d = os.path.join(jobs_dir(), job["id"])
    jf = os.path.join(d, "job.json")

    def update(**kw):
        cur = read(jf, job)
        cur.update(kw)
        write(jf, cur)
        return cur

    update(status="rendering", stage="Preparing footage", startedAt=now())
    if job.get("template") not in TEMPLATES:
        return update(status="failed", error="Unknown reel style.", finishedAt=now())
    pfile = os.path.join(d, "params.json")
    write(pfile, build_params(job))
    out = os.path.join(d, "reel.mp4")
    cmd = [sys.executable, os.path.join(ROOT, "render/render.py"), os.path.join(ROOT, "templates", job["template"]),
           os.path.join(d, "in"), out, "--params", pfile]
    if os.environ.get("CREWREEL_MAX_SECONDS"):
        cmd += ["--seconds", os.environ["CREWREEL_MAX_SECONDS"]]
    # Stock voiceover: template VO lines are generic (no business name), so one studio take per
    # template serves every customer at no per-reel cost. Custom per-job VO comes with the API key.
    take = os.path.join(ROOT, "assets", "vo", f"{job['template']}_blain.mp3")
    if os.path.exists(take):
        cmd += ["--vo-take", take]
    log = open(os.path.join(d, "render.log"), "w")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1,
                            env={**os.environ, "PYTHONUNBUFFERED": "1"})
    for line in proc.stdout:
        log.write(line)
        for key, stage in STAGES:
            if line.startswith(key):
                update(stage=stage)
    rc = proc.wait()
    log.close()
    if rc != 0 or not os.path.exists(out):
        tail = open(os.path.join(d, "render.log")).read()[-600:]
        msg = "We couldn't read one of the clips. Try re-exporting it from your phone's camera roll."
        if "missing footage" in tail:
            msg = "A clip is missing. Upload all the shots and try again."
        return update(status="failed", error=msg, finishedAt=now())

    # poster for the reels grid
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                               capture_output=True, text=True).stdout or 0)
    at = min(POSTER_AT.get(job["template"], 1.0), max(0.0, dur - 0.1))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", out, "-frames:v", "1",
                    "-vf", "scale=540:-2", "-q:v", "3", os.path.join(d, "poster.jpg")])
    report = read(os.path.splitext(out)[0] + ".footage.json", {}) or {}
    hints = {slot: r.get("warnings", []) for slot, r in report.items() if r.get("warnings")}
    return update(status="done", stage=None, hints=hints, finishedAt=now())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    print(f"worker: data at {DATA}", flush=True)
    while True:
        job = claim_next()
        if job:
            print(f"worker: rendering {job['id']} ({job['template']})", flush=True)
            res = render(job)
            print(f"worker: {job['id']} -> {res['status']}", flush=True)
        if args.once:
            return
        if not job:
            time.sleep(2)


if __name__ == "__main__":
    main()
