// sc-comms.jsx — Scene 8 Adaptive-Card Email, Scene 9 Open RFP & Reminders

// ── Outlook-style frame ──────────────────────────────────────────────────────
function OutlookFrame({ x, y, w, h, children }) {
  const mails = [
    ['SmartRFP', 'New RFP assigned: SEC RFP-C001744045', '08:01', true],
    ['Procurement', 'Weekly bid review — agenda', '07:42', false],
    ['SmartRFP', 'Reminder: Aramco 4203238879 due in 3d', 'Yest', false],
  ];
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, background: C.card,
      borderRadius: 14, overflow: 'hidden', boxShadow: '0 40px 90px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column' }}>
      {/* titlebar */}
      <div style={{ height: 40, background: '#0E4B8C', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 10, flexShrink: 0 }}>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="#fff"><rect x="2" y="5" width="13" height="14" rx="2"/><path d="M2 7l6.5 4L15 7" stroke="#0E4B8C" strokeWidth="1.6" fill="none"/><path d="M15 9h7v8a2 2 0 01-2 2h-5z" opacity="0.7"/></svg>
        <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: '#fff' }}>Outlook</span>
        <span style={{ marginLeft: 'auto', fontFamily: F.ui, fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>Inbox · Basim K.</span>
      </div>
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* mail list */}
        <div style={{ width: 270, borderRight: `1px solid ${C.line}`, flexShrink: 0, background: '#FAFBFD' }}>
          {mails.map((m, i) => (
            <div key={i} style={{ padding: '13px 15px', borderBottom: `1px solid ${C.line2}`,
              background: i === 0 ? C.redSoft : 'transparent',
              boxShadow: i === 0 ? `inset 3px 0 0 ${C.red}` : 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: C.ink }}>{m[0]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 11, color: C.faint }}>{m[2]}</span>
              </div>
              <div style={{ fontFamily: F.ui, fontSize: 12, color: i === 0 ? C.text : C.mute, marginTop: 3,
                fontWeight: i === 0 ? 600 : 400, lineHeight: 1.3 }}>{m[1]}</div>
            </div>
          ))}
        </div>
        {/* reading pane */}
        <div style={{ flex: 1, padding: 22, overflow: 'hidden' }}>{children}</div>
      </div>
    </div>
  );
}

