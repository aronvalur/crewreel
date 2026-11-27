"""Remote rendering on GitHub Actions (the chosen free render host, docs/DECISIONS.md).

The web box (Render free: 0.1 CPU) can't render, so its worker ships each queued job to GitHub:
  1. ship(): create a pre-release tagged job-<id> in the repo, upload the clips + params.json as its assets,
     dispatch .github/workflows/render-job.yml with the job id and style.
  2. The workflow downloads the assets, renders with the stock VO, uploads reel.mp4, poster.jpg and
     reel.footage.json (or error.txt) back to the same release.
  3. poll(): when the reel is there, download it into the job folder, then delete the release and its tag
     so customer footage never lingers in the repo.
No inbound webhook, no extra service: the web box only makes outbound HTTPS calls.
Swap point for later: when a bucket exists, assets go to the bucket and only the dispatch stays.
"""
import json, os, time, urllib.error, urllib.parse, urllib.request

API = os.environ.get("GITHUB_API", "https://api.github.com")
WORKFLOW = "render-job.yml"
OUTPUTS = ("reel.mp4", "poster.jpg", "reel.footage.json")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class GitHub:
    def __init__(self, repo, token, api=API, ref="main"):
        self.repo, self.token, self.api, self.ref = repo, token, api.rstrip("/"), ref

    def _req(self, method, url, data=None, headers=None, raw=False, follow=True):
        if not url.startswith("http"):
            url = f"{self.api}/repos/{self.repo}{url}"
        h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "crewreel-worker"}
        h.update(headers or {})
        body = data
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(req, timeout=120) as r:
                out = r.read()
                return out if raw else (json.loads(out) if out else None)
        except urllib.error.HTTPError as e:
            if not follow and e.code in (301, 302, 303, 307, 308):
                return e.headers["Location"]
            if e.code == 404:
                return None
            raise RuntimeError(f"GitHub {method} {url} -> {e.code}: {e.read()[:300]!r}") from None

    # --- releases as a temporary job mailbox ---
    def create_release(self, tag, body=""):
        return self._req("POST", "/releases", {"tag_name": tag, "target_commitish": self.ref, "name": tag,
                                               "body": body, "prerelease": True})

    def release(self, tag):
        return self._req("GET", f"/releases/tags/{urllib.parse.quote(tag)}")

    def upload(self, rel, path, name=None):
        name = name or os.path.basename(path)
        url = rel["upload_url"].split("{")[0] + "?" + urllib.parse.urlencode({"name": name})
        size = os.path.getsize(path)
        with open(path, "rb") as f:            # streamed: clips can be hundreds of MB
            return self._req("POST", url, f, {"Content-Type": "application/octet-stream",
                                               "Content-Length": str(size)})

    def download(self, asset, dest):
        loc = self._req("GET", f"/releases/assets/{asset['id']}", headers={"Accept": "application/octet-stream"},
                        raw=True, follow=False)
        if isinstance(loc, str):                # signed storage URL: fetch WITHOUT our token
            req = urllib.request.Request(loc, headers={"User-Agent": "crewreel-worker"})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest + ".part", "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
        else:
            open(dest + ".part", "wb").write(loc)
        os.replace(dest + ".part", dest)

    def delete_release(self, rel):
        self._req("DELETE", f"/releases/{rel['id']}")
        self._req("DELETE", f"/git/refs/tags/{urllib.parse.quote(rel['tag_name'])}")

    def dispatch(self, inputs):
        return self._req("POST", f"/actions/workflows/{WORKFLOW}/dispatches", {"ref": self.ref, "inputs": inputs})


def tag_for(job):
    return f"job-{job['id']}"


def ship(gh, job_dir, job, params_file):
    """Upload the job's clips + params and start the render. Returns the remote record for job.json."""
    tag = tag_for(job)
    rel = gh.release(tag) or gh.create_release(tag, f"Crewreel render job {job['id']} (temporary, auto-deleted)")
    have = {a["name"] for a in rel.get("assets", [])}
    ind = os.path.join(job_dir, "in")
    for f in sorted(os.listdir(ind)):
        if f not in have:
            gh.upload(rel, os.path.join(ind, f))
    if "params.json" not in have:
        gh.upload(rel, params_file, "params.json")
    gh.dispatch({"job_id": job["id"], "template": job["template"]})
    return {"host": "github", "tag": tag, "release": rel["id"], "shippedAt": time.time()}


def poll(gh, job_dir, job, timeout_s=45 * 60):
    """-> ("done", None) | ("failed", message) | ("waiting", None). Cleans up the release when finished."""
    rel = gh.release(job["remote"]["tag"])
    if rel is None:
        return "failed", "The render server lost this job. Please submit it again."
    assets = {a["name"]: a for a in rel.get("assets", [])}
    if "error.txt" in assets:
        p = os.path.join(job_dir, "render.log")
        gh.download(assets["error.txt"], p)
        gh.delete_release(rel)
        tail = open(p, errors="replace").read()[-600:]
        if "missing footage" in tail:
            return "failed", "A clip is missing. Upload all the shots and try again."
        return "failed", "We couldn't read one of the clips. Try re-exporting it from your phone's camera roll."
    if "reel.mp4" in assets and "poster.jpg" in assets:
        for name in OUTPUTS:
            if name in assets:
                gh.download(assets[name], os.path.join(job_dir, name))
        gh.delete_release(rel)
        return "done", None
    if time.time() - job["remote"].get("shippedAt", time.time()) > timeout_s:
        gh.delete_release(rel)
        return "failed", "Rendering took too long. Please submit it again."
    return "waiting", None
