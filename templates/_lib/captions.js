// Word-timed captions for VO lines that no on-screen text already carries.
// Timing comes from the VO audio itself (render/audio.py: take_timing -> PARAMS.voTiming).
// Captions.mount(); Captions.seek(t, P.voTiming, P.vo)  (line i is captioned when P.vo[i].caption)
window.Captions = (() => {
  let root, cache = new Map();
  const CHUNK = 18;                                  // max chars on screen: short chunks read at a glance
  const chunks = words => {
    const out = []; let cur = [];
    words.forEach((w, i) => {
      const len = cur.reduce((n, x) => n + x.w.length + 1, 0) + w.w.length;
      if (cur.length && len > CHUNK) { out.push(cur); cur = []; }
      cur.push({ ...w, i });
      if (/[.,!?;:]$/.test(w.w)) { out.push(cur); cur = []; }
    });
    if (cur.length) out.push(cur);
    return out;
  };
  const mount = () => {
    root = document.createElement('div');
    root.className = 'cap'; root.id = 'cap';
    document.body.appendChild(root);
  };
  const seek = (t, timing, lines) => {
    root.style.display = 'none';
    if (!timing || !lines) return;
    timing.forEach((L, li) => {
      if (!lines[li] || !lines[li].caption || !L.words.length) return;
      const rel = t - L.at;
      if (rel < -0.05 || rel > L.dur + 0.35) return;
      if (!cache.has(li)) cache.set(li, chunks(L.words));
      const cs = cache.get(li);
      let ci = cs.findIndex(c => rel < c[c.length - 1].t1 + 0.05);
      if (ci < 0) ci = cs.length - 1;
      const c = cs[ci];
      const fadeIn = M.clamp((rel - c[0].t0 + 0.05) / 0.1), fadeOut = 1 - M.clamp((rel - L.dur - 0.2) / 0.15);
      root.innerHTML = c.map(w => `<span class="w${rel >= w.t0 && rel < w.t1 + 0.08 ? ' on' : ''}">${M.esc(w.w.replace(/[.,;:]$/, ''))}</span>`).join(' ');
      root.style.display = 'block';
      root.style.opacity = Math.min(fadeIn, fadeOut);
      root.style.transform = `translateY(${(1 - M.outExpo(fadeIn)) * 18}px)`;
    });
  };
  return { mount, seek };
})();
