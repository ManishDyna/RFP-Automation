---
title: User Manual — Bidder
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: RFP Bidders (sales engineers)
status: Draft
---

# User Manual — Bidder

Welcome. This guide walks you through everything you need to respond to RFPs quickly and correctly.

> **First time here?** Read the [Quick Start Guide](16-Quick-Start-Guide.md) first (5 minutes).

---

## What you can do

As a **Bidder** you can:

- See RFPs assigned to you on the dashboard
- Open an RFP, review the BOQ and the auto-matched materials
- Fill in prices and lead times
- **Submit** a response, or **Decline** with a reason
- Respond directly from Outlook (adaptive card) without opening the portal
- View your past submissions and activity log

You **cannot**:

- See other bidders' prices
- Create users, roles, or change system settings
- Edit the material master or keyword list

---

## 1. Logging in

1. Go to the portal URL provided by your admin (e.g., `https://rfp.bahra-example.com`).
2. Enter your **email** and **password**.
3. Click **Sign in**.

If you forgot your password:
1. Click **Forgot password?** on the login screen.
2. Enter your email.
3. Check your inbox for a reset link (valid 24 hours).
4. Click the link, set a new password.

After five failed attempts your account is locked. Contact your admin to unlock.

---

## 2. The dashboard

After login you land on the **Dashboard**. It shows:

| Tile | What it means |
|---|---|
| **Total RFPs** | All RFPs you have access to, in the selected date range |
| **Open** | Not yet submitted or declined |
| **Submitted** | Awaiting approval (or already sent to customer) |
| **Declined** | You or a teammate declined these |

Use the **date** and **customer** filters at the top to narrow the view.

---

## 3. Finding your RFPs

1. Click **RFP Insights** in the sidebar.
2. You see a table with one row per RFP.
3. Sort or filter by clicking column headers or typing in the search box.
4. Look for RFPs with status **New** or **In Progress** — those are the ones waiting on you.

**Columns to pay attention to:**

- **RFP ID** — the customer's reference, click to open detail
- **Customer** — who sent the RFP
- **Received** — the date we ingested it
- **Deadline** — when you must respond by (if set)
- **Status** — New / In Progress / Submitted / Declined
- **Match %** — how much of the BOQ our system auto-matched against SAP

A low **Match %** doesn't mean the RFP is bad — it means you'll spend more time manually selecting material codes.

---

## 4. Opening an RFP

Click an **RFP ID**. The detail page has three sections:

### 4.1 Header
RFP metadata: customer, project, received date, deadline, attachments. Click an attachment filename to download the original file.

### 4.2 BOQ + matches
One row per line item, with our auto-match suggestion:

- Green badge = high confidence match (≥ 90 %)
- Yellow badge = medium confidence (75–89 %)
- Red badge = no match (needs your attention)

You can click the material-code dropdown to change the match.

### 4.3 Response form
Your input area. Fields are configured by your admin — typically:

- **Unit price** (required)
- **Lead time (days)** (required)
- **Remarks** (optional)
- Other custom fields your company has set up

---

## 5. Submitting a response

**From the portal:**

1. Open the RFP.
2. For each line, confirm or change the matched material code.
3. Enter unit price, lead time, and any remarks.
4. Click **Submit RFP** at the bottom.
5. Confirm in the dialog.

**From Outlook (adaptive card):**

1. Open the RFP email.
2. The card shows each line item.
3. Fill in the price / lead time fields.
4. Click **Submit** inside the card.
5. The card updates in place to show "Submitted — thank you".

Both paths do the same thing. Use whichever is convenient.

> **Tip:** If you're away from your desk, the adaptive card works on the Outlook mobile app too.

---

## 6. Declining an RFP

**From the portal:**

1. Open the RFP.
2. Click **Decline**.
3. Select or type a reason (required).
4. Confirm.

**From Outlook:**

1. Click **Decline** inside the adaptive card.
2. Enter a reason.
3. Click **Submit**.

A declined RFP drops off your active list. If it was declined in error, ask your admin to reassign it.

---

## 7. Partial submissions

You may not have a price for every line. You can:

1. Leave unknown line items blank and submit the rest. The row stays flagged so your admin can see what's missing.
2. Save a **draft** (if enabled) and come back later. Click **Save draft** instead of Submit.

Drafts don't count as responses — the reminder email will keep coming until you Submit.

---

## 8. Reminders

You'll receive a reminder email daily for RFPs you haven't responded to, until:
- You submit or decline, **or**
- The RFP deadline passes

Reminders stop automatically — you do not need to unsubscribe.

---

## 9. Your activity

Click **Activity Logs** in the sidebar to see what you and the system have done recently — RFPs downloaded, submissions made, reminders sent.

This is a helpful place to verify "did my submission go through?" if you're unsure.

---

## 10. Profile & password

Click your avatar (top right) → **Profile**.

- Update your display name or phone
- **Change password** — enter your current password, then the new one
- Sign out

---

## 11. Material insights

Click **Material Insights** in the sidebar. This shows which materials come up most often in RFPs, broken down by customer. Useful for:

- Identifying frequently requested items you should stock-check
- Spotting a customer's buying patterns
- Preparing for the next tender cycle

---

## 12. Frequently asked questions

**Q. I submitted by mistake — can I undo?**
Not directly. Contact your admin; they can reset the RFP to `In Progress`.

**Q. The adaptive card in Outlook is blank.**
Reload the email. If it stays blank, your organisation may not have actionable messages enabled — use the portal instead.

**Q. I can't see an RFP that my colleague says is assigned to me.**
Check the date filter on the RFP list — it might be hidden by a narrow range. If still missing, your RBAC role may not include it; ask your admin.

**Q. Why is the match percentage so low?**
The description on the customer's BOQ is ambiguous or uses non-standard terms. Click the material-code dropdown to select manually, or ask your admin to add a keyword alias.

**Q. My dashboard shows no RFPs at all.**
Either there genuinely are none in the date range, or your role is missing `rfp.view`. Ask your admin.

**Q. Can I export the RFP list?**
Yes — use the **Export** button on the RFP Insights page. Exports as XLSX.

---

## 13. Troubleshooting

| Problem | What to check |
|---|---|
| Can't log in | Caps Lock · try "Forgot password" · contact admin if still blocked |
| "Session expired" pop-up | You've been idle 8+ hours. Click OK and sign in again |
| Adaptive card button does nothing | Try the portal instead; tell your admin the card failed |
| Submit button disabled | One or more required fields are empty — scroll up, look for red outlines |
| Page looks broken / blank | Refresh (Ctrl+F5). If persistent, switch browser or tell your admin |

---

## 14. Getting help

- Quick questions → your team lead
- Access problems → your admin (`admin@bahra-example.com` — confirm in your company)
- System down → on-call IT

Always include:
- Your email
- The RFP ID (if any)
- A screenshot of the error
- What you were trying to do
