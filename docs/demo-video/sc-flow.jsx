// sc-flow.jsx — Scene 3: Flow Overview, the end-to-end pipeline

function FlowGlyph({ k, color, size = 26 }) {
  const s = { width: size, height: size, stroke: color, strokeWidth: 1.8, fill: 'none',
              strokeLinecap: 'round', strokeLinejoin: 'round' };
  const p = {
    discover: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3M11 7v8M7 11h8" /></>,
    parse: <><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" /><path d="M14 3v5h5M8 13h7M8 17h7" /></>,
    match: <><path d="M9 12a3 3 0 013-3h3a3 3 0 010 6h-1" /><path d="M15 12a3 3 0 01-3 3H9a3 3 0 010-6h1" /></>,
    route: <><path d="M3 11l18-8-8 18-2.5-7.5L3 11z" /></>,
    quote: <><path d="M20 12l-8.5 8.5a2.8 2.8 0 01-4-4L16 8" /><path d="M7 7h.01" /><path d="M3 3l5 1 12 12" /></>,
    submit: <><path d="M12 19V5M5 12l7-7 7 7" /><path d="M5 21h14" /></>,
    audit: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" /><path d="M9 12l2 2 4-4" /></>,
  };
  return <svg viewBox="0 0 24 24" style={s}>{p[k]}</svg>;
}

const STAGES = [
  { key: 'discover', t: 'Discover', s: 'Scheduled portal scrape' },
  { key: 'parse', t: 'Parse BOQ', s: 'Extract codes & keywords' },
  { key: 'match', t: 'Auto-Match', s: 'Against SAP material master' },
  { key: 'route', t: 'Route', s: 'Adaptive-card to bidders' },
  { key: 'quote', t: 'Capture', s: 'Prices & lead times' },
  { key: 'submit', t: 'Submit', s: 'Back to the customer' },
];

function SceneFlow({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const stageStart = 5.5;     // first stage lights
  const stageGap = 3.4;       // between stages
  const colW = 182, gap = 14;
  const totalW = STAGES.length * colW + (STAGES.length - 1) * gap;
  const x0 = (1280 - totalW) / 2;
  const rowY = 286;

  // packet progress across the whole chain
  const chainStart = t0 + stageStart;
  const chainEnd = t0 + stageStart + STAGES.length * stageGap;
  const packetP = clamp((time - chainStart) / (chainEnd - chainStart), 0, 1);

  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.35} />

      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.red,
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 11 }}>Flow overview</div>
        <div style={{ fontFamily: F.display, fontSize: 42, fontWeight: 700, color: C.inv,
          letterSpacing: '-0.02em' }}>One pipeline, six stages, zero re-keying</div>
      </Appear>

      {/* source portals feeding in */}
      <Appear at={t0 + 3.6} dur={0.6} y={0}
        style={{ position: 'absolute', top: rowY - 96, left: x0 - 6, display: 'flex', gap: 8 }}>
        <span style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.invMute, alignSelf: 'center' }}>Sources</span>
        {['Ariba', 'SEC', 'Aramco', 'HADEED'].map((p) => (
          <span key={p} style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 600, color: C.inv,
            background: C.panel2, border: `1px solid ${C.hair}`, borderRadius: 7, padding: '4px 9px' }}>{p}</span>
        ))}
        <svg width="20" height="40" style={{ position: 'absolute', left: 40, top: 30 }}>
          <path d="M2 0 V30 H18" stroke={C.hair2} strokeWidth="1.5" fill="none" />
        </svg>
      </Appear>

      {/* connector track behind cards */}
      <div style={{ position: 'absolute', top: rowY + 52, left: x0, width: totalW, height: 3,
        background: 'rgba(255,255,255,0.10)', borderRadius: 2 }}>
        <div style={{ width: `${packetP * 100}%`, height: '100%', background: C.red, borderRadius: 2 }} />
      </div>
      {/* travelling packet */}
      {time > chainStart && time < chainEnd + 0.4 && (
        <div style={{ position: 'absolute', top: rowY + 53 - 5, left: x0 + packetP * totalW - 6,
          width: 13, height: 13, borderRadius: 99, background: C.red,
          boxShadow: `0 0 14px ${C.red}`, marginTop: 0 }} />
      )}

      {/* stage cards */}
      {STAGES.map((st, i) => {
        const onAt = t0 + stageStart + i * stageGap;
        const active = time >= onAt && time < onAt + stageGap;
        const done = time >= onAt + stageGap;
        const lit = active || done;
        return (
          <Appear key={st.key} at={t0 + 3.0 + i * 0.18} dur={0.5} y={20}
            style={{ position: 'absolute', left: x0 + i * (colW + gap), top: rowY, width: colW }}>
            <div style={{ background: lit ? C.panel2 : C.panel,
              border: `1px solid ${active ? C.red : (done ? 'rgba(18,166,107,0.4)' : C.hair)}`,
              borderRadius: 14, padding: '18px 16px',
              boxShadow: active ? `0 0 0 3px ${C.redSoft}, 0 16px 40px rgba(0,0,0,0.4)` : 'none',
              transition: 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ width: 44, height: 44, borderRadius: 11,
                  background: active ? C.red : (done ? C.greenSoft : 'rgba(255,255,255,0.05)'),
                  display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <FlowGlyph k={st.key} color={active ? '#fff' : (done ? C.green : C.invMute)} />
                </div>
                <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 700,
                  color: lit ? C.inv : C.invFaint }}>{String(i + 1).padStart(2, '0')}</span>
              </div>
              <div style={{ fontFamily: F.display, fontSize: 19, fontWeight: 700,
                color: lit ? C.inv : C.invMute, letterSpacing: '-0.01em' }}>{st.t}</div>
              <div style={{ fontFamily: F.ui, fontSize: 12.5, color: lit ? C.invMute : C.invFaint,
                marginTop: 5, lineHeight: 1.35, minHeight: 34 }}>{st.s}</div>
              {done && (
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 5,
                  fontFamily: F.mono, fontSize: 10.5, fontWeight: 700, color: C.green }}>
                  <span>✓</span> DONE
                </div>
              )}
            </div>
          </Appear>
        );
      })}

      {/* audit backbone */}
      <Appear at={t0 + stageStart + STAGES.length * stageGap - 1} dur={0.7} y={16}
        style={{ position: 'absolute', top: rowY + 200, left: x0, width: totalW }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, background: C.panel,
          border: `1px solid rgba(122,92,255,0.4)`, borderRadius: 12, padding: '14px 20px' }}>
          <div style={{ width: 38, height: 38, borderRadius: 9, background: C.violetSoft,
            display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FlowGlyph k="audit" color={C.violet} size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 15, color: C.inv }}>
              Persisted to Microsoft Dataverse — every step, attributed & timestamped
            </div>
            <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.invMute, marginTop: 2 }}>
              Files in SharePoint · responses in Dataverse · append-only audit log underneath it all
            </div>
          </div>
          <Pill color={C.violet} bg={C.violetSoft}>RBAC + AUDIT</Pill>
        </div>
      </Appear>

      {/* closing line */}
      <Appear at={t0 + dur - 6.5} dur={0.6} y={14} exitAt={t0 + dur - 0.6} exitDur={0.5}
        style={{ position: 'absolute', bottom: 78, left: 0, right: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: F.ui, fontSize: 21, fontWeight: 600, color: C.inv }}>
          Receipt to bidder in <span style={{ color: C.red }}>minutes</span>, not hours.
          Now let's walk each stage on the real product.
        </span>
      </Appear>
    </SceneWrap>
  );
}

Object.assign(window, { SceneFlow, FlowGlyph, STAGES });
