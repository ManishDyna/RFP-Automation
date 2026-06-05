// sc-value.jsx — Scene 12 Business Value / ROI, Scene 13 Outro

function CompareRow({ at, lt, metric, before, after }) {
  if (lt < at) return null;
  const op = clamp((lt - at) / 0.45, 0, 1);
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 44px 1fr', alignItems: 'center',
      padding: '13px 0', borderBottom: `1px solid ${C.hair}`, opacity: op, transform: `translateY(${(1 - op) * 12}px)` }}>
      <span style={{ fontFamily: F.ui, fontSize: 15, fontWeight: 600, color: C.inv }}>{metric}</span>
      <span style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: C.invMute, textDecoration: 'line-through', textDecorationColor: 'rgba(238,61,51,0.5)' }}>{before}</span>
      <span style={{ textAlign: 'center', color: C.red }}>→</span>
      <span style={{ fontFamily: F.mono, fontSize: 16, fontWeight: 700, color: C.green }}>{after}</span>
    </div>
  );
}

function SceneValue({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.25} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 52, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.red, letterSpacing: '0.14em',
          textTransform: 'uppercase', marginBottom: 10 }}>Business value</div>
        <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          Hours to minutes. Guesswork to evidence.
        </div>
      </Appear>

      {/* comparison */}
      <Appear at={t0 + 0.8} dur={0.5} style={{ position: 'absolute', top: 168, left: 120, width: 600 }}>
        <div style={{ background: C.panel, border: `1px solid ${C.hair}`, borderRadius: 16, padding: '6px 22px 14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 44px 1fr', padding: '12px 0',
            fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: C.invFaint, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            <span>Metric</span><span>Manual</span><span></span><span>SmartRFP</span>
          </div>
          <CompareRow at={1.4} lt={lt} metric="Receipt → bidder" before="~4 hours" after="< 30 min" />
          <CompareRow at={1.8} lt={lt} metric="Receipt → submission" before="2–3 days" after="< 1 day" />
          <CompareRow at={2.2} lt={lt} metric="Data entry / RFP" before="2.5 hours" after="~0" />
          <CompareRow at={2.6} lt={lt} metric="Missed on coordination" before="~5 / month" after="0" />
          <CompareRow at={3.0} lt={lt} metric="BOQ auto-match" before="manual" after="≥ 73%" />
          <CompareRow at={3.4} lt={lt} metric="Audit trail" before="none" after="full" />
        </div>
      </Appear>

      {/* ROI tiles */}
      <div style={{ position: 'absolute', top: 168, left: 760, width: 400, display: 'flex', flexDirection: 'column', gap: 14 }}>
        {[
          { at: 4.2, big: 800, suf: ' hrs', col: C.green, lbl: 'engineering time saved / year', note: '≈ 10 FTE-months back to pricing strategy' },
          { at: 4.8, big: 6, suf: ' mo', col: C.amber, lbl: 'estimated payback period', note: 'at current RFP volume', pre: '6–9' },
          { at: 5.4, big: 4, suf: ' deals', col: C.violet, lbl: 'missed-deadline losses avoided', note: '~SAR 500k average value each', pre: '3–5' },
        ].map((r) => (
          <Appear key={r.lbl} at={t0 + r.at} dur={0.5} y={20} sc={0.06}>
            <div style={{ background: C.panel, border: `1px solid ${C.hair}`, borderRadius: 16, padding: '18px 20px',
              display: 'flex', alignItems: 'center', gap: 18 }}>
              <div style={{ fontFamily: F.display, fontSize: 46, fontWeight: 700, color: r.col, lineHeight: 1, minWidth: 130 }}>
                {r.pre ? r.pre + r.suf : <Count to={r.big} suffix={r.suf} at={t0 + r.at + 0.2} dur={1.1} />}
              </div>
              <div>
                <div style={{ fontFamily: F.ui, fontSize: 14.5, fontWeight: 700, color: C.inv, lineHeight: 1.25 }}>{r.lbl}</div>
                <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.invMute, marginTop: 3 }}>{r.note}</div>
              </div>
            </div>
          </Appear>
        ))}
      </div>

      <Appear at={t0 + dur - 6} dur={0.6} y={14} exitAt={t0 + dur - 0.6}
        style={{ position: 'absolute', bottom: 80, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.ui, fontSize: 20, fontWeight: 600, color: C.inv }}>
          Your engineers stop being data-entry clerks — and start <span style={{ color: C.red }}>winning more bids</span>.
        </div>
      </Appear>
    </SceneWrap>
  );
}

// ── Scene 13 — Outro ─────────────────────────────────────────────────────────
function SceneOutro({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.5} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
        <Appear at={t0 + 0.3} dur={0.8} sc={0.3} ease={Easing.easeOutBack}>
          <Logo size={72} />
        </Appear>
        <Appear at={t0 + 1.3} dur={0.7} y={18} style={{ marginTop: 30 }}>
          <div style={{ fontFamily: F.display, fontSize: 46, fontWeight: 700, color: C.inv, letterSpacing: '-0.03em' }}>
            From RFP to quote, <span style={{ color: C.red }}>automated.</span>
          </div>
        </Appear>
        <Appear at={t0 + 2.3} dur={0.7} style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'center' }}>
            {['Discover', 'Match', 'Route', 'Quote', 'Submit', 'Audit'].map((s, i) => (
              <React.Fragment key={s}>
                {i > 0 && <span style={{ color: C.invFaint, fontSize: 14 }}>→</span>}
                <span style={{ fontFamily: F.mono, fontSize: 15, fontWeight: 600, color: i % 2 ? C.inv : C.red }}>{s}</span>
              </React.Fragment>
            ))}
          </div>
        </Appear>
        <Appear at={t0 + 3.4} dur={0.7} style={{ marginTop: 40 }}>
          <div style={{ fontFamily: F.ui, fontSize: 17, fontWeight: 500, color: C.invMute, maxWidth: 620, lineHeight: 1.5 }}>
            Discovery, matching, routing, quoting and audit — one governed pipeline,
            built on your existing Microsoft 365 tenant.
          </div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

Object.assign(window, { SceneValue, SceneOutro });
