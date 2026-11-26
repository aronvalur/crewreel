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
  return { clamp, outCubic, outExpo, inOutCubic, inOutSine, prog, lerp, $, esc, words, riseWords, show };
})();
