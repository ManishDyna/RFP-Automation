// sc-ingest.jsx — Scene 4 Discover & Ingest, Scene 5 Auto-Match

// ── Streaming console line ──────────────────────────────────────────────────
function LogLine({ at, lt, time, ts, text, tone = 'mute', last }) {
  if (lt < at) return null;
  const op = clamp((lt - at) / 0.25, 0, 1);
  const col = { mute: C.invMute, ok: C.green, hot: C.red, info: C.blue, warn: C.amber }[tone];
  return (
    <div style={{ display: 'flex', gap: 12, opacity: op, padding: '3px 0',
      fontFamily: F.mono, fontSize: 12.5, lineHeight: 1.5 }}>
      <span style={{ color: C.invFaint, flexShrink: 0 }}>{ts}</span>
      <span style={{ color: col, flexShrink: 0, width: 8 }}>{tone === 'ok' ? '✓' : '›'}</span>
      <span style={{ color: tone === 'mute' ? 'rgba(234,239,247,0.78)' : col,
        fontWeight: tone === 'mute' ? 400 : 600 }}>{text}</span>
    </div>
  );
}

function SceneIngest({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const clickAt = 2.6;
  const logStart = clickAt + 0.7;
  const LOG = [
    [0.0, '08:00:04', 'Scheduled run started — playwright/chromium', 'info'],
    [1.2, '08:00:09', 'Logging into Ariba supplier portal…', 'mute'],
    [2.4, '08:00:13', 'Session OK · scanning open events', 'ok'],
    [3.6, '08:00:18', '7 new RFPs found across SEC · Aramco · HADEED', 'hot'],
    [5.0, '08:00:24', 'Downloading BOQ — SEC RFP-C001744045.xlsx', 'mute'],
    [6.3, '08:00:29', 'Downloading BOQ — Aramco 4203238879.xlsx', 'mute'],
    [7.6, '08:00:35', 'Unprotecting workbook · normalizing columns', 'mute'],
    [8.9, '08:00:41', 'Uploaded 7 bundles → SharePoint /RFP-logs', 'ok'],
    [10.2, '08:00:46', 'Records upserted → Dataverse rfps_v2', 'ok'],
  ];
  const counter = lt < logStart + 3.6 ? 0 : Math.min(7, Math.floor((lt - (logStart + 3.6)) / 0.5) + 1);

  const cursor = [
    { t: t0 + 1.0, x: 980, y: 520 },
    { t: t0 + clickAt, x: 322, y: 232, click: true },
    { t: t0 + clickAt + 1.4, x: 322, y: 232 },
  ];

  return (
    <SceneWrap t0={t0} dur={dur}>
      <DotGrid opacity={0.22} />
      <BrowserFrame x={56} y={64} w={1168} h={584} url="app.smartrfp.io/dashboard">
        <AppShell active="Dashboard" title="Dashboard" subtitle="Automation control & live RFP feed">
          <div style={{ position: 'absolute', inset: 0, padding: 22, display: 'flex', gap: 18 }}>
            {/* left: actions + counter */}
            <div style={{ width: 318, display: 'flex', flexDirection: 'column', gap: 14, flexShrink: 0 }}>
              <Appear at={t0 + 0.5} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 16 }}>
                  <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.ink, marginBottom: 12 }}>
                    Portal automation
                  </div>
                  {/* primary button */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9,
                    height: 44, borderRadius: 10, background: lt > clickAt ? C.redDk : C.red,
                    color: '#fff', fontFamily: F.ui, fontWeight: 700, fontSize: 14,
                    boxShadow: lt > clickAt && lt < clickAt + 0.5 ? `0 0 0 4px ${C.redSoft}` : `0 8px 20px ${C.redSoft}` }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2"
                      strokeLinecap="round" strokeLinejoin="round"
                      style={{ animation: lt > clickAt && lt < logStart + 11 ? 'spin 1.1s linear infinite' : 'none' }}>
                      <path d="M21 12a9 9 0 11-3-6.7M21 4v4h-4" />
                    </svg>
                    {lt > clickAt ? 'Syncing portals…' : 'Sync Portals'}
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    {['Open RFPs', 'Historical'].map((b) => (
                      <div key={b} style={{ flex: 1, height: 36, borderRadius: 9, border: `1px solid ${C.line}`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: F.ui, fontWeight: 600, fontSize: 12.5, color: C.mute }}>{b}</div>
                    ))}
                  </div>
                </div>
              </Appear>

              <Appear at={t0 + 0.7} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 16 }}>
                  <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute, fontWeight: 600 }}>New RFPs discovered</div>
                  <div style={{ fontFamily: F.display, fontSize: 52, fontWeight: 700, color: C.ink, lineHeight: 1.1 }}>
                    {counter}<span style={{ fontSize: 22, color: C.faint }}> today</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <Pill color={C.red} bg={C.redSoft}>SEC · 3</Pill>
                    <Pill color={C.amber} bg={C.amberSoft}>Aramco · 3</Pill>
                    <Pill color={C.blue} bg={C.blueSoft}>HADEED · 1</Pill>
                  </div>
                </div>
              </Appear>

              <Appear at={t0 + 0.9} dur={0.5}>
                <div style={{ background: 'linear-gradient(135deg,#11151D,#0E141C)', borderRadius: 14, padding: 16,
                  border: `1px solid ${C.line}` }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 99, background: C.green }} />
                    <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: '#fff' }}>Scheduled cron · active</span>
                  </div>
                  <div style={{ fontFamily: F.ui, fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 6, lineHeight: 1.45 }}>
                    Runs Sun–Thu, 08:00 AST via Power Automate. No analyst has to remember to poll.
                  </div>
                </div>
              </Appear>
            </div>

            {/* right: live console */}
            <Appear at={t0 + 0.6} dur={0.5} style={{ flex: 1 }}>
              <div style={{ height: '100%', background: '#0C111A', borderRadius: 14, border: `1px solid ${C.line}`,
                overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <div style={{ height: 38, borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex',
                  alignItems: 'center', gap: 9, padding: '0 14px' }}>
                  <span style={{ width: 9, height: 9, borderRadius: 99, background: C.red }} />
                  <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 600, color: 'rgba(234,239,247,0.7)' }}>
                    automation · live log
                  </span>
                  <span style={{ marginLeft: 'auto', fontFamily: F.mono, fontSize: 11, color: C.invFaint }}>
                    download_open_rfps
                  </span>
                </div>
                <div style={{ padding: '12px 16px', flex: 1 }}>
                  {lt < logStart && (
                    <div style={{ fontFamily: F.mono, fontSize: 12.5, color: C.invFaint, paddingTop: 6 }}>
                      idle — waiting for trigger…
                    </div>
                  )}
                  {LOG.map(([a, ts, text, tone], i) => (
                    <LogLine key={i} at={logStart + a} lt={lt} ts={ts} text={text} tone={tone} />
                  ))}
                  {lt > logStart + 11 && (
                    <Appear at={t0 + logStart + 11.3} dur={0.5} style={{ marginTop: 10 }}>
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '7px 13px',
                        background: C.greenSoft, borderRadius: 8, fontFamily: F.mono, fontSize: 12.5,
                        fontWeight: 700, color: C.green }}>
                        ✓ Run complete · 7 RFPs ready to match
                      </div>
                    </Appear>
                  )}
                </div>
              </div>
            </Appear>
          </div>
        </AppShell>
      </BrowserFrame>

      {/* callout footer */}
      <Appear at={t0 + dur - 7} dur={0.6} y={12} exitAt={t0 + dur - 0.6}
        style={{ position: 'absolute', bottom: 84, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 10 }}>
        {['Playwright browser automation', 'BOQ stored in SharePoint', 'Indexed in Dataverse'].map((c) => (
          <span key={c} style={{ fontFamily: F.mono, fontSize: 12.5, fontWeight: 600, color: C.inv,
            background: C.panel2, border: `1px solid ${C.hair}`, borderRadius: 8, padding: '7px 13px' }}>{c}</span>
        ))}
      </Appear>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </SceneWrap>
  );
}

