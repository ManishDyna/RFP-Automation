# Step-by-step guide: serve the RFP portal over HTTPS (get the lock icon) on your server

> **Read me first.** This is a hands-on runbook you can follow yourself on the server. Work
> through the phases **in order**. Each phase ends with a **"✅ Done when…"** check — don't move
> on until it passes. Nothing here is destructive; the old setup keeps running until **Phase 4**,
> and there's a **Rollback** section at the end.

---

## What you'll achieve

Today the portal is `http://be-aramco-01.bahra-cables.com:3000` → the browser says **"Not secure"**
because it's plain HTTP. You'll put **IIS** in front of it on port **443** with an SSL certificate,
so the address becomes **`https://be-aramco-01.bahra-cables.com`** with a **lock icon**.

There are **two separate connections** to understand — this is the key to the whole plan:

| Connection | Who connects | What it needs |
|---|---|---|
| **Browser → portal UI** | your internal staff on company PCs | HTTPS on 443 + a cert your PCs trust → **Phases 1–4** |
| **Microsoft cloud → Actionable-Card callback** | Outlook/Microsoft servers (public internet) | a **public** HTTPS URL (the devtunnel) → **Phase 2** |

Because your app is **on-premises only**, Microsoft's cloud can't reach your server directly — so
the Outlook "Submit/Decline" buttons must keep using a public **devtunnel**. We just make that
devtunnel **stable** so it stops breaking. The UI lock icon and the callback are fixed separately.

> **Where am I running these?** All server steps run **on the server** `be-aramco-01.bahra-cables.com`
> (Remote Desktop into it as an Administrator). The code there is at `C:\python\RFP-automation`.
> (Your laptop `DSPL-LPT-477` is *not* the server — don't run the cert/IIS steps there.)

---

## Before you start — prerequisites

- [ ] You can **Remote Desktop (RDP) into the server** as a local **Administrator**.
- [ ] The backend is running: open PowerShell on the server and run
      `curl http://localhost:8000/health` → you should get `{"status":"healthy",...}`.
      (It runs as the `RFP-Dashboard` Windows service / NSSM. If not running, start it first.)
- [ ] **Node.js 20** is installed on the server (`node --version`). If not, install it from
      nodejs.org — needed once to build the UI. (Alternatively build on your laptop and copy the
      `frontend\dist` folder over.)
- [ ] You know the server's intended web address: **`be-aramco-01.bahra-cables.com`**.

---

## What the domain `be-aramco-01.bahra-cables.com` needs (on-prem)

The name has to **agree in four places** — if any one differs you get "can't reach the site" or a
cert warning:

| # | Requirement | Verify (on the server / a company PC) |
|---|---|---|
| 1 | **Internal DNS record** → server's LAN IP (an A record in Bahra's internal DNS) | `Resolve-DnsName be-aramco-01.bahra-cables.com` returns the server IP |
| 2 | **SSL cert issued for this exact name** (Subject/SAN) | the `DNS` column in Step 1.1 output |
| 3 | **Cert trusted by PCs** (company CA, or pushed to Trusted Root) | lock shows with no warning |
| 4 | **Port 443 open + IIS site bound to this host name** | Steps 1.5–1.6 |

**Often #1 is already done:** if the server is joined to the `bahra-cables.com` Active Directory
domain and its computer name is `be-aramco-01`, AD auto-registers the DNS record. Only ask IT to
add an A record if `Resolve-DnsName` on a company PC comes back empty.

**Not needed (on-prem only):** ❌ public/internet DNS · ❌ public IP / internet port-forward for the
UI · ❌ public CA cert (internal/company-CA cert is fine).

**This domain is NOT used for the Outlook callback.** The callback uses a separate **public** URL
(today via VS Code Port Forwarding on port 8000 — which is why it breaks when VS Code closes). See
Phase 2.

---

## PHASE 1 — Get the lock icon (the main goal)

### Step 1.1 — Find out what SSL certificate the server already has

Run this in **PowerShell (as Administrator) on the server**:

```powershell
Get-ChildItem Cert:\LocalMachine\My, Cert:\LocalMachine\WebHosting -ErrorAction SilentlyContinue |
  Select-Object Subject, Issuer, NotAfter, HasPrivateKey,
    @{n='DNS';e={$_.DnsNameList -join ', '}}, Thumbprint | Format-List
```

Look at the output and find a certificate where **`DNS` (or `Subject`) contains
`be-aramco-01.bahra-cables.com`**. Then decide which case you're in:

