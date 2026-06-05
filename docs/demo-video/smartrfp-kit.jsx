// smartrfp-kit.jsx — shared design tokens, animation helpers, frames & video chrome
// Loaded after animations.jsx. Exports everything to window.

// ── Design tokens ────────────────────────────────────────────────────────────
const C = {
  // video stage / dark surfaces
  bg:        '#0A0D13',
  bgGrad:    'radial-gradient(120% 90% at 50% -10%, #141A24 0%, #0A0D13 60%)',
  panel:     '#10151E',
  panel2:    '#161D28',
  hair:      'rgba(255,255,255,0.08)',
  hair2:     'rgba(255,255,255,0.14)',
  inv:       '#EAEFF7',
  invMute:   'rgba(234,239,247,0.58)',
  invFaint:  'rgba(234,239,247,0.30)',
  // product UI (light)
  paper:     '#F4F6FA',
  card:      '#FFFFFF',
  line:      '#E7EAF1',
  line2:     '#EEF1F6',
  ink:       '#141A23',
  text:      '#1E2733',
  mute:      '#6B7686',
  faint:     '#9AA4B2',
  // brand + signal
  red:       '#EE3D33',
  redDk:     '#C92B22',
  redSoft:   'rgba(238,61,51,0.12)',
  green:     '#12A66B',
  greenSoft: 'rgba(18,166,107,0.13)',
  amber:     '#EE9A18',
  amberSoft: 'rgba(238,154,24,0.15)',
  blue:      '#2C7BF2',
  blueSoft:  'rgba(44,123,242,0.13)',
  violet:    '#7A5CFF',
  violetSoft:'rgba(122,92,255,0.14)',
};
const F = {
  display: "'Space Grotesk', system-ui, sans-serif",
  ui:      "'Manrope', system-ui, sans-serif",
  mono:    "'JetBrains Mono', ui-monospace, monospace",
};

// ── Tiny anim helpers (absolute Stage time) ─────────────────────────────────
const lerp = (a, b, t) => a + (b - a) * t;
// progress 0..1 of a clip [start, start+dur]
const seg = (time, start, dur) => clamp((time - start) / dur, 0, 1);

// Fade/slide-in wrapper driven by absolute Stage time. Stays mounted (parent
// SceneWrap gates the window). Optional exit window.
function Appear({ at = 0, dur = 0.55, y = 18, x = 0, sc = 0, blur = 0,
                  ease = Easing.easeOutCubic, exitAt = null, exitDur = 0.4,
                  style = {}, className, children }) {
  const time = useTime();
  const p = ease(seg(time, at, dur));
  let op = p;
  let ty = (1 - p) * y, tx = (1 - p) * x;
  let s = sc ? lerp(1 - sc, 1, p) : 1;
  let bl = blur ? lerp(blur, 0, p) : 0;
  if (exitAt != null) {
    const e = Easing.easeInCubic(seg(time, exitAt, exitDur));
    op *= (1 - e); ty -= e * 12;
  }
  return (
    <div className={className} style={{
      opacity: op,
      transform: `translate(${tx}px, ${ty}px)` + (s !== 1 ? ` scale(${s})` : ''),
      filter: bl ? `blur(${bl}px)` : undefined,
      willChange: 'transform, opacity',
      ...style,
    }}>{children}</div>
  );
}

// Animated integer/decimal counter
function Count({ to, from = 0, at = 0, dur = 1.1, decimals = 0, prefix = '', suffix = '',
                ease = Easing.easeOutCubic, style }) {
  const time = useTime();
  const p = ease(seg(time, at, dur));
  const v = lerp(from, to, p);
  const txt = decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString();
  return <span style={style}>{prefix}{txt}{suffix}</span>;
}

// Width-growing bar (for progress / match meters)
function GrowBar({ to = 100, at = 0, dur = 0.9, h = 8, color = C.green, track = 'rgba(255,255,255,0.10)',
                   radius = 99, ease = Easing.easeOutCubic, style }) {
  const time = useTime();
  const w = lerp(0, to, ease(seg(time, at, dur)));
  return (
    <div style={{ height: h, background: track, borderRadius: radius, overflow: 'hidden', ...style }}>
      <div style={{ width: `${w}%`, height: '100%', background: color, borderRadius: radius }} />
    </div>
  );
}