// ── Scene 5 — Auto-Match ─────────────────────────────────────────────────────
function MatchRow({ at, lt, desc, code, qty, conf, kind }) {
  const show = lt >= at;
  if (!show) return null;
  const op = clamp((lt - at) / 0.4, 0, 1);
  const col = conf >= 95 ? C.green : conf >= 60 ? C.amber : C.red;
  const label = kind === 'exact' ? 'Exact SAP code' : kind === 'kw' ? 'Keyword match' : 'Manual review';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '11px 16px',
      borderBottom: `1px solid ${C.line2}`, opacity: op,
      transform: `translateX(${(1 - op) * 14}px)` }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text,
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{desc}</div>
        <div style={{ fontFamily: F.mono, fontSize: 11, color: C.faint, marginTop: 2 }}>
          {code} · qty {qty}
        </div>
      </div>
      <div style={{ width: 130 }}>
        <GrowBar to={conf} at={lt + 0} dur={0.6} color={col} h={6} track={C.line} />
      </div>
      <div style={{ width: 116, display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: col, width: 38 }}>
          {conf === 0 ? '—' : conf + '%'}
        </span>
        <span style={{ fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, color: col,
          background: col + '1e', borderRadius: 6, padding: '2px 6px', whiteSpace: 'nowrap' }}>{label}</span>
      </div>
    </div>
  );
}

