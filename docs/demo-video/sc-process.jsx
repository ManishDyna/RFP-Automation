// sc-process.jsx — Full-feature walkthrough scenes (process + animated clicks):
//   SceneStorage  · Dataverse + SharePoint single source of truth
//   SceneSubmit   · end-to-end submission flow (upload → click → portal)
//   SceneDecline  · decline-participation flow
//   SceneSchedule · unattended scheduled automation
//   FeatIntro / FeatChapter / FeatOutro · framing cards
// Dark kit (C, F, BrowserFrame, AppShell, Cursor, Appear, Pill, Count, GrowBar, DotGrid).

// ── Small atoms ──────────────────────────────────────────────────────────────
function FileChip({ show, name, kind, color }) {
  if (!show) return null;
  return (
    <Appear at={0} dur={0.01} style={{ display: 'inline-flex' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 9, padding: '7px 12px',
        background: '#fff', border: `1px solid ${C.line}`, borderRadius: 9, boxShadow: '0 6px 16px rgba(0,0,0,0.08)' }}>
        <span style={{ width: 24, height: 24, borderRadius: 6, background: color, display: 'flex',
          alignItems: 'center', justifyContent: 'center', color: '#fff', fontFamily: F.ui, fontWeight: 800, fontSize: 9 }}>{kind}</span>
        <span style={{ fontFamily: F.ui, fontWeight: 600, fontSize: 12, color: C.text }}>{name}</span>
        <span style={{ color: C.green, fontWeight: 800 }}>✓</span>
      </div>
    </Appear>
  );
}

