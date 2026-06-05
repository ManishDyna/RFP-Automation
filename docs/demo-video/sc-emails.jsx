// sc-emails.jsx — Real Bahra email templates, recreated faithfully for video.
// Replaces the illustrated adaptive-card scene with the actual product emails:
//   1. New RFP assignment card (interactive: Results/Remarks dropdowns + Upload File)
//   2. Team response status email (3/5 answered + Refresh Status)
//   3. URGENT 1-day deadline reminder
// Light-mode email cards shown inside a clean Outlook-style reading pane.

// ── Generic Outlook reading-pane frame ──────────────────────────────────────
function MailFrame({ x, y, w, h, from, to, subject, when, children }) {
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, background: C.card,
      borderRadius: 14, overflow: 'hidden', boxShadow: '0 40px 90px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
      display: 'flex', flexDirection: 'column' }}>
      {/* outlook titlebar */}
      <div style={{ height: 38, background: '#0E4B8C', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 10, flexShrink: 0 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="#fff"><rect x="2" y="5" width="13" height="14" rx="2"/><path d="M2 7l6.5 4L15 7" stroke="#0E4B8C" strokeWidth="1.6" fill="none"/><path d="M15 9h7v8a2 2 0 01-2 2h-5z" opacity="0.7"/></svg>
        <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: '#fff' }}>Outlook</span>
        <span style={{ marginLeft: 'auto', fontFamily: F.ui, fontSize: 12, color: 'rgba(255,255,255,0.72)' }}>{when}</span>
      </div>
      {/* mail header */}
      <div style={{ padding: '15px 26px 13px', borderBottom: `1px solid ${C.line}`, flexShrink: 0 }}>
        <div style={{ fontFamily: F.display, fontSize: 18, fontWeight: 700, color: C.ink, letterSpacing: '-0.02em' }}>{subject}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
          <div style={{ width: 30, height: 30, borderRadius: 99, background: 'linear-gradient(135deg,#7A5CFF,#2C7BF2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontFamily: F.ui, fontWeight: 700, fontSize: 12 }}>D</div>
          <div style={{ fontFamily: F.ui, fontSize: 12.5, color: C.text }}>
            <span style={{ fontWeight: 700 }}>{from}</span>
            <span style={{ color: C.mute }}>{'  ·  to '}{to}</span>
          </div>
        </div>
      </div>
      {/* body */}
      <div style={{ flex: 1, padding: '20px 26px', overflow: 'hidden', position: 'relative' }}>{children}</div>
    </div>
  );
}

// ── Shared mini table ───────────────────────────────────────────────────────
function ResultText({ v }) {
  const map = { No: C.green, Yes: C.green, Pending: C.blue };
  return <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: map[v] || C.mute }}>{v}</span>;
}