// ── Scene gate w/ fade envelope ─────────────────────────────────────────────
// Each scene wraps its content. Renders only inside [t0-fade, t0+dur+fade].
function SceneWrap({ t0, dur, bg = C.bg, fade = 0.5, style = {}, children }) {
  const time = useTime();
  const lt = time - t0;
  if (lt < -fade || lt > dur + fade) return null;
  let op = 1;
  if (lt < fade) op = clamp(lt / fade, 0, 1);
  else if (lt > dur - fade) op = clamp((dur - lt) / fade, 0, 1);
  return (
    <div style={{
      position: 'absolute', inset: 0, opacity: op,
      background: bg, fontFamily: F.ui, color: C.inv, ...style,
    }}>{children}</div>
  );
}

// ── Brand logo ───────────────────────────────────────────────────────────────
function Logo({ size = 32, light = false, withText = true, gap = 11 }) {
  const txt = light ? '#0E141C' : C.inv;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap }}>
      <div style={{
        width: size, height: size, borderRadius: size * 0.28,
        background: `linear-gradient(150deg, ${C.red} 0%, ${C.redDk} 100%)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 6px 18px ${C.redSoft}, inset 0 1px 0 rgba(255,255,255,0.25)`,
        flexShrink: 0,
      }}>
        <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
          <path d="M5 16.5 L12 6 L19 16.5" stroke="#fff" strokeWidth="2.4"
                strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="12" cy="19" r="1.7" fill="#fff" />
        </svg>
      </div>
      {withText && (
        <div style={{ fontFamily: F.display, fontWeight: 700, fontSize: size * 0.62,
                      letterSpacing: '-0.02em', color: txt, lineHeight: 1 }}>
          Smart<span style={{ color: C.red }}>RFP</span>
        </div>
      )}
    </div>
  );
}

// ── Lower-third narration captions (doubles as voiceover script) ────────────
function CaptionBar({ script }) {
  const time = useTime();
  let cur = null, nextT = Infinity;
  for (let i = 0; i < script.length; i++) {
    if (script[i].t <= time) { cur = script[i]; nextT = script[i + 1] ? script[i + 1].t : Infinity; }
  }
  if (!cur) return null;
  const inP = clamp((time - cur.t) / 0.4, 0, 1);
  const outP = nextT - time < 0.35 ? clamp((nextT - time) / 0.35, 0, 1) : 1;
  const op = Math.min(inP, outP);
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 46,
      display: 'flex', justifyContent: 'center', pointerEvents: 'none', zIndex: 60,
    }}>
      <div style={{
        opacity: op, transform: `translateY(${(1 - op) * 8}px)`,
        maxWidth: 1180, padding: '13px 26px',
        background: 'rgba(8,11,16,0.74)', backdropFilter: 'blur(10px)',
        border: `1px solid ${C.hair}`, borderRadius: 13,
        boxShadow: '0 12px 40px rgba(0,0,0,0.45)',
        fontFamily: F.ui, fontWeight: 500, fontSize: 23, lineHeight: 1.4,
        color: '#F3F6FB', textAlign: 'center', letterSpacing: '-0.01em',
      }}>{cur.text}</div>
    </div>
  );
}

// ── Top chrome: chapter chip + progress dots + brand watermark ──────────────
function VideoChrome({ chapters, total }) {
  const time = useTime();
  let idx = 0, acc = 0;
  for (let i = 0; i < chapters.length; i++) {
    if (time >= acc) idx = i;
    acc += chapters[i].dur;
  }
  const ch = chapters[idx];
  return (
    <>
      {/* chapter chip top-left */}
      <div style={{
        position: 'absolute', top: 26, left: 30, zIndex: 60,
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 9,
          padding: '7px 13px 7px 9px', borderRadius: 9,
          background: 'rgba(8,11,16,0.6)', border: `1px solid ${C.hair}`,
          backdropFilter: 'blur(8px)',
        }}>
          <span style={{
            fontFamily: F.mono, fontSize: 11, fontWeight: 600, color: C.red,
            background: C.redSoft, borderRadius: 5, padding: '3px 6px',
          }}>{String(idx + 1).padStart(2, '0')}</span>
          <span style={{ fontFamily: F.ui, fontSize: 13.5, fontWeight: 600,
                         color: C.inv, letterSpacing: '-0.01em' }}>{ch.label}</span>
        </div>
      </div>
      {/* brand watermark top-right */}
      <div style={{ position: 'absolute', top: 24, right: 30, zIndex: 60, opacity: 0.92 }}>
        <Logo size={26} />
      </div>
    </>
  );
}

