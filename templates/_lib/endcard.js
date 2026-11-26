// Shared end card. Call EndCard.mount(P) once, EndCard.seek(t, start) every frame.
window.EndCard = (() => {
  let els;
  const mount = P => {
    const d = document.createElement('div');
    d.className = 'layer end'; d.id = 'end';
    const logo = P.logoUrl ? `<img src="${M.esc(P.logoUrl)}">` : M.esc(P.initials || (P.business || '?')[0]);
    d.innerHTML = `<div class="logo">${logo}</div><div class="biz">${M.esc(P.business)}</div>
      <div class="area">${M.esc(P.area)}</div><div class="rule"></div>
      <div class="cta">${M.esc(P.cta || 'Free quote in 60 seconds')}</div>
      <div class="url">${M.esc(P.url)}<span class="arr">→</span></div>`;
    document.body.appendChild(d);
    els = ['logo', 'biz', 'area', 'rule', 'cta', 'url'].map(c => d.querySelector('.' + c));
  };
  const seek = (t, start) => {
    const e = t - start, on = e >= 0;
    const root = document.getElementById('end');
    root.style.display = on ? 'flex' : 'none';
    if (!on) return;
    const delays = [0.05, 0.15, 0.25, 0.35, 0.55, 0.7];
    els.forEach((el, i) => {
      const k = M.outExpo((e - delays[i]) / 0.6);
      if (i === 3) { el.style.opacity = k; el.style.transform = `scaleX(${k})`; }
      else if (i === 0) { el.style.opacity = k; el.style.transform = `scale(${0.85 + 0.15 * k})`; }
      else M.show(el, k, 36);
    });
  };
  return { mount, seek };
})();
