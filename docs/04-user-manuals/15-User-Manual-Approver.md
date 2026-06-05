---
title: User Manual — Approver
version: 1.0
last_updated: 2026-04-22
owner: Samir Tak (samir.tak@dynatechconsultancy.com)
audience: RFP Approvers (procurement managers)
status: Draft
---

# User Manual — Approver

You review RFP submissions before they go to the customer. This guide walks you through the approval workflow.

> The **Approver** role is a custom role your admin creates. If you don't see the screens below, ask your admin to grant you an Approver role (see [RBAC Matrix §6](../03-operations/11-RBAC-Permissions-Matrix.md#6-creating-a-custom-role)).

---

## What you can do

- Review submissions from your team of bidders
- Approve, reject, or send back for rework
- See complete RFP history and audit trail
- Access analytics and material insights
- Export RFP lists for management reporting

You cannot:
- Edit the bidder's submission (you can only accept or reject)
- Change system settings, users, or roles
- Submit bids yourself (a different role exists for that)

---

## 1. Logging in

Same as everyone else:

1. Open the portal URL.
2. Enter email + password.
3. Sign in.

If you can't, contact your admin.

---

## 2. Finding submissions to review

1. Sidebar → **RFP Insights**.
2. Filter **Status = Submitted**.
3. Click a row to open the RFP.

**Tip:** Save a bookmark for this filtered view for daily access.

---

## 3. Reviewing a submission

The RFP detail page shows you:

### 3.1 Header
Customer, project, received date, **deadline** (if any), and attachments. Click an attachment to download.

### 3.2 BOQ + matches
Each line item with its matched material code and confidence. You can't change the match; that's the bidder's decision. But you should verify:

- Any **unmatched** line items (flagged red) have a manual code
- Obvious mismatches (e.g., cable vs. junction box) aren't approved
- Quantities and units are reasonable

### 3.3 Response — the bidder's prices
For each line: **unit price**, **lead time**, **remarks**, plus any custom fields.

Totals are computed automatically at the bottom.

### 3.4 Activity
A timeline of what's happened on this RFP: ingest, assignments, submission time, reminders, approvals.

---

## 4. Approving

1. Open a submitted RFP.
2. Scroll through every line — confirm prices and lead times.
3. Click **Approve**.
4. Add a comment (optional but helpful).
5. Confirm.

Approval marks the RFP `Approved` and triggers any downstream integration (e.g., sending the proposal to the customer). Your comment is stored in the audit trail.

---

## 5. Rejecting

Click **Reject** instead. A reason is **required**. The RFP goes back to `In Progress` and the bidder is notified.

Good rejection reasons:
- "Pricing misaligned with current market"
- "Line 12 matched wrong material — please review MC-xxx"
- "Lead time on line 3 exceeds customer requirement"

Bad (avoid):
- "Wrong"
- "Please fix"

---

## 6. Sending back for clarification

If you want the bidder to double-check but not fully redo:

1. Click **Request Clarification** (if enabled by your admin).
2. Enter the questions.
3. Confirm.

The bidder receives an email with your questions. The RFP stays in a `Clarification` state until they reply.

*(If your admin hasn't enabled this action, use **Reject** with a clear reason.)*

---

## 7. Analytics for oversight

Click **Analytics** in the sidebar. Useful charts:

- **Submissions per bidder per month** — who's producing?
- **Win rate by customer** — where are we strong?
- **Average response time** — are we meeting deadlines?
- **Decline rate by customer** — are we chasing the wrong customers?

Use these in your weekly team sync.

---

## 8. Material insights

Click **Material Insights**. See:

- Which SAP materials are being quoted most often
- Which bidder quoted what
- Average prices over time (if your admin has enabled price history)

Useful for pricing strategy discussions.

---

## 9. Audit log

Click **Audit Logs** in the sidebar (if your role has `audit_logs.view`).

Filter by:
- **Action** = `RFP_APPROVED`, `RFP_REJECTED` — your decisions
- **User** = a bidder's email — their activity

Export regularly for quarterly reviews.

---

## 10. Your profile

Click your avatar → **Profile** to update display name or change password. Same flow as any other user.

---

## 11. Frequently asked questions

**Q. Can I edit a bidder's price before approving?**
No. You can reject with a reason and let them resubmit.

**Q. What if two bidders submitted for the same RFP?**
Only one submission per RFP per bidder in v1. If your process requires multiple, ask your admin — it may involve a custom workflow.

**Q. I approved by mistake.**
Contact your admin. They can reset the status, but the approval is audited.

**Q. Can I see a bidder's past submissions?**
Yes — filter RFP Insights by **Bidder** (if your admin has added this column).

**Q. I need a Friday summary.**
Export RFP Insights filtered on `Approved` or `Submitted` this week. Analytics also provides ready-made weekly views.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| Can't see RFPs submitted by a bidder | Check your role includes `rfp.view` |
| Can't find the Approve/Reject buttons | Your role might be missing the approval permission — ask admin |
| Approve button disabled | There's an unfilled required field; scroll up |
| Email notifications not arriving | Check spam; ask admin to verify your email in User Management |

---

## 13. Getting help

- Workflow questions → your procurement director
- System issues → your admin
- Anything urgent → on-call IT
