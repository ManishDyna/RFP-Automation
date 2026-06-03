// sc-tour.jsx — Live product tour: real screenshots with Ken-Burns + callouts.
// Renders the actual portal screens inside a browser chrome. Step data carries
// focus point (Ken-Burns target), highlight rings, and per-step narration.

const SHOT = 'assets/shots/';

// Frame geometry on the 1280×720 stage
const FR = { x: 96, y: 96, w: 1088, h: 536 };
const TAB = 38;                       // browser tab-bar height
const CW = FR.w, CH = FR.h - TAB;     // content area (where the screenshot lives)

// ── One screenshot scene ─────────────────────────────────────────────────────
function ShotScene({ step, t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const p = clamp(lt / dur, 0, 1);

  // Ken-Burns: ease scale from→to, anchored at the focus point
  const from = step.from || 1.04, to = step.to || 1.14;
  const sc = lerp(from, to, Easing.easeInOutSine(p));
  const ox = (step.focus?.x ?? 0.5) * 100;
  const oy = (step.focus?.y ?? 0.45) * 100;

  // scene entry/exit envelope (the parent Movie already cross-fades scenes,
  // but a touch of local motion keeps it lively)
  const intro = Easing.easeOutCubic(clamp(lt / 0.5, 0, 1));
  const outro = 1 - Easing.easeInCubic(clamp((lt - (dur - 0.45)) / 0.45, 0, 1));
  const env = Math.min(intro, outro);

  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <DotGrid opacity={0.16} />
      {/* title / chapter card */}
      <div style={{ position: 'absolute', left: FR.x, top: 40, opacity: env, transform: `translateY(${(1 - intro) * 8}px)` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <span style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700, color: C.red, background: C.redSoft, borderRadius: 6, padding: '4px 8px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{step.chapter}</span>
          <span style={{ fontFamily: F.display, fontSize: 22, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>{step.title}</span>
          <span style={{ fontFamily: F.mono, fontSize: 11.5, color: C.invFaint }}>{step.url}</span>
        </div>
      </div>

      {/* browser frame */}
      <div style={{ position: 'absolute', left: FR.x, top: FR.y, width: FR.w, height: FR.h, opacity: env,
        transform: `translateY(${(1 - intro) * 14}px)`, borderRadius: 14, overflow: 'hidden',
        boxShadow: '0 40px 90px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.05)', background: C.card,
        display: 'flex', flexDirection: 'column' }}>
        {/* tab bar */}
        <div style={{ height: TAB, background: '#EDEFF4', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 8, flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 7 }}>{['#FF5F57', '#FEBC2E', '#28C840'].map(c => <div key={c} style={{ width: 11, height: 11, borderRadius: 99, background: c }} />)}</div>
          <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 23, minWidth: 300, padding: '0 14px', background: '#fff', borderRadius: 7, border: `1px solid ${C.line}`, fontFamily: F.mono, fontSize: 11.5, color: C.mute }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M6 10V8a6 6 0 1112 0v2" stroke={C.green} strokeWidth="2"/><rect x="4" y="10" width="16" height="10" rx="2" fill={C.green} opacity="0.18"/><rect x="4" y="10" width="16" height="10" rx="2" stroke={C.green} strokeWidth="1.6"/></svg>
              {step.url}
            </div>
          </div>
          <div style={{ width: 54 }} />
        </div>
        {/* screenshot + Ken-Burns */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: C.paper }}>
          <img src={SHOT + step.img} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
            objectFit: 'cover', objectPosition: 'top center', transformOrigin: `${ox}% ${oy}%`, transform: `scale(${sc})`, willChange: 'transform' }} />
          {/* rings overlay (same coordinate space as the content area) */}
          {(step.rings || []).map((r, i) => <Ring key={i} r={r} lt={lt} sc={sc} ox={ox} oy={oy} />)}
        </div>
      </div>
    </div>
  );
}

// Highlight ring + label, expressed in fractions of the content area, tracked
// through the Ken-Burns transform so it stays glued to the pixels it marks.
function Ring({ r, lt }) {
  if (lt < r.at - 0.3) return null;
  const op = Easing.easeOutCubic(clamp((lt - r.at) / 0.45, 0, 1));
  const x = r.x * CW, y = r.y * CH, w = r.w * CW, h = r.h * CH;
  const labelBelow = r.below;
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, opacity: op,
      border: `2.5px solid ${C.red}`, borderRadius: 10, boxShadow: `0 0 0 2px rgba(238,61,51,0.18), 0 8px 30px rgba(238,61,51,0.25)`,
      transform: `scale(${lerp(1.03, 1, op)})` }}>
      {r.label && (
        <div style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)',
          [labelBelow ? 'top' : 'bottom']: labelBelow ? 'calc(100% + 8px)' : 'calc(100% + 8px)',
          whiteSpace: 'nowrap', background: C.red, color: '#fff', fontFamily: F.ui, fontWeight: 700, fontSize: 12,
          padding: '4px 10px', borderRadius: 7, boxShadow: '0 6px 16px rgba(238,61,51,0.4)' }}>{r.label}</div>
      )}
    </div>
  );
}

// ── Tour intro / outro title cards ───────────────────────────────────────────
function TourIntro({ t0, dur }) {
  const time = useTime(); const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.26} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
        <Appear at={t0 + 0.3} dur={0.6}><Logo size={46} /></Appear>
        <Appear at={t0 + 0.7} dur={0.6} y={20}>
          <div style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 700, color: C.red, letterSpacing: '0.2em', textTransform: 'uppercase', textAlign: 'center' }}>Part Two</div>
        </Appear>
        <Appear at={t0 + 1.0} dur={0.7} y={24}>
          <div style={{ fontFamily: F.display, fontSize: 52, fontWeight: 700, color: C.inv, letterSpacing: '-0.03em', textAlign: 'center' }}>
            The Live Product Tour
          </div>
        </Appear>
        <Appear at={t0 + 1.5} dur={0.7} y={18}>
          <div style={{ fontFamily: F.ui, fontSize: 19, color: C.invMute, textAlign: 'center', maxWidth: 720, lineHeight: 1.5 }}>
            Every screen that follows is the real portal — sign-in to audit trail, exactly as your team uses it.
          </div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

function TourOutro({ t0, dur }) {
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.26} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 22 }}>
        <Appear at={t0 + 0.3} dur={0.7}><Logo size={56} /></Appear>
        <Appear at={t0 + 0.8} dur={0.7} y={22}>
          <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em', textAlign: 'center', maxWidth: 900, lineHeight: 1.25 }}>
            From RFP to quote — discovered, matched, routed, bid, submitted and audited in one governed portal.
          </div>
        </Appear>
        <Appear at={t0 + 1.6} dur={0.7} y={16}>
          <div style={{ fontFamily: F.ui, fontSize: 18, color: C.invMute, textAlign: 'center' }}>
            Built on the Microsoft 365 tenant you already own.
          </div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

Object.assign(window, { ShotScene, TourIntro, TourOutro, SHOT });