function SceneEmail({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const typeAt = 6.5, submitAt = 11.5;
  const submitted = lt > submitAt;
  const priceFull = '184.50';
  const typed = lt < typeAt ? '' : priceFull.slice(0, Math.min(priceFull.length, Math.floor((lt - typeAt) / 0.18)));
  const cursor = [
    { t: t0 + 2.0, x: 760, y: 260 },
    { t: t0 + typeAt - 0.3, x: 720, y: 388, click: true },
    { t: t0 + typeAt + 1.2, x: 720, y: 388 },
    { t: t0 + submitAt, x: 690, y: 470, click: true },
    { t: t0 + submitAt + 0.8, x: 690, y: 470 },
  ];
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.22} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 40, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.display, fontSize: 30, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          Bidders respond <span style={{ color: C.red }}>without leaving Outlook</span>
        </div>
      </Appear>

      <OutlookFrame x={150} y={104} w={980} h={544}>
        <Appear at={t0 + 0.6} dur={0.5}>
          {/* email header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 11, marginBottom: 14 }}>
            <div style={{ width: 38, height: 38, borderRadius: 9, background: `linear-gradient(150deg,${C.red},${C.redDk})`,
              display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M5 16.5L12 6l7 10.5" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/><circle cx="12" cy="19" r="1.6" fill="#fff"/></svg>
            </div>
            <div>
              <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>New RFP assigned to you</div>
              <div style={{ fontFamily: F.ui, fontSize: 12, color: C.faint }}>SmartRFP · to basim.k@company.com · 08:01</div>
            </div>
          </div>

          {/* adaptive card */}
          <div style={{ border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', maxWidth: 600 }}>
            <div style={{ background: '#0E141C', padding: '13px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13.5, color: '#fff' }}>SEC · RFP-C001744045</span>
              <span style={{ fontFamily: F.mono, fontSize: 11.5, fontWeight: 700, color: '#fff', background: C.red, borderRadius: 6, padding: '3px 9px' }}>DUE IN 3 DAYS</span>
            </div>
            <div style={{ padding: 18 }}>
              <div style={{ display: 'flex', gap: 22, marginBottom: 16 }}>
                {[['Line items', '42'], ['Auto-matched', '73%'], ['Scope', 'LV cabling']].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ fontFamily: F.ui, fontSize: 11, color: C.faint }}>{k}</div>
                    <div style={{ fontFamily: F.display, fontSize: 17, fontWeight: 700, color: C.ink }}>{v}</div>
                  </div>
                ))}
              </div>

              {submitted ? (
                <Appear at={t0 + submitAt + 0.2} dur={0.5} sc={0.08}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '16px 18px',
                    background: C.greenSoft, borderRadius: 12 }}>
                    <span style={{ width: 30, height: 30, borderRadius: 99, background: C.green, color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>✓</span>
                    <div>
                      <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13.5, color: C.green }}>Response recorded</div>
                      <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute }}>SAR 184.50 · 4 weeks · written to Dataverse, dashboard updated.</div>
                    </div>
                  </div>
                </Appear>
              ) : (
                <>
                  <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, marginBottom: 6 }}>Unit price — line 01 (SAR)</div>
                  <div style={{ height: 42, border: `1px solid ${lt > typeAt - 0.3 ? C.red : C.line}`, borderRadius: 9,
                    display: 'flex', alignItems: 'center', padding: '0 13px', background: C.paper, fontFamily: F.mono, fontSize: 14, color: C.text, maxWidth: 220 }}>
                    {typed}{lt > typeAt && typed.length < priceFull.length &&
                      <span style={{ width: 1.5, height: 18, background: C.red, marginLeft: 1, animation: 'blink 0.8s step-end infinite' }} />}
                    {typed === '' && lt <= typeAt && <span style={{ color: C.faint }}>0.00</span>}
                  </div>
                  <div style={{ fontFamily: F.ui, fontSize: 12, fontWeight: 600, color: C.text, margin: '14px 0 6px' }}>Lead time</div>
                  <div style={{ display: 'flex', gap: 8, maxWidth: 280 }}>
                    {['2 wks', '4 wks', '6 wks'].map((o, i) => (
                      <div key={o} style={{ flex: 1, height: 34, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontFamily: F.ui, fontSize: 12, fontWeight: 600, border: `1px solid ${i === 1 ? C.red : C.line}`,
                        color: i === 1 ? C.red : C.mute, background: i === 1 ? C.redSoft : '#fff' }}>{o}</div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
                    <div style={{ padding: '0 26px', height: 42, borderRadius: 9, background: lt > submitAt ? C.redDk : C.red, color: '#fff',
                      display: 'flex', alignItems: 'center', fontFamily: F.ui, fontWeight: 700, fontSize: 13.5,
                      boxShadow: `0 8px 20px ${C.redSoft}` }}>Submit price</div>
                    <div style={{ padding: '0 22px', height: 42, borderRadius: 9, border: `1px solid ${C.line}`, color: C.mute,
                      display: 'flex', alignItems: 'center', fontFamily: F.ui, fontWeight: 600, fontSize: 13 }}>Decline</div>
                  </div>
                </>
              )}
            </div>
          </div>
          <div style={{ fontFamily: F.ui, fontSize: 11.5, color: C.faint, marginTop: 12 }}>
            Office 365 actionable message · works on desktop & mobile Outlook
          </div>
        </Appear>
      </OutlookFrame>
      <Cursor path={cursor} />
      <style>{`@keyframes blink{50%{opacity:0}}`}</style>
    </SceneWrap>
  );
}

