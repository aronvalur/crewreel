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


def test_guided_camera_films_keeps_and_sends_clips(server, tmp_path):
    """Film the before in the browser camera, leave, come back: it's still there, the after shows it as a
    ghost, and the filmed clips upload like picked ones (fake camera device)."""
    base, data = server
    clip = tmp_path / "a.mp4"; clip.write_bytes(b"\x00" * 2048)
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const [base, clip] = JSON.parse(process.argv.at(-1));
      const b = await chromium.launch({ args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] });
      const c = await b.newContext({ viewport: { width: 390, height: 844 } });
      const p = await c.newPage(); const out = {};
      await p.goto(base + '/jobs/new');
      const film = async (n) => {
        await p.locator('.drop').nth(n).locator('.drop-acts .btn:not(.ghost)').click();
        await p.waitForFunction(() => document.querySelector('.cam-view')?.videoWidth > 0);
        out['ghost' + n] = await p.locator('.cam-ghost').count();
        await p.click('.cam-rec'); await p.waitForTimeout(5300);
        out['good' + n] = await p.locator('.cam-time.ok').count();
        await p.click('.cam-rec'); await p.getByRole('button', { name: 'Use this clip' }).click();
      };
      await film(0);                                         // before
      await p.waitForTimeout(300);
      await p.reload(); await p.waitForTimeout(800);         // crew closes the app, comes back after the job
      out.keptBefore = await p.locator('.drop').nth(0).locator('.small').first().innerText();
      await p.locator('.drop').nth(1).locator('input[type=file]').setInputFiles(clip);
      await film(2);                                         // after, with the before as ghost
      await p.click('button[type=submit]');
      await p.waitForURL(/\\/jobs\\/[0-9]/, { timeout: 15000 });
      out.url = p.url();
      await p.goto(base + '/jobs/new'); await p.waitForTimeout(800);
      out.cleared = await p.locator('.drop.filled').count();
      console.log(JSON.stringify(out)); await b.close();
    })();"""
    r = subprocess.run(["node", "-e", js, json.dumps([base, str(clip)])], capture_output=True, text=True, cwd=ROOT, timeout=90)
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads(r.stdout)
    assert out["ghost0"] == 0 and out["ghost2"] == 1, out          # ghost only on the after shot
    assert out["good0"] == 1 and out["good2"] == 1, out            # timer says long enough at ~5 s
    assert "before-" in out["keptBefore"], out                     # survived the reload
    jid = out["url"].rstrip("/").split("/")[-1]
    job = json.loads((data / "jobs" / jid / "job.json").read_text())
    assert job["status"] == "queued" and job["files"]["before"].startswith("before.") and job["files"]["after"].startswith("after.")
    assert (data / "jobs" / jid / "in" / job["files"]["before"]).stat().st_size > 20_000   # real video bytes
    assert out["cleared"] == 0, out                                 # sent clips are forgotten on the phone


@pytest.fixture(scope="module")
def locked(tmp_path_factory):
    """Same build, started with CREWREEL_PASSWORD: everything but the quote page needs the sign-in cookie."""
    data = tmp_path_factory.mktemp("locked")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = {**os.environ, "CREWREEL_DATA": str(data), "CREWREEL_PASSWORD": "hunter2-long", "CREWREEL_INSECURE_COOKIE": "1"}
    p = subprocess.Popen(["npx", "next", "start", "-p", str(port)], cwd=WEB, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            urllib.request.urlopen(base + "/q", timeout=1); break
        except Exception:
            time.sleep(.5)
    yield base, data
    p.terminate(); p.wait()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def test_password_protects_the_app_but_not_the_quote_page(locked):
    base, data = locked
    op = urllib.request.build_opener(NoRedirect)
    def status(path, cookie=None):
        req = urllib.request.Request(base + path, headers={"Cookie": cookie} if cookie else {})
        try:
            return op.open(req).status
        except urllib.error.HTTPError as e:
            return e.code
    assert status("/") == 307 and status("/quotes") == 307 and status("/api/jobs") == 401
    assert status("/q") == 200
    assert call(base, "POST", "/api/leads", {"name": "Ann", "contact": "ann@example.com"})[0] == 201
    assert status("/api/files/20261126-deadbeef/poster.jpg") == 404          # public route, just no such file
    assert status("/api/files/20261126-deadbeef/reel.mp4") == 404           # public proof, just no such file
    assert status("/api/files/20261126-deadbeef/feed.mp4") == 401           # everything else needs sign-in
    assert status("/", "cr_session=9999999999999.forged") == 307
    js = """
    const { chromium } = require('playwright');
    (async () => {
      const base = process.argv.at(-1); const b = await chromium.launch(); const p = await b.newPage();
      await p.goto(base + '/quotes'); await p.fill('input[name=password]', 'wrong'); await p.click('button[type=submit]');
      await p.waitForSelector('.error'); const bad = p.url();
      await p.fill('input[name=password]', 'hunter2-long'); await p.click('button[type=submit]');
      await p.waitForURL(/\\/quotes$/); const h = await p.textContent('h1');
      console.log(JSON.stringify({ bad, h })); await b.close();
    })();"""
    r = subprocess.run(["node", "-e", js, base], capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert r.returncode == 0, r.stderr[-1200:]
    out = json.loads(r.stdout)
    assert "bad=1" in out["bad"] and out["h"] == "Quote requests"


def test_clip_upload_route_checks_sign_in_itself(locked):
    base, _ = locked
    code, body = call(base, "PUT", "/api/drafts/20261126-deadbeef/before?name=b.mp4", b"x" * 10, "application/octet-stream")
    assert code == 401
