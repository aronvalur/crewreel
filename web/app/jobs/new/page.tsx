"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TEMPLATES, type Slot } from "@/lib/templates";

const mb = (n: number) => (n / 1024 / 1024).toFixed(n > 10 * 1024 * 1024 ? 0 : 1) + " MB";

function SlotInput({ slot, file, onPick }: { slot: Slot; file?: File; onPick: (f?: File) => void }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return setUrl(null);
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);
  const isVideo = file?.type.startsWith("video/") || /\.(mov|mp4|m4v|webm|mkv)$/i.test(file?.name || "");
  return (
    <label className={`drop${file ? " filled" : ""}`}>
      <input type="file" accept={slot.kind === "video" ? "video/*" : "video/*,image/*"}
        onChange={e => onPick(e.target.files?.[0])} />
      <div className="pv">
        {url ? (isVideo ? <video src={url} muted playsInline preload="metadata" /> : <img src={url} alt="" />) : "9:16"}
      </div>
      <div>
        <b>{slot.label}</b>
        <p className="muted small">{file ? `${file.name} · ${mb(file.size)}` : slot.hint}</p>
      </div>
      <span className="btn ghost sm">{file ? "Change" : "Choose"}</span>
    </label>
  );
}

export default function NewReel() {
  const router = useRouter();
  const [tplId, setTplId] = useState(TEMPLATES[0].id);
  const [files, setFiles] = useState<Record<string, File | undefined>>({});
  const [text, setText] = useState<Record<string, string>>({});
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const tpl = TEMPLATES.find(t => t.id === tplId)!;
  const missing = tpl.slots.filter(s => !s.optional && !files[s.name]);

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
        body: JSON.stringify({ draft: id, template: tpl.id, title, fields: text }),
      });
      const body = await r.json().catch(() => ({}));
      if (r.status !== 201) throw new Error(body.error || "Couldn't start the render. Try again.");
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
              <input type="radio" name="template" checked={t.id === tplId} onChange={() => setTplId(t.id)} />
              <b>{t.title}</b>
              <p className="muted small" style={{ marginTop: 4 }}>{t.length} · {t.blurb}</p>
            </label>
          ))}
        </div>
      </section>

      <section className="section">
        <h2>2. Footage</h2>
        <p className="muted small">Phone upright. Before and after from the same spot so we can line them up.</p>
        <div className="slots">
          {tpl.slots.map(s => (
            <SlotInput key={tpl.id + s.name} slot={s} file={files[s.name]}
              onPick={f => setFiles(prev => ({ ...prev, [s.name]: f }))} />
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
