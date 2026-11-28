"""Reel audio: music bed + transition sounds + optional ElevenLabs voiceover, mixed to -14 LUFS.

The bed is synthesised (no licence issues) until we have a royalty-free library:
warm I-V-vi-IV pad with soft plucked arpeggio and a gentle pulse, 100 bpm.
Whooshes land on every cut in meta['cuts']; a soft low 'thump' marks meta['impacts'].
VO lines (meta['vo'] = [{at, text}]) are rendered with ElevenLabs when ELEVENLABS_API_KEY
is set; the bed ducks ~9 dB under the voice. Without a key the reel ships without VO.
"""
import json, os, subprocess, urllib.request
import numpy as np

SR = 48000
BPM = 100
rng = np.random.default_rng(3)


def _note(f, dur, amp, attack=.02, release=.3, harmonics=(1, .5, .25, .12)):
    t = np.arange(int(dur * SR)) / SR
    w = sum(a * np.sin(2 * np.pi * f * (k + 1) * t + k) for k, a in enumerate(harmonics))
    env = np.minimum(1, t / attack) * np.exp(-np.maximum(0, t - attack) / release)
    return amp * w * env


def _pad(f, dur, amp):
    t = np.arange(int(dur * SR)) / SR
    w = sum(np.sin(2 * np.pi * f * d * t) for d in (0.997, 1.0, 1.003)) / 3
    w += .3 * np.sin(2 * np.pi * f * 2 * t)
    env = np.minimum(1, t / .6) * np.minimum(1, (dur - t) / .6)
    return amp * w * env


