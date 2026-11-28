// Shared end card: a framed before|after proof shot, the business, and one clear call to action.
// EndCard.mount(P) once; every frame: EndCard.seek(t, start) for graphics and
// layers.push(...EndCard.layers(t, start)) for footage (background + the proof card's two halves).
// The CTA is readable from ~0.8 s in: viewers who reach the end card decide in the first second.
window.EndCard = (() => {
  // Card geometry (px, 1080x1920). Keeps clear of the top 300 px and bottom 520 px UI zones.
  const BOX = [96, 316, 888, 560], R = 44;
  let P, els, card, divider, chipB, chipA, DY = 0;
  const mount = P_ => {
    P = P_;
    const d = document.createElement('div');
    d.className = 'layer end'; d.id = 'end';
    const logo = P.logoUrl ? `<img src="${M.esc(P.logoUrl)}">` : M.esc(P.initials || (P.business || '?')[0]);
    const split = P.aligned !== false;
    d.innerHTML = `
      <div class="proof" style="left:${BOX[0]}px;top:${BOX[1]}px;width:${BOX[2]}px;height:${BOX[3]}px;border-radius:${R}px">
        ${split ? `<div class="pdiv"></div><div class="ec-chip b">Before</div>` : ''}<div class="ec-chip a">After</div>
      </div>
      <div class="id"><div class="logo">${logo}</div><div class="who"><div class="biz">${M.esc(P.business)}</div>
        <div class="area">${M.esc(P.area)}</div></div></div>
      <div class="cta"><span>${M.esc(P.cta || 'Get a free quote')}</span><span class="arr">→</span></div>
      <div class="url">${M.esc(P.url)}</div>`;
    document.body.appendChild(d);
    // 4:5 feed: the block (316..1340) re-centres in the crop band (285..1635)
    DY = P.frame === 'feed' ? Math.round((M.FEED_Y0 + M.FEED_Y1) / 2 - (BOX[1] + 1340) / 2) : 0;
    if (DY) d.style.transform = `translateY(${DY}px)`;
    card = d.querySelector('.proof'); divider = d.querySelector('.pdiv');
    chipB = d.querySelector('.ec-chip.b'); chipA = d.querySelector('.ec-chip.a');
    els = ['.id', '.cta', '.url'].map(c => d.querySelector(c));
  };
  // long business names shrink to fit one line (down to 44 px) instead of crowding the CTA.
  // Runs on the first visible frame, after web fonts have loaded.
  let fitted = false;
  const fit = () => {
    const biz = document.querySelector('#end .biz');
    let fs = 66;
    for (; fs > 50 && biz.scrollWidth > biz.clientWidth + 1; fs -= 2) biz.style.fontSize = fs + 'px';
    if (biz.scrollWidth > biz.clientWidth + 1) {        // still too long: two balanced lines
      biz.style.whiteSpace = 'normal'; biz.style.textWrap = 'balance';
      for (fs = 56; fs > 38 && (biz.scrollHeight > 2.1 * fs * 1.02 || biz.scrollWidth > biz.clientWidth + 1); fs -= 2)
        biz.style.fontSize = fs + 'px';
    }
    const cta = document.querySelector('#end .cta');
    for (let fs = 58; fs > 40 && cta.scrollWidth > cta.clientWidth - 40; fs -= 2) cta.style.fontSize = fs + 'px';
    fitted = true;
  };
  // card entrance (0..1) and where the before|after divider sits (0..1 across the card)
  const cardK = e => M.outExpo(e / .7);
  const divX = e => .5 + .38 * (1 - M.inOutCubic(M.prog(e, .35, 1.35)));
  const seek = (t, start) => {
    const e = t - start, on = e >= 0, root = document.getElementById('end');
    root.style.display = on ? 'flex' : 'none';
    if (!on) return;
    if (!fitted) fit();
    const k = cardK(e);
    card.style.opacity = k;
    card.style.transform = `translateY(${(1 - k) * 40}px) scale(${.96 + .04 * k})`;
    if (divider) {
      const x = divX(e);
      divider.style.left = (x * BOX[2]) + 'px';
      chipB.style.opacity = M.outExpo((e - .5) / .5);
    }
    chipA.style.opacity = M.outExpo((e - .95) / .45);   // after the divider has cleared it
    [.35, .6, .8].forEach((dl, i) => M.show(els[i], M.outExpo((e - dl) / .6), 34));
    // a single soft pulse on the CTA once everything has landed, to pull the eye there
    const p = Math.max(0, Math.sin(Math.PI * M.prog(e, 1.6, 2.2)));
    els[1].style.transform += ` scale(${1 + .035 * p})`;
  };
  // Footage under the card. Only runs once the end card is on; P.focus[0] frames the proof
  // on the spot where the clean-up shows most.
  const layers = (t, start) => {
    const e = Math.max(0, t - start), k = cardK(e);
    const f = M.focusAt(P, 0, { fx: .5, fy: .55 });
    const at = 1.2 + e * .3;          // tiny drift keeps the proof alive; stays early so short clips needn't slow down
    const [x, y0, w, h] = BOX, y = y0 + DY, dy = (1 - k) * 40, s = .96 + .04 * k;
    const box = [x + w * (1 - s) / 2, y + dy + h * (1 - s) / 2, w * s, h * s];
    const L = [{ src: 'after', t: at, zoom: 1.12, blur: 40, dim: .62 },
               { color: '#000000', alpha: .45 * k, box: [box[0], box[1] + 24, box[2], box[3]], radius: R, boxFeather: 60 }];
    const inCard = { t: at, box, radius: R, zoom: 1.15, fx: f.fx, fy: f.fy, alpha: k, feather: 1.5 };
    if (P.aligned !== false) {
      const cx = (box[0] + divX(e) * box[2]) / 1080;
      L.push({ src: 'before', ...inCard });
      L.push({ src: 'after', ...inCard, mask: [cx, 1] });
    } else L.push({ src: 'after', ...inCard });
    return L;
  };
  return { mount, seek, layers, BOX };
})();
