// sc-app.jsx — Scene 6 Login + Dashboard, Scene 7 RFP Insights

// ── KPI tile ─────────────────────────────────────────────────────────────────
function KpiTile({ at, label, value, suffix = '', prefix = '', accent, sub, dec = 0, trend }) {
  return (
    <Appear at={at} dur={0.5} y={18} sc={0.06}>
      <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: '15px 16px',
        position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, width: 3, height: '100%', background: accent }} />
        <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.mute }}>{label}</div>
        <div style={{ fontFamily: F.display, fontSize: 34, fontWeight: 700, color: C.ink, lineHeight: 1.15,
          letterSpacing: '-0.02em', marginTop: 2 }}>
          <Count to={value} prefix={prefix} suffix={suffix} decimals={dec} at={at + 0.2} dur={1.0} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
          {trend && <span style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700, color: trend[0] === '+' ? C.green : C.red }}>{trend}</span>}
          <span style={{ fontFamily: F.ui, fontSize: 11.5, color: C.faint }}>{sub}</span>
        </div>
      </div>
    </Appear>
  );
}

const COMPANY_COLORS = { SEC: C.red, Aramco: C.green, HADEED: C.blue, 'Saudi Energy': C.violet };
function CompanyTag({ c }) {
  const col = COMPANY_COLORS[c] || C.mute;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontFamily: F.ui,
      fontWeight: 700, fontSize: 12, color: C.text }}>
      <span style={{ width: 18, height: 18, borderRadius: 5, background: col + '22', color: col,
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 800 }}>
        {c[0]}
      </span>{c}
    </span>
  );
}
function StatusPill({ s }) {
  const map = { New: C.red, 'In Progress': C.amber, Submitted: C.green, Declined: C.faint, Won: C.violet };
  const col = map[s] || C.mute;
  return <span style={{ fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: col, background: col + '1c',
    borderRadius: 6, padding: '3px 9px' }}>{s}</span>;
}
function MatchBadge({ v }) {
  const col = v >= 90 ? C.green : v >= 60 ? C.amber : C.red;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
      <div style={{ width: 54, height: 5, background: C.line, borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: v + '%', height: '100%', background: col }} />
      </div>
      <span style={{ fontFamily: F.mono, fontSize: 11.5, fontWeight: 700, color: col }}>{v}%</span>
    </div>
  );
}

const RFP_ROWS = [
  ['SEC', 'RFP-C001744045', 42, 73, 'New', '3d'],
  ['Aramco', '4203238879', 18, 91, 'In Progress', '5d'],
  ['HADEED', 'RAJHI-2291', 27, 64, 'In Progress', '6d'],
  ['SEC', 'RFP-C001734554', 15, 88, 'Submitted', '—'],
  ['Aramco', '4201990township', 9, 100, 'Submitted', '—'],
];

