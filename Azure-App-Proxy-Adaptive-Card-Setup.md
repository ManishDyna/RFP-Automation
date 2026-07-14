# Step-by-step guide: replace the RFP Adaptive-Card devtunnel with Microsoft Entra Application Proxy

> **Read me first.** This is a hands-on runbook you can follow on the server. Work through the
> steps **in order**. Each ends with a **"✅ Done when…"** check — don't move on until it passes.
> Nothing here is destructive; the old devtunnel keeps running until the final step, and there's a
> **Rollback** section at the end.
>
> **This complements the *COA & RFP On-Premises Deployment Guide*** — it replaces that guide's
> Section 8 follow-up item *"Keep the existing dev-tunnel running … used by Outlook Actionable-
> Message callbacks."* It touches **only the RFP application**; COA is unaffected.

---

## Environment (from the deployment guide — RFP only)

| Thing | Value |
|---|---|
| Server VM (LAN-only) | `192.168.111.192` (Windows Server 2016) |
| RFP portal URL (internal, IIS) | `https://rfp.be-aramco-01.bahra-cables.com` |
| RFP backend | FastAPI/Uvicorn on **`127.0.0.1:8000`** (localhost-only) |
| RFP Windows service | **`rfp-api`** (WinSW) |
| RFP repo | **`C:\Bahra-Automation-RFP-System`** |
| RFP venv python | `C:\Bahra-Automation-RFP-System\env\Scripts\python.exe` |
| Config file | `C:\Bahra-Automation-RFP-System\backend\config\config.py` |
| TLS | self-signed wildcard `*.be-aramco-01.bahra-cables.com` (LAN-trusted only) |

## What you'll achieve

Today the Outlook **Adaptive Card** buttons (Submit / Refresh / Decline) call back into the RFP
backend through a **devtunnel** forwarding port 8000. That URL is unstable and is the only public
exposure of a LAN-only server. You'll replace it with **Microsoft Entra Application Proxy**, whose
connector is **outbound-only** — so Microsoft's cloud can reach the callback **without opening any
inbound firewall port or publishing the VM on the internet**.

The address the card calls becomes a stable Microsoft-managed URL like
`https://bahra-rfp-callback-<tenant>.msappproxy.net/api/actionable-card/response`.

**Two independent connections (unchanged model, just swapping the second one):**

| Connection | Who connects | Path | Changing? |
|---|---|---|---|
| Browser → RFP portal | internal staff on the Bahra LAN | IIS `https://rfp.be-aramco-01…` → `127.0.0.1:8000` | **No** |
| Microsoft cloud → Adaptive-Card callback | Outlook / Microsoft servers (public internet) | ~~devtunnel~~ → **App Proxy** → `127.0.0.1:8000` | **Yes** |

> **Scope:** we publish **only** the `/api/actionable-card/` path through App Proxy. The RBAC
> dashboard, the file-upload page, and `/api/automation/*` stay **LAN-only via IIS** and are never
> put on the public proxy.

---

## Why Application Proxy is the right choice here

- ✅ **Outbound-only connector.** The Entra *private network connector* only dials out on 443 to
  `*.msappproxy.net` and `*.servicebus.windows.net`. **No inbound port, no public IP, no
  port-forward** on the VM — exactly the "keep it LAN-only, don't expose the server publicly"
  requirement, and Entra-native.
- ✅ **The callback secures itself.** `backend/routes/actionable_cards.py`
  (`_verify_actionable_message_token`) already validates the Entra bearer token Microsoft sends.
  App Proxy just forwards the request; your own validation still runs — security is unchanged.
- ⚠️ **Must be published as "Passthrough" (not "Microsoft Entra ID" pre-auth).** Outlook's Actions
  service sends a **service** token, not an interactive sign-in. On Entra-ID pre-auth the proxy
  would redirect the call to a login page and the buttons would break. Passthrough forwards the
  request (and its `Authorization` header) straight to the backend.

---

## Before you start — prerequisites

