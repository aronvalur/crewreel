"""Web API contract (needs a production build: cd web && npx next build). Starts its own server."""
import json, os, socket, subprocess, time, urllib.request, urllib.error
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


def call(base, method, path, body=None, ctype="application/json"):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    req = urllib.request.Request(base + path, data, {"Content-Type": ctype} if data is not None else {}, method=method)
    try:
        r = urllib.request.urlopen(req); return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def get(base, path):
    try:
        r = urllib.request.urlopen(base + path); return r.status
    except urllib.error.HTTPError as e:
        return e.code


def draft(base):
    code, body = call(base, "POST", "/api/drafts")
    assert code == 201
    return body["id"]


def put(base, jid, slot, name, data):
    return call(base, "PUT", f"/api/drafts/{jid}/{slot}?name={name}", data, "application/octet-stream")


def test_rejects_missing_clips_with_plain_message(server):
    base, _ = server
    jid = draft(base)
    assert put(base, jid, "before", "b.mp4", b"x" * 10)[0] == 200
    code, body = call(base, "POST", "/api/jobs", {"draft": jid, "template": "driveway"})
    assert code == 400 and body["error"] == "Still missing: Cleaning, After."


def test_rejects_photo_for_video_slot_and_unknown_types(server):
    base, _ = server
    jid = draft(base)
    for slot, name in (("before", "b.jpg"), ("action1", "a.jpg"), ("after", "c.jpg")):
        assert put(base, jid, slot, name, b"x")[0] == 200
    code, body = call(base, "POST", "/api/jobs", {"draft": jid, "template": "driveway"})
    assert code == 400 and "Cleaning" in body["error"]
    assert put(base, jid, "before", "evil.sh", b"x")[0] == 400
    assert put(base, jid, "nope", "a.mp4", b"x")[0] == 400


def test_streams_upload_and_queues_job(server):
    base, data = server
    jid = draft(base)
    big = os.urandom(20 * 1024 * 1024)
    assert put(base, jid, "before", "b.JPG", b"x")[0] == 200
    assert put(base, jid, "action1", "a.MOV", big)[1]["bytes"] == len(big)
    assert put(base, jid, "after", "c.mp4", b"x")[0] == 200
    assert put(base, jid, "after", "c2.mov", b"yy")[0] == 200            # re-pick replaces the old clip
    code, body = call(base, "POST", "/api/jobs", {"draft": jid, "template": "driveway", "title": "Drive",
                                                  "fields": {"hook": "Clean\r\n*now*"}})
    assert code == 201
    d = data / "jobs" / jid
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "queued" and job["files"] == {"before": "before.jpg", "action1": "action1.mov", "after": "after.mov"}
    assert job["params"]["hook"] == "Clean\n*now*"
    assert (d / "in" / "action1.mov").read_bytes() == big
    assert not (d / "in" / "after.mp4").exists()
    assert get(base, f"/api/jobs/{jid}") == 200
    assert put(base, jid, "before", "b.jpg", b"x")[0] == 404              # no uploads into a queued job


def test_drafts_are_hidden_from_the_reels_list(server):
    base, _ = server
    jid = draft(base)
    r = urllib.request.urlopen(base + "/api/jobs")
    assert jid not in [j["id"] for j in json.loads(r.read())]


def test_files_route_only_serves_outputs(server):
    base, _ = server
    assert get(base, "/api/files/20261126-deadbeef/job.json") == 404
    assert get(base, "/api/files/..%2F..%2Fetc/reel.mp4") == 404
    assert get(base, "/api/jobs/..%2Fprofile") == 404


def leads(data):
    d = data / "leads"
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []


def test_quote_request_is_stored_and_credited_to_the_reel(server):
    base, data = server
    jid = draft(base)                                                  # any existing job id counts as a reel ref
    before = len(leads(data))
    code, _ = call(base, "POST", "/api/leads", {"name": "  Sigga  ", "contact": "+354 555 1234", "address": "Laugavegur 1",
                                                "services": ["Roof", "Hot tub"], "message": "Moss on the north side", "ref": jid})
    assert code == 201
    assert len(leads(data)) == before + 1
    l = next(x for x in leads(data) if x["name"] == "Sigga")
    assert l["name"] == "Sigga" and l["services"] == ["Roof"] and l["ref"] == jid and not l.get("seen")
    # unknown reel ids are dropped, not trusted
    assert call(base, "POST", "/api/leads", {"name": "Anna", "contact": "a@b.is", "ref": "20990101-ffffffff"})[0] == 201
    assert next(x for x in leads(data) if x["name"] == "Anna").get("ref") is None


def test_quote_request_needs_a_way_to_reply_and_drops_bots(server):
    base, data = server
    n = len(leads(data))
    code, body = call(base, "POST", "/api/leads", {"name": "Jón", "contact": "12"})
    assert code == 400 and "phone number or email" in body["error"]
    assert call(base, "POST", "/api/leads", {"name": "", "contact": "a@b.is"})[1]["error"] == "Add your name."
    assert call(base, "POST", "/api/leads", {"name": "Bot", "contact": "a@b.is", "website": "http://spam"})[0] == 201
    assert len(leads(data)) == n                                       # honeypot: looks accepted, nothing stored
    assert get(base, "/q") == 200 and get(base, "/quotes") == 200
