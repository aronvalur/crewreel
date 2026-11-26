// Shared deterministic motion helpers for Crewreel templates.
// Templates must be pure functions of t: no timers, no CSS transitions/animations.
window.M = (() => {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const outCubic = x => 1 - Math.pow(1 - clamp(x), 3);
  const outExpo = x => (x = clamp(x), x === 1 ? 1 : 1 - Math.pow(2, -10 * x));
  const inOutCubic = x => (x = clamp(x), x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
  const inOutSine = x => -(Math.cos(Math.PI * clamp(x)) - 1) / 2;
  const prog = (t, a, b) => clamp((t - a) / (b - a));
  const lerp = (a, b, k) => a + (b - a) * k;
  const $ = id => document.getElementById(id);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // Split text into word spans (\n = line break). *word* = accent word.
  const words = (el, text) => {
    el.innerHTML = String(text).split('\n').map(l => l.split(' ').map(w => {
      const acc = /^\*.*\*$/.test(w);
      return `<span class="w${acc ? ' acc' : ''}">${esc(acc ? w.slice(1, -1) : w)}</span>`;
    }).join(' ')).join('<br>');
    return [...el.querySelectorAll('.w')];
  };
  // Word-by-word rise-in with stagger; returns nothing, mutates styles.
  const riseWords = (ws, t, start, { stagger = .07, dur = .5, dist = 46, out = Infinity, outDur = .3 } = {}) => {
    const o = 1 - prog(t, out - outDur, out);
    ws.forEach((w, i) => {
      const k = outExpo((t - start - i * stagger) / dur);
      w.style.opacity = k * o;
      w.style.transform = `translateY(${(1 - k) * dist}px)`;
      w.style.filter = k < 1 ? `blur(${(1 - k) * 6}px)` : 'none';
    });
  };
  const show = (el, k, dy = 30) => { el.style.opacity = k; el.style.transform = `translateY(${(1 - k) * dy}px)`; };
  // Pick the text zone with the least on-screen action. profiles: per-clip activity
  // profiles from ingest (BINS floats, top->bottom); zones: [[y0, y1], ...] in px.
  // Zone 0 is the designed default; we only move if another zone is clearly quieter.
  const quietZone = (profiles, zones, bias = .8) => {
    const ps = profiles.filter(Boolean);
    if (!ps.length) return 0;
    // Motion alone misses the hero: the nozzle/wand is held steady relative to the camera.
    // Operators frame the subject near the centre, so blend in a centre prior (y~0.55).
    const n = ps[0].length, bh = 1920 / n;
    const prior = Array.from({ length: n }, (_, i) => Math.exp(-.5 * (((i + .5) / n - .55) / .17) ** 2));
    const ps_ = prior.reduce((a, b) => a + b, 0);
    const energy = ([y0, y1]) => ps.reduce((s, p) => {
      let e = 0;
      for (let i = 0; i < n; i++)
        e += (.35 * p[i] + .65 * prior[i] / ps_) * clamp((Math.min(y1, (i + 1) * bh) - Math.max(y0, i * bh)) / bh);
      return s + e;
    }, 0);
    const es = zones.map(energy);
    let best = 0;
    es.forEach((e, i) => { if (e < es[best] * bias && e < es[best] - .04) best = i; });
    return best;
  };
  // Seconds a viewer needs to read a line: 0.9 s + 0.28 s per word, at least 2.2 s.
  const readTime = text => Math.max(2.2, .9 + .28 * String(text).trim().split(/\s+/).length);
  const activity = (P, names) => names.map(n => (P.activity || {})[n] && P.activity[n].profile);
  return { quietZone, activity, readTime, clamp, outCubic, outExpo, inOutCubic, inOutSine, prog, lerp, $, esc, words, riseWords, show };
})();