- [ ] **Microsoft Entra ID P1 or P2** licensing on the tenant *(Step 0 — the connector /
      "Add an on-premises application" option won't appear without it).*
- [ ] **Remote Desktop into the VM `192.168.111.192`** as Administrator; backend healthy:
      `Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing`.
- [ ] An Entra **Application Administrator** account for [entra.microsoft.com](https://entra.microsoft.com).
- [ ] Access to the **Actionable Email Developer Dashboard** for originator
      `8dc8a969-5abf-4c49-828f-fbced5ae7570`.
- [ ] The VM has **outbound 443** to `*.msappproxy.net` and `*.servicebus.windows.net`, **without**
      TLS inspection on that traffic.

---

## STEP 0 — Confirm you have Entra ID P1/P2

1. [entra.microsoft.com](https://entra.microsoft.com) → **Billing → Licenses**; confirm a
   **Microsoft Entra ID P1** (or P2) plan.
2. Proof it's usable: **Entra ID → Enterprise apps → New application** — if
   **"Add an on-premises application"** appears, you're licensed.

✅ **Done when:** the **Add an on-premises application** option is visible.
> **If not licensed:** stop — App Proxy is unavailable. Fall back to making the **existing devtunnel
> permanent** (run `devtunnel host` as a `WinSW`/service with a fixed tunnel ID) or a **Cloudflare
> Tunnel** — both are also outbound-only. This runbook then doesn't apply.

---

## STEP 1 — Install the private network connector **on the VM**

> **Why on this VM specifically:** the backend listens on **`127.0.0.1:8000`** (localhost-only), so
> only a connector running **on `192.168.111.192` itself** can reach it. Don't install the connector
> on another host (it couldn't reach `127.0.0.1:8000`).

1. **Entra ID → Enterprise apps → New application → Add an on-premises application**.
2. Click **Download private network connector**, and run the installer **on `192.168.111.192`**.
3. Sign in with your Entra admin during install so the connector registers to your tenant.
4. In **Entra ID → Application proxy**, confirm the connector shows **Status = Active**.

✅ **Done when:** the connector is **Active**. (No inbound firewall rule needed — it dials out.)

---

## STEP 2 — Publish only the callback path (Passthrough)

**Entra ID → Enterprise apps → New application → Add an on-premises application**:

| Field | Value |
|---|---|
| **Name** | `Bahra RFP – Adaptive Card Callback` |
| **Internal URL** | `http://localhost:8000/api/actionable-card/` &nbsp;*(trailing `/` matters — path-scopes the publish to ONLY the callback endpoints; the connector hits the backend directly, bypassing IIS)* |
| **External URL** | leave the **default `msappproxy.net`** domain → `https://bahra-rfp-callback-<tenant>.msappproxy.net/api/actionable-card/` |
| **Pre Authentication** | **Passthrough** &nbsp;← **critical** |
| **Connector Group** | Default |

**Additional settings** — keep defaults except: **Backend Application Timeout** = `Default` (85 s;
the callback is fast) · **Translate URLs in Application Body** = `Off` · **Validate Backend TLS
Certificate** = `Off` (the internal leg is plain `http` to `:8000`).

Click **Add**, then copy the **External URL** from the app's **Application proxy** page.

> **Leave Users and groups empty** — Passthrough forwards anonymously and the app checks the token
> itself, so no user assignment is needed.
>
> **Alternative (via IIS instead of direct):** you *could* set Internal URL to
> `https://rfp.be-aramco-01.bahra-cables.com/api/actionable-card/` to reuse the existing IIS/ARR
> path. That needs the VM's hosts entry (already present) and **Validate Backend TLS = Off** (the
> wildcard cert is self-signed). Direct-to-`:8000` above is simpler — prefer it.

✅ **Done when:** the app exists and shows its
`…msappproxy.net/api/actionable-card/` external URL.

*(Optional, for apps created after 30 Jun 2026: open the app → **Permissions → Grant admin consent**
for `User.Read`. Unused in Passthrough, but clears the tutorial checklist.)*

---

## STEP 3 — Confirm the public endpoint is live

From **any internet-connected machine** (off the Bahra LAN — e.g. your laptop on the internet):

```powershell
curl.exe -i https://bahra-rfp-callback-<tenant>.msappproxy.net/api/actionable-card/response
```

✅ **Done when:** you get a **401/500 from the app** (a token-validation error), **not** a Microsoft
**login redirect** and not a timeout. That proves the connector reaches `:8000` and Passthrough is
forwarding. *(A login page ⇒ pre-auth was left on — fix Step 2.)*

Confirm nothing else leaked (only the callback path is published):
```powershell
curl.exe -i https://bahra-rfp-callback-<tenant>.msappproxy.net/health      # should NOT be served
curl.exe -i https://bahra-rfp-callback-<tenant>.msappproxy.net/api/login   # should NOT be served
```

---

## STEP 4 — Whitelist the new host in the Actionable Email Developer Dashboard

1. Open [outlook.office.com/connectors/oam/publish](https://outlook.office.com/connectors/oam/publish).
2. Select the provider for originator **`8dc8a969-5abf-4c49-828f-fbced5ae7570`**.
3. Add `https://bahra-rfp-callback-<tenant>.msappproxy.net/` to the provider's **Target URLs**. Save.

> Originator ID is unchanged — you're just adding a new allowed host alongside the old devtunnel one,
> exactly as the devtunnel host is registered today. No provider re-migration.

✅ **Done when:** the msappproxy.net URL appears in the provider's Target URLs.

---

## STEP 5 — Point the app at the new callback URL (the only code change)

Edit `C:\Bahra-Automation-RFP-System\backend\config\config.py` **line 137**:

```python
ACTIONABLE_CARD_CALLBACK_URL = "https://bahra-rfp-callback-<tenant>.msappproxy.net/api/actionable-card/response"
```

**Rules:**
- Keep the exact suffix **`/api/actionable-card/response`** — the card code appends `/refresh` and
  derives `/decline` from this one value (`backend/helpers/email_helper.py`), so every button
  follows automatically.
- This value is **config-file only** (it's in `REMOVED_KEYS` in
  `backend/Support-Files/seed_system_settings.py` — not read from Dataverse System Settings), so
  line 137 is the single source of truth.

Restart the backend so new emails embed the new URL:
```powershell
Restart-Service rfp-api
Invoke-WebRequest http://127.0.0.1:8000/health -UseBasicParsing
```

✅ **Done when:** `rfp-api` restarts and `/health` is healthy.

---

## STEP 6 — Repoint the *second* devtunnel before removing anything (`UPLOAD_BASE_URL`)

⚠️ `config.py` **line 158**, `UPLOAD_BASE_URL`, is a **separate** devtunnel used by the Adaptive
Card **"Upload"** button (`<UPLOAD_BASE_URL>/upload?token=…`). Staff open these links from inside
the LAN, so point it at the **internal RFP HTTPS** address (served by IIS):

```python
UPLOAD_BASE_URL = "https://rfp.be-aramco-01.bahra-cables.com/"
```

Restart `rfp-api` again after the change. *(Only if bidders open upload links from OUTSIDE the LAN
would this path also need App Proxy — a second published app, same Passthrough steps. Out of scope
per current requirement; decide before Step 8.)*

✅ **Done when:** `UPLOAD_BASE_URL` no longer points at a devtunnel.

---

## STEP 7 — Test the card end-to-end

1. Trigger a **fresh** New-RFP Adaptive Card email to yourself; open it in **Outlook**.
2. **Submit** → the response saves (check the portal / the RFP response table).
3. **Refresh** action → the card updates in place.
4. **Decline** on a consolidated card → it records the decline.
5. **Upload** → opens `https://rfp.be-aramco-01.bahra-cables.com/upload?...` (not a dead tunnel).

✅ **Done when:** Submit, Refresh, and Decline all work from a freshly-sent card, via the
`msappproxy.net` URL.

---

## STEP 8 — Retire the devtunnel

Once Steps 3–7 pass:
1. Stop/disable the devtunnel (however it runs today — WinSW service, scheduled task, or a
   VS Code port-forward). E.g. if it's a service: `Stop-Service <devtunnel-svc>` then set it disabled.
2. Keep running: **`rfp-api`** (backend :8000), **IIS** (RFP site), and the Entra **connector**.
3. Update the deployment guide's Section 8 — the "keep the dev-tunnel running" item is now resolved.

✅ **Done when:** the devtunnel is off and a fresh card still Submits/Refreshes/Declines correctly.

---

## What must stay LAN-ONLY (never publish through App Proxy)

- The RBAC dashboard and all session-authenticated `/api/*`, `/dashboard/*`, `/upload` routes →
  internal staff reach them via IIS at `https://rfp.be-aramco-01.bahra-cables.com`.
- **`/api/automation/*`** (e.g. `/api/automation/run`) → **unauthenticated**; must **never** be
  internet-reachable. Publishing only the `/api/actionable-card/` path keeps them private.

---

## Notes specific to this environment

- **Default `msappproxy.net` is the right domain choice here.** A custom domain
  (`rfp-callback.be-aramco-01…`) would need a **publicly trusted** TLS cert — the server's
  self-signed wildcard would be rejected — so stick with the Microsoft-managed default.
- **Backend stays on `127.0.0.1:8000`.** Do **not** rebind uvicorn to `0.0.0.0` for this — the
  connector on the same VM reaches localhost fine, and keeping it localhost-only preserves the
  LAN-only posture.
- **Redeploys don't touch this.** Per the deployment guide's Section 4, `config.py` is not
  overwritten by `git pull`/`npm run build`; the App Proxy app and connector are independent of code
  deploys. Just remember a backend config change ⇒ `Restart-Service rfp-api`.

---

## Final verification checklist

- [ ] `curl https://…msappproxy.net/api/actionable-card/response` → app 401/500 (not a login page).
- [ ] `…msappproxy.net/health` and `/api/login` are **not** served.
- [ ] A **fresh** Outlook card Submit / Refresh / Decline all succeed.
- [ ] The Upload button opens `https://rfp.be-aramco-01.bahra-cables.com/upload?...`.
- [ ] The devtunnel is stopped and nothing broke; `rfp-api`, IIS, and the connector are running.

---

## If something goes wrong (troubleshooting)

| Symptom | Likely cause | Fix |
|---|---|---|
| Card action gets an **Entra login page** / 302 | App published with **Entra ID** pre-auth | Set **Pre Authentication = Passthrough** (Step 2) |
| Card action **times out / 502** | Connector can't reach `:8000`, or `rfp-api` down | `Invoke-WebRequest http://127.0.0.1:8000/health`; confirm connector **Active** and installed **on this VM**; Internal URL = `http://localhost:8000/api/actionable-card/` |
| Card action **401 "invalid audience/issuer"** | App's own token check config | Confirm `ACTIONABLE_CARD_APP_ID_URI` set for the provider (unrelated to App Proxy) |
| Outlook **won't render / POST** the buttons | New host not registered | Add the msappproxy.net URL to provider **Target URLs** (Step 4) |
| Connector won't register / **"Unauthorized"** | TLS inspection on outbound 443 | Exempt `*.msappproxy.net` + `*.servicebus.windows.net` from inline TLS inspection |
| Upload button opens a **dead** page | `UPLOAD_BASE_URL` still on the old devtunnel | Set to `https://rfp.be-aramco-01.bahra-cables.com/` (Step 6), `Restart-Service rfp-api` |
| `…/response/refresh` **404** but base works | Callback URL suffix wrong | Line 137 must end exactly `/api/actionable-card/response` |

---

## Rollback (undo safely)

Nothing was deleted:
1. Revert `C:\Bahra-Automation-RFP-System\backend\config\config.py` line 137 (and line 158 if changed).
2. `Restart-Service rfp-api`.
3. Re-enable and start the devtunnel.

The App Proxy app can be left published (idle) or deleted. Dataverse data is never touched.
