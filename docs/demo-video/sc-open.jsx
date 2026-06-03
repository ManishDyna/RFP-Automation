// sc-open.jsx — Scene 1 Title, Scene 2 The Problem

function DotGrid({ opacity = 0.5 }) {
  return <div style={{ position: 'absolute', inset: 0, opacity,
    backgroundImage: `radial-gradient(${C.hair2} 1px, transparent 1px)`,
    backgroundSize: '34px 34px', maskImage: 'radial-gradient(80% 70% at 50% 40%, #000 0%, transparent 90%)',
    WebkitMaskImage: 'radial-gradient(80% 70% at 50% 40%, #000 0%, transparent 90%)' }} />;
}

// ── Scene 1 — Title ──────────────────────────────────────────────────────────
function SceneTitle({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  // logo lockup scales in, tagline, sub
  const pulse = 0.5 + 0.5 * Math.sin(lt * 1.6);
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.6} />
      {/* faint flow line sweeping */}
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
        <line x1="0" y1="540" x2="1280" y2="540" stroke={C.hair} strokeWidth="1" />
      </svg>

      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
        <Appear at={t0 + 0.3} dur={0.8} y={0} sc={0.35} ease={Easing.easeOutBack}>
          <Logo size={86} />
        </Appear>
        <Appear at={t0 + 1.5} dur={0.7} y={20} style={{ marginTop: 34 }}>
          <div style={{ fontFamily: F.display, fontSize: 56, fontWeight: 700, letterSpacing: '-0.03em',
            color: C.inv, lineHeight: 1.05 }}>
            From RFP to quote,<br /><span style={{ color: C.red }}>automated end-to-end.</span>
          </div>
        </Appear>
        <Appear at={t0 + 2.6} dur={0.7} y={16} style={{ marginTop: 26, maxWidth: 760 }}>
          <div style={{ fontFamily: F.ui, fontSize: 22, fontWeight: 500, color: C.invMute, lineHeight: 1.5 }}>
            SmartRFP discovers tenders, parses the Bill of Quantities, auto-matches it to your
            material master, routes to bidders, and tracks every step — with a full audit trail.
          </div>
        </Appear>
        <Appear at={t0 + 4.0} dur={0.6} y={14} style={{ marginTop: 40 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'center' }}>
            {['Discover', 'Match', 'Route', 'Quote', 'Submit', 'Audit'].map((s, i) => (
              <React.Fragment key={s}>
                {i > 0 && <span style={{ color: C.invFaint, fontSize: 14 }}>→</span>}
                <span style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 600,
                  color: i % 2 ? C.inv : C.red, letterSpacing: '0.02em' }}>{s}</span>
              </React.Fragment>
            ))}
          </div>
        </Appear>
        <Appear at={t0 + 5.2} dur={0.6} style={{ marginTop: 30, opacity: 0.6 + pulse * 0.4 }}>
          <div style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.invFaint,
            letterSpacing: '0.08em', textTransform: 'uppercase' }}>Product demo · 8 min</div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