// Recreates the "New RFP" assignment email with the live dropdown + status flip.
function EmailNewRFP({ lt }) {
  // interactive beat: open Results (Yes/No) -> pick Yes -> open Remarks (Create TIR / Not in scope) -> pick -> row answered
  const openResAt = 4.0, pickResAt = 5.4, openRemAt = 6.4, pickRemAt = 7.6, doneAt = 8.6;
  const resDropOpen = lt > openResAt && lt < pickResAt + 0.15;
  const remDropOpen = lt > openRemAt && lt < pickRemAt + 0.15;
  const resVal = lt > pickResAt ? 'Yes' : null;
  const remVal = lt > pickRemAt ? 'Create TIR' : null;
  const openAt = openResAt;
  const rows = [
    ['TBS and BED', 'mohammad.ariff@bahra-electric.com', true],
    ['TBS and BED', 'intikhab.ali@bahra-cables.com', false],
    ['Non-Cables', 'karim.ahmad@bahra-cables.com', false],
    ['Cable Accessories', 'ahmed.ebeed@bahra-cables.com', false],
    ['Cables', 'lotfy.mohammad@bahra-electric.com', false],
  ];
  const head = ['Products', 'Email', 'Results', 'Remarks', 'Upload File'];
  const col = [150, 250, 130, 130, 110];
  return (
    <div>
      <div style={{ fontFamily: F.ui, fontSize: 13.5, color: C.text, marginBottom: 4 }}>Dear's,</div>
      <div style={{ fontFamily: F.ui, fontSize: 13.5, color: C.text, marginBottom: 14 }}>Kindly advise us regarding to the attached file</div>
      {/* table */}
      <div style={{ border: `1px solid ${C.line}`, borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ display: 'flex', background: '#F0F2F6', borderBottom: `1px solid ${C.line}` }}>
          {head.map((h, i) => (
            <div key={h} style={{ width: col[i], padding: '9px 12px', fontFamily: F.ui, fontWeight: 700, fontSize: 11.5, color: C.text }}>{h}</div>
          ))}
        </div>
        {rows.map(([prod, email, active], r) => {
          const answered = active && lt > doneAt;
          return (
            <div key={r} style={{ display: 'flex', alignItems: 'center', borderBottom: r < rows.length - 1 ? `1px solid ${C.line2}` : 'none',
              background: answered ? C.greenSoft : active ? 'rgba(44,123,242,0.05)' : '#fff', height: 40 }}>
              <div style={{ width: col[0], padding: '0 12px', fontFamily: F.ui, fontWeight: 700, fontSize: 12, color: C.ink }}>{prod}</div>
              <div style={{ width: col[1], padding: '0 12px', fontFamily: F.ui, fontSize: 11.5, color: C.mute, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</div>
              {/* Results */}
              <div style={{ width: col[2], padding: '0 12px', position: 'relative' }}>
                {active ? (
                  resVal
                    ? <ResultText v={resVal} />
                    : <div style={{ height: 28, border: `1px solid ${lt > openAt - 0.3 ? C.red : C.line}`, borderRadius: 7, display: 'flex',
                        alignItems: 'center', justifyContent: 'space-between', padding: '0 8px', fontFamily: F.ui, fontSize: 11, color: C.faint, background: '#fff' }}>
                        Select…<span style={{ color: C.mute }}>▾</span>
                      </div>
                ) : <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: C.amber, fontStyle: 'italic' }}>Pending</span>}
                {active && resDropOpen && (
                  <div style={{ position: 'absolute', top: 30, left: 12, width: 92, background: '#fff', border: `1px solid ${C.line}`,
                    borderRadius: 8, boxShadow: '0 12px 28px rgba(0,0,0,0.18)', zIndex: 6, overflow: 'hidden' }}>
                    {['Yes', 'No'].map((o, i) => (
                      <div key={o} style={{ padding: '8px 11px', fontFamily: F.ui, fontSize: 12.5, fontWeight: 700,
                        color: i === 0 ? C.green : C.red, background: i === 0 ? C.greenSoft : '#fff' }}>{o}</div>
                    ))}
                  </div>
                )}
              </div>
              {/* Remarks */}
              <div style={{ width: col[3], padding: '0 12px', position: 'relative' }}>
                {active ? (
                  remVal
                    ? <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12, color: C.green }}>{remVal}</span>
                    : <div style={{ height: 28, border: `1px solid ${lt > openRemAt - 0.3 && resVal ? C.red : C.line}`, borderRadius: 7, display: 'flex', alignItems: 'center',
                        justifyContent: 'space-between', padding: '0 8px', fontFamily: F.ui, fontSize: 11, color: C.faint, background: '#fff' }}>
                        Select…<span style={{ color: C.mute }}>▾</span>
                      </div>
                ) : <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: C.amber, fontStyle: 'italic' }}>Pending</span>}
                {active && remDropOpen && (
                  <div style={{ position: 'absolute', top: 30, left: 12, width: 124, background: '#fff', border: `1px solid ${C.line}`,
                    borderRadius: 8, boxShadow: '0 12px 28px rgba(0,0,0,0.18)', zIndex: 6, overflow: 'hidden' }}>
                    {['Create TIR', 'Not in scope'].map((o, i) => (
                      <div key={o} style={{ padding: '8px 11px', fontFamily: F.ui, fontSize: 12, fontWeight: 700,
                        color: i === 0 ? C.green : C.text, background: i === 0 ? C.greenSoft : '#fff', whiteSpace: 'nowrap' }}>{o}</div>
                    ))}
                  </div>
                )}
              </div>
              {/* Upload */}
              <div style={{ width: col[4], padding: '0 12px' }}>
                <div style={{ height: 28, borderRadius: 7, background: C.blue, color: '#fff', display: 'inline-flex', alignItems: 'center',
                  padding: '0 12px', fontFamily: F.ui, fontWeight: 700, fontSize: 11 }}>Upload File</div>
              </div>
            </div>
          );
        })}
      </div>
      {/* due-date note */}
      <div style={{ marginTop: 14, padding: '9px 12px', background: '#FFF7C2', borderRadius: 7, fontFamily: F.ui, fontSize: 12.5, color: '#5C4B00' }}>
        Note: the due date for <b>Sample RFP Title</b> is 3/15/2026
      </div>
      <div style={{ marginTop: 12, fontFamily: F.ui, fontSize: 12, color: C.mute }}>Best Regards,<br/>Automation System</div>
    </div>
  );
}

