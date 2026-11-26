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
    return .5 * y * np.sin(np.pi * t) ** 1.5


def thump():
    t = np.arange(int(.6 * SR)) / SR
    return .35 * np.sin(2 * np.pi * (45 + 40 * np.exp(-t * 20)) * t) * np.exp(-t * 6)


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


def build_mix(meta, out_wav, work):
    dur = meta["duration"]
    music = music_bed(dur)
    fx = np.zeros_like(music)
    for c in meta.get("cuts", []):
        if 0 < c < dur:
            add(fx, whoosh(), c - .32)
    for c in meta.get("impacts", []):
        if 0 < c < dur:
            add(fx, thump(), c)
    vo = np.zeros_like(music)
    for i, line in enumerate(meta.get("vo", [])):
        p = os.path.join(work, f"vo{i}.mp3")
        try:
            if tts(line["text"], p):
                add(vo, load_audio(p) * .9, line["at"])
        except Exception as e:  # never fail a render because of VO
            print("VO skipped:", e)
    # duck music under VO (smoothed envelope)
    env = np.abs(vo)
    k = int(.15 * SR)
    env = np.convolve(env, np.ones(k) / k, "same")
    duck = 1 - .65 * np.clip(env / (env.max() + 1e-9) * 4, 0, 1)
    mix = music * duck + fx * .8 + vo
    raw = os.path.join(work, "raw.wav")
    data = (np.clip(mix / (np.abs(mix).max() + 1e-9) * .7, -1, 1) * 32767).astype(np.int16)
    import wave
    with wave.open(raw, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(data.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
                    "aecho=0.8:0.6:40|70:0.12|0.08,loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", str(SR), "-ac", "2", "-t", f"{dur:.3f}", out_wav],
                   check=True)
    return out_wav