// ── Scene 2 — The Problem ────────────────────────────────────────────────────
function PainCard({ at, x, y, rot, icon, app, note, color }) {
  return (
    <Appear at={at} dur={0.6} y={26} sc={0.12} ease={Easing.easeOutBack}
      style={{ position: 'absolute', left: x, top: y, transform: `rotate(${rot}deg)` }}>
      <div style={{ width: 230, background: C.card, borderRadius: 12, padding: '14px 16px',
        boxShadow: '0 18px 40px rgba(0,0,0,0.4)', transform: `rotate(${rot}deg)` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
          <div style={{ width: 30, height: 30, borderRadius: 7, background: color + '22',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>{icon}</div>
          <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>{app}</div>
        </div>
        <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.mute, lineHeight: 1.4 }}>{note}</div>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6,
          fontFamily: F.mono, fontSize: 11, fontWeight: 700, color: C.red }}>
          <span style={{ width: 14, height: 14, borderRadius: 99, background: C.redSoft,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>✕</span>
          manual · error-prone
        </div>
      </div>
    </Appear>
  );
}

function SceneProblem({ t0, dur }) {
  const time = useTime();
  // Phase A (0-16): scattered tools. Phase B (16+): collapse to stats.
  const statsAt = t0 + 16;
  const showStats = time >= statsAt - 0.5;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.4} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 92, left: 0, right: 0, textAlign: 'center' }}
        exitAt={statsAt - 0.6} exitDur={0.5}>
        <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.red,
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 12 }}>The old way</div>
        <div style={{ fontFamily: F.display, fontSize: 44, fontWeight: 700, color: C.inv,
          letterSpacing: '-0.02em' }}>One RFP. Five disconnected tools.</div>
      </Appear>

      {/* scattered pain cards */}
      {!showStats && (
        <>
          <PainCard at={t0 + 1.2} x={150} y={250} rot={-5} icon="📄" app="PDF / Email" color={C.blue}
            note="BOQ arrives buried in an inbox — re-keyed by hand into a sheet." />
          <PainCard at={t0 + 1.9} x={420} y={330} rot={3} icon="📊" app="Excel" color={C.green}
            note="Line items copy-pasted, versions multiply, totals drift." />
          <PainCard at={t0 + 2.6} x={700} y={250} rot={-3} icon="🔎" app="SAP search" color={C.amber}
            note="Each material code looked up one at a time, from memory." />
          <PainCard at={t0 + 3.3} x={930} y={345} rot={5} icon="✉️" app="Outlook" color={C.violet}
            note="Hand-offs by email — status scattered across folders." />
          <PainCard at={t0 + 4.0} x={560} y={170} rot={-2} icon="⏰" app="Deadlines" color={C.red}
            note="No reminders. RFP due dates quietly slip past." />
        </>
      )}

      {/* tangled connector lines */}
      {!showStats && (
        <Appear at={t0 + 4.6} dur={0.8} style={{ position: 'absolute', inset: 0 }}>
          <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.5 }}>
            <path d="M280 300 C 400 200, 520 420, 660 300 S 900 220, 1040 380" fill="none"
              stroke={C.red} strokeWidth="1.5" strokeDasharray="5 6" opacity="0.5" />
          </svg>
        </Appear>
      )}

      {/* Phase B — stats */}
      {showStats && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 40 }}>
          <Appear at={statsAt} dur={0.6}>
            <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 700, color: C.inv,
              textAlign: 'center', letterSpacing: '-0.02em' }}>What that costs you</div>
          </Appear>
          <div style={{ display: 'flex', gap: 28 }}>
            {[
              { v: 2.5, suf: ' hrs', dec: 1, lbl: 'per RFP, just on data entry', at: statsAt + 0.5, col: C.red },
              { v: 5, suf: '/mo', dec: 0, lbl: 'RFPs missed on coordination', at: statsAt + 1.0, col: C.amber },
              { v: 0, suf: '%', dec: 0, lbl: 'auditable match history', at: statsAt + 1.5, col: C.violet, zero: true },
            ].map((s) => (
              <Appear key={s.lbl} at={s.at} dur={0.6} y={22} sc={0.1}>
                <div style={{ width: 300, background: C.panel, border: `1px solid ${C.hair}`,
                  borderRadius: 16, padding: '28px 26px', textAlign: 'center' }}>
                  <div style={{ fontFamily: F.display, fontSize: 64, fontWeight: 700, color: s.col,
                    letterSpacing: '-0.03em', lineHeight: 1 }}>
                    {s.zero ? 'None' : <Count to={s.v} suffix={s.suf} decimals={s.dec} at={s.at + 0.2} dur={1.1} />}
                  </div>
                  <div style={{ fontFamily: F.ui, fontSize: 16, color: C.invMute, marginTop: 14,
                    lineHeight: 1.4 }}>{s.lbl}</div>
                </div>
              </Appear>
            ))}
          </div>
          <Appear at={statsAt + 3.4} dur={0.6} y={14}>
            <div style={{ fontFamily: F.ui, fontSize: 20, fontWeight: 600, color: C.inv }}>
              The work isn't pricing. It's <span style={{ color: C.red }}>plumbing</span>. SmartRFP removes it.
            </div>
          </Appear>
        </div>
      )}
    </SceneWrap>
  );
}

Object.assign(window, { SceneTitle, SceneProblem, DotGrid });