// ── Animated cursor ─────────────────────────────────────────────────────────
// path: [{t, x, y, click?}] absolute times; interpolates position, pulses on click
function Cursor({ path }) {
  const time = useTime();
  if (!path || !path.length) return null;
  if (time < path[0].t - 0.2) return null;
  let a = path[0], b = path[path.length - 1];
  for (let i = 0; i < path.length - 1; i++) {
    if (time >= path[i].t && time <= path[i + 1].t) { a = path[i]; b = path[i + 1]; break; }
    if (time > path[i + 1].t) { a = path[i + 1]; b = path[i + 1]; }
  }
  const span = b.t - a.t;
  const p = span > 0 ? Easing.easeInOutCubic(clamp((time - a.t) / span, 0, 1)) : 1;
  const x = lerp(a.x, b.x, p), y = lerp(a.y, b.y, p);
  // click pulse
  let ring = null;
  for (const pt of path) {
    if (pt.click && time >= pt.t && time < pt.t + 0.5) {
      const cp = seg(time, pt.t, 0.5);
      ring = { o: 1 - cp, s: 0.4 + cp * 1.3, x: pt.x, y: pt.y };
    }
  }
  return (
    <div style={{ position: 'absolute', inset: 0, zIndex: 55, pointerEvents: 'none' }}>
      {ring && (
        <div style={{ position: 'absolute', left: ring.x, top: ring.y,
          width: 40, height: 40, marginLeft: -20, marginTop: -20, borderRadius: 99,
          border: `2px solid ${C.red}`, opacity: ring.o, transform: `scale(${ring.s})` }} />
      )}
      <svg width="26" height="26" viewBox="0 0 24 24" style={{
        position: 'absolute', left: x, top: y,
        filter: 'drop-shadow(0 3px 5px rgba(0,0,0,0.4))' }}>
        <path d="M5 3l14 7-6 1.6L9.6 18 5 3z" fill="#fff" stroke="#141A23" strokeWidth="1.1" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ── Browser window frame (for product screens) ──────────────────────────────
function BrowserFrame({ x = 0, y = 0, w = 1180, h = 600, url = 'app.smartrfp.io', children, style }) {
  return (
    <div style={{
      position: 'absolute', left: x, top: y, width: w, height: h,
      background: C.card, borderRadius: 14, overflow: 'hidden',
      boxShadow: '0 40px 90px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
      display: 'flex', flexDirection: 'column', ...style,
    }}>
      <div style={{ height: 38, background: '#EDEFF4', borderBottom: `1px solid ${C.line}`,
        display: 'flex', alignItems: 'center', padding: '0 14px', gap: 8, flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 7 }}>
          {['#FF5F57', '#FEBC2E', '#28C840'].map(c => (
            <div key={c} style={{ width: 11, height: 11, borderRadius: 99, background: c }} />
          ))}
        </div>
        <div style={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 23, minWidth: 320,
            padding: '0 14px', background: '#fff', borderRadius: 7, border: `1px solid ${C.line}`,
            fontFamily: F.mono, fontSize: 11.5, color: C.mute }}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M6 10V8a6 6 0 1112 0v2" stroke={C.green} strokeWidth="2"/><rect x="4" y="10" width="16" height="10" rx="2" fill={C.green} opacity="0.18"/><rect x="4" y="10" width="16" height="10" rx="2" stroke={C.green} strokeWidth="1.6"/></svg>
            {url}
          </div>
        </div>
        <div style={{ width: 54 }} />
      </div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: C.paper }}>{children}</div>
    </div>
  );
}