// ── Scene 9 — Open RFP & Reminders ───────────────────────────────────────────
function ReminderToast({ at, lt, days, color }) {
  if (lt < at) return null;
  const op = clamp((lt - at) / 0.4, 0, 1) * (1 - clamp((lt - at - 5) / 0.5, 0, 1));
  return (
    <div style={{ opacity: op, transform: `translateX(${(1 - clamp((lt - at) / 0.4, 0, 1)) * 30}px)`,
      display: 'flex', alignItems: 'center', gap: 12, background: C.card, borderRadius: 12,
      border: `1px solid ${C.line}`, padding: '13px 16px', boxShadow: '0 14px 36px rgba(0,0,0,0.25)', marginBottom: 12 }}>
      <span style={{ width: 34, height: 34, borderRadius: 9, background: color + '20', color,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M10 21a2 2 0 004 0"/></svg>
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.ink }}>
          Reminder sent · {days}-day notice
        </div>
        <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute }}>To assigned bidder · flag {days === 3 ? 'Reminder_3Day_Sent' : 'Reminder_1Day_Sent'} set</div>
      </div>
      <span style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700, color, background: color + '18', borderRadius: 6, padding: '3px 8px' }}>AUTO</span>
    </div>
  );
}

function SceneReminders({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  // due-date timeline marker
  const days = ['Receipt', '−5d', '−3d', '−1d', 'Due'];
  const markP = clamp((lt - 2) / 8, 0, 1);
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.22} />
      <Appear at={t0 + 0.2} dur={0.6} style={{ position: 'absolute', top: 70, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.mono, fontSize: 13, fontWeight: 700, color: C.red, letterSpacing: '0.14em',
          textTransform: 'uppercase', marginBottom: 10 }}>Open RFP · deadline guard</div>
        <div style={{ fontFamily: F.display, fontSize: 38, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          No tender slips because someone forgot
        </div>
      </Appear>

      {/* timeline */}
      <div style={{ position: 'absolute', top: 250, left: 160, width: 620 }}>
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
                  <div style={{ fontFamily: F.mono, fontSize: 11, fontWeight: 700,
                    color: isDue ? C.red : isRem ? C.amber : C.invMute, marginTop: 8 }}>{d}</div>
                </div>
              );
            })}
          </div>
        </Appear>
        <Appear at={t0 + 1.4} dur={0.6} style={{ marginTop: 60 }}>
          <div style={{ fontFamily: F.ui, fontSize: 14, color: C.invMute, lineHeight: 1.5 }}>
            Reminder emails fire automatically at <span style={{ color: C.amber, fontWeight: 700 }}>3 days</span> and
            again at <span style={{ color: C.amber, fontWeight: 700 }}>1 day</span> before the deadline. Sent-flags
            prevent duplicates — each bidder is nudged exactly once per window.
          </div>
        </Appear>
      </div>

      {/* toasts */}
      <div style={{ position: 'absolute', top: 240, right: 150, width: 300 }}>
        <ReminderToast at={5.0} lt={lt} days={3} color={C.amber} />
        <ReminderToast at={8.0} lt={lt} days={1} color={C.red} />
        {lt > 12 && (
          <Appear at={t0 + 12.2} dur={0.5} sc={0.06}>
            <div style={{ background: 'linear-gradient(135deg,#11151D,#0E141C)', border: `1px solid ${C.hair}`,
              borderRadius: 12, padding: 18, textAlign: 'center' }}>
              <div style={{ fontFamily: F.display, fontSize: 40, fontWeight: 700, color: C.green }}>
                <Count to={0} at={t0 + 12.4} dur={0.8} /></div>
              <div style={{ fontFamily: F.ui, fontSize: 13, color: C.invMute }}>tenders missed on coordination since go-live</div>
            </div>
          </Appear>
        )}
      </div>
    </SceneWrap>
  );
}

Object.assign(window, { SceneEmail, SceneReminders, OutlookFrame });
