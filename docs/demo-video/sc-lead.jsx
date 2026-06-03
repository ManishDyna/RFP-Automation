// sc-lead.jsx — cinematic per-feature lead-in cards: "the manual way" (the
// problem this feature solves) → "with SmartRFP" (the automated promise), shown
// right before each real-product demo.

function FeatLead({ t0, dur, n, title, old, now }) {
  const time = useTime(); const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.26} />
      {/* giant faded index */}
      <Appear at={t0 + 0.1} dur={0.7} sc={0.2} style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 150, fontWeight: 700, lineHeight: 1, opacity: 0.10,
          background: `linear-gradient(135deg,${C.red},${C.amber})`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          {String(n).padStart(2, '0')}
        </div>
      </Appear>

      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 0 }}>
        {/* feature title */}
        <Appear at={t0 + 0.25} dur={0.5} y={14}>
          <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.invMute, letterSpacing: '0.18em', textTransform: 'uppercase' }}>{title}</div>
        </Appear>

        {/* the manual way */}
        <Appear at={t0 + 0.5} dur={0.6} y={20} style={{ marginTop: 22, textAlign: 'center', maxWidth: 940 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 9, marginBottom: 14 }}>
            <span style={{ width: 22, height: 22, borderRadius: 99, background: C.redSoft, color: C.red, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 12 }}>✕</span>
            <span style={{ fontFamily: F.mono, fontSize: 12.5, fontWeight: 700, color: C.red, letterSpacing: '0.16em', textTransform: 'uppercase' }}>The manual way</span>
          </div>
          <div style={{ fontFamily: F.display, fontSize: 34, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em', lineHeight: 1.25 }}>{old}</div>
        </Appear>

        {/* divider arrow */}
        <Appear at={t0 + 1.6} dur={0.5} sc={0.3} style={{ marginTop: 26 }}>
          <div style={{ width: 44, height: 44, borderRadius: 99, background: C.panel2, border: `1px solid ${C.hair2}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={C.red} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M6 13l6 6 6-6"/></svg>
          </div>
        </Appear>

        {/* with SmartRFP */}
        <Appear at={t0 + 2.0} dur={0.6} y={18} style={{ marginTop: 26, textAlign: 'center', maxWidth: 940 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 9, marginBottom: 12 }}>
            <span style={{ width: 22, height: 22, borderRadius: 99, background: C.greenSoft, color: C.green, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 12 }}>✓</span>
            <span style={{ fontFamily: F.mono, fontSize: 12.5, fontWeight: 700, color: C.green, letterSpacing: '0.16em', textTransform: 'uppercase' }}>With SmartRFP</span>
          </div>
          <div style={{ fontFamily: F.ui, fontSize: 21, fontWeight: 600, color: C.invMute, lineHeight: 1.45 }}>{now}</div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

Object.assign(window, { FeatLead });
