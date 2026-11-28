// Who did the job, said early: most viewers never reach the end card, so the business name rides
// under the hook from ~0.5 s. Byline.mount(P) once (after the hook exists); Byline.seek(t, start, end).
window.Byline = (() => {
  let el;
  const mount = P => {
    el = document.createElement('div');
    el.className = 'byline'; el.id = 'byline';
    const logo = P.logoUrl ? `<img src="${M.esc(P.logoUrl)}">` : M.esc(P.initials || (P.business || '?')[0]);
    el.innerHTML = `<span class="bl-logo">${logo}</span><span class="bl-name">${M.esc(P.business || '')}</span>`;
    document.body.appendChild(el);
    if (!P.business) el.style.visibility = 'hidden';
  };
  // sits under the hook wherever relayout() put it (top or low zone)
  const place = () => {
    const h = document.getElementById('hook');
    el.style.top = (h.offsetTop + h.offsetHeight + 30) + 'px';
  };
  const seek = (t, start, end) => {
    const on = t >= start - .01 && t < end;
    el.style.display = on ? 'flex' : 'none';
    if (!on) return;
    place();
    const k = M.outExpo((t - start) / .5) * (1 - M.prog(t, end - .3, end));
    M.show(el, k, 18);
  };
  return { mount, seek };
})();
