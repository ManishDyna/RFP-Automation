// sc-admin.jsx — Scene 11 Admin & Governance (montage)

function Check({ on }) {
  return (
    <span style={{ width: 18, height: 18, borderRadius: 5, display: 'inline-flex', alignItems: 'center',
      justifyContent: 'center', background: on ? C.green : '#fff', border: `1.5px solid ${on ? C.green : C.line}` }}>
      {on && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round"><path d="M5 13l4 4L19 7"/></svg>}
    </span>
  );
}

function AdminUsers({ t0 }) {
  const users = [
    ['Basim Khan', 'basim.k@company.com', 'Bidder', C.blue, 'Active'],
    ['Khalid Omar', 'khalid.o@company.com', 'Admin', C.red, 'Active'],
    ['Salma Yusuf', 'salma.y@company.com', 'Approver', C.violet, 'Active'],
    ['Noura Ali', 'noura.a@company.com', 'Bidder', C.blue, 'Invited'],
  ];
  return (
    <div style={{ padding: 22 }}>
      <Appear at={t0} dur={0.4}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 18px', borderBottom: `1px solid ${C.line}` }}>
            <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>Users · 5 active</span>
            <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12.5, color: '#fff', background: C.red, borderRadius: 8, padding: '7px 14px' }}>+ Create user</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1.8fr 1fr 0.8fr', padding: '8px 18px',
            fontFamily: F.ui, fontSize: 10.5, fontWeight: 700, color: C.faint, letterSpacing: '0.04em', textTransform: 'uppercase', borderBottom: `1px solid ${C.line2}` }}>
            <span>Name</span><span>Email</span><span>Role</span><span>Status</span>
          </div>
          {users.map((u, i) => (
            <Appear key={u[0]} at={t0 + 0.2 + i * 0.1} dur={0.35} x={10}>
              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1.8fr 1fr 0.8fr', alignItems: 'center', padding: '13px 18px', borderBottom: `1px solid ${C.line2}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 30, height: 30, borderRadius: 99, background: u[3] + '22', color: u[3],
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F.ui, fontWeight: 700, fontSize: 12 }}>
                    {u[0].split(' ').map(n => n[0]).join('')}</span>
                  <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text }}>{u[0]}</span>
                </div>
                <span style={{ fontFamily: F.mono, fontSize: 12, color: C.mute }}>{u[1]}</span>
                <span><Pill color={u[3]} bg={u[3] + '1c'}>{u[2]}</Pill></span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: F.ui, fontSize: 12.5, fontWeight: 600, color: u[4] === 'Active' ? C.green : C.amber }}>
                  <StatusDot color={u[4] === 'Active' ? C.green : C.amber} />{u[4]}</span>
              </div>
            </Appear>
          ))}
        </div>
      </Appear>
    </div>
  );
}

function AdminRoles({ t0 }) {
  const perms = [
    ['rfp.view', true, true, true],
    ['rfp.submit', true, false, true],
    ['rfp.approve', false, true, true],
    ['users.manage', false, false, true],
    ['roles.manage', false, false, true],
    ['sap_password.change', false, false, true],
  ];
  return (
    <div style={{ padding: 22, display: 'flex', gap: 16 }}>
      <Appear at={t0} dur={0.4} style={{ width: 220, flexShrink: 0 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 8 }}>
          {[['Bidder', C.blue, 'rfp.* limited'], ['Approver', C.violet, '+ approve'], ['Admin', C.red, 'full control']].map((r, i) => (
            <div key={r[0]} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '11px 12px', borderRadius: 10,
              background: i === 2 ? C.redSoft : 'transparent', marginBottom: 2 }}>
              <span style={{ width: 9, height: 9, borderRadius: 99, background: r[1] }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 13, color: C.ink }}>{r[0]}</div>
                <div style={{ fontFamily: F.ui, fontSize: 11, color: C.faint }}>{r[2]}</div>
              </div>
            </div>
          ))}
          <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 12, color: C.red, textAlign: 'center', padding: '10px 0 4px' }}>+ New role</div>
        </div>
      </Appear>
      <Appear at={t0 + 0.2} dur={0.4} style={{ flex: 1 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
          <div style={{ padding: '12px 18px', borderBottom: `1px solid ${C.line}`, fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>
            Permission matrix · granular, no code
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', padding: '9px 18px',
            fontFamily: F.ui, fontSize: 11, fontWeight: 700, color: C.faint, textTransform: 'uppercase', letterSpacing: '0.03em', borderBottom: `1px solid ${C.line2}` }}>
            <span>Permission key</span><span style={{ textAlign: 'center' }}>Bidder</span><span style={{ textAlign: 'center' }}>Approver</span><span style={{ textAlign: 'center' }}>Admin</span>
          </div>
          {perms.map((p, i) => (
            <Appear key={p[0]} at={t0 + 0.4 + i * 0.08} dur={0.3} x={8}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', alignItems: 'center', padding: '10px 18px', borderBottom: `1px solid ${C.line2}` }}>
                <span style={{ fontFamily: F.mono, fontSize: 12.5, color: C.text }}>{p[0]}</span>
                {[1, 2, 3].map(j => <span key={j} style={{ display: 'flex', justifyContent: 'center' }}><Check on={p[j]} /></span>)}
              </div>
            </Appear>
          ))}
        </div>
      </Appear>
    </div>
  );
}

