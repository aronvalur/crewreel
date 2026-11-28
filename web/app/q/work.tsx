"use client";
// Recent work strip: posters (mid-reveal frames); tap one to watch the reel.
import { useState } from "react";

export default function Work({ items }: { items: { id: string; title: string }[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <div className="q-strip">
        {items.map(j => (
          <button key={j.id} type="button" className="q-shot" onClick={() => setOpen(j.id)} aria-label={`Watch: ${j.title}`}>
            <img src={`/api/files/${j.id}/poster.jpg`} alt="" loading="lazy" />
            <span className="q-play" aria-hidden="true" />
          </button>
        ))}
      </div>
      {open && (
        <div className="q-watch" role="dialog" aria-label="Reel" onClick={() => setOpen(null)}>
          <video src={`/api/files/${open}/reel.mp4`} poster={`/api/files/${open}/poster.jpg`} autoPlay controls playsInline
            onClick={e => e.stopPropagation()} />
          <button type="button" className="cam-x q-close" onClick={() => setOpen(null)} aria-label="Close">✕</button>
        </div>
      )}
    </>
  );
}
