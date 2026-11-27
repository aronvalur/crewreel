"""Render worker: picks queued jobs from the job store and turns them into reels.

  python worker/worker.py            # run forever, polling every 2 s
  python worker/worker.py --once     # render at most one job, then exit (tests, cron)
  python worker/worker.py --remote github   # web box: ship jobs to GitHub Actions (render-job.yml), collect reels

Job store layout (shared with web/lib/store.ts):
  $CREWREEL_DATA/profile.json
  $CREWREEL_DATA/jobs/<id>/job.json, in/<slot>.<ext>  ->  reel.mp4, poster.jpg, render.log
"""
import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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

    make_poster(out, job["template"], os.path.join(d, "poster.jpg"))
    return update(status="done", stage=None, hints=hints_for(out), finishedAt=now())


def make_poster(out, template, dest):
    """Poster for the reels grid, at the moment that sells the job (mid-reveal)."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                               capture_output=True, text=True).stdout or 0)
    at = min(POSTER_AT.get(template, 1.0), max(0.0, dur - 0.1))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}", "-i", out, "-frames:v", "1",
                    "-vf", "scale=540:-2", "-q:v", "3", dest])


def hints_for(out):
    report = read(os.path.splitext(out)[0] + ".footage.json", {}) or {}
    return {slot: r.get("warnings", []) for slot, r in report.items() if r.get("warnings")}


# ---- remote mode: the web box ships jobs to GitHub Actions (worker/remote.py) ----
def remote_step(gh):
    """Ship every newly queued job, collect every finished one. Returns True if anything happened."""
    import remote
    busy = False
    try:
        ids = sorted(os.listdir(jobs_dir()))
    except OSError:
        return False
    for i in ids:
        d = os.path.join(jobs_dir(), i)
        jf = os.path.join(d, "job.json")
        j = read(jf)
        if not j or j.get("status") != "rendering" or not j.get("remote"):
            continue
        state, err = remote.poll(gh, d, j)
        if state == "waiting":
            continue
        busy = True
        cur = read(jf, j)
        if state == "done":
            cur.update(status="done", stage=None, hints=hints_for(os.path.join(d, "reel.mp4")), finishedAt=now())
        else:
            cur.update(status="failed", error=err, finishedAt=now())
        write(jf, cur)
        print(f"worker: {i} -> {cur['status']} (remote)", flush=True)
    job = claim_next()
    if job:
        busy = True
        d = os.path.join(jobs_dir(), job["id"])
        jf = os.path.join(d, "job.json")
        if job.get("template") not in TEMPLATES:
            cur = read(jf, job); cur.update(status="failed", error="Unknown reel style.", finishedAt=now())
            write(jf, cur)
            return busy
        pfile = os.path.join(d, "params.json")
        write(pfile, build_params(job))
        cur = read(jf, job)
        cur.update(status="rendering", stage="Uploading to the render machine", startedAt=now())
        write(jf, cur)
        try:
            rec = remote.ship(gh, d, job, pfile)
        except Exception as e:                 # network/API trouble: put it back in the queue
            print(f"worker: ship {job['id']} failed: {e}", flush=True)
            cur.update(status="queued", stage=None)
            write(jf, cur)
            os.remove(os.path.join(d, ".lock"))
            return busy
        cur.update(stage="Rendering (about 5 minutes)", remote=rec)
        write(jf, cur)
        print(f"worker: {job['id']} shipped to {rec['host']} ({rec['tag']})", flush=True)
    return busy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--remote", choices=["github"], default=os.environ.get("CREWREEL_REMOTE") or None,
                    help="ship jobs to GitHub Actions instead of rendering here (needs GITHUB_REPO + GITHUB_TOKEN)")
    args = ap.parse_args()
    print(f"worker: data at {DATA}", flush=True)
    if args.remote:
        import remote
        gh = remote.GitHub(os.environ["GITHUB_REPO"], os.environ["GITHUB_TOKEN"],
                           api=os.environ.get("GITHUB_API", remote.API))
        print(f"worker: remote rendering on GitHub Actions ({gh.repo})", flush=True)
        while True:
            busy = remote_step(gh)
            if args.once:
                return
            time.sleep(2 if busy else 15)
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
