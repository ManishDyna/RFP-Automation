// sc-demo.jsx — real-screenshot "product demo" scenes: actual UI in the dark
// browser frame, a smooth cursor that clicks the real button, then the real
// result screen (cross-fade) or a zoom into the result area.

function DemoShot({ t0, dur, chapter, title, url, resultUrl, img, result,
                   hotspot, clickAt = 3.4, approach = { x: 950, y: 250 }, postFocus, toast,
                   inputs = [], panFrom, panTo }) {
  const time = useTime(); const lt = time - t0;
  const FR = { x: 96, y: 84, w: 1088, h: 556 }, TAB = 38;
  const CW = FR.w;

  const intro = Easing.easeOutCubic(clamp(lt / 0.42, 0, 1));
  const outro = 1 - Easing.easeInCubic(clamp((lt - (dur - 0.4)) / 0.4, 0, 1));
  const env = Math.min(intro, outro);

  const hasResult = !!result;
  const hasClick = !!hotspot;
  const resP = hasResult ? Easing.easeInOutCubic(clamp((lt - (clickAt + 0.5)) / 0.7, 0, 1)) : 0;

  // base image transform
  let baseScale = 1, ox = 50, oy = 0;
  if (!hasClick && (panFrom || panTo)) {           // pure view: slow Ken-Burns
    const p = Easing.easeInOutSine(clamp(lt / dur, 0, 1));
    baseScale = lerp((panFrom?.s ?? 1.05), (panTo?.s ?? 1.14), p);
    ox = lerp((panFrom?.fx ?? 0.5), (panTo?.fx ?? 0.5), p) * 100;
    oy = lerp((panFrom?.fy ?? 0.2), (panTo?.fy ?? 0.45), p) * 100;
  } else if (!hasResult && postFocus) {            // click → zoom into result area
    const zp = Easing.easeInOutSine(clamp((lt - (clickAt + 0.35)) / 1.3, 0, 1));
    baseScale = lerp(1, postFocus.s ?? 1.4, zp); ox = postFocus.fx * 100; oy = postFocus.fy * 100;
  }
  const rscale = hasResult ? lerp(1.0, 1.08, Easing.easeInOutSine(clamp((lt - (clickAt + 0.5)) / Math.max(0.1, dur - (clickAt + 0.5)), 0, 1))) : 1;

  const cursor = hasClick ? [
    { t: t0 + 0.8, x: approach.x, y: approach.y },
    ...inputs.map(i => ({ t: t0 + i.at, x: i.x, y: i.y, click: true })),
    { t: t0 + clickAt, x: hotspot.x, y: hotspot.y, click: true },
    { t: t0 + clickAt + 0.7, x: hotspot.x, y: hotspot.y },
  ] : null;
  const showCursor = hasClick && lt < clickAt + (hasResult ? 0.7 : 0.9);

  const imgCss = { position: 'absolute', inset: 0, width: '100%', height: '100%',
    objectFit: 'cover', objectPosition: 'top center', willChange: 'transform' };

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <DotGrid opacity={0.16} />
      {/* title card */}
      <div style={{ position: 'absolute', left: FR.x, top: 40, opacity: env, transform: `translateY(${(1 - intro) * 8}px)` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <span style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700, color: C.red, background: C.redSoft, borderRadius: 6, padding: '4px 8px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{chapter}</span>
          <span style={{ fontFamily: F.display, fontSize: 22, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>{title}</span>
          <span style={{ fontFamily: F.mono, fontSize: 11.5, color: C.invFaint }}>{(hasResult && resP > 0.5 && resultUrl) ? resultUrl : url}</span>
        </div>
      </div>

      {/* browser frame */}
      <div style={{ position: 'absolute', left: FR.x, top: FR.y, width: FR.w, height: FR.h, opacity: env,
        transform: `translateY(${(1 - intro) * 22}px) scale(${lerp(0.975, 1, intro)})`, transformOrigin: '50% 60%', borderRadius: 14, overflow: 'hidden',
        boxShadow: '0 40px 90px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.05)', background: C.card,
        display: 'flex', flexDirection: 'column' }}>
        <div style={{ height: TAB, background: '#EDEFF4', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 8, flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 7 }}>{['#FF5F57', '#FEBC2E', '#28C840'].map(c => <div key={c} style={{ width: 11, height: 11, borderRadius: 99, background: c }} />)}</div>
          <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 23, minWidth: 300, padding: '0 14px', background: '#fff', borderRadius: 7, border: `1px solid ${C.line}`, fontFamily: F.mono, fontSize: 11.5, color: C.mute }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M6 10V8a6 6 0 1112 0v2" stroke={C.green} strokeWidth="2"/><rect x="4" y="10" width="16" height="10" rx="2" fill={C.green} opacity="0.18"/><rect x="4" y="10" width="16" height="10" rx="2" stroke={C.green} strokeWidth="1.6"/></svg>
              {(hasResult && resP > 0.5 && resultUrl) ? resultUrl : url}
            </div>
          </div>
          <div style={{ width: 54 }} />
        </div>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: C.paper }}>
          <img src={SHOT + img} alt="" style={{ ...imgCss, transformOrigin: `${ox}% ${oy}%`, transform: `scale(${baseScale})`, opacity: hasResult ? 1 - resP : 1 }} />
          {hasResult && <img src={SHOT + result} alt="" style={{ ...imgCss, transformOrigin: '50% 12%', transform: `scale(${rscale})`, opacity: resP }} />}
          {/* input highlights — mark the fields being filled before the action */}
          {(!hasResult || resP < 0.2) && inputs.map((i, k) => {
            if (lt < i.at - 0.25) return null;
            const op = clamp((lt - (i.at - 0.25)) / 0.4, 0, 1);
            return (
              <div key={k} style={{ position: 'absolute', left: i.x - FR.x - i.w / 2, top: i.y - FR.y - TAB - i.h / 2,
                width: i.w, height: i.h, border: `2.5px solid ${C.amber}`, borderRadius: 9, opacity: op,
                boxShadow: `0 0 0 2px ${C.amberSoft}, 0 6px 20px rgba(238,154,24,0.25)`, transform: `scale(${lerp(1.04, 1, op)})` }}>
                {i.label && (
                  <div style={{ position: 'absolute', left: 0, top: -24, whiteSpace: 'nowrap', background: C.amber, color: '#1a1206',
                    fontFamily: F.ui, fontWeight: 800, fontSize: 11, padding: '3px 8px', borderRadius: 6 }}>{i.label}</div>
                )}
              </div>
            );
          })}
          {/* click ripple on the real screen */}
          {hasClick && lt > clickAt && lt < clickAt + 0.5 && (
            <div style={{ position: 'absolute', left: hotspot.x - FR.x, top: hotspot.y - FR.y - TAB, width: 46, height: 46, marginLeft: -23, marginTop: -23,
              borderRadius: 99, border: `2px solid ${C.red}`, opacity: 1 - seg(lt, clickAt, 0.5), transform: `scale(${0.4 + seg(lt, clickAt, 0.5) * 1.4})` }} />
          )}
          {/* result toast (for single-screen flows) */}
          {hasClick && !hasResult && toast && lt > clickAt + 0.4 && (
            <div style={{ position: 'absolute', right: 22, bottom: 22, maxWidth: 380, display: 'flex', alignItems: 'center', gap: 11,
              background: '#fff', border: `1px solid ${C.line}`, borderRadius: 12, padding: '13px 16px', boxShadow: '0 18px 44px rgba(0,0,0,0.2)',
              opacity: clamp((lt - (clickAt + 0.4)) / 0.4, 0, 1), transform: `translateY(${(1 - clamp((lt - (clickAt + 0.4)) / 0.4, 0, 1)) * 14}px)` }}>
              <span style={{ width: 30, height: 30, borderRadius: 99, background: C.green, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>✓</span>
              <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13.5, color: C.ink, lineHeight: 1.35 }}>{toast}</span>
            </div>
          )}
        </div>
      </div>
      {showCursor && <Cursor path={cursor} />}
      {window.__CALIB && <CalibGrid hotspot={hotspot} />}
    </div>
  );
}

