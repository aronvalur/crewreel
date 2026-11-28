"use client";
// Guided camera: films one slot in the browser so the clip comes out the way the templates need it.
// - upright check (the reel is 9:16), a level line from the phone's tilt sensor, a "hold steady" nudge
// - a timer that turns green once the clip is long enough for its slot (no slow-mo needed)
// - for the AFTER shot: the BEFORE frame as a ghost, so both are filmed from the same spot and the
//   split reveal lines up (render/align.py has far less to fix)
import { useEffect, useRef, useState } from "react";
import type { Slot } from "@/lib/templates";

type Props = { slot: Slot; ghost?: File; onDone: (f: File) => void; onClose: () => void };

const MIME = ["video/mp4;codecs=avc1", "video/mp4", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
const pickMime = () => (typeof MediaRecorder === "undefined" ? "" : MIME.find(m => MediaRecorder.isTypeSupported(m)) || "");

// One still from the before clip (or the photo itself) for the ghost overlay.
async function stillOf(file: File): Promise<string | null> {
  const url = URL.createObjectURL(file);
  if (file.type.startsWith("image/")) return url;
  try {
    const v = document.createElement("video");
    v.muted = true; v.playsInline = true; v.src = url;
    await new Promise((ok, bad) => { v.onloadeddata = ok; v.onerror = bad; });
    v.currentTime = Math.min(1.5, (v.duration || 2) / 2);
    await new Promise(ok => { v.onseeked = ok; });
    const c = document.createElement("canvas");
    c.width = v.videoWidth; c.height = v.videoHeight;
    c.getContext("2d")!.drawImage(v, 0, 0);
    return c.toDataURL("image/jpeg", .8);
  } catch { return null; } finally { URL.revokeObjectURL(url); }
}

export default function Camera({ slot, ghost, onDone, onClose }: Props) {
  const live = useRef<HTMLVideoElement>(null);
  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const [error, setError] = useState("");
  const [ghostUrl, setGhostUrl] = useState<string | null>(null);
  const [ghostOn, setGhostOn] = useState(true);
  const [sideways, setSideways] = useState(false);
  const [roll, setRoll] = useState<number | null>(null);
  const [shaky, setShaky] = useState(false);
  const [t0, setT0] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const [take, setTake] = useState<File | null>(null);
  const [takeUrl, setTakeUrl] = useState<string | null>(null);
  // long enough that the template never has to slow the clip down, plus a little to trim
  const target = Math.max(4, Math.ceil((slot.min || 3) + 1.5));

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({
          audio: false,           // the reel gets voiceover and music; site noise isn't used
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1080 }, height: { ideal: 1920 }, frameRate: { ideal: 30 } },
        });
        if (!alive) return s.getTracks().forEach(t => t.stop());
        stream.current = s;
        if (live.current) { live.current.srcObject = s; await live.current.play().catch(() => {}); }
      } catch {
        setError("Can't open the camera. Allow camera access for this site, or choose a clip from your phone instead.");
      }
    })();
    return () => { alive = false; stream.current?.getTracks().forEach(t => t.stop()); };
  }, []);

  useEffect(() => { if (ghost) stillOf(ghost).then(setGhostUrl); }, [ghost]);

  // tilt + shake from the phone's sensors (absent on laptops: the level simply doesn't show)
  useEffect(() => {
    const o = (e: DeviceOrientationEvent) => { if (e.gamma !== null) setRoll(e.gamma); };
    const m = (e: DeviceMotionEvent) => {
      const r = e.rotationRate;
      if (r) setShaky(Math.hypot(r.alpha || 0, r.beta || 0, r.gamma || 0) > 30);
    };
    window.addEventListener("deviceorientation", o);
    window.addEventListener("devicemotion", m);
    return () => { window.removeEventListener("deviceorientation", o); window.removeEventListener("devicemotion", m); };
  }, []);

  // ticking clock while recording; upright check from the camera itself
  useEffect(() => {
    const id = setInterval(() => {
      setNow(performance.now());
      const v = live.current;
      if (v && v.videoWidth) setSideways(v.videoWidth > v.videoHeight * 1.1);
    }, 100);
    return () => clearInterval(id);
  }, []);

  const secs = t0 === null ? 0 : (now - t0) / 1000;
  useEffect(() => { if (t0 !== null && secs >= 15) stop(); });   // hard stop: nobody needs more than 15 s

  async function start() {
    const D = DeviceOrientationEvent as unknown as { requestPermission?: () => Promise<string> };
    D.requestPermission?.().catch(() => {});                       // iOS asks once, on a tap
    if (!stream.current) return;
    const mime = pickMime();
    let r: MediaRecorder;
    try { r = new MediaRecorder(stream.current, { ...(mime ? { mimeType: mime } : {}), videoBitsPerSecond: 12_000_000 }); }
    catch { return setError("This browser can't record video. Choose a clip from your phone instead."); }
    const parts: Blob[] = [];
    r.ondataavailable = e => { if (e.data.size) parts.push(e.data); };
    r.onstop = () => {
      const type = r.mimeType || mime || "video/webm";
      const ext = type.includes("mp4") ? "mp4" : "webm";
      const f = new File(parts, `${slot.name}-${Date.now()}.${ext}`, { type: type.split(";")[0] });
      setTake(f); setTakeUrl(URL.createObjectURL(f));
    };
    r.start(500);
    rec.current = r;
    setT0(performance.now());
  }

  function stop() {
    if (rec.current && rec.current.state !== "inactive") rec.current.stop();
    rec.current = null;
    setT0(null);
  }

  function retake() {
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    setTake(null); setTakeUrl(null);
  }

  const recording = t0 !== null;
  const enough = secs >= target;
  const level = roll !== null && Math.abs(roll) < 2.5;

  return (
    <div className="cam" role="dialog" aria-label={`Film: ${slot.label}`}>
      {takeUrl ? (
        <video className="cam-view" src={takeUrl} autoPlay loop muted playsInline />
      ) : (
        <video ref={live} className="cam-view" muted playsInline />
      )}
      {!takeUrl && ghostUrl && ghostOn && <img className="cam-ghost" src={ghostUrl} alt="" />}
      {!takeUrl && <div className="cam-grid" aria-hidden="true" />}
      {!takeUrl && roll !== null && (
        <div className={`cam-level${level ? " ok" : ""}`} style={{ transform: `rotate(${-roll}deg)` }} aria-hidden="true" />
      )}

      <div className="cam-top">
        <div>
          <b>{slot.label}</b>
          <p>{takeUrl ? "Check it, then use it or film again." : slot.hint}</p>
        </div>
        <button type="button" className="cam-x" onClick={onClose} aria-label="Close camera">✕</button>
      </div>

      {!takeUrl && (sideways || shaky || (ghostUrl && ghostOn && !recording)) && (
        <p className="cam-tip">
          {sideways ? "Turn the phone upright" : shaky ? "Hold steady" : "Line up with the before shot"}
        </p>
      )}
      {error && <p className="cam-tip bad">{error}</p>}

      <div className="cam-bottom">
        {takeUrl ? (
          <>
            <button type="button" className="btn ghost cam-alt" onClick={retake}>Film again</button>
            <button type="button" className="btn cam-use" onClick={() => take && onDone(take)}>Use this clip</button>
          </>
        ) : (
          <>
            {ghostUrl ? (
              <button type="button" className="btn ghost cam-alt" onClick={() => setGhostOn(g => !g)}>
                {ghostOn ? "Hide before" : "Show before"}
              </button>
            ) : <span className="cam-alt" />}
            <button type="button" className={`cam-rec${recording ? " on" : ""}`} disabled={!!error}
              onClick={recording ? stop : start} aria-label={recording ? "Stop" : "Record"}>
              <svg viewBox="0 0 88 88" aria-hidden="true">
                <circle cx="44" cy="44" r="40" className="trk" />
                {recording && <circle cx="44" cy="44" r="40" className={`arc${enough ? " ok" : ""}`}
                  style={{ strokeDashoffset: 251.3 * (1 - Math.min(1, secs / target)) }} />}
              </svg>
              <i />
            </button>
            <span className={`cam-time${enough ? " ok" : ""}`}>
              {recording ? `${secs.toFixed(1)} s${enough ? " · good" : ` / ${target} s`}` : `${target} s`}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