def music_bed(duration):
    n = int(duration * SR) + SR
    out = np.zeros(n)
    beat = 60 / BPM
    # C major-ish in a low register: C G Am F
    chords = [(130.8, 164.8, 196.0), (98.0, 123.5, 146.8), (110.0, 130.8, 164.8), (87.3, 110.0, 130.8)]
    bar = 4 * beat
    k = 0
    pos = 0.0
    while pos < duration:
        ch = chords[k % 4]
        for f in ch:
            p = _pad(f, bar + .3, .05)
            add(out, p, pos)
        b = _note(ch[0] / 2, bar, .10, attack=.01, release=1.2, harmonics=(1, .2))
        add(out, b, pos)
        for j in range(8):  # eighth-note arpeggio, soft
            f = ch[j % 3] * (2 if j % 4 < 2 else 4)
            nt = _note(f, .5, .035 * (1 if j % 2 == 0 else .6), attack=.005, release=.18)
            add(out, nt, pos + j * beat / 2)
        for j in range(4):  # soft pulse (felt kick)
            t = np.arange(int(.25 * SR)) / SR
            kick = .12 * np.sin(2 * np.pi * (55 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 14)
            add(out, kick, pos + j * beat)
        pos += bar
        k += 1
    out = out[: int(duration * SR)]
    t = np.arange(len(out)) / SR
    out *= np.minimum(1, t / 1.0) * np.minimum(1, (duration - t) / 1.5)
    return out


def whoosh(dur=.55):
    n = int(dur * SR)
    x = rng.standard_normal(n)
    # sweep a one-pole lowpass cutoff up then down
    t = np.arange(n) / n
    cut = 300 + 6000 * np.sin(np.pi * t) ** 2
    y = np.zeros(n)
    acc = 0.0
    for i in range(n):
        a = 1 - np.exp(-2 * np.pi * cut[i] / SR)
        acc += a * (x[i] - acc)
        y[i] = acc
    y -= np.convolve(y, np.ones(64) / 64, "same")  # remove rumble
    y = _band(y, 120, 4500)                         # no fizz above ~5 kHz: air, not hiss
    return .5 * y * np.sin(np.pi * t) ** 1.5


def thump():
    t = np.arange(int(.6 * SR)) / SR
    return .35 * np.sin(2 * np.pi * (45 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 6)


def _band(x, lo, hi):
    """Band-limit noise with a soft-edged FFT mask (no scipy needed)."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + (lo / np.maximum(f, 1)) ** 4) / (1 + (f / hi) ** 4)
    return np.fft.irfft(X * m, len(x))


def squeegee(dur=1.3):
    """A squeegee pulled across glass: a bright wet swish that builds, a faint rubber squeak riding it,
    and a crisp stop where the blade leaves the glass."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    swish = _band(rng.standard_normal(n), 1800, 7000) * (k ** 1.4) * np.minimum(1, (dur - t) / .03)
    f = 950 + 380 * k + 25 * np.sin(2 * np.pi * 7 * t)                   # rubber chatter: slight vibrato
    squeak = np.sin(2 * np.pi * np.cumsum(f) / SR) * .22 * np.sin(np.pi * k) ** 2 * (.6 + .4 * np.sin(2 * np.pi * 13 * t))
    y = swish / (np.abs(swish).max() + 1e-9) + squeak
    return .5 * y / (np.abs(y).max() + 1e-9)


def rinse(dur=1.9):
    """Water sheeting down a roof: soft, low-passed hiss that swells and settles."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    k = t / dur
    x = _band(rng.standard_normal(n), 250, 3200)
    x *= 1 + .25 * np.sin(2 * np.pi * 3.1 * t) * np.sin(2 * np.pi * .7 * t)   # gentle surging
    env = np.sin(np.pi * np.minimum(1, k * 1.15)) ** .7 * np.minimum(1, (dur - t) / .25)
    y = x * env
    return .45 * y / (np.abs(y).max() + 1e-9)


SFX = {"squeegee": squeegee, "rinse": rinse}


def add(buf, clip, at):
    s = max(0, int(at * SR))
    e = min(len(buf), s + len(clip))
    if e > s:
        buf[s:e] += clip[: e - s]


def tts(text, path):
    """ElevenLabs TTS. Returns True if a file was written."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return False
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "")
    if not voice:
        return False
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=json.dumps({"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
                         "voice_settings": {"stability": .5, "similarity_boost": .75, "style": .2}}).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
        f.write(r.read())
    return True


def load_audio(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


# ---------- voiceover takes: one generation holding every line, split on its pauses ----------
# One TTS call for the whole script is cheaper (one request, consistent delivery) than a call per line.

def _rms_frames(x, hop=.01):
    n = int(hop * SR)
    m = len(x) // n
    return np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(1) + 1e-12), n


def split_take(samples, n_lines, min_gap=.18):
    """Split a VO take into n_lines segments at its n_lines-1 longest pauses.
    Returns [(start_s, end_s)] trimmed to speech."""
    rms, hop = _rms_frames(samples)
    db = 20 * np.log10(rms / (rms.max() + 1e-12))
    voiced = db > -38
    idx = np.where(voiced)[0]
    if not len(idx):
        return []
    first, last = idx[0], idx[-1]
    gaps, i = [], first
    while i <= last:                                    # runs of silence inside the speech
        if not voiced[i]:
            j = i
            while j <= last and not voiced[j]:
                j += 1
            if (j - i) * hop / SR >= min_gap:
                gaps.append((j - i, i, j))
            i = j
        else:
            i += 1
    cuts = sorted(sorted(gaps, reverse=True)[: n_lines - 1], key=lambda g: g[1])
    bounds, start = [], first
    for _, a, b in cuts:
        bounds.append((start, a)); start = b
    bounds.append((start, last + 1))
    return [(a * hop / SR, b * hop / SR) for a, b in bounds]


def _syllables(w):
    import re
    w = re.sub(r"[^a-z]", "", w.lower())
    n = len(re.findall(r"[aeiouy]+", w)) - (1 if w.endswith("e") and not w.endswith("le") and len(w) > 2 else 0)
    return max(1, n)


def word_times(samples, text, min_pause=.12):
    """Estimate per-word (start, end) seconds within one spoken line, from the audio itself:
    speech time is shared out by syllable count, and pauses (commas, full stops) are skipped
    over rather than smeared across words. Good to ~0.1 s, plenty for caption highlighting."""
    words = text.split()
    rms, hop = _rms_frames(samples)
    db = 20 * np.log10(rms / (rms.max() + 1e-12))
    voiced = db > -38
    # close tiny dropouts inside words
    k = int(min_pause * SR / hop)
    v = voiced.copy()
    i = 0
    while i < len(v):
        if not v[i]:
            j = i
            while j < len(v) and not v[j]:
                j += 1
            if j - i < k and i > 0 and j < len(v):
                v[i:j] = True
            i = j
        else:
            i += 1
    if not v.any() or not words:
        return []
    # voiced runs (separated by real pauses) and phrases (separated by punctuation)
    runs, i = [], 0
    while i < len(v):
        if v[i]:
            j = i
            while j < len(v) and v[j]:
                j += 1
            runs.append((i, j)); i = j
        else:
            i += 1
    phrases, cur = [], []
    for w in words:
        cur.append(w)
        if w[-1] in ",.;:!?":
            phrases.append(cur); cur = []
    if cur:
        phrases.append(cur)
    if len(phrases) != len(runs):                 # can't pair them up: one phrase over all speech
        phrases, runs = [words], [(runs[0][0], runs[-1][1])]
    out = []
    for ph, (ra, rb) in zip(phrases, runs):
        frames = np.arange(ra, rb)
        frames = frames[v[ra:rb]] if v[ra:rb].any() else frames
        syl = np.array([_syllables(w) for w in ph], float)
        edges = np.concatenate([[0], np.cumsum(syl) / syl.sum()]) * (len(frames) - 1)
        for w, a, b in zip(ph, edges[:-1], edges[1:]):
            fa = frames[min(len(frames) - 1, int(round(a)) + (1 if a > 0 else 0))]
            fb = frames[min(len(frames) - 1, int(round(b)))]
            out.append(dict(w=w, t0=round(float(fa * hop / SR), 3), t1=round(float((fb + 1) * hop / SR), 3)))
    return out


def take_timing(take_path, lines):
    """-> [{at, dur, words}] for each template VO line, plus the segment samples for the mix."""
    x = load_audio(take_path)
    segs = split_take(x, len(lines))
    if len(segs) != len(lines):
        raise ValueError(f"take has {len(segs)} spoken lines, template expects {len(lines)}")
    timing, clips = [], []
    for line, (a, b) in zip(lines, segs):
        clip = x[int(a * SR): int(b * SR)]
        clips.append(clip)
        timing.append(dict(at=line["at"], dur=round(float(b - a), 3), words=word_times(clip, line["text"])))
    return timing, clips


VO_DB = -18.0          # speech RMS before final loudness normalisation
BED_DB = -26.0         # music RMS when nobody is talking
DUCK_DB = -8.0         # extra music reduction under the voice (-> ~16 dB below VO)
FX_PEAK_DB = -14.0     # whoosh / thump peaks (momentary ~6 dB under the voice: felt, not heard)


def _db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


def _active_db(x):
    """RMS over the parts that actually carry sound (speech without its pauses)."""
    rms, hop = _rms_frames(x)
    on = rms > rms.max() * 10 ** (-35 / 20)
    return 20 * np.log10(np.sqrt(np.mean(rms[on] ** 2)) + 1e-12) if on.any() else -120.0


def _gain(x, from_db, to_db):
    return x * 10 ** ((to_db - from_db) / 20)


def _envelope(x, attack=.06, release=.35):
    """Smooth 0..1 'voice present' envelope with separate attack/release (no pumping)."""
    rms, hop = _rms_frames(np.abs(x), .01)
    on = (rms > rms.max() * 10 ** (-40 / 20)).astype(float) if rms.max() > 0 else rms * 0
    a, r = np.exp(-.01 / attack), np.exp(-.01 / release)
    e, out = 0.0, np.zeros_like(on)
    for i, v in enumerate(on):
        e = (a if v > e else r) * e + (1 - (a if v > e else r)) * v
        out[i] = e
    full = np.repeat(out, hop)
    return np.pad(full, (0, max(0, len(x) - len(full))), mode="edge")[: len(x)]


def _echo(x):
    """Tiny room on the music bed only. Never on the voice."""
    y = x.copy()
    for d, g in ((.040, .12), (.070, .08)):
        n = int(d * SR)
        y[n:] += g * x[:-n]
    return y


def mix_stems(meta, work, vo_clips=None):
    """Levelled stems (music, fx, vo) at SR, same length. Split out so tests can check balance."""
    dur = meta["duration"]
    music = music_bed(dur)
    fx = np.zeros_like(music)
    for c in meta.get("cuts", []):
        if 0 < c < dur:
            add(fx, whoosh(), c - .32)
    for c in meta.get("impacts", []):
        if 0 < c < dur:
            add(fx, thump(), c)
    # template-specific foley that matches the reveal (meta['sfx'] = [{at, dur, kind}]), kept under the
    # whooshes: it should be felt more than heard
    for e in meta.get("sfx", []):
        if e.get("kind") in SFX and 0 <= e["at"] < dur:
            add(fx, .55 * SFX[e["kind"]](max(.3, float(e.get("dur", 1.2)))), e["at"])
    vo = np.zeros_like(music)
    if vo_clips:                                   # pre-rendered take, already split per line
        for line, clip in zip(meta.get("vo", []), vo_clips):
            fade = np.minimum(1, np.minimum(np.arange(len(clip)), np.arange(len(clip))[::-1]) / (.012 * SR))
            add(vo, clip * fade, line["at"])
    else:
        for i, line in enumerate(meta.get("vo", [])):
            p = os.path.join(work, f"vo{i}.mp3")
            try:
                if tts(line["text"], p):
                    add(vo, load_audio(p), line["at"])
            except Exception as e:  # never fail a render because of VO
                print("VO skipped:", e)
    has_vo = np.abs(vo).max() > 1e-4
    if has_vo:
        vo = _gain(vo, _active_db(vo), VO_DB)
    music = _echo(_gain(music, _db(music), BED_DB if has_vo else BED_DB + 6))
    if has_vo:
        music = music * (1 - (1 - 10 ** (DUCK_DB / 20)) * _envelope(vo))
    if np.abs(fx).max() > 0:
        fx = _echo(fx * 10 ** (FX_PEAK_DB / 20) / np.abs(fx).max())
    return music, fx, vo


def _limit(x, ceiling=10 ** (-2.0 / 20), look=.005, release=.08):
    """Look-ahead peak limiter: gain never lets |x| exceed ceiling; smooth release, no clicks."""
    need = np.minimum(1.0, ceiling / (np.abs(x) + 1e-12))
    n = int(look * SR)
    # min over the look-ahead window so the gain is already down when the peak arrives
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(need, (0, n), constant_values=1.0)
    g = sliding_window_view(pad, n + 1).min(axis=1)
    r = np.exp(-1 / (release * SR))
    out = np.empty_like(g)
    cur = 1.0
    for i in range(len(g)):                   # instant attack, exponential release
        cur = g[i] if g[i] < cur else r * cur + (1 - r) * g[i]
        out[i] = cur
    return x * out


def _lufs(x):
    """Integrated loudness (LUFS) of a mono signal played on both channels, via ffmpeg ebur128."""
    import wave, tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav") as f:
        st = np.repeat((np.clip(x, -1, 1) * 32767).astype(np.int16)[:, None], 2, axis=1)
        with wave.open(f.name, "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f.name, "-af", "ebur128", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    vals = [l.split()[1] for l in r.splitlines() if l.strip().startswith("I:")]
    return float(vals[-1])


def normalise(x, target=-14.0, passes=6):
    """Gain to the loudness target, limit peaks to -2 dBFS (true peak stays under -1.5), re-measure, correct."""
    y = x
    gain = 0.0
    for _ in range(passes):
        y = _limit(x * 10 ** (gain / 20))
        err = target - _lufs(y)
        if abs(err) < .3:
            break
        gain += err
    return y


def build_mix(meta, out_wav, work, vo_clips=None):
    music, fx, vo = mix_stems(meta, work, vo_clips)
    y = normalise(music + fx + vo)[: int(meta["duration"] * SR)]
    import wave
    st = np.repeat((np.clip(y, -1, 1) * 32767).astype(np.int16)[:, None], 2, axis=1)
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
    return out_wav