| Case | What you see | Go to |
|---|---|---|
| **A — Ready to use** | A cert for `be-aramco-01.bahra-cables.com`, `HasPrivateKey = True`, `NotAfter` is in the future, and **Issuer ≠ Subject** (issued by a real CA) | Skip to **Step 1.3** — copy its **Thumbprint** |
| **B — Self-signed / wrong / expired** | A cert exists but **Issuer = Subject** (self-signed), or wrong name, or expired | Do **Step 1.2** |
| **C — Nothing** | No cert mentions the hostname | Do **Step 1.2** |

> **Why "Issuer = Subject" matters:** that means the cert signed itself (self-signed). Browsers
> don't trust it, so you'd still see a warning unless every PC imports it. A cert from your
> **company's Certificate Authority (CA)** is trusted automatically on company PCs — that's what
> you want.

### Step 1.2 — Get a usable certificate (only if Case B or C)

Pick **one** option. **Option 1 is best** for an internal company app.

**Option 1 — Request one from your company's Certificate Authority (recommended).**
Most companies run an internal CA. Ask IT *"Do we have an internal Certificate Authority I can
request a Web Server certificate from?"* If yes:
1. On the server run `certlm.msc` → **Personal → Certificates** → right-click → **All Tasks →
   Request New Certificate**.
2. Next → choose **Active Directory Enrollment Policy** → Next.
3. Tick the **Web Server** template → click **⚠ More information is required…** →
   **Subject** tab → set **Common Name = `be-aramco-01.bahra-cables.com`** and add it again under
   **Alternative name → DNS**. OK → **Enroll**.
4. The cert now appears in `Cert:\LocalMachine\My`, trusted on all company PCs. Re-run Step 1.1
   to grab its **Thumbprint**, then go to Step 1.3.

   *(Or, if IT simply hands you a `.pfx` file: double-click it → install to
   **Local Machine → Personal** → enter its password.)*

**Option 2 — IIS "Create Domain Certificate"** (same idea, via the IIS UI): IIS Manager → server
node → **Server Certificates** → **Create Domain Certificate…** → fill in the common name
`be-aramco-01.bahra-cables.com` → pick your online CA. Use this only if Option 1's wizard isn't
convenient.

**Option 3 — Self-signed (last resort, no company CA available).** Creates the cert but you must
push it to every PC's trust store:
```powershell
New-SelfSignedCertificate -DnsName "be-aramco-01.bahra-cables.com" `
  -CertStoreLocation Cert:\LocalMachine\My `
  -FriendlyName "RFP Portal" -NotAfter (Get-Date).AddYears(3)
```
Then export the **public** part and have IT deploy it to **Trusted Root Certification Authorities**
on the staff PCs (via Group Policy). Until that's done, browsers will keep warning.

### Step 1.3 — Install IIS + the two add-ons

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole, IIS-WebServer, IIS-HttpRedirect -All
```
Then install these two free Microsoft modules (download the MSI from microsoft.com, or use the Web
Platform Installer):
- **URL Rewrite 2.1**
- **Application Request Routing (ARR) 3.0**

Now turn on proxying: open **IIS Manager** → click the **server name** (top of the left tree) →
double-click **Application Request Routing Cache** → in the right pane click **Server Proxy
Settings…** → tick **Enable proxy** → **Apply**.

✅ **Done when:** IIS Manager opens and "Application Request Routing Cache" and "URL Rewrite" icons
are visible on the server node.

### Step 1.4 — Build the web UI

```powershell
cd C:\python\RFP-automation\frontend
npm install
npm run build
```
This creates `C:\python\RFP-automation\frontend\dist`.

✅ **Done when:** the folder `frontend\dist` exists and contains `index.html` and an `assets`
folder.

### Step 1.5 — Create the website, the rules file, and the HTTPS binding

**(a) Create the `web.config` rules file.** Create a new file at
`C:\python\RFP-automation\frontend\dist\web.config` with exactly this content (it tells IIS to
forward API calls to the backend on :8000 and serve the app for everything else):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <!-- 1. Send API / upload / health to the backend on port 8000 -->
        <rule name="ProxyApi" stopProcessing="true">
          <match url="^(api|upload|health)(/.*)?$" />
          <action type="Rewrite" url="http://localhost:8000/{R:0}" />
        </rule>
        <!-- 2. /dashboard: forward only data calls (not page loads) to the backend -->
        <rule name="ProxyDashboardXhr" stopProcessing="true">
          <match url="^dashboard(/.*)?$" />
          <conditions><add input="{HTTP_ACCEPT}" pattern="text/html" negate="true" /></conditions>
          <action type="Rewrite" url="http://localhost:8000/{R:0}" />
        </rule>
        <!-- 3. Everything else: serve the React app -->
        <rule name="SpaFallback" stopProcessing="true">
          <match url=".*" />
          <conditions logicalGrouping="MatchAll">
            <add input="{REQUEST_FILENAME}" matchType="IsFile" negate="true" />
            <add input="{REQUEST_FILENAME}" matchType="IsDirectory" negate="true" />
          </conditions>
          <action type="Rewrite" url="/index.html" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```
