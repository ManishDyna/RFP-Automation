# Plan: Serve the Vite dev server over HTTPS to remove the browser "Not secure" warning

## Context

The app is reached at `http://be-aramco-01.bahra-cables.com:3000` — plain HTTP, so
the browser shows **"Not secure."** Owning a certificate does not change this; the
warning only clears when the page is actually **served over HTTPS (TLS)** with a
certificate the users' browsers trust.

Decision (chosen by the user):
- **Approach:** enable HTTPS **directly on the existing Vite dev server** (add
  `server.https`), keeping the current port-3000 setup. This is the smallest change.
- **Out of scope / leave untouched:** the Actionable Card flow stays exactly as-is —
  `ACTIONABLE_CARD_CALLBACK_URL`, the originator ID, and the dashboard Target URLs
  remain on the devtunnel. The "Not secure" fix is the **browser → UI** connection and
  is completely independent of the **Microsoft cloud → callback** connection. The
  backend on `:8000` is also untouched.
- **Cert format:** unknown → the runbook starts with a discovery step and then branches.

Intended outcome: browsing to `https://be-aramco-01.bahra-cables.com:3000` shows the
lock icon, no "Not secure."

## Key facts that shape the steps

- All steps run **on the server** (`be-aramco-01…`), where the cert lives — not on a
  dev laptop.
- **`frontend/vite.config.js` is the ACTIVE config — it shadows `vite.config.ts`**
  (Vite loads `.js` before `.ts`). So the real edit goes in `vite.config.js`; mirror it
  into `vite.config.ts` to keep them consistent. (Both already contain the
  `allowedHosts: ['be-aramco-01.bahra-cables.com']` line added earlier.)
- For the warning to fully clear, the cert must be **trusted by the users' browsers**:
  public CA → automatic; corporate/internal CA → works if its root is deployed to the
  PCs (typical in AD orgs); self-signed → each PC must import it into Trusted Root.

## Step 1 — Locate the certificate on the server and detect its format

Run in PowerShell on the server. First check the Windows cert store:

```powershell
@('Cert:\LocalMachine\My','Cert:\LocalMachine\WebHosting','Cert:\CurrentUser\My') |
  Where-Object { Test-Path $_ } |
  ForEach-Object { Get-ChildItem $_ } |
  Select-Object Subject, FriendlyName, Thumbprint, NotAfter, HasPrivateKey, Issuer |
  Format-List
```

Then check common file locations:

```powershell
@('C:\certs','C:\ssl','C:\inetpub','C:\python\RFP-automation') |
  Where-Object { Test-Path $_ } |
  ForEach-Object { Get-ChildItem $_ -Recurse -Include *.pfx,*.p12,*.crt,*.cer,*.pem,*.key -ErrorAction SilentlyContinue } |
  Select-Object FullName, Length, LastWriteTime
```

Branch on what's found:
- **A `.pfx`/`.p12` file** → use the PFX variant in Step 2 (needs its password).
- **A `.crt`/`.cer` + `.key` pair** → use the PEM variant in Step 2.
- **Only in the Windows store (no key file)** → export it to a PFX first:
  ```powershell
  $pwd = ConvertTo-SecureString -String 'CHOOSE_A_PASSWORD' -Force -AsPlainText
  Export-PfxCertificate -Cert Cert:\LocalMachine\My\<THUMBPRINT> -FilePath C:\certs\bahra.pfx -Password $pwd
  ```
  then use the PFX variant. (Requires the cert to have a private key — `HasPrivateKey = True` above.)

## Step 2 — Add `server.https` to the Vite config

Edit **`frontend/vite.config.js`** (active) and mirror into **`frontend/vite.config.ts`**.

Add the `fs` import at the top (alongside the existing `path` import):
```js
import fs from 'fs';
```

Insert an `https` block inside `server`, right after the existing `allowedHosts` line.

**PFX variant** (read the password from an env var — do not hardcode the secret in the repo):
```js
    server: {
        host: '0.0.0.0',
        port: 3000,
        allowedHosts: ['be-aramco-01.bahra-cables.com'],
        https: {
            pfx: fs.readFileSync('C:/certs/bahra.pfx'),
            passphrase: process.env.VITE_PFX_PASSWORD,
        },
        proxy: { /* ...unchanged... */ },
    },
```
Set the password in the same shell before `npm run dev`:
```powershell
$env:VITE_PFX_PASSWORD = 'the-pfx-password'
```

**PEM variant:**
```js
        https: {
            key:  fs.readFileSync('C:/certs/be-aramco-01.key'),
            cert: fs.readFileSync('C:/certs/be-aramco-01.crt'),
        },
```

Notes:
- Use forward slashes (or escaped backslashes) in the JS path strings.
- The `proxy` block and everything else stay unchanged — `/api`, `/dashboard`,
  `/upload` still proxy to `http://localhost:8000` (server-side, unaffected by TLS).
- The `.ts` `https` value is written the same way; add `import fs from 'fs'` at the top
  of `vite.config.ts` as well.

## Step 3 — Restart and verify

```powershell
cd C:\python\RFP-automation\frontend
npm run dev
```

## Verification

1. The dev server starts without TLS/cert errors in the console (a bad path,
   wrong password, or key/cert mismatch shows here).
2. Browse to **`https://be-aramco-01.bahra-cables.com:3000/login`** (note **https**).
3. The address bar shows the **lock / neutral icon** instead of "Not secure."
   - If it still warns about the certificate, the cert isn't trusted by this browser →
     confirm it's a public/corporate-CA cert, or import a self-signed one into
     **Trusted Root Certification Authorities** on the client PCs.
4. Log in → dashboard loads, RFP tables populate (confirms the `/api` + `/dashboard`
   proxy still works over HTTPS).
5. Confirm the Actionable Card emails are **unaffected** — their Submit/Decline buttons
   still hit the unchanged devtunnel callback (we changed nothing in that path).

## Follow-up (optional, not required for this task)

- The duplicate `vite.config.js` + `vite.config.d.ts` (compiled artifacts that shadow
  the `.ts`) are fragile — every change must be made twice. A later cleanup is to delete
  those two generated files so Vite uses `vite.config.ts` as the single source, and stop
  the build from regenerating them.
- Running the Vite **dev server** as the production face is fine for now but not ideal;
  the robust long-term setup is a reverse proxy (IIS/Caddy/nginx) on 443 serving the
  built bundle — deferred by choice.