function SceneMatch({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const tokens = [
    { lbl: '4203238879', x: 96, c: C.blue },
    { lbl: 'WIRE', x: 230, c: C.green },
    { lbl: 'ELEC', x: 314, c: C.green },
    { lbl: '600V', x: 392, c: C.green },
  ];
  return (
    <SceneWrap t0={t0} dur={dur}>
      <DotGrid opacity={0.22} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 56, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.red,
          letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 9 }}>Stage 02 · Auto-Match</div>
        <div style={{ fontFamily: F.display, fontSize: 38, fontWeight: 700, color: C.inv,
          letterSpacing: '-0.02em' }}>Two-tier matching against your material master</div>
      </Appear>

      {/* top: single-line deep dive */}
      <Appear at={t0 + 1.0} dur={0.6} style={{ position: 'absolute', top: 150, left: 80, width: 470 }}>
        <div style={{ background: C.card, borderRadius: 14, border: `1px solid ${C.line}`, padding: 16,
          boxShadow: '0 20px 50px rgba(0,0,0,0.35)' }}>
          <div style={{ fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: C.faint,
            letterSpacing: '0.08em', textTransform: 'uppercase' }}>BOQ line · from the portal</div>
          <div style={{ fontFamily: F.ui, fontSize: 15, fontWeight: 700, color: C.ink, marginTop: 7, lineHeight: 1.3 }}>
            WIRE,ELEC 331MM2 (12 AWG) WHITE — 600V
          </div>
          <div style={{ fontFamily: F.mono, fontSize: 12, color: C.mute, marginTop: 4 }}>qty 5,000 M · unit EA</div>
          <div style={{ marginTop: 12, fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: C.faint,
            letterSpacing: '0.08em', textTransform: 'uppercase' }}>Extracted</div>
          <div style={{ display: 'flex', gap: 7, marginTop: 7, flexWrap: 'wrap' }}>
            {tokens.map((tk, i) => (
              <Appear key={tk.lbl} at={t0 + 2.2 + i * 0.25} dur={0.4} sc={0.2}>
                <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 700, color: tk.c,
                  background: tk.c + '18', borderRadius: 7, padding: '4px 9px' }}>
                  {i === 0 ? '#' : ''}{tk.lbl}
                </span>
              </Appear>
            ))}
          </div>
          <div style={{ marginTop: 12, fontFamily: F.ui, fontSize: 12, color: C.mute, lineHeight: 1.45 }}>
            <b style={{ color: C.text }}>Tier 1</b> — exact match on the 9-digit SAP code.
            <b style={{ color: C.text }}> Tier 2</b> — keyword substring match on name & description when the code misses.
          </div>
        </div>
      </Appear>

      {/* connector */}
      <Appear at={t0 + 3.4} dur={0.6} style={{ position: 'absolute', top: 250, left: 552, width: 86 }}>
        <svg width="86" height="40"><path d="M0 20H78M70 13l9 7-9 7" stroke={C.red} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <div style={{ fontFamily: F.mono, fontSize: 10, color: C.red, textAlign: 'center', marginTop: 2 }}>match</div>
      </Appear>

      {/* right: master hit */}
      <Appear at={t0 + 3.6} dur={0.6} style={{ position: 'absolute', top: 150, left: 648, width: 470 }}>
        <div style={{ background: C.card, borderRadius: 14, border: `2px solid ${C.green}`, padding: 16,
          boxShadow: `0 20px 50px rgba(0,0,0,0.35), 0 0 0 4px ${C.greenSoft}` }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: C.faint,
              letterSpacing: '0.08em', textTransform: 'uppercase' }}>SAP Material Master</div>
            <Pill color={C.green} bg={C.greenSoft}>✓ EXACT · 100%</Pill>
          </div>
          <div style={{ fontFamily: F.mono, fontSize: 14, fontWeight: 700, color: C.green, marginTop: 9 }}>4203238879</div>
          <div style={{ fontFamily: F.ui, fontSize: 14, fontWeight: 700, color: C.ink, marginTop: 3, lineHeight: 1.3 }}>
            CABLE, ELEC 1×3.31MM² 600V WHITE PVC
          </div>
          <div style={{ display: 'flex', gap: 18, marginTop: 11 }}>
            {[['Group', 'Cables / LV'], ['Unit', 'Metre'], ['Stock', 'Active']].map(([k, v]) => (
              <div key={k}>
                <div style={{ fontFamily: F.ui, fontSize: 10.5, color: C.faint }}>{k}</div>
                <div style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      </Appear>

      {/* bottom: batch table + overall rate */}
      <Appear at={t0 + 6.0} dur={0.6} style={{ position: 'absolute', top: 390, left: 80, width: 760 }}>
        <div style={{ background: C.card, borderRadius: 14, border: `1px solid ${C.line}`, overflow: 'hidden',
          boxShadow: '0 18px 44px rgba(0,0,0,0.3)' }}>
          <div style={{ padding: '11px 16px', borderBottom: `1px solid ${C.line}`, fontFamily: F.ui,
            fontWeight: 700, fontSize: 13, color: C.ink, display: 'flex', justifyContent: 'space-between' }}>
            <span>BOQ — SEC RFP-C001744045 · 42 line items</span>
            <span style={{ fontFamily: F.mono, fontSize: 12, color: C.mute }}>auto-matching…</span>
          </div>
          <MatchRow at={6.6} lt={lt} desc="WIRE,ELEC 331MM2 (12 AWG) WHITE — 600V" code="#4203238879" qty="5,000 M" conf={100} kind="exact" />
          <MatchRow at={7.1} lt={lt} desc="CIRCUIT BREAKER MCCB 250A 3P 36KA" code="#4109887421" qty="24 EA" conf={100} kind="exact" />
          <MatchRow at={7.6} lt={lt} desc="CABLE GLAND BRASS 32MM IP68 WEATHERPROOF" code="kw: gland·brass·32mm" qty="180 EA" conf={82} kind="kw" />
          <MatchRow at={8.1} lt={lt} desc="BUSBAR SUPPORT INSULATOR — CUSTOM 1100V" code="no code · ambiguous" qty="60 EA" conf={0} kind="manual" />
        </div>
      </Appear>

      {/* overall rate card */}
      <Appear at={t0 + 8.6} dur={0.6} y={20} style={{ position: 'absolute', top: 390, left: 872, width: 246 }}>
        <div style={{ background: 'linear-gradient(135deg,#11151D,#0E141C)', borderRadius: 14,
          border: `1px solid ${C.hair}`, padding: 20, textAlign: 'center' }}>
          <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.invMute }}>Auto-matched this RFP</div>
          <div style={{ fontFamily: F.display, fontSize: 60, fontWeight: 700, color: C.green, lineHeight: 1.1 }}>
            <Count to={73} suffix="%" at={t0 + 9.0} dur={1.2} />
          </div>
          <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.invMute, lineHeight: 1.4 }}>
            of line items matched with no human lookup
          </div>
          <div style={{ height: 1, background: C.hair, margin: '14px 0' }} />
          <div style={{ fontFamily: F.ui, fontSize: 12, color: C.invMute, lineHeight: 1.4 }}>
            The rest are flagged for a <span style={{ color: C.amber, fontWeight: 700 }}>one-click review</span> — never silently wrong.
          </div>
        </div>
      </Appear>
    </SceneWrap>
  );
}

Object.assign(window, { SceneIngest, SceneMatch });
