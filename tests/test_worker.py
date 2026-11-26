"""Worker: a queued job in the store comes out as a reel + poster + hints."""
import json, os, shutil, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_job(data, jid, template, footage, files):
    d = data / "jobs" / jid
    (d / "in").mkdir(parents=True)
    for slot in files:
        shutil.copy(footage / f"{slot}.mp4", d / "in" / f"{slot}.mp4")
    job = dict(id=jid, createdAt="2026-11-26T12:00:00Z", template=template, title="Test", status="queued",
               params={"hook": "Clean in\n*one* morning."}, files={s: f"{s}.mp4" for s in files})
    (d / "job.json").write_text(json.dumps(job))
    return d


def run_worker(data, seconds="2"):
    env = {**os.environ, "CREWREEL_DATA": str(data), "CREWREEL_MAX_SECONDS": seconds}
    subprocess.run([sys.executable, f"{ROOT}/worker/worker.py", "--once"], check=True, env=env, capture_output=True)


@pytest.mark.slow
def test_worker_renders_a_queued_job(tmp_path):
    foot = tmp_path / "foot"
    subprocess.run([sys.executable, f"{ROOT}/scripts/gen_placeholder.py", "pavers", str(foot)], check=True,
                   capture_output=True)
    data = tmp_path / "data"
    (data).mkdir()
    (data / "profile.json").write_text(json.dumps({"business": "Valur Exterior", "area": "Reykjavík", "url": "v.is/q"}))
    d = make_job(data, "20261126-aaaa0001", "driveway", foot, ["before", "after", "action1"])
    run_worker(data)
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "done", (d / "render.log").read_text()[-800:]
    assert (d / "reel.mp4").stat().st_size > 10_000
    assert (d / "poster.jpg").stat().st_size > 1_000
    assert json.loads((d / "params.json").read_text())["initials"] == "VE"
    assert job["hints"] == {}                        # placeholder footage is clean, upright, full-res


def test_worker_fails_gracefully_on_missing_clip(tmp_path):
    foot = tmp_path / "foot"
    foot.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1",
                    "-pix_fmt", "yuv420p", str(foot / "before.mp4")], check=True)
    data = tmp_path / "data"
    d = make_job(data, "20261126-bbbb0002", "driveway", foot, ["before"])
    run_worker(data)
    job = json.loads((d / "job.json").read_text())
    assert job["status"] == "failed"
    assert "missing" in job["error"].lower()


def test_worker_never_double_claims(tmp_path):
    sys.path.insert(0, f"{ROOT}/worker")
    import worker
    worker.DATA = str(tmp_path)
    d = tmp_path / "jobs" / "20261126-cccc0003"
    d.mkdir(parents=True)
    (d / "job.json").write_text(json.dumps(dict(id="20261126-cccc0003", createdAt="x", status="queued", template="driveway")))
    assert worker.claim_next()["id"] == "20261126-cccc0003"
    assert worker.claim_next() is None