> **Important:** `dist` gets erased every time you run `npm run build`, which deletes this file.
> Keep a backup copy of `web.config` and re-paste it after any future rebuild.

**(b) Create the IIS website.** IIS Manager → right-click **Sites** → **Add Website**:
- **Site name:** `RFP-Portal`
- **Physical path:** `C:\python\RFP-automation\frontend\dist`
- **Binding → Type:** `https`  **Port:** `443`  **Host name:** `be-aramco-01.bahra-cables.com`
- **SSL certificate:** pick the certificate from Step 1.1/1.2 (match the Thumbprint)
- Click **OK**.

> If port 443 is already used by another site, edit that site's bindings instead, or stop it.

### Step 1.6 — Allow port 443 through the firewall

```powershell
New-NetFirewallRule -DisplayName "RFP Portal HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```
(Internal network only — no internet rule needed for the UI.)

### Step 1.7 — Test the lock 🔒

From a **normal company PC** (not the server), open a browser to:
**`https://be-aramco-01.bahra-cables.com`**

✅ **Done when:**
- The address bar shows a **lock** (no "Not secure").
- The login page loads; you can log in and the dashboard + RFP tables appear.
- Press **F5** on the dashboard page — it reloads as the app (not raw text/JSON).

> **Still see a warning?** It almost always means the certificate isn't trusted on that PC →
> you're on a self-signed cert (Step 1.2 Option 3). Use Option 1 (company CA) or have IT push the
> cert to Trusted Root. See Troubleshooting below.

At this point the **lock icon goal is achieved.** The dev server on :3000 is still running in
parallel (we retire it in Phase 4). Phases 2–3 fix the Outlook buttons and old emails.

---

## PHASE 2 — Keep the Outlook "Submit / Decline" buttons working

The card buttons are clicked in Outlook, but **Microsoft's servers** (not the user's browser) make
the actual call to your app. They come from the public internet, so they can only reach a **public
URL** — that's the **devtunnel**. The problem today is the devtunnel URL changes every session and
breaks. Fix = make it **permanent** and run it as a service.

### Step 2.1 — Create a permanent devtunnel and run it as a service

On the server (the devtunnel CLI is already in use by this project):
```powershell
devtunnel user login
devtunnel create rfp-callback                 # a reusable tunnel with a fixed ID
devtunnel port create rfp-callback -p 8000    # expose the backend port
devtunnel host rfp-callback                   # starts hosting; note the https URL it prints
```
Copy the printed URL — it looks like `https://<fixed-id>-8000.<region>.devtunnels.ms`. Because the
tunnel ID is fixed, **this URL stays the same** from now on.

Then make it survive reboots by running `devtunnel host rfp-callback` as a Windows service (same
NSSM tool used for the other services):
```powershell
nssm install "RFP-Devtunnel" "C:\path\to\devtunnel.exe" "host rfp-callback"
nssm start "RFP-Devtunnel"
```

### Step 2.2 — Point the app's URLs at the right places

Set these three values. **Best practice:** set them in the portal's **Admin → System Settings**
page (takes effect without editing code). If a key isn't there, edit `C:\python\RFP-automation\config\config.py`:

| Setting | Set it to | Why |
|---|---|---|
| `ACTIONABLE_CARD_CALLBACK_URL` | `https://<fixed-id>-8000.<region>.devtunnels.ms/api/actionable-card/response` | Microsoft reaches it via the public tunnel |
| `UPLOAD_BASE_URL` | `https://be-aramco-01.bahra-cables.com/` | staff open upload links from inside → internal HTTPS is fine |
| `FRONTEND_URL` | `https://be-aramco-01.bahra-cables.com` | password-reset links point to the new address |

After changing these, **restart the backend** (`RFP-Dashboard` service) so new emails use the new
URLs. (No need to re-register anything in Outlook — the originator ID is unchanged.)