function AdminMaster({ t0 }) {
  return (
    <div style={{ padding: 22, display: 'flex', gap: 16 }}>
      <Appear at={t0} dur={0.4} style={{ flex: 1 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
          <div style={{ padding: '12px 18px', borderBottom: `1px solid ${C.line}`, fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>SAP material master · 8,421 rows</div>
          {[['4203238879', 'CABLE, ELEC 1×3.31MM² 600V WHITE'], ['4109887421', 'MCCB 250A 3P 36KA'], ['4201556730', 'CABLE GLAND BRASS 32MM IP68'], ['4205590012', 'EARTH ROD COPPER 16MM ×1.2M']].map((m, i) => (
            <Appear key={m[0]} at={t0 + 0.2 + i * 0.1} dur={0.35} x={8}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 18px', borderBottom: `1px solid ${C.line2}` }}>
                <span style={{ fontFamily: F.mono, fontSize: 12.5, fontWeight: 700, color: C.blue, width: 96 }}>{m[0]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 13, color: C.text, flex: 1 }}>{m[1]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 11.5, color: C.faint }}>edit</span>
              </div>
            </Appear>
          ))}
        </div>
      </Appear>
      <Appear at={t0 + 0.3} dur={0.4} style={{ width: 300, flexShrink: 0 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18 }}>
          <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink, marginBottom: 4 }}>Keyword aliases</div>
          <div style={{ fontFamily: F.ui, fontSize: 12, color: C.mute, marginBottom: 14 }}>Teach the matcher new words — improves every future RFP.</div>
          {[['gland → cable gland', C.green], ['mccb → circuit breaker', C.green], ['busbar → bus bar support', C.amber]].map((k) => (
            <div key={k[0]} style={{ display: 'flex', alignItems: 'center', gap: 9, padding: '9px 12px', background: C.paper, borderRadius: 9, marginBottom: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: 99, background: k[1] }} />
              <span style={{ fontFamily: F.mono, fontSize: 12, color: C.text }}>{k[0]}</span>
            </div>
          ))}
          <div style={{ height: 38, borderRadius: 9, border: `1.5px dashed ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: F.ui, fontSize: 12.5, fontWeight: 600, color: C.red, marginTop: 4 }}>+ Add alias</div>
        </div>
      </Appear>
    </div>
  );
}

function AdminAudit({ t0 }) {
  const rows = [
    ['08:14', 'Khalid Omar', 'role.update', 'Bidder → added rfp.export', C.violet],
    ['08:09', 'System', 'rfp.submit', 'SEC RFP-C001744045 by Basim K.', C.green],
    ['07:58', 'Khalid Omar', 'sap_password.change', 'SAP service credential rotated', C.red],
    ['07:51', 'Salma Yusuf', 'rfp.approve', 'Aramco 4203238879 approved', C.blue],
    ['07:40', 'System', 'master_data.update', '3 keyword aliases added', C.amber],
  ];
  return (
    <div style={{ padding: 22 }}>
      <Appear at={t0} dur={0.4}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 18px', borderBottom: `1px solid ${C.line}` }}>
            <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>Audit log · append-only</span>
            <Pill color={C.violet} bg={C.violetSoft}>🔒 immutable · 7-yr retention</Pill>
          </div>
          {rows.map((r, i) => (
            <Appear key={i} at={t0 + 0.2 + i * 0.1} dur={0.35} x={10}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '13px 18px', borderBottom: `1px solid ${C.line2}` }}>
                <span style={{ fontFamily: F.mono, fontSize: 12, color: C.faint, width: 42 }}>{r[0]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text, width: 130 }}>{r[1]}</span>
                <span style={{ fontFamily: F.mono, fontSize: 12, fontWeight: 700, color: r[4], background: r[4] + '16', borderRadius: 6, padding: '3px 9px', width: 180 }}>{r[2]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.mute, flex: 1 }}>{r[3]}</span>
              </div>
            </Appear>
          ))}
        </div>
      </Appear>
    </div>
  );
}

function AdminGovern({ t0 }) {
  return (
    <div style={{ padding: 22, display: 'flex', gap: 16 }}>
      <Appear at={t0} dur={0.4} style={{ flex: 1 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', height: '100%' }}>
          <div style={{ padding: '12px 18px', borderBottom: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', gap: 9 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={C.red} strokeWidth="2"><circle cx="8" cy="8" r="4"/><path d="M11 11l8 8M16 16l2-2"/></svg>
            <span style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink }}>SAP password log</span>
          </div>
          {[['07:58 today', 'Khalid Omar', 'rotated', C.green], ['12 Mar', 'Khalid Omar', 'rotated', C.green], ['18 Jan', 'IT Service', 'rotated', C.green]].map((r, i) => (
            <Appear key={i} at={t0 + 0.2 + i * 0.1} dur={0.35} x={8}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '13px 18px', borderBottom: `1px solid ${C.line2}` }}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke={C.faint} strokeWidth="2"><circle cx="8" cy="8" r="4"/><path d="M11 11l8 8"/></svg>
                <span style={{ fontFamily: F.ui, fontSize: 12.5, color: C.faint, width: 90 }}>{r[0]}</span>
                <span style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text, flex: 1 }}>{r[1]}</span>
                <Pill color={r[3]} bg={r[3] + '18'}>✓ {r[2]}</Pill>
              </div>
            </Appear>
          ))}
          <div style={{ padding: '12px 18px', fontFamily: F.ui, fontSize: 12, color: C.mute }}>
            Every rotation is logged — only <span style={{ fontFamily: F.mono, color: C.text }}>sap_password.change</span> holders can do it.
          </div>
        </div>
      </Appear>
      <Appear at={t0 + 0.3} dur={0.4} style={{ width: 330, flexShrink: 0 }}>
        <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, padding: 18, height: '100%' }}>
          <div style={{ fontFamily: F.ui, fontWeight: 700, fontSize: 14, color: C.ink, marginBottom: 14 }}>System settings</div>
          {[['Email mode', 'Production', true], ['New-RFP routing', 'On', true], ['Reminder emails', 'On', true], ['Dev tunnel callback', 'Off', false]].map((s, i) => (
            <div key={s[0]} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '11px 0', borderBottom: i < 3 ? `1px solid ${C.line2}` : 'none' }}>
              <div>
                <div style={{ fontFamily: F.ui, fontSize: 13, fontWeight: 600, color: C.text }}>{s[0]}</div>
                <div style={{ fontFamily: F.ui, fontSize: 11.5, color: C.faint }}>{s[1]}</div>
              </div>
              <div style={{ width: 40, height: 23, borderRadius: 99, background: s[2] ? C.green : C.line, position: 'relative' }}>
                <div style={{ position: 'absolute', top: 2.5, left: s[2] ? 20 : 2.5, width: 18, height: 18, borderRadius: 99, background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
              </div>
            </div>
          ))}
          <div style={{ marginTop: 14, fontFamily: F.ui, fontSize: 12, color: C.mute, lineHeight: 1.5 }}>
            Recipients & schedules live in Dataverse — change them here, no redeploy.
          </div>
        </div>
      </Appear>
    </div>
  );
}

function SceneAdmin({ t0, dur }) {
  const time = useTime();
  const lt = time - t0;
  const views = [
    { at: 0, nav: 'Users', title: 'Users', sub: 'Provision people, assign one role each', C: AdminUsers },
    { at: 9, nav: 'Roles', title: 'Roles & Permissions', sub: 'Create roles and grant permissions — no developer needed', C: AdminRoles },
    { at: 18, nav: 'Master Data', title: 'Master Data', sub: 'Materials & keyword aliases that power matching', C: AdminMaster },
    { at: 27, nav: 'Audit Logs', title: 'Audit Logs', sub: 'Who changed what, when — append-only', C: AdminAudit },
    { at: 36, nav: 'SAP Logs', title: 'Governance', sub: 'SAP credential rotation & system settings', C: AdminGovern },
  ];
  let cur = views[0];
  for (const v of views) if (lt >= v.at) cur = v;
  const View = cur.C;
  return (
    <SceneWrap t0={t0} dur={dur} bg={C.bgGrad}>
      <DotGrid opacity={0.2} />
      <Appear at={t0 + 0.1} dur={0.5} style={{ position: 'absolute', top: 30, left: 0, right: 0, textAlign: 'center' }}>
        <div style={{ fontFamily: F.display, fontSize: 27, fontWeight: 700, color: C.inv, letterSpacing: '-0.02em' }}>
          Governed end-to-end — <span style={{ color: C.red }}>RBAC, master data & audit</span>
        </div>
      </Appear>
      <BrowserFrame x={86} y={86} w={1108} h={556} url={`app.smartrfp.io/admin/${cur.nav.toLowerCase().replace(' ', '-')}`}>
        <AppShell active={cur.nav} title={cur.title} subtitle={cur.sub} showAdmin>
          <View t0={t0 + cur.at + 0.1} />
        </AppShell>
      </BrowserFrame>
    </SceneWrap>
  );
}

Object.assign(window, { SceneAdmin });