// ── Scene 6 — Login + Dashboard ──────────────────────────────────────────────
function SceneDashboard({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const signAt = 5.0;          // click sign-in
  const dashAt = signAt + 1.0; // dashboard appears
  const showLogin = lt < dashAt + 0.5;
  const cursor = [
    { t: t0 + 1.6, x: 760, y: 520 },
    { t: t0 + signAt, x: 640, y: 430, click: true },
    { t: t0 + signAt + 0.8, x: 640, y: 430 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.3} />

      {/* LOGIN */}
      {showLogin && (
        <Appear at={t0 + 0.2} dur={0.6} exitAt={t0 + dashAt - 0.3} exitDur={0.4}
          style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 392, background: C.card, borderRadius: 18, padding: '34px 34px 30px',
            boxShadow: '0 40px 90px rgba(0,0,0,0.5)' }}>
            <Logo size={34} light />
            <div style={{ fontFamily: F.display, fontSize: 25, fontWeight: 700, color: C.ink, marginTop: 22,
              letterSpacing: '-0.02em' }}>Welcome back</div>
            <div style={{ fontFamily: F.ui, fontSize: 13.5, color: C.mute, marginTop: 4 }}>
              Sign in to the RFP automation portal.
            </div>
            {[['Email', 'basim.k@company.com'], ['Password', '••••••••••']].map(([l, v], i) => (
              <div key={l} style={{ marginTop: 16 }}>
                <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 6 }}>{l}</div>
                <div style={{ height: 42, border: `1px solid ${lt > 3 && i === 0 ? C.red : C.line}`, borderRadius: 10,
                  display: 'flex', alignItems: 'center', padding: '0 13px', fontFamily: F.ui, fontSize: 13.5,
                  color: i ? C.faint : C.text, background: C.paper }}>{v}</div>
              </div>
            ))}
            <div style={{ height: 44, borderRadius: 10, marginTop: 22, background: lt > signAt ? C.redDk : C.red,
              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: F.ui, fontWeight: 700, fontSize: 14,
              boxShadow: lt > signAt && lt < signAt + 0.5 ? `0 0 0 4px ${C.redSoft}` : `0 10px 24px ${C.redSoft}` }}>
              {lt > signAt ? 'Signing in…' : 'Sign in'}
            </div>
            <div style={{ textAlign: 'center', marginTop: 14, fontFamily: F.ui, fontSize: 12, color: C.faint }}>
              Forgot password?
            </div>
          </div>
        </Appear>
      )}

      {/* DASHBOARD */}
      {lt >= dashAt - 0.4 && (
        <Appear at={t0 + dashAt} dur={0.6} sc={0.04} style={{ position: 'absolute', inset: 0 }}>
          <BrowserFrame x={56} y={64} w={1168} h={584} url="app.smartrfp.io/dashboard">
            <AppShell active="Dashboard" title="Dashboard" subtitle="Welcome back, Basim — here's today's pipeline">
              <div style={{ position: 'absolute', inset: 0, padding: 22, overflow: 'hidden' }}>
                {/* KPI row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6,1fr)', gap: 12 }}>
                  <KpiTile at={t0 + dashAt + 0.3} label="Total RFPs" value={1284} accent={C.violet} sub="all time" />
                  <KpiTile at={t0 + dashAt + 0.45} label="New" value={7} accent={C.red} sub="awaiting action" trend="+3" />
                  <KpiTile at={t0 + dashAt + 0.6} label="In Progress" value={23} accent={C.amber} sub="being priced" />
                  <KpiTile at={t0 + dashAt + 0.75} label="Submitted" value={41} accent={C.green} sub="this month" trend="+12" />
                  <KpiTile at={t0 + dashAt + 0.9} label="Declined" value={12} accent={C.faint} sub="out of scope" />
                  <KpiTile at={t0 + dashAt + 1.05} label="Avg cycle" value={0.8} suffix="d" dec={1} accent={C.blue} sub="receipt→submit" trend="-64%" />
                </div>

                {/* table + side panel */}
                <div style={{ display: 'flex', gap: 14, marginTop: 16 }}>
                  <Appear at={t0 + dashAt + 1.2} dur={0.5} style={{ flex: 1 }}>
                    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '12px 16px', borderBottom: `1px solid ${C.line}` }}>
                        <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13.5, color: C.ink }}>Recent RFPs</span>
                        <span style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.red }}>View all →</span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 0.6fr 1fr 1fr 0.6fr',
                        padding: '8px 16px', fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, color: C.faint,
                        letterSpacing: '0.04em', textTransform: 'uppercase', borderBottom: `1px solid ${C.line2}` }}>
                        <span>Company</span><span>RFP ID</span><span>Items</span><span>Match</span><span>Status</span><span>Due</span>
                      </div>
                      {RFP_ROWS.map((r, i) => (
                        <Appear key={i} at={t0 + dashAt + 1.5 + i * 0.14} dur={0.4} x={12}>
                          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.4fr 0.6fr 1fr 1fr 0.6fr',
                            alignItems: 'center', padding: '11px 16px', borderBottom: `1px solid ${C.line2}` }}>
                            <CompanyTag c={r[0]} />
                            <span style={{ fontFamily: F.mono, fontSize: 12, color: C.text }}>{r[1]}</span>
                            <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.mute }}>{r[2]}</span>
                            <MatchBadge v={r[3]} />
                            <StatusPill s={r[4]} />
                            <span style={{ fontFamily: F.ui, fontSize: 12.5, fontWeight: 600,
                              color: r[5] === '3d' ? C.red : C.mute }}>{r[5]}</span>
                          </div>
                        </Appear>
                      ))}
                    </div>
                  </Appear>

                  {/* throughput mini chart */}
                  <Appear at={t0 + dashAt + 1.4} dur={0.5} style={{ width: 250 }}>
                    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 16, height: '100%' }}>
                      <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.ink }}>Throughput</div>
                      <div style={{ fontFamily: F.ui, fontSize: 11.5, color: C.faint, marginBottom: 14 }}>RFPs submitted / week</div>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 120 }}>
                        {[40, 55, 48, 70, 62, 85, 96].map((h, i) => (
                          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                            <div style={{ width: '100%', borderRadius: 5, background: i === 6 ? C.red : C.redSoft,
                              height: 0, animation: `none` }}>
                              <GrowBar to={100} at={t0 + dashAt + 1.6 + i * 0.06} dur={0.7}
                                color={i === 6 ? C.red : 'rgba(238,61,51,0.35)'} h={h} radius={5} track="transparent" />
                            </div>
                          </div>
                        ))}
                      </div>
                      <div style={{ marginTop: 12, fontFamily: F.ui, fontSize: 12, color: C.mute }}>
                        <span style={{ color: C.green, fontWeight: 700 }}>▲ 2.4×</span> vs. manual baseline
                      </div>
                    </div>
                  </Appear>
                </div>
              </div>
            </AppShell>
          </BrowserFrame>
        </Appear>
      )}

      {showLogin && <Cursor path={cursor} />}
    </SceneWrap>
  );
}