### Step 2.3 — Test
Send yourself a **fresh** RFP card (trigger a new-RFP email), open it in Outlook, fill it in, click
**Submit**.

✅ **Done when:** the response is saved (visible in the portal / the `cr6db_cr673_bahra_rfp_response`
table) and the upload button opens `https://be-aramco-01.bahra-cables.com/upload?...`.

---

## PHASE 3 — Handle emails that were already sent (so nothing breaks during the switch)

You can't change links already sitting in people's inboxes, so:

1. **Keep the OLD devtunnel running for ~72 hours** after Phase 2. Upload links carry a token that
   **expires in 72 hours** anyway, so after 3 days the old links are dead naturally and the old
   tunnel can be shut off.
2. **Redirect the old `:3000` address.** So old bookmarks and links keep working, add two small
   IIS redirect sites that bounce **http :80** and **http :3000** to
   `https://be-aramco-01.bahra-cables.com` (IIS Manager → Add Website on those ports → use the
   **HTTP Redirect** feature pointing to the HTTPS address).
3. *(Optional, for impatience)* re-send the card emails for any **currently-open** RFPs so people
   immediately have fresh, working links.

---

## PHASE 4 — Go live (retire the old dev server)

Once Phases 1–3 test clean and the 72-hour window has passed:

1. **Stop the old Vite dev server** that served `:3000`. If it runs as a service, e.g.:
   ```powershell
   nssm stop "RFP-Frontend"      # use the real service name from services.msc
   nssm set "RFP-Frontend" Start SERVICE_DISABLED
   ```
   **Keep running:** `RFP-Dashboard` (backend :8000) and `RFP-Devtunnel` (callback).
2. Shut down the **old** devtunnel (the previous, random-URL one) — the new permanent one stays.
3. Confirm the `:80`/`:3000` redirects from Phase 3 are active.

✅ **Done when:** `https://be-aramco-01.bahra-cables.com` is the only address people use, it shows
the lock, and the old `:3000` link redirects to it.

---

## Final verification checklist

- [ ] `https://be-aramco-01.bahra-cables.com` shows the **lock** on a company PC (no warning).
- [ ] Login works; dashboard, RFP tables, admin pages all load; F5 on any page keeps you in the app.
- [ ] `https://be-aramco-01.bahra-cables.com/health` returns `{"status":"healthy",...}`.
- [ ] A **fresh** Outlook card Submit/Decline saves correctly.
- [ ] The upload button opens an `https://be-aramco-01.bahra-cables.com/upload?...` page that accepts a file.
- [ ] The old `http://be-aramco-01.bahra-cables.com:3000` redirects to the HTTPS address.

---

## If something goes wrong (troubleshooting)

| Symptom | Likely cause | Fix |
|---|---|---|
| Browser still says **"Not secure"** / cert warning | Cert is self-signed or not trusted on that PC | Use a **company-CA** cert (Step 1.2 Option 1) or have IT push your cert to **Trusted Root** on PCs |
| Page loads but **login/data fails** (502/504 in Network tab) | Backend not running, or ARR proxy not enabled | `curl http://localhost:8000/health`; re-check Step 1.3 "Enable proxy" |
| Refreshing **/dashboard** shows raw JSON/text | The `/dashboard` rule is missing/edited | Re-paste the `web.config` exactly (the `ProxyDashboardXhr` rule with the `text/html` condition) |
| **403 Forbidden** opening the site | IIS can't read the `dist` folder | Grant **IIS_IUSRS** read access to `C:\python\RFP-automation\frontend\dist` |
| Outlook **Submit** does nothing / errors | Callback URL wrong or devtunnel down | Verify the permanent devtunnel is hosting; confirm `ACTIONABLE_CARD_CALLBACK_URL` matches its URL; restart `RFP-Dashboard` |
| `npm run build` fails | Node not installed / wrong version | Install **Node 20 LTS**, re-run `npm install` then `npm run build` |
| Port **443 already in use** | Another IIS site or app holds 443 | Edit that site's binding, or stop it, then bind `RFP-Portal` to 443 |

---

## Rollback (undo everything safely)

Nothing was deleted, so you can revert at any time:
1. IIS Manager → **stop** (or remove) the `RFP-Portal` site.
2. **Re-start** the old Vite dev-server service → the app is back on
   `http://be-aramco-01.bahra-cables.com:3000` exactly as before.
3. Revert the three URL settings (Phase 2.2) to their previous devtunnel values if you changed them.

The backend and your Dataverse data are never modified by this guide.
