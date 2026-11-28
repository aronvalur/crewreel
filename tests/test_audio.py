"""Voiceover + mix: lines split from one take, words timed from the audio, voice on top, -14 LUFS."""
import os, sys, subprocess
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "render"))
import audio  # noqa: E402

TAKE = os.path.join(ROOT, "assets/vo/driveway_blain.mp3")
LINES = [{"at": .4, "text": "Eight years of grime on this driveway."},
         {"at": 3.4, "text": "Surface cleaner, then a soft rinse. No harsh chemicals."},
         {"at": 8.6, "text": "Same morning."},
         {"at": 12.4, "text": "Get your free quote at the link."}]
META = {"duration": 15, "cuts": [3, 8, 12], "impacts": [8.05], "vo": LINES}


def tone_take(spans, sr=audio.SR):
    """Synthetic 'speech': bursts of noise at the given (start, end) seconds."""
    x = np.zeros(int((spans[-1][1] + .5) * sr))
    rng = np.random.default_rng(0)
    for a, b in spans:
        x[int(a * sr):int(b * sr)] = rng.standard_normal(int(b * sr) - int(a * sr)) * .3
    return x


def test_split_take_uses_the_longest_pauses():
    x = tone_take([(.2, 1.0), (1.25, 1.6), (2.6, 3.0), (3.9, 4.5)])   # 0.25 s comma pause + two 0.9 s gaps
    segs = audio.split_take(x, 3)
    assert len(segs) == 3
    assert abs(segs[0][1] - 1.6) < .03 and abs(segs[1][0] - 2.6) < .03 and abs(segs[2][0] - 3.9) < .03


def test_words_after_a_pause_start_after_it():
    x = tone_take([(0, .8), (1.2, 1.8)])
    w = audio.word_times(x, "Soft rinse. No chemicals.")
    assert [d["w"] for d in w] == ["Soft", "rinse.", "No", "chemicals."]
    assert w[1]["t1"] <= .85 and w[2]["t0"] >= 1.15


@pytest.mark.skipif(not os.path.exists(TAKE), reason="no cached VO take")
def test_real_take_timing_and_mix_balance(tmp_path):
    timing, clips = audio.take_timing(TAKE, LINES)
    assert len(timing) == 4 and timing[2]["words"][0]["w"] == "Same"
    assert all(t["dur"] < 4 for t in timing)
    music, fx, vo = audio.mix_stems(META, str(tmp_path), clips)
    speaking = audio._envelope(vo) > .5
    assert audio._active_db(vo) - audio._db(music[speaking]) > 12      # voice clearly on top of the bed
    out = audio.build_mix(META, str(tmp_path / "m.wav"), str(tmp_path), clips)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    I = float([l.split()[1] for l in r.splitlines() if l.strip().startswith("I:")][-1])
    peak = float([l.split()[1] for l in r.splitlines() if l.strip().startswith("Peak:")][-1])
    assert abs(I + 14) < .6 and peak < -1.4


def test_reveal_foley_lands_on_its_wipe_and_stays_under_the_whooshes(tmp_path):
    """meta['sfx'] puts the squeegee / rinse sound exactly over the reveal; it is subtle (peak below the cut
    whoosh) and the squeegee stops crisply when the blade leaves the glass."""
    meta = {"duration": 6.0, "cuts": [1.0], "impacts": [], "vo": [],
            "sfx": [{"at": 2.0, "dur": 1.3, "kind": "squeegee"}, {"at": 4.0, "dur": 1.5, "kind": "rinse"}, {"at": 5, "kind": "nope"}]}
    _, fx, _ = audio.mix_stems(meta, str(tmp_path))
    SR = audio.SR
    seg = lambda a, b: np.abs(fx[int(a * SR):int(b * SR)])
    assert seg(2.2, 3.2).max() > 5 * seg(1.5, 1.9).max() + 1e-6        # nothing before, sound during
    assert seg(4.3, 5.2).max() > 0
    assert seg(2.0, 3.3).max() < seg(.6, 1.0).max()                    # whoosh stays the loudest fx
    s, SR = audio.squeegee(1.3), audio.SR
    tail, body = np.abs(s[-int(.01 * SR):]).max(), np.abs(s[int(.9 * SR):int(1.25 * SR)]).max()
    assert body > .2 and tail < body                                   # builds, then a crisp stop
