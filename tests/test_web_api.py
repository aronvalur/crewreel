"""Web API contract (needs a production build: cd web && npx next build). Starts its own server."""
import json, os, socket, subprocess, time, urllib.request, urllib.error, uuid
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(WEB, ".next", "BUILD_ID")), reason="web not built")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    p = subprocess.Popen(["npx", "next", "start", "-p", str(port)], cwd=WEB, env={**os.environ, "CREWREEL_DATA": str(data)},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/api/jobs", timeout=1); break
        except Exception:
            time.sleep(.5)
    yield base, data
    p.terminate(); p.wait()


def post(base, fields, files):
    b = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (name, data) in files.items():
        body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n"
    body += f"--{b}--\r\n".encode()
    req = urllib.request.Request(base + "/api/jobs", body, {"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        r = urllib.request.urlopen(req); return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(base, path):
    try:
        r = urllib.request.urlopen(base + path); return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_rejects_missing_clips_with_plain_message(server):
    base, _ = server
    code, body = post(base, {"template": "driveway"}, {"before": ("b.mp4", b"x" * 10)})
    assert code == 400 and body["error"] == "Still missing: Cleaning, After."


def test_rejects_photo_for_video_slot(server):
    base, _ = server
    code, body = post(base, {"template": "driveway"}, {"before": ("b.jpg", b"x"), "action1": ("a.jpg", b"x"), "after": ("c.jpg", b"x")})
    assert code == 400 and "Cleaning" in body["error"]


def test_creates_queued_job(server):
    base, data = server
    code, body = post(base, {"template": "driveway", "title": "Drive", "hook": "Clean\r\n*now*"},
                      {"before": ("b.JPG", b"x"), "action1": ("a.MOV", b"x"), "after": ("c.mp4", b"x")})
    assert code == 201
    job = json.loads((data / "jobs" / body["id"] / "job.json").read_text())
    assert job["status"] == "queued" and job["files"] == {"before": "before.jpg", "action1": "action1.mov", "after": "after.mp4"}
    assert job["params"]["hook"] == "Clean\n*now*"
    assert get(base, f"/api/jobs/{body['id']}") == 200


def test_files_route_only_serves_outputs(server):
    base, _ = server
    assert get(base, "/api/files/20261126-deadbeef/job.json") == 404
    assert get(base, "/api/files/..%2F..%2Fetc/reel.mp4") == 404
    assert get(base, "/api/jobs/..%2Fprofile") == 404