// Recreates the team response-status email (co-assignees answered, 3/5).
function EmailTeamStatus({ lt }) {
  const rows = [
    ['Cable Accessories', 'ahmed.ebeed@bahra-cables.com', 'No', 'Not in Scope'],
    ['Cables', 'lotfy.mohammad@bahra-electric.com', 'No', 'Not in Scope'],
    ['Non-Cables', 'karim.ahmad@bahra-cables.com', 'No', 'Not in Scope'],
    ['TBS and BED', 'intikhab.ali@bahra-cables.com', 'Pending', 'Pending'],
    ['TBS and BED', 'mohammad.ariff@bahra-electric.com', 'Pending', 'Pending'],
  ];
  const head = ['Products', 'Email', 'Results', 'Remarks', 'Upload File'];
  const col = [150, 250, 110, 130, 90];
  return (
    <div>
      {/* attachment chip */}
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 9, padding: '6px 12px', border: `1px solid ${C.line}`,
        borderRadius: 9, marginBottom: 10, background: '#FAFBFD' }}>
        <span style={{ width: 24, height: 24, borderRadius: 6, background: '#1D7044', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontFamily: F.ui, fontWeight: 800, fontSize: 9 }}>XLS</span>
        <div>
          <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 11.5, color: C.ink }}>SEC RFP - C001785668.xls</div>
          <div style={{ fontFamily: F.ui, fontSize: 10.5, color: C.faint }}>146 KB</div>
        </div>
      </div>
      <div style={{ fontFamily: F.ui, fontSize: 12, color: C.text, marginBottom: 3 }}>
        Dear Ksagov Tenders, kindly advise us regarding the attached RFP file for <b>Cable Accessories, Non-Cables, TBS and BED, Cables</b>.</div>
      <div style={{ fontFamily: F.ui, fontSize: 11.5, color: C.green, fontWeight: 600, marginBottom: 10 }}>
        Your responsibilities have already been answered by your co-assignees. Thank you.</div>
      <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: C.ink, marginBottom: 6 }}>Your Products</div>
      <div style={{ border: `1px solid ${C.line}`, borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ display: 'flex', background: '#F0F2F6', borderBottom: `1px solid ${C.line}` }}>
          {head.map((h, i) => <div key={h} style={{ width: col[i], padding: '6px 12px', fontFamily: F.ui, fontWeight: 700, fontSize: 10.5, color: C.text }}>{h}</div>)}
        </div>
        {rows.map(([prod, email, res, rem], r) => (
          <div key={r} style={{ display: 'flex', alignItems: 'center', height: 33, borderBottom: r < rows.length - 1 ? `1px solid ${C.line2}` : 'none' }}>
            <div style={{ width: col[0], padding: '0 12px', fontFamily: F.ui, fontWeight: 700, fontSize: 11, color: C.ink }}>{prod}</div>
            <div style={{ width: col[1], padding: '0 12px', fontFamily: F.ui, fontSize: 10.5, color: C.mute, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{email}</div>
            <div style={{ width: col[2], padding: '0 12px' }}><ResultText v={res} /></div>
            <div style={{ width: col[3], padding: '0 12px' }}><span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 11.5, color: res === 'Pending' ? C.blue : C.green }}>{rem}</span></div>
            <div style={{ width: col[4], padding: '0 12px', fontFamily: F.ui, fontSize: 12, color: C.faint }}>—</div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
        <span style={{ fontFamily: F.ui, fontSize: 11.5, color: C.mute }}>Team responses: <b style={{ color: C.ink }}>3 / 5</b> answered.</span>
        <div style={{ flex: 1, maxWidth: 180, height: 7, background: '#EEF1F6', borderRadius: 99, overflow: 'hidden' }}>
          <div style={{ width: '60%', height: '100%', background: C.green, borderRadius: 99 }} />
        </div>
        <div style={{ height: 30, borderRadius: 8, border: `1px solid ${C.blue}`, color: C.blue, display: 'flex', alignItems: 'center',
          padding: '0 14px', fontFamily: F.ui, fontWeight: 700, fontSize: 11.5 }}>Refresh Status</div>
      </div>
    </div>
  );
}

// Recreates the URGENT 1-day deadline reminder.
function EmailReminder({ lt }) {
  return (
    <div>
      <div style={{ fontFamily: F.ui, fontSize: 13.5, color: C.text, marginBottom: 10 }}>Dear Team,</div>
      <div style={{ fontFamily: F.ui, fontSize: 13.5, color: C.text, marginBottom: 16 }}>
        The following RFP(s) have their deadline within <b>1 day</b>.
        <span style={{ color: C.red, fontWeight: 800 }}>  Immediate action required!</span>
      </div>
      <div style={{ border: `1px solid #1f2733`, borderRadius: 8, overflow: 'hidden', maxWidth: 560 }}>
        <div style={{ display: 'flex', background: '#fff', borderBottom: '2px solid #1f2733' }}>
          {['RFP ID', 'End Date', 'Time Left'].map((h, i) => (
            <div key={h} style={{ flex: i === 0 ? 1.3 : 1, padding: '11px 14px', textAlign: 'center', fontFamily: F.ui, fontWeight: 800, fontSize: 13, color: C.ink, borderRight: i < 2 ? '1px solid #1f2733' : 'none' }}>{h}</div>
          ))}
        </div>
        <div style={{ display: 'flex', background: '#FBE0E0' }}>
          <div style={{ flex: 1.3, padding: '12px 14px', textAlign: 'center', fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.ink, borderRight: '1px solid #d9b3b3' }}>SEC RFP C001743163</div>
          <div style={{ flex: 1, padding: '12px 14px', textAlign: 'center', fontFamily: F.ui, fontSize: 13, color: C.ink, borderRight: '1px solid #d9b3b3' }}>2026-02-26 02:15</div>
          <div style={{ flex: 1, padding: '12px 14px', textAlign: 'center', fontFamily: F.ui, fontWeight: 800, fontSize: 14, color: C.red }}>
            <Count to={10} from={14} at={lt} dur={0.01} suffix=" hour(s)" />
          </div>
        </div>
      </div>
      <div style={{ marginTop: 16, fontFamily: F.ui, fontSize: 13, color: C.text }}>Please review and take necessary action urgently.</div>
      <div style={{ marginTop: 14, fontFamily: F.ui, fontSize: 12, color: C.mute }}>Best Regards,<br/>Automation System</div>
    </div>
  );
}

// ── Scene: Adaptive-Card / Real Email flow (replaces SceneEmail) ─────────────
function SceneEmailReal({ t0, dur, swap = 17 }) {
  const time = useTime();
  const lt = time - t0;
  const SWAP = swap; // switch from new-RFP card to team-status email
  const showStatus = lt > SWAP;
  // cursor for the interactive new-RFP beat
  const cursor = [
    { t: t0 + 3.4, x: 900, y: 280 },
    { t: t0 + 4.0, x: 700, y: 322, click: true },   // open Results dropdown
    { t: t0 + 5.2, x: 700, y: 352 },                // move to "Yes"
    { t: t0 + 5.4, x: 700, y: 352, click: true },   // pick Yes
    { t: t0 + 6.4, x: 826, y: 322, click: true },   // open Remarks dropdown
    { t: t0 + 7.4, x: 826, y: 352 },                // move to "Create TIR"
    { t: t0 + 7.6, x: 826, y: 352, click: true },   // pick Create TIR
    { t: t0 + 8.8, x: 826, y: 322 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.2} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 22, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 11.5, fontWeight: 700, color: C.red, letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
          Routing & response · in Outlook
        </div>
        <div style={{ fontFamily: F.display, fontSize: 24, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          {showStatus ? <>Every teammate sees <span style={{ color: C.red }}>who has answered</span></>
                      : <>Bidders respond <span style={{ color: C.red }}>right inside the email</span></>}
        </div>
      </Appear>

      {!showStatus ? (
        <Appear key="a" at={t0 + 0.6} dur={0.5} exitAt={t0 + SWAP - 0.4} exitDur={0.4}>
          <MailFrame x={205} y={84} w={870} h={516}
            subject="New RFP — Sample RFP Title" from="Automation System <automation@bahra-cables.com>"
            to="RFP Team Members" when="Today 08:01">
            <EmailNewRFP lt={lt} />
          </MailFrame>
        </Appear>
      ) : (
        <Appear key="b" at={t0 + SWAP} dur={0.5}>
          <MailFrame x={205} y={84} w={870} h={516}
            subject="SEC RFP - C001785668" from="D365FOadmin <D365FOadmin@bahra-electric.com>"
            to="KSAGov Tenders" when="Fri 2026-05-22 00:04">
            <EmailTeamStatus lt={lt - SWAP} />
          </MailFrame>
        </Appear>
      )}
      {!showStatus && <Cursor path={cursor} />}
    </SceneWrap>
  );
}

// ── Scene: Reminders / deadline guard (replaces SceneReminders) ──────────────
function SceneRemindersReal({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const days = ['Receipt', '−5d', '−3d', '−1d', 'Due'];
  const markP = clamp((lt - 2) / 8, 0, 1);
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.2} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 40, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 12.5, fontWeight: 700, color: C.red, letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
          Open RFP · deadline guard
        </div>
        <div style={{ fontFamily: F.display, fontSize: 32, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          No tender slips because someone forgot
        </div>
      </Appear>

      {/* left: timeline */}
      <div style={{ position: 'absolute', top: 200, left: 110, width: 470 }}>
        <Appear at={t0 + 1.0} dur={0.6}>
          <div style={{ position: 'relative', height: 4, background: 'rgba(255,255,255,0.14)', borderRadius: 2 }}>
            <div style={{ width: `${markP * 100}%`, height: '100%', background: C.red, borderRadius: 2 }} />
            {days.map((d, i) => {
              const px = (i / (days.length - 1)) * 100;
              const isRem = d === '−3d' || d === '−1d';
              const isDue = d === 'Due';
              return (
                <div key={d} style={{ position: 'absolute', left: `${px}%`, top: -7, transform: 'translateX(-50%)', textAlign: 'center' }}>
                  <div style={{ width: 16, height: 16, borderRadius: 99, border: `2px solid ${isDue ? C.red : isRem ? C.amber : C.hair2}`,
                    background: isDue ? C.red : isRem ? C.amber : C.bg, margin: '0 auto' }} />
                  <div style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700, color: isDue ? C.red : isRem ? C.amber : C.invMute, marginTop: 8 }}>{d}</div>
                </div>
              );
            })}
          </div>
        </Appear>
        <Appear at={t0 + 1.4} dur={0.6} style={{ marginTop: 56 }}>
          <div style={{ fontFamily: F.ui, fontSize: 14, color: C.invMute, lineHeight: 1.55 }}>
            Reminder emails fire automatically at <span style={{ color: C.amber, fontWeight: 700 }}>3 days</span> and again at <span style={{ color: C.red, fontWeight: 700 }}>1 day</span> before the deadline.
            Sent-flags prevent duplicates — each bidder is nudged exactly once per window.
          </div>
        </Appear>
        {lt > 11 && (
          <Appear at={t0 + 11.2} dur={0.5} sc={0.06} style={{ marginTop: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, background: 'linear-gradient(135deg,#11151D,#0E141C)', border: `1px solid ${C.hair}`, borderRadius: 12, padding: '16px 20px' }}>
              <div style={{ fontFamily: F.display, fontSize: 42, fontWeight: 700, color: C.green }}><Count to={0} at={t0 + 11.4} dur={0.8} /></div>
              <div style={{ fontFamily: F.ui, fontSize: 13, color: C.invMute }}>tenders missed on coordination<br/>since go-live</div>
            </div>
          </Appear>
        )}
      </div>

      {/* right: the real URGENT reminder email */}
      <Appear at={t0 + 3.0} dur={0.6} sc={0.04}>
        <MailFrame x={620} y={150} w={520} h={420}
          subject="🚨 URGENT: RFP Deadline Tomorrow (1 Day)" from="D365FOadmin" to="Manish Soni" when="Wed 18:23">
          <EmailReminder lt={lt - 3} />
        </MailFrame>
      </Appear>
    </SceneWrap>
  );
}

Object.assign(window, { SceneEmailReal, SceneRemindersReal, MailFrame, EmailNewRFP, EmailTeamStatus, EmailReminder });