// ── Scene 7 — RFP Insights (detail + BOQ + response form) ───────────────────
function SceneRFP({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const typeAt = 7.0;     // start typing price
  const submitAt = 12.5;  // click submit
  const submitted = lt > submitAt;
  // typed price animation
  const priceFull = '184.50';
  const typed = lt < typeAt ? '' : priceFull.slice(0, Math.min(priceFull.length, Math.floor((lt - typeAt) / 0.18)));

  const cursor = [
    { t: t0 + 2.0, x: 700, y: 200 },
    { t: t0 + typeAt - 0.3, x: 880, y: 430, click: true },
    { t: t0 + typeAt + 1.2, x: 880, y: 430 },
    { t: t0 + submitAt, x: 1010, y: 540, click: true },
    { t: t0 + submitAt + 0.8, x: 1010, y: 540 },
  ];

  const boq = [
    ['WIRE,ELEC 331MM2 WHITE 600V', '4203238879', '5,000 M', 100],
    ['MCCB 250A 3P 36KA', '4109887421', '24 EA', 100],
    ['CABLE GLAND BRASS 32MM IP68', 'kw match', '180 EA', 82],
    ['BUSBAR SUPPORT 1100V', 'review', '60 EA', 0],
  ];

  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.22} />
      <BrowserFrame x={56} y={64} w={1168} h={584} url="app.smartrfp.io/rfp-insights/C001744045">
        <AppShell active="RFP Insights" title="RFP Insights" subtitle="SEC · RFP-C001744045">
          <div style={{ position: 'absolute', inset: 0, padding: 22, overflow: 'hidden', display: 'flex', gap: 16 }}>
            {/* left: header + BOQ */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
              <Appear at={t0 + 0.4} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 16,
                  display: 'flex', alignItems: 'center', gap: 16 }}>
                  <div style={{ width: 46, height: 46, borderRadius: 11, background: C.redSoft, color: C.red,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F.display,
                    fontWeight: 700, fontSize: 20 }}>S</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontFamily: F.display, fontSize: 19, fontWeight: 700, color: C.ink }}>
                      Saudi Electricity Company
                    </div>
                    <div style={{ fontFamily: F.mono, fontSize: 12, color: C.mute }}>RFP-C001744045 · LV cabling & protection</div>
                  </div>
                  {[['Items', '42'], ['Auto-match', '73%'], ['Due in', '3 days']].map(([k, v]) => (
                    <div key={k} style={{ textAlign: 'right', paddingLeft: 18 }}>
                      <div style={{ fontFamily: F.ui, fontSize: 11, color: C.faint }}>{k}</div>
                      <div style={{ fontFamily: F.display, fontSize: 18, fontWeight: 700,
                        color: k === 'Due in' ? C.red : C.ink }}>{v}</div>
                    </div>
                  ))}
                  <StatusPill s={submitted ? 'Submitted' : 'New'} />
                </div>
              </Appear>

              <Appear at={t0 + 0.7} dur={0.5} style={{ flex: 1 }}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', height: '100%' }}>
                  <div style={{ padding: '11px 16px', borderBottom: `1px solid ${C.line}`, fontFamily: F.ui,
                    fontWeight: 700, fontSize: 13, color: C.ink }}>Bill of Quantities · matched</div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr 0.8fr 1fr', padding: '8px 16px',
                    fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, color: C.faint, letterSpacing: '0.04em',
                    textTransform: 'uppercase', borderBottom: `1px solid ${C.line2}` }}>
                    <span>Description</span><span>SAP code</span><span>Qty</span><span>Match</span>
                  </div>
                  {boq.map((r, i) => (
                    <Appear key={i} at={t0 + 1.0 + i * 0.14} dur={0.4} x={10}>
                      <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr 0.8fr 1fr', alignItems: 'center',
                        padding: '11px 16px', borderBottom: `1px solid ${C.line2}` }}>
                        <span style={{ fontFamily: F.ui, fontSize: 12.5, fontWeight: 600, color: C.text,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r[0]}</span>
                        <span style={{ fontFamily: F.mono, fontSize: 11, color: r[3] === 0 ? C.red : C.mute }}>{r[1]}</span>
                        <span style={{ fontFamily: F.ui, fontSize: 12, color: C.mute }}>{r[2]}</span>
                        <MatchBadge v={r[3]} />
                      </div>
                    </Appear>
                  ))}
                  <div style={{ padding: '10px 16px', fontFamily: F.ui, fontSize: 12, color: C.faint }}>
                    + 38 more line items · <span style={{ color: C.red, fontWeight: 600 }}>3 flagged for review</span>
                  </div>
                </div>
              </Appear>
            </div>

            {/* right: response form */}
            <Appear at={t0 + 1.2} dur={0.5} style={{ width: 320, flexShrink: 0 }}>
              <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18, height: '100%',
                display: 'flex', flexDirection: 'column' }}>
                <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>Your response</div>
                <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute, marginTop: 3, marginBottom: 16 }}>
                  Price the matched lines, set a lead time, submit.
                </div>

                <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 6 }}>Unit price — line 01 (SAR)</div>
                <div style={{ height: 42, border: `1px solid ${lt > typeAt - 0.3 && !submitted ? C.red : C.line}`, borderRadius: 10,
                  display: 'flex', alignItems: 'center', padding: '0 13px', background: C.paper,
                  fontFamily: F.mono, fontSize: 14, color: C.text }}>
                  {typed}{!submitted && lt > typeAt && typed.length < priceFull.length &&
                    <span style={{ width: 1.5, height: 18, background: C.red, marginLeft: 1, animation: 'blink 0.8s step-end infinite' }} />}
                  {typed === '' && lt <= typeAt && <span style={{ color: C.faint }}>0.00</span>}
                </div>

                <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, margin: '14px 0 6px' }}>Lead time</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {['2 wks', '4 wks', '6 wks'].map((o, i) => (
                    <div key={o} style={{ flex: 1, height: 36, borderRadius: 9, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontFamily: F.ui, fontSize: 12.5, fontWeight: 600,
                      border: `1px solid ${i === 1 ? C.red : C.line}`, color: i === 1 ? C.red : C.mute,
                      background: i === 1 ? C.redSoft : '#fff' }}>{o}</div>
                  ))}
                </div>

                <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, margin: '14px 0 6px' }}>Note to estimator</div>
                <div style={{ height: 52, border: `1px solid ${C.line}`, borderRadius: 10, padding: '9px 13px',
                  background: C.paper, fontFamily: F.ui, fontSize: 12, color: C.faint }}>
                  Stock confirmed for cable & MCCB…
                </div>

                <div style={{ flex: 1 }} />
                {submitted ? (
                  <Appear at={t0 + submitAt + 0.2} dur={0.5} sc={0.1}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9, height: 46,
                      borderRadius: 10, background: C.greenSoft, color: C.green, fontFamily: F.ui, fontWeight: 700, fontSize: 14 }}>
                      ✓ Submitted to SEC · logged
                    </div>
                  </Appear>
                ) : (
                  <div style={{ display: 'flex', gap: 9 }}>
                    <div style={{ flex: 1, height: 46, borderRadius: 10, background: lt > submitAt ? C.redDk : C.red, color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F.ui, fontWeight: 700, fontSize: 14,
                      boxShadow: `0 10px 22px ${C.redSoft}` }}>Submit RFP</div>
                    <div style={{ width: 96, height: 46, borderRadius: 10, border: `1px solid ${C.line}`, color: C.mute,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F.ui, fontWeight: 600, fontSize: 13 }}>Decline</div>
                  </div>
                )}
              </div>
            </Appear>
          </div>
        </AppShell>
      </BrowserFrame>
      <Cursor path={cursor} />
      <style>{`@keyframes blink{50%{opacity:0}}`}</style>
    </SceneWrap>
  );
}

Object.assign(window, { SceneDashboard, SceneRFP, KpiTile, CompanyTag, StatusPill, MatchBadge });