function CalibGrid({ hotspot }) {
  const lines = [];
  for (let x = 0; x <= 1280; x += 160) lines.push(
    <div key={'vx'+x} style={{ position:'absolute', left:x, top:0, bottom:0, width:1.5, background:'rgba(0,150,255,0.5)' }} />,
    <div key={'vt'+x} style={{ position:'absolute', left:x+2, top:2, fontFamily:'monospace', fontSize:18, fontWeight:700, color:'#0af', background:'#fff' }}>{x}</div>,
    <div key={'vb'+x} style={{ position:'absolute', left:x+2, bottom:2, fontFamily:'monospace', fontSize:18, fontWeight:700, color:'#0af', background:'#fff' }}>{x}</div>);
  for (let y = 0; y <= 720; y += 80) lines.push(
    <div key={'hy'+y} style={{ position:'absolute', top:y, left:0, right:0, height:1.5, background:'rgba(0,150,255,0.5)' }} />,
    <div key={'ht'+y} style={{ position:'absolute', top:y+1, left:2, fontFamily:'monospace', fontSize:18, fontWeight:700, color:'#0af', background:'#fff' }}>{y}</div>,
    <div key={'hr'+y} style={{ position:'absolute', top:y+1, right:2, fontFamily:'monospace', fontSize:18, fontWeight:700, color:'#0af', background:'#fff' }}>{y}</div>);
  return <div style={{ position:'absolute', inset:0, zIndex:99 }}>
    {lines}
    {hotspot && <div style={{ position:'absolute', left:hotspot.x-12, top:hotspot.y-12, width:24, height:24, borderRadius:99, border:'3px solid #00ff66', background:'rgba(0,255,102,0.3)' }} />}
  </div>;
}

Object.assign(window, { DemoShot });
