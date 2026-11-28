"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TEMPLATES, type Slot } from "@/lib/templates";
import { keepClip, keptClips, forgetClips } from "@/lib/keep";
import Camera from "./camera";

const mb = (n: number) => n < 100 * 1024 ? "<0.1 MB" : (n / 1024 / 1024).toFixed(n > 10 * 1024 * 1024 ? 0 : 1) + " MB";

function SlotInput({ slot, file, ghost, onPick }: { slot: Slot; file?: File; ghost?: File; onPick: (f?: File) => void }) {
  const [filming, setFilming] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return setUrl(null);
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  const isVideo = file?.type.startsWith("video/") || /\.(mov|mp4|m4v|webm|mkv)$/i.test(file?.name || "");
  // Same rules the renderer's footage check uses (render/ingest.py), said before the upload, not after.
  const [meta, setMeta] = useState<{ dur: number; w: number; h: number } | null>(null);
  useEffect(() => setMeta(null), [file]);
  const notes: string[] = [];
  if (meta && isVideo) {
    if (slot.min && meta.dur > 0 && meta.dur < slot.min * .8)
      notes.push(`${meta.dur.toFixed(1)} s: needs ~${slot.min} s, will play slow-mo`);
    if (meta.w > meta.h * 1.1) notes.push("Sideways: we'll crop it to vertical");
    if (Math.min(meta.w, meta.h) > 0 && Math.min(meta.w, meta.h) < 700) notes.push("Low resolution: will look soft");
  }
  return (
    <>
    {filming && <Camera slot={slot} ghost={ghost} onClose={() => setFilming(false)}
      onDone={f => { setFilming(false); onPick(f); }} />}
    <label className={`drop${file ? " filled" : ""}`}>
      <input type="file" accept={slot.kind === "video" ? "video/*" : "video/*,image/*"}
        onChange={e => onPick(e.target.files?.[0])} />
      <div className="pv">
        {url ? (isVideo ? <video src={url + "#t=0.5"} muted playsInline preload="metadata"
          onLoadedMetadata={e => { const v = e.currentTarget; setMeta({ dur: v.duration, w: v.videoWidth, h: v.videoHeight }); }} /> : <img src={url} alt="" />) : "9:16"}
      </div>
      <div>
        <b>{slot.label}</b>
        <p className="muted small">{file ? `${file.name} · ${mb(file.size)}` : slot.hint}</p>
        {notes.map(n => <p key={n} className="small warn">⚠ {n}</p>)}
      </div>
      <span className="drop-acts">
        <button type="button" className="btn sm" onClick={e => { e.preventDefault(); setFilming(true); }}>
          {file ? "Refilm" : "Film"}</button>
        <span className="btn ghost sm">{file ? "Change" : "Choose"}</span>
      </span>
    </label>
    </>
  );
}

