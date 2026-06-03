// sc-insight.jsx — Scene 10 Analytics + Material Insights

function Donut({ at, segs, size = 150, stroke = 22 }) {
  const time = useTime();
  const p = Easing.easeOutCubic(seg(time, at, 1.1));
  const r = (size - stroke) / 2, cx = size / 2, circ = 2 * Math.PI * r;
  let acc = 0;
  const total = segs.reduce((a, b) => a + b.v, 0);
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={cx} cy={cx} r={r} fill="none" stroke={C.line} strokeWidth={stroke} />
      {segs.map((s, i) => {
        const frac = (s.v / total) * p;
        const dash = frac * circ;
        const el = (
          <circle key={i} cx={cx} cy={cx} r={r} fill="none" stroke={s.c} strokeWidth={stroke}
            strokeDasharray={`${dash} ${circ - dash}`} strokeDashoffset={-acc * circ} strokeLinecap="butt" />
        );
        acc += frac;
        return el;
      })}
    </svg>
  );
}

function SceneAnalytics({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const matAt = 20;  // switch to material insights
  const onMaterial = lt >= matAt;
  const companies = [['SEC', 86, C.red], ['Aramco', 64, C.green], ['HADEED', 41, C.blue], ['Saudi Energy', 28, C.violet]];
  const materials = [
    ['LV Power Cable 600V', 312, 94],
    ['MCCB 3-Pole', 248, 90],
    ['Cable Gland Brass', 196, 78],
    ['Busbar Support', 154, 61],
    ['Earth Rod Copper', 121, 88],
  ];
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.2} />
      <BrowserFrame x={56} y={64} w={1168} h={584} url={`app.smartrfp.io/${onMaterial ? 'material-insights' : 'analytics'}`}>
        <AppShell active={onMaterial ? 'Material Insights' : 'Analytics'}
          title={onMaterial ? 'Material Insights' : 'Analytics'}
          subtitle={onMaterial ? 'What customers ask for — and how well we auto-match it' : 'Pipeline performance by company & outcome'}>
          <div style={{ position: 'absolute', inset: 0, padding: 22 }}>
            {!onMaterial ? (
              <div key="ana" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
                {/* KPI strip */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
                  {[['Bid win rate', 38, '%', C.green, '+6 pts'], ['Avg cycle time', 0.8, 'd', C.blue, '−64%'],
                    ['RFPs / month', 64, '', C.red, '+22'], ['Auto-match rate', 73, '%', C.amber, '+5 pts']].map((k, i) => (
                    <KpiTile key={k[0]} at={t0 + 0.4 + i * 0.12} label={k[0]} value={k[1]} suffix={k[2]}
                      dec={k[2] === 'd' ? 1 : 0} accent={k[3]} sub="vs last quarter" trend={k[4]} />
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 14, flex: 1 }}>
                  {/* bar chart by company */}
                  <Appear at={t0 + 0.9} dur={0.5} style={{ flex: 1 }}>
                    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18, height: '100%' }}>
                      <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>RFP volume by customer</div>
                      <div style={{ fontFamily: F.ui, fontSize: 12, color: C.faint, marginBottom: 20 }}>last 90 days</div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {companies.map((c, i) => (
                          <div key={c[0]} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <span style={{ width: 96, fontFamily: F.ui, fontSize: 12.5, fontWeight: 600, color: C.text }}>{c[0]}</span>
                            <div style={{ flex: 1 }}>
                              <GrowBar to={(c[1] / 90) * 100} at={t0 + 1.2 + i * 0.12} dur={0.8} color={c[2]} h={16} radius={6} track={C.line2} />
                            </div>
                            <span style={{ width: 30, fontFamily: F.mono, fontSize: 12.5, fontWeight: 700, color: C.text, textAlign: 'right' }}>
                              <Count to={c[1]} at={t0 + 1.2 + i * 0.12} dur={0.9} /></span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </Appear>
                  {/* donut outcomes */}
                  <Appear at={t0 + 1.1} dur={0.5} style={{ width: 290 }}>
                    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18, height: '100%' }}>
                      <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink, marginBottom: 6 }}>Outcomes</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <div style={{ position: 'relative' }}>
                          <Donut at={t0 + 1.4} segs={[{ v: 38, c: C.green }, { v: 24, c: C.amber }, { v: 38, c: C.line2 }]} />
                          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                            alignItems: 'center', justifyContent: 'center' }}>
                            <div style={{ fontFamily: F.display, fontSize: 26, fontWeight: 700, color: C.ink }}>
                              <Count to={38} suffix="%" at={t0 + 1.6} dur={1} /></div>
                            <div style={{ fontFamily: F.ui, fontSize: 10.5, color: C.faint }}>won</div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                          {[['Won', C.green, '38%'], ['Pending', C.amber, '24%'], ['Lost', C.faint, '38%']].map((s) => (
                            <div key={s[0]} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ width: 9, height: 9, borderRadius: 99, background: s[1] }} />
                              <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.text, fontWeight: 600 }}>{s[0]}</span>
                              <span style={{ fontFamily: F.mono, fontSize: 12, color: C.mute, marginLeft: 'auto' }}>{s[2]}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div style={{ height: 1, background: C.line2, margin: '16px 0' }} />
                      <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.mute, lineHeight: 1.5 }}>
                        Export any view to <span style={{ color: C.red, fontWeight: 700 }}>XLSX</span> for the board pack — one click.
                      </div>
                    </div>
                  </Appear>
                </div>
              </div>
            ) : (
              <div key="mat" style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
                <Appear at={t0 + matAt + 0.2} dur={0.5}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
                    {[['Unique materials tracked', 8421, C.violet], ['Avg auto-match', 73, C.green, '%'], ['Keyword aliases', 1290, C.blue]].map((k, i) => (
                      <KpiTile key={k[0]} at={t0 + matAt + 0.3 + i * 0.12} label={k[0]} value={k[1]} suffix={k[3] || ''} accent={k[2]} sub="material master" />
                    ))}
                  </div>
                </Appear>
                <Appear at={t0 + matAt + 0.6} dur={0.5} style={{ flex: 1 }}>
                  <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', height: '100%' }}>
                    <div style={{ padding: '12px 18px', borderBottom: `1px solid ${C.line}`, fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>
                      Most-requested materials
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.4fr 1.2fr', padding: '8px 18px',
                      fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, color: C.faint, letterSpacing: '0.04em',
                      textTransform: 'uppercase', borderBottom: `1px solid ${C.line2}` }}>
                      <span>Material family</span><span>Appears in RFPs</span><span>Auto-match rate</span>
                    </div>
                    {materials.map((m, i) => (
                      <Appear key={m[0]} at={t0 + matAt + 0.9 + i * 0.12} dur={0.4} x={10}>
                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.4fr 1.2fr', alignItems: 'center',
                          padding: '12px 18px', borderBottom: `1px solid ${C.line2}` }}>
                          <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text }}>{m[0]}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingRight: 24 }}>
                            <div style={{ flex: 1 }}>
                              <GrowBar to={(m[1] / 312) * 100} at={t0 + matAt + 1.1 + i * 0.1} dur={0.7} color={C.violet} h={8} track={C.line2} />
                            </div>
                            <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 700, color: C.text, width: 30 }}>{m[1]}</span>
                          </div>
                          <MatchBadge v={m[2]} />
                        </div>
                      </Appear>
                    ))}
                    <div style={{ padding: '12px 18px', fontFamily: F.ui, fontSize: 12, color: C.mute }}>
                      Low match-rate families tell admins exactly where to add a <span style={{ color: C.red, fontWeight: 700 }}>keyword alias</span> next.
                    </div>
                  </div>
                </Appear>
              </div>
            )}
          </div>
        </AppShell>
      </BrowserFrame>
    </SceneWrap>
  );
}

Object.assign(window, { SceneAnalytics, Donut });