// pipeline step that lights up at `at`
function StepRow({ at, lt, text, sub, done }) {
  const on = lt >= at;
  const op = clamp((lt - at) / 0.4, 0, 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '9px 0', opacity: on ? 1 : 0.32,
      transform: `translateX(${(1 - (on ? op : 0)) * 10}px)`, transition: 'none' }}>
      <span style={{ width: 24, height: 24, borderRadius: 99, flexShrink: 0, marginTop: 1,
        background: on ? C.green : 'transparent', border: on ? 'none' : `2px solid ${C.hair2}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: 13, fontWeight: 800 }}>
        {on ? '✓' : ''}</span>
      <div>
        <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13.5, color: C.inv }}>{text}</div>
        {sub && <div style={{ fontFamily: F.mono, fontSize: 11.5, color: C.invMute, marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  );
}

function FieldBox({ label, value, accent }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontFamily: F.ui, fontSize: 11.5, fontWeight: 700, color: C.faint, marginBottom: 5 }}>{label}</div>
      <div style={{ height: 40, border: `1px solid ${accent ? C.red : C.line}`, borderRadius: 9, background: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 13px',
        fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text }}>
        {value}<span style={{ color: C.mute }}>▾</span>
      </div>
    </div>
  );
}

function PrimaryBtn({ label, busy, pressed, color = C.red, icon }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9, height: 46, borderRadius: 11,
      background: pressed ? C.redDk : color, color: '#fff', fontFamily: F.ui, fontWeight: 800, fontSize: 14.5,
      boxShadow: pressed ? `0 0 0 5px ${C.redSoft}` : `0 10px 24px ${C.redSoft}` }}>
      {busy && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round"
        style={{ animation: 'spin 1s linear infinite' }}><path d="M21 12a9 9 0 11-3-6.7M21 4v4h-4"/></svg>}
      {label}
    </div>
  );
}

function FeatHeader({ t0, kicker, title }) {
  return (
    <Appear at={t0 + 0.2} dur={0.55} style={{ position: 'absolute', top: 30, left: 0, right: 0, textAlign: 'center', zIndex: 5 }}>
      <div style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 700, color: C.red, letterSpacing: '0.16em', textTransform: 'uppercase', marginBottom: 7 }}>{kicker}</div>
      <div style={{ fontFamily: F.display, fontSize: 27, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>{title}</div>
    </Appear>
  );
}

// ── Scene: Storage — Dataverse + SharePoint ─────────────────────────────────
function SceneStorage({ t0, dur }) {
  const time = useTime(); const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.2} />
      <FeatHeader t0={t0} kicker="Persisted · governed" title="One source of truth — Dataverse + SharePoint" />

      {/* source bundle */}
      <Appear at={t0 + 0.8} dur={0.6} sc={0.06} style={{ position: 'absolute', top: 300, left: 110, width: 250 }}>
        <div style={{ background: C.card, borderRadius: 14, padding: 18, boxShadow: '0 22px 50px rgba(0,0,0,0.4)', border: `1px solid ${C.line}` }}>
          <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: C.ink }}>Processed RFP bundle</div>
          <div style={{ fontFamily: F.mono, fontSize: 11.5, color: C.mute, marginTop: 4 }}>SEC · RFP-C001744045</div>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {['42 matched line items', '5 product assignments', 'BOQ + TDS files'].map(x =>
              <div key={x} style={{ fontFamily: F.ui, fontSize: 12, color: C.text, display: 'flex', gap: 7 }}>
                <span style={{ color: C.green }}>•</span>{x}</div>)}
          </div>
        </div>
      </Appear>

      {/* connectors */}
      <Appear at={t0 + 1.6} dur={0.6} style={{ position: 'absolute', top: 250, left: 360, width: 230, height: 240 }}>
        <svg width="230" height="240" fill="none">
          <path d="M0 110 C90 110 90 60 200 60" stroke={C.blue} strokeWidth="2.5" strokeDasharray="5 5" />
          <path d="M0 130 C90 130 90 185 200 185" stroke={C.violet} strokeWidth="2.5" strokeDasharray="5 5" />
        </svg>
      </Appear>

      {/* Dataverse card */}
      <Appear at={t0 + 2.0} dur={0.6} y={20} style={{ position: 'absolute', top: 200, left: 600, width: 540 }}>
        <div style={{ background: C.card, borderRadius: 14, border: `1px solid ${C.line}`, padding: 16, boxShadow: '0 18px 44px rgba(0,0,0,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: C.blueSoft, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={C.blue} strokeWidth="2"><ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg></span>
            <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: C.ink }}>Microsoft Dataverse</div>
            <Pill color={C.blue} bg={C.blueSoft} style={{ marginLeft: 'auto' }}>OData v9.2</Pill>
          </div>
          {[['cr673_bahra_rfps_v2', 'RFP + activity rows'], ['line items', '42 upserted'], ['responses', 'price · lead time · decline']].map(([a, b], i) => (
            <div key={a} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 11px',
              background: lt > 2.6 + i * 0.4 ? C.blueSoft : C.line2, borderRadius: 8, marginBottom: 6,
              opacity: lt > 2.4 + i * 0.4 ? 1 : 0.3 }}>
              <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 600, color: C.text }}>{a}</span>
              <span style={{ fontFamily: F.ui, fontSize: 11.5, color: C.mute }}>{b} {lt > 2.6 + i * 0.4 && <span style={{ color: C.green, fontWeight: 800 }}>✓</span>}</span>
            </div>
          ))}
        </div>
      </Appear>

      {/* SharePoint card */}
      <Appear at={t0 + 3.4} dur={0.6} y={20} style={{ position: 'absolute', top: 392, left: 600, width: 540 }}>
        <div style={{ background: C.card, borderRadius: 14, border: `1px solid ${C.line}`, padding: 16, boxShadow: '0 18px 44px rgba(0,0,0,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <span style={{ width: 30, height: 30, borderRadius: 8, background: C.greenSoft, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={C.green} strokeWidth="2"><path d="M3 7a2 2 0 012-2h5l2 2h7a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg></span>
            <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: C.ink }}>SharePoint · /ALLRFPs</div>
            <Pill color={C.green} bg={C.greenSoft} style={{ marginLeft: 'auto' }}>via MS Graph</Pill>
          </div>
          <div style={{ fontFamily: F.mono, fontSize: 11.5, color: C.text }}>
            {[['📁 ALLRFPs / Saudi Energy /', 0, 'company portal'],
              ['   📁 SEC RFP-C001744045 / download-file /', 1, 'downloaded RFP .xls'],
              ['   📁 TDS-files /', 1, 'technical datasheets'],
              ['   📁 Pricing-file /', 1, 'priced workbook'],
              ['   📁 upload-rfp-file /', 1, 'submitted package']].map(([line, depth, note], i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '4px 0',
                opacity: lt > 3.9 + i * 0.3 ? 1 : 0.25, color: depth === 0 ? C.ink : C.mute, fontWeight: depth === 0 ? 700 : 500 }}>
                <span>{line}</span>
                <span style={{ fontFamily: F.ui, fontSize: 10.5, color: C.faint, whiteSpace: 'nowrap', marginLeft: 10 }}>· {note}</span>
              </div>
            ))}
          </div>
        </div>
      </Appear>

      <Appear at={t0 + dur - 4.5} dur={0.6} y={12} style={{ position: 'absolute', bottom: 78, left: 0, right: 0, textAlign: 'center' }}>
        <span style={{ fontFamily: F.ui, fontSize: 14, color: C.invMute }}>Every record is <b style={{ color: C.inv }}>attributed, timestamped</b> and governed by role-based access — a full audit trail, automatically.</span>
      </Appear>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </SceneWrap>
  );
}

// ── Scene: Submit flow ───────────────────────────────────────────────────────
function SceneSubmit({ t0, dur }) {
  const time = useTime(); const lt = time - t0;
  const upXlsx = 3.0, upPdf = 4.8, submitAt = 7.0, doneAt = 8.2;
  const busy = lt > submitAt && lt < submitAt + 1.2;
  const cursor = [
    { t: t0 + 1.0, x: 980, y: 250 },
    { t: t0 + upXlsx - 0.2, x: 640, y: 330, click: true },
    { t: t0 + upPdf - 0.2, x: 640, y: 410, click: true },
    { t: t0 + submitAt - 0.2, x: 470, y: 560, click: true },
    { t: t0 + submitAt + 1.0, x: 470, y: 560 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur}>
      <DotGrid opacity={0.2} />
      <BrowserFrame x={56} y={70} w={1168} h={580} url="app.smartrfp.io/submit">
        <AppShell active="Open RFP" title="Submit Response" subtitle="Send the priced package back to the customer portal">
          <div style={{ position: 'absolute', inset: 0, padding: 22, display: 'flex', gap: 18 }}>
            {/* form */}
            <div style={{ width: 440, flexShrink: 0 }}>
              <Appear at={t0 + 0.4} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18 }}>
                  <FieldBox label="Open RFP" value="SEC · RFP-C001744045" />
                  <FieldBox label="Customer / portal" value="Saudi Energy (SEC)" />
                  {/* upload excel */}
                  <div style={{ fontFamily: F.ui, fontSize: 11.5, fontWeight: 700, color: C.faint, marginBottom: 5 }}>Filled BOQ (Excel)</div>
                  <div style={{ minHeight: 44, border: `1.5px dashed ${lt > upXlsx - 0.3 && lt < upXlsx + 0.4 ? C.red : C.line}`, borderRadius: 9,
                    display: 'flex', alignItems: 'center', padding: '6px 12px', marginBottom: 12, background: C.paper }}>
                    {lt > upXlsx ? <FileChip show name="C001744045-priced.xlsx" kind="XLS" color="#1D7044" />
                      : <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.faint }}>⬆ Click to upload the priced workbook</span>}
                  </div>
                  {/* upload pdf */}
                  <div style={{ fontFamily: F.ui, fontSize: 11.5, fontWeight: 700, color: C.faint, marginBottom: 5 }}>Technical datasheets (PDF)</div>
                  <div style={{ minHeight: 44, border: `1.5px dashed ${lt > upPdf - 0.3 && lt < upPdf + 0.4 ? C.red : C.line}`, borderRadius: 9,
                    display: 'flex', alignItems: 'center', padding: '6px 12px', marginBottom: 16, background: C.paper }}>
                    {lt > upPdf ? <FileChip show name="cable-datasheets.pdf" kind="PDF" color="#C0322B" />
                      : <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.faint }}>⬆ Optional technical attachments</span>}
                  </div>
                  <PrimaryBtn label={busy ? 'Submitting…' : lt > doneAt ? 'Submitted' : 'Submit to portal'} busy={busy}
                    pressed={lt > submitAt - 0.1 && lt < submitAt + 0.5} color={lt > doneAt ? C.green : C.red} />
                </div>
              </Appear>
            </div>

            {/* what happens */}
            <Appear at={t0 + 0.6} dur={0.5} style={{ flex: 1 }}>
              <div style={{ height: '100%', background: 'linear-gradient(135deg,#11151D,#0E141C)', borderRadius: 14,
                border: `1px solid ${C.line}`, padding: '18px 22px' }}>
                <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: '#fff', marginBottom: 6 }}>What happens on Submit</div>
                <div style={{ fontFamily: F.ui, fontSize: 12, color: C.invMute, marginBottom: 8 }}>Driven by Playwright — no manual portal work.</div>
                <StepRow at={submitAt + 0.3} lt={lt} text="Files uploaded to SharePoint" sub="/RFP-logs/C001744045/TDS/" />
                <StepRow at={submitAt + 1.1} lt={lt} text="Logs into the supplier portal" sub="session restored · Ariba/SEC" />
                <StepRow at={submitAt + 1.9} lt={lt} text="Attaches package & posts response" sub="price · lead time · documents" />
                <StepRow at={submitAt + 2.7} lt={lt} text="Status flips to Submitted" sub="written to Dataverse · activity logged" />
                {lt > submitAt + 3.4 && (
                  <Appear at={t0 + submitAt + 3.6} dur={0.5} sc={0.06} style={{ marginTop: 8 }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 9, padding: '9px 14px', background: C.greenSoft, borderRadius: 10 }}>
                      <span style={{ width: 22, height: 22, borderRadius: 99, background: C.green, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>✓</span>
                      <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.green }}>Submitted to SEC · receipt logged</span>
                    </div>
                  </Appear>
                )}
              </div>
            </Appear>
          </div>
        </AppShell>
      </BrowserFrame>
      <Cursor path={cursor} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </SceneWrap>
  );
}

// ── Scene: Decline flow ──────────────────────────────────────────────────────
function SceneDecline({ t0, dur }) {
  const time = useTime(); const lt = time - t0;
  const openAt = 2.2, pickAt = 3.4, declineAt = 5.2, doneAt = 6.2;
  const dropOpen = lt > openAt && lt < pickAt + 0.2;
  const reason = lt > pickAt ? 'Not in scope — no matching products' : null;
  const cursor = [
    { t: t0 + 1.0, x: 900, y: 250 },
    { t: t0 + openAt - 0.2, x: 470, y: 322, click: true },
    { t: t0 + pickAt - 0.2, x: 470, y: 372, click: true },
    { t: t0 + declineAt - 0.2, x: 470, y: 470, click: true },
    { t: t0 + declineAt + 1.0, x: 470, y: 470 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur}>
      <DotGrid opacity={0.2} />
      <BrowserFrame x={56} y={70} w={1168} h={580} url="app.smartrfp.io/decline">
        <AppShell active="Open RFP" title="Decline Participation" subtitle="Record a no-bid and notify the customer">
          <div style={{ position: 'absolute', inset: 0, padding: 22, display: 'flex', gap: 18 }}>
            <div style={{ width: 440, flexShrink: 0 }}>
              <Appear at={t0 + 0.4} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18, position: 'relative' }}>
                  <FieldBox label="Open RFP" value="HADEED · RAJHI-22112" />
                  {/* reason dropdown */}
                  <div style={{ fontFamily: F.ui, fontSize: 11.5, fontWeight: 700, color: C.faint, marginBottom: 5 }}>Reason for declining</div>
                  <div style={{ height: 40, border: `1px solid ${lt > openAt - 0.3 ? C.red : C.line}`, borderRadius: 9, background: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 13px',
                    fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: reason ? C.text : C.faint, position: 'relative', zIndex: 2 }}>
                    {reason || 'Select a reason…'}<span style={{ color: C.mute }}>▾</span>
                  </div>
                  {dropOpen && (
                    <div style={{ position: 'absolute', left: 18, right: 18, top: 124, background: '#fff', border: `1px solid ${C.line}`,
                      borderRadius: 10, boxShadow: '0 16px 36px rgba(0,0,0,0.18)', zIndex: 5, overflow: 'hidden' }}>
                      {['Not in scope — no matching products', 'No capacity in the window', 'Pricing not viable'].map((o, i) => (
                        <div key={o} style={{ padding: '10px 13px', fontFamily: F.ui, fontSize: 12.5, fontWeight: i === 0 ? 700 : 500,
                          color: i === 0 ? C.red : C.text, background: i === 0 ? C.redSoft : '#fff' }}>{o}</div>
                      ))}
                    </div>
                  )}
                  <div style={{ height: 16 }} />
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9, height: 46, borderRadius: 11,
                    background: lt > doneAt ? C.green : '#fff', border: `1.5px solid ${lt > doneAt ? C.green : C.red}`,
                    color: lt > doneAt ? '#fff' : C.red, fontFamily: F.ui, fontWeight: 800, fontSize: 14.5,
                    boxShadow: lt > declineAt - 0.1 && lt < declineAt + 0.5 ? `0 0 0 5px ${C.redSoft}` : 'none' }}>
                    {lt > doneAt ? '✓ Declined' : 'Decline participation'}
                  </div>
                </div>
              </Appear>
            </div>
            <Appear at={t0 + 0.6} dur={0.5} style={{ flex: 1 }}>
              <div style={{ height: '100%', background: 'linear-gradient(135deg,#11151D,#0E141C)', borderRadius: 14, border: `1px solid ${C.line}`, padding: '18px 22px' }}>
                <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: '#fff', marginBottom: 10 }}>One click — fully recorded</div>
                <StepRow at={declineAt + 0.3} lt={lt} text="Decline posted to the customer portal" sub="Playwright · no manual login" />
                <StepRow at={declineAt + 1.0} lt={lt} text="Reason + actor written to Dataverse" sub="who declined, when, and why" />
                <StepRow at={declineAt + 1.7} lt={lt} text="RFP marked Not Participated" sub="removed from the open board" />
                {lt > declineAt + 2.3 && (
                  <Appear at={t0 + declineAt + 2.5} dur={0.5} style={{ marginTop: 8 }}>
                    <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.invMute, lineHeight: 1.5 }}>
                      No silent drop-outs — declines are auditable evidence, just like wins.</div>
                  </Appear>
                )}
              </div>
            </Appear>
          </div>
        </AppShell>
      </BrowserFrame>
      <Cursor path={cursor} />
    </SceneWrap>
  );
}

// ── Scene: Schedule automation ───────────────────────────────────────────────
function SceneSchedule({ t0, dur }) {
  const time = useTime(); const lt = time - t0;
  const toggleAt = 3.0;
  const on = lt > toggleAt;
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const cursor = [
    { t: t0 + 1.2, x: 900, y: 250 },
    { t: t0 + toggleAt - 0.2, x: 470, y: 470, click: true },
    { t: t0 + toggleAt + 1.0, x: 470, y: 470 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur}>
      <DotGrid opacity={0.2} />
      <BrowserFrame x={56} y={70} w={1168} h={580} url="app.smartrfp.io/settings/schedule">
        <AppShell active="System Settings" title="Schedule Automation" subtitle="Run discovery unattended — set it once" showAdmin>
          <div style={{ position: 'absolute', inset: 0, padding: 22, display: 'flex', gap: 18 }}>
            <div style={{ width: 440, flexShrink: 0 }}>
              <Appear at={t0 + 0.4} dur={0.5}>
                <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18 }}>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ flex: 1 }}><FieldBox label="Frequency" value="Every 1 day" /></div>
                    <div style={{ flex: 1 }}><FieldBox label="Time zone" value="Asia/Riyadh" /></div>
                  </div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div style={{ flex: 1 }}><FieldBox label="Start time" value="08:00 AST" /></div>
                    <div style={{ flex: 1 }}><FieldBox label="Action" value="Download open RFPs" /></div>
                  </div>
                  {/* toggle */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6,
                    padding: '12px 14px', borderRadius: 11, background: on ? C.greenSoft : C.line2, border: `1px solid ${on ? C.green : C.line}` }}>
                    <div>
                      <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: C.ink }}>Scheduled automation</div>
                      <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute }}>{on ? 'Enabled — running unattended' : 'Disabled'}</div>
                    </div>
                    <div style={{ width: 54, height: 30, borderRadius: 99, background: on ? C.green : '#C7CFDA', position: 'relative',
                      boxShadow: lt > toggleAt - 0.1 && lt < toggleAt + 0.5 ? `0 0 0 5px ${C.greenSoft}` : 'none' }}>
                      <div style={{ position: 'absolute', top: 3, left: on ? 27 : 3, width: 24, height: 24, borderRadius: 99, background: '#fff', boxShadow: '0 2px 5px rgba(0,0,0,0.25)' }} />
                    </div>
                  </div>
                </div>
              </Appear>
            </div>
            {/* week strip */}
            <Appear at={t0 + 0.6} dur={0.5} style={{ flex: 1 }}>
              <div style={{ height: '100%', background: 'linear-gradient(135deg,#11151D,#0E141C)', borderRadius: 14, border: `1px solid ${C.line}`, padding: '18px 22px' }}>
                <div style={{ fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: '#fff', marginBottom: 4 }}>Unattended cron · Power Automate</div>
                <div style={{ fontFamily: F.ui, fontSize: 12, color: C.invMute, marginBottom: 16 }}>Runs every morning, Sunday to Thursday.</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {days.map((d, i) => {
                    const work = i <= 4;
                    const fire = on && work && lt > toggleAt + 0.6 + i * 0.25;
                    return (
                      <div key={d} style={{ flex: 1, textAlign: 'center' }}>
                        <div style={{ height: 70, borderRadius: 10, border: `1px solid ${work ? C.hair2 : C.hair}`,
                          background: fire ? C.greenSoft : 'rgba(255,255,255,0.03)', display: 'flex', flexDirection: 'column',
                          alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                          {work ? <>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={fire ? C.green : C.invFaint} strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
                            <span style={{ fontFamily: F.mono, fontSize: 9, color: fire ? C.green : C.invFaint }}>08:00</span>
                          </> : <span style={{ fontFamily: F.mono, fontSize: 10, color: C.invFaint }}>—</span>}
                        </div>
                        <div style={{ fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: work ? C.inv : C.invFaint, marginTop: 6 }}>{d}</div>
                      </div>
                    );
                  })}
                </div>
                {on && lt > toggleAt + 2.2 && (
                  <Appear at={t0 + toggleAt + 2.4} dur={0.5} style={{ marginTop: 16 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span style={{ width: 9, height: 9, borderRadius: 99, background: C.green }} />
                      <span style={{ fontFamily: F.ui, fontSize: 13, color: C.inv }}>Next run <b>tomorrow 08:00 AST</b> — no analyst has to remember to poll.</span>
                    </div>
                  </Appear>
                )}
              </div>
            </Appear>
          </div>
        </AppShell>
      </BrowserFrame>
      <Cursor path={cursor} />
    </SceneWrap>
  );
}

// ── Framing cards ────────────────────────────────────────────────────────────
function FeatIntro({ t0, dur }) {
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.28} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
        <Appear at={t0 + 0.3} dur={0.6}><Logo size={50} /></Appear>
        <Appear at={t0 + 0.8} dur={0.7} y={22}>
          <div style={{ fontFamily: F.display, fontSize: 54, fontWeight: 700, color: C.inv, letterSpacing: '-0.03em', textAlign: 'center' }}>The Full Feature Walkthrough</div>
        </Appear>
        <Appear at={t0 + 1.3} dur={0.7} y={16}>
          <div style={{ fontFamily: F.ui, fontSize: 19, color: C.invMute, textAlign: 'center', maxWidth: 760, lineHeight: 1.5 }}>
            Every high-value step, end to end — discover, match, store, route, remind, submit, decline, schedule and analyse.
          </div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

function FeatChapter({ t0, dur, n, title, sub }) {
  const time = useTime(); const lt = time - t0;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.22} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
        <Appear at={t0 + 0.1} dur={0.5} sc={0.3}>
          <div style={{ fontFamily: F.mono, fontSize: 100, fontWeight: 700, lineHeight: 1,
            background: `linear-gradient(135deg,${C.red},${C.amber})`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{String(n).padStart(2, '0')}</div>
        </Appear>
        <Appear at={t0 + 0.35} dur={0.5} y={14}>
          <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>{title}</div>
        </Appear>
        <Appear at={t0 + 0.55} dur={0.5} y={10}>
          <div style={{ fontFamily: F.ui, fontSize: 17, color: C.invMute }}>{sub}</div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

function FeatOutro({ t0, dur }) {
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.28} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 22 }}>
        <Appear at={t0 + 0.3} dur={0.7}><Logo size={58} /></Appear>
        <Appear at={t0 + 0.8} dur={0.7} y={20}>
          <div style={{ fontFamily: F.display, fontSize: 38, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em', textAlign: 'center', maxWidth: 880, lineHeight: 1.3 }}>
            Nine features. One governed pipeline. Zero manual re-entry.
          </div>
        </Appear>
        <Appear at={t0 + 1.5} dur={0.7} y={14}>
          <div style={{ fontFamily: F.ui, fontSize: 18, color: C.invMute }}>From RFP to quote — automated, end to end.</div>
        </Appear>
      </div>
    </SceneWrap>
  );
}

Object.assign(window, { SceneStorage, SceneSubmit, SceneDecline, SceneSchedule, FeatIntro, FeatChapter, FeatOutro });