export default function NewReel() {
  const router = useRouter();
  const [tplId, setTplId] = useState(TEMPLATES[0].id);
  const [files, setFiles] = useState<Record<string, File | undefined>>({});
  const [text, setText] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [feed, setFeed] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const tpl = TEMPLATES.find(t => t.id === tplId)!;
  const missing = tpl.slots.filter(s => !s.optional && !files[s.name]);
  // clips stay on the phone between visits (film the before on arrival, the after when done)
  useEffect(() => {
    let alive = true;
    keptClips(tplId, tpl.slots.map(s => s.name)).then(k => { if (alive && Object.keys(k).length) setFiles(k); });
    return () => { alive = false; };
  }, [tplId]);  // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (slot: string, f?: File) => { setFiles(prev => ({ ...prev, [slot]: f })); keepClip(tplId, slot, f); };

  // Clips stream one by one to disk (PUT), so big 4K phone files never sit in server memory.
  // XHR (not fetch) so the crew sees upload progress: site signal is often bad.
  function put(url: string, file: File, onProgress: (loaded: number) => void) {
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", url);
      xhr.upload.onprogress = ev => onProgress(ev.loaded);
      xhr.onload = () => {
        if (xhr.status < 300) return resolve();
        let msg = "Upload failed. Try again.";
        try { msg = JSON.parse(xhr.responseText).error || msg; } catch { /* keep default */ }
        reject(new Error(msg));
      };
      xhr.onerror = () => reject(new Error("Upload failed. Check your connection and try again."));
      xhr.send(file);
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (missing.length) return setError(`Still missing: ${missing.map(s => s.label).join(", ")}.`);
    setError("");
    setProgress(0);
    try {
      const d = await fetch("/api/drafts", { method: "POST" });
      if (!d.ok) throw new Error("Couldn't start the upload. Try again.");
      const { id } = await d.json();
      const todo = tpl.slots.filter(s => files[s.name]).map(s => ({ slot: s, file: files[s.name]! }));
      const total = todo.reduce((n, t) => n + t.file.size, 0) || 1;
      let done = 0;
      for (const t of todo) {
        await put(`/api/drafts/${id}/${t.slot.name}?name=${encodeURIComponent(t.file.name)}`, t.file,
          loaded => setProgress((done + loaded) / total));
        done += t.file.size;
      }
      const r = await fetch("/api/jobs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft: id, template: tpl.id, title, fields: text, feed }),
      });
      const body = await r.json().catch(() => ({}));
      if (r.status !== 201) throw new Error(body.error || "Couldn't start the render. Try again.");
      await forgetClips(tpl.id, tpl.slots.map(s => s.name));
      router.push(`/jobs/${id}`);
    } catch (err) {
      setProgress(null);
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} style={{ maxWidth: 720 }}>
      <h1>New reel</h1>
      <p className="muted" style={{ marginTop: 6 }}>Three steps. Takes about a minute once you have the clips.</p>

      <section className="section">
        <h2>1. Style</h2>
        <p className="muted small">Pick the reel that fits the job.</p>
        <div className="choices">
          {TEMPLATES.map(t => (
            <label key={t.id} className="choice">
              <input type="radio" name="template" checked={t.id === tplId} onChange={() => { setTplId(t.id); setFiles({}); }} />
              <b>{t.title}</b>
              <p className="muted small" style={{ marginTop: 4 }}>{t.length} · {t.blurb}</p>
            </label>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>2. Footage</h2>
        <p className="muted small">Phone upright. Before and after from the same spot so we can line them up. Film here and we&apos;ll
          guide you; clips stay on this phone until you send them, so you can film the after later.</p>
        <div className="slots">
          {tpl.slots.map(s => (
            <SlotInput key={tpl.id + s.name} slot={s} file={files[s.name]}
              ghost={s.name === "after" ? files.before : undefined} onPick={f => pick(s.name, f)} />
          ))}
        </div>
      </section>

      <section className="section">
        <h2>3. Words</h2>
        <p className="muted small">Optional. Leave blank to use the suggestions.</p>
        <div className="stack">
          <label className="field"><span>Job name</span>
            <input type="text" value={title} maxLength={60} placeholder="Driveway, Kópavogur"
              onChange={e => setTitle(e.target.value)} />
            <small>Only you see this.</small>
          </label>
          {tpl.fields.map(f => (
            <label key={tpl.id + f.name} className="field"><span>{f.label}</span>
              <textarea rows={2} maxLength={f.max} placeholder={f.placeholder} value={text[f.name] || ""}
                onChange={e => setText(prev => ({ ...prev, [f.name]: e.target.value }))} />
              {f.hint && <small>{f.hint}</small>}
            </label>
          ))}
        </div>
      </section>

      <section className="section stack">
        <label className="check">
          <input type="checkbox" checked={feed} onChange={e => setFeed(e.target.checked)} />
          <span><b>Also make a 4:5 feed version</b><small className="muted">For Facebook and Instagram feed posts. Adds about 2 minutes.</small></span>
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        {progress !== null ? (
          <div className="stack">
            <div className="bar"><i style={{ width: `${Math.round(progress * 100)}%` }} /></div>
            <p className="muted small">Uploading… {Math.round(progress * 100)}%. Keep this page open.</p>
          </div>
        ) : (
          <button className="btn" type="submit">Make my reel</button>
        )}
      </section>
    </form>
  );
}
