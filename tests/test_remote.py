"""Remote rendering hand-off: web box -> GitHub release + workflow dispatch -> reel back, footage cleaned up.
Runs against a fake GitHub API (no network, no account)."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "worker"))
import remote  # noqa: E402
import worker  # noqa: E402


class FakeGitHub:
    def __init__(self):
        self.releases, self.blobs, self.dispatches, self.tags_deleted = {}, {}, [], []
        self.next_id, self.bad_auth = 100, []
        self.on_dispatch = None
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None, headers=None):
                body = raw if raw is not None else (json.dumps(obj).encode() if obj is not None else b"")
                self.send_response(code)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _auth(self):
                if self.headers.get("Authorization") != "Bearer t0k":
                    fake.bad_auth.append(self.path)

            def do_GET(self):
                u = urlparse(self.path)
                if u.path.startswith("/dl/"):                 # signed storage URL: must NOT carry our token
                    if self.headers.get("Authorization"):
                        fake.bad_auth.append("token leaked to storage")
                    return self._send(200, raw=fake.blobs[int(u.path[4:])])
                self._auth()
                if u.path.startswith("/repos/o/r/releases/tags/"):
                    tag = u.path.rsplit("/", 1)[1]
                    rel = fake.releases.get(tag)
                    return self._send(200, rel) if rel else self._send(404, {"message": "Not Found"})
                if u.path.startswith("/repos/o/r/releases/assets/"):
                    aid = int(u.path.rsplit("/", 1)[1])
                    return self._send(302, headers={"Location": f"http://127.0.0.1:{fake.port}/dl/{aid}"})
                self._send(404, {})

            def do_POST(self):
                self._auth()
                u = urlparse(self.path)
                n = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(n)
                if u.path == "/repos/o/r/releases":
                    d = json.loads(body)
                    rid = fake.next_id; fake.next_id += 1
                    rel = {"id": rid, "tag_name": d["tag_name"], "prerelease": d["prerelease"], "assets": [],
                           "upload_url": f"http://127.0.0.1:{fake.port}/uploads/repos/o/r/releases/{rid}/assets{{?name,label}}"}
                    fake.releases[d["tag_name"]] = rel
                    return self._send(201, rel)
                if u.path.startswith("/uploads/repos/o/r/releases/"):
                    rid = int(u.path.split("/")[-2])
                    name = parse_qs(u.query)["name"][0]
                    fake.add_asset(rid, name, body)
                    return self._send(201, {"name": name})
                if u.path.endswith("/actions/workflows/render-job.yml/dispatches"):
                    fake.dispatches.append(json.loads(body))
                    if fake.on_dispatch:
                        fake.on_dispatch(json.loads(body))
                    return self._send(204)
                self._send(404, {})

            def do_DELETE(self):
                self._auth()
                u = urlparse(self.path)
                if u.path.startswith("/repos/o/r/releases/"):
                    rid = int(u.path.rsplit("/", 1)[1])
                    for tag, rel in list(fake.releases.items()):
                        if rel["id"] == rid:
                            del fake.releases[tag]
                    return self._send(204)
                if u.path.startswith("/repos/o/r/git/refs/tags/"):
                    fake.tags_deleted.append(u.path.rsplit("/", 1)[1])
                    return self._send(204)
                self._send(404, {})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def add_asset(self, rid, name, data):
        aid = self.next_id; self.next_id += 1
        self.blobs[aid] = data
        for rel in self.releases.values():
            if rel["id"] == rid:
                rel["assets"] = [a for a in rel["assets"] if a["name"] != name] + [{"id": aid, "name": name}]

    def rel(self, job_id):
        return self.releases.get(f"job-{job_id}")


def setup_job(tmp_path, monkeypatch, jid="20261127-abcd0001", template="roof"):
    data = tmp_path / "data"
    d = data / "jobs" / jid
    (d / "in").mkdir(parents=True)
    for s in ("before", "after", "action1", "action2"):
        (d / "in" / f"{s}.mp4").write_bytes(os.urandom(2048))
    (data / "profile.json").write_text(json.dumps({"business": "Valur Exterior", "area": "Reykjavík"}))
    (d / "job.json").write_text(json.dumps(dict(id=jid, createdAt="2026-11-27T01:00:00Z", template=template,
                                                status="queued", params={"hook": "Black streaks?"})))
    monkeypatch.setattr(worker, "DATA", str(data))
    return d


def test_ship_render_collect_and_clean_up(tmp_path, monkeypatch):
    fake = FakeGitHub()
    gh = remote.GitHub("o/r", "t0k", api=f"http://127.0.0.1:{fake.port}")
    d = setup_job(tmp_path, monkeypatch)
    jid = d.name

    assert worker.remote_step(gh)                                   # ship
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "rendering" and job["remote"]["tag"] == f"job-{jid}"
    rel = fake.rel(jid)
    assert rel["prerelease"] is True
    assert sorted(a["name"] for a in rel["assets"]) == ["action1.mp4", "action2.mp4", "after.mp4", "before.mp4",
                                                         "params.json"]
    params = json.loads(fake.blobs[[a for a in rel["assets"] if a["name"] == "params.json"][0]["id"]])
    assert params["business"] == "Valur Exterior" and params["hook"] == "Black streaks?"
    assert fake.dispatches == [{"ref": "main", "inputs": {"job_id": jid, "template": "roof"}}]

    worker.remote_step(gh)                                          # still rendering: nothing changes
    assert json.loads((d / "job.json").read_text())["status"] == "rendering"

    # the workflow finishes: reel, poster and footage report land on the release
    fake.add_asset(rel["id"], "reel.mp4", b"MP4" * 1000)
    fake.add_asset(rel["id"], "poster.jpg", b"JPG" * 100)
    fake.add_asset(rel["id"], "reel.footage.json",
                   json.dumps({"before": {"warnings": [{"code": "too_dark", "message": "dark"}]}}).encode())
    worker.remote_step(gh)
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "done"
    assert (d / "reel.mp4").read_bytes() == b"MP4" * 1000 and (d / "poster.jpg").exists()
    assert job["hints"] == {"before": [{"code": "too_dark", "message": "dark"}]}
    assert fake.rel(jid) is None and fake.tags_deleted == [f"job-{jid}"]   # footage gone from GitHub
    assert fake.bad_auth == []                                      # token on API calls only, never on storage


def test_remote_failure_reports_plain_english(tmp_path, monkeypatch):
    fake = FakeGitHub()
    gh = remote.GitHub("o/r", "t0k", api=f"http://127.0.0.1:{fake.port}")
    d = setup_job(tmp_path, monkeypatch)
    worker.remote_step(gh)
    fake.add_asset(fake.rel(d.name)["id"], "error.txt", b"...\nSystemExit: missing footage: action2 in job/in\n")
    worker.remote_step(gh)
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "failed" and "clip is missing" in job["error"]
    assert fake.rel(d.name) is None


def test_ship_failure_requeues(tmp_path, monkeypatch):
    gh = remote.GitHub("o/r", "t0k", api="http://127.0.0.1:9")     # nothing listens: network failure
    d = setup_job(tmp_path, monkeypatch)
    worker.remote_step(gh)
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "queued" and not (d / ".lock").exists()


def test_lost_release_fails_the_job(tmp_path, monkeypatch):
    fake = FakeGitHub()
    gh = remote.GitHub("o/r", "t0k", api=f"http://127.0.0.1:{fake.port}")
    d = setup_job(tmp_path, monkeypatch)
    worker.remote_step(gh)
    fake.releases.clear()
    worker.remote_step(gh)
    assert json.loads((d / "job.json").read_text())["status"] == "failed"
