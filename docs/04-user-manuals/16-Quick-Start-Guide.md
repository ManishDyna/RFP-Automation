---
title: Quick Start Guide — Bahra Electric RFP Automation
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: All roles — first-time users
status: Draft
---

# Quick Start Guide

Welcome. Read this once (5 minutes) before your first hour on the portal. For role-specific detail, head to the [Bidder](13-User-Manual-Bidder.md), [Admin](14-User-Manual-Admin.md), or [Approver](15-User-Manual-Approver.md) manual.

---

## 1. What the portal does, in one paragraph

It collects RFPs from email, SharePoint, and the Ariba portal; auto-matches the Bill of Quantities against SAP material codes; routes each RFP to the right bidder; captures their prices (inside Outlook or in the portal); and tracks every step for your manager and the auditor.

---

## 2. Log in

1. Open the URL your admin gave you.
2. Enter your **email** and **password**.
3. Click **Sign in**.

Forgot password? Click the link on the login page.

After 5 failed attempts, your account is locked — ask your admin to unlock.

---

## 3. Know your role

You have **one role**. Find it on your avatar (top right) → Profile.

| Role | First place to look |
|---|---|
| **Bidder** | Sidebar → RFP Insights → filter Status = New |
| **Approver** | Sidebar → RFP Insights → filter Status = Submitted |
| **Admin** | Sidebar → everything. Start with Dashboard |
| **Auditor / read-only** | Sidebar → Audit Logs |

If the sidebar looks empty, your role may not have been assigned yet — contact your admin.

---

## 4. Your first 5 minutes

1. **Dashboard** — glance at the KPI tiles. Are there open RFPs?
2. **RFP Insights** — click the first open RFP you see.
3. **Read the BOQ table** — note the match percentages (green = good, yellow = OK, red = manual work needed).
4. **Read the response form at the bottom** — that's where you'd enter prices.
5. **Close it** (no commit yet). You're oriented.

---

## 5. How to do the 3 most common tasks

### 5.1 Respond to an RFP (Bidder)

- **In Outlook**: open the email, fill the prices in the adaptive card, click **Submit**. Done.
- **In the portal**: RFP Insights → click RFP → fill form → **Submit RFP**.

### 5.2 Approve a submission (Approver)

RFP Insights → filter **Status = Submitted** → click → review → **Approve** (or **Reject** with reason).

### 5.3 Create a user (Admin)

User Management → **Create User** → fill in → assign role → Save. Tell them to log in and change the initial password.

---

## 6. Glossary cheat sheet

| Term | Means |
|---|---|
| **RFP** | Request for Proposal — a customer asking for a quote |
| **BOQ** | Bill of Quantities — the line-item list inside an RFP |
| **Bidder** | Sales engineer who prices the RFP |
| **Approver** | Manager who signs off on the bid |
| **Match %** | How confident the system is in auto-matching BOQ items to SAP |
| **Adaptive card** | The fancy interactive email you can fill inline in Outlook |
| **Dataverse** | Where all data is stored (Microsoft's cloud DB — you don't interact with it directly) |

Full glossary: [03-Glossary-and-Acronyms.md](../01-business/03-Glossary-and-Acronyms.md).

---

## 7. FAQ (quickest answers)

**Q. Where's my RFP?**
RFP Insights → clear date filter → use the search box.

**Q. The system hasn't sent my adaptive card.**
Check your spam. If still missing, ask your admin — the ingestion run may have failed.

**Q. I can't see Admin screens.**
You're not an admin. That's by design.

**Q. How do I know my submission went through?**
The RFP status changes to **Submitted** and you see it in Activity Logs.

**Q. Can I work on mobile?**
Yes — both the portal and the Outlook adaptive card work on mobile. Prefer portrait orientation.

**Q. Can I change the match the system auto-picked?**
Bidder: yes, on the RFP detail page — click the material-code dropdown. Admin: also yes, plus can add keyword aliases to improve future matches.

**Q. Something is broken.**
Screenshot → email your admin → describe what you clicked and what happened. The more detail, the faster the fix.

---

## 8. Shortcuts & tips

- **Keyboard:** `Ctrl+K` opens the search (on most pages)
- **Filters are saved per user** — narrow once, it stays next visit
- **Export** anywhere you see a list — CSV / XLSX download
- **Dark mode** is in Profile settings (if your build includes it)
- **Refresh** if anything looks stale — client caches may lag 1–2 seconds

---

## 9. Next steps

- **Bidder** → read [User Manual — Bidder](13-User-Manual-Bidder.md)
- **Admin** → read [User Manual — Admin](14-User-Manual-Admin.md)
- **Approver** → read [User Manual — Approver](15-User-Manual-Approver.md)
- **Auditor / curious** → read the [Glossary](../01-business/03-Glossary-and-Acronyms.md) and skim the [SAD](../02-architecture/04-SAD-Software-Architecture-Document.md) Section 1

Bookmark this page — you'll come back when onboarding teammates.