// ── Product app shell: sidebar + topbar ─────────────────────────────────────
const NAV_MENU = [
  ['Dashboard', 'grid'],
  ['RFP Insights', 'search'],
  ['Material Insights', 'box'],
  ['Activity Logs', 'list'],
  ['Open RFP', 'mail'],
];
const NAV_ADMIN = [
  ['Users', 'users'],
  ['Roles', 'shield'],
  ['Audit Logs', 'list'],
  ['Analytics', 'chart'],
  ['SAP Logs', 'key'],
  ['Master Data', 'db'],
  ['System Settings', 'gear'],
];
function NavIcon({ k, color }) {
  const s = { width: 16, height: 16, stroke: color, strokeWidth: 1.9, fill: 'none',
              strokeLinecap: 'round', strokeLinejoin: 'round' };
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></>,
    box: <><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/></>,
    list: <><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></>,
    users: <><circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3 2.7-5 6-5s6 2 6 5"/><path d="M16 4a3 3 0 010 6M21 20c0-2.5-1.5-4-3.5-4.5"/></>,
    shield: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z"/></>,
    chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></>,
    key: <><circle cx="8" cy="8" r="4"/><path d="M11 11l8 8M16 16l2-2M19 19l2-2"/></>,
    db: <><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
    gear: <><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></>,
  };
  return <svg viewBox="0 0 24 24" style={s}>{paths[k]}</svg>;
}
function AppShell({ active = 'Dashboard', title, subtitle, children, actions, showAdmin = false }) {
  return (
    <div style={{ position: 'absolute', inset: 0, display: 'flex', background: C.paper }}>
      {/* sidebar */}
      <div style={{ width: 224, background: '#0E141C', flexShrink: 0, display: 'flex',
        flexDirection: 'column', padding: '0 0 14px' }}>
        <div style={{ padding: '17px 18px 14px', borderBottom: `1px solid rgba(255,255,255,0.06)` }}>
          <Logo size={26} />
        </div>
        <div style={{ padding: '14px 12px', overflow: 'hidden', flex: 1 }}>
          <div style={{ fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.13em',
            color: 'rgba(234,239,247,0.32)', padding: '0 10px 8px' }}>MENU</div>
          {NAV_MENU.map(([label, ic]) => {
            const on = label === active;
            return (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 11,
                padding: '8.5px 10px', borderRadius: 8, marginBottom: 2,
                background: on ? C.redSoft : 'transparent',
                boxShadow: on ? `inset 2px 0 0 ${C.red}` : 'none' }}>
                <NavIcon k={ic} color={on ? C.red : 'rgba(234,239,247,0.55)'} />
                <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: on ? 700 : 500,
                  color: on ? '#fff' : 'rgba(234,239,247,0.7)' }}>{label}</span>
              </div>
            );
          })}
          <div style={{ fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.13em',
            color: 'rgba(234,239,247,0.32)', padding: '16px 10px 8px' }}>ADMINISTRATION</div>
          {NAV_ADMIN.map(([label, ic]) => {
            const on = label === active;
            return (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 11,
                padding: '8.5px 10px', borderRadius: 8, marginBottom: 2,
                background: on ? C.redSoft : 'transparent',
                boxShadow: on ? `inset 2px 0 0 ${C.red}` : 'none' }}>
                <NavIcon k={ic} color={on ? C.red : 'rgba(234,239,247,0.55)'} />
                <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: on ? 700 : 500,
                  color: on ? '#fff' : 'rgba(234,239,247,0.7)' }}>{label}</span>
              </div>
            );
          })}
        </div>
      </div>
      {/* main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ height: 58, background: C.card, borderBottom: `1px solid ${C.line}`,
          display: 'flex', alignItems: 'center', padding: '0 24px', gap: 16, flexShrink: 0 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: F.display, fontSize: 17, fontWeight: 700, color: C.ink,
              letterSpacing: '-0.02em' }}>{title}</div>
            {subtitle && <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute }}>{subtitle}</div>}
          </div>
          {actions}
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, paddingLeft: 4 }}>
            <div style={{ width: 32, height: 32, borderRadius: 99, background: 'linear-gradient(135deg,#2C7BF2,#7A5CFF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff',
              fontFamily: F.ui, fontWeight: 700, fontSize: 12 }}>BA</div>
          </div>
        </div>
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>{children}</div>
      </div>
    </div>
  );
}

// ── Small atoms ──────────────────────────────────────────────────────────────
function Pill({ children, color = C.mute, bg = '#EEF1F6', style }) {
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5,
    fontFamily: F.ui, fontSize: 11.5, fontWeight: 700, color, background: bg,
    padding: '3px 9px', borderRadius: 7, letterSpacing: '-0.01em', ...style }}>{children}</span>;
}
function StatusDot({ color }) {
  return <span style={{ width: 7, height: 7, borderRadius: 99, background: color, display: 'inline-block' }} />;
}

Object.assign(window, {
  C, F, lerp, seg, Appear, Count, GrowBar, SceneWrap, Logo,
  CaptionBar, VideoChrome, Cursor, BrowserFrame, AppShell, NavIcon,
  Pill, StatusDot, NAV_MENU, NAV_ADMIN,
});
