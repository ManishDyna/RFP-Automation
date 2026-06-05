# SmartRFP — Product Demo Video Script

**Runtime:** ~7 min 53 sec · auto-playing with timeline scrubber
**File:** `SmartRFP Demo Video.html`
**Audience:** Prospective client / sales demo · neutral "SmartRFP" branding

The on-screen captions are the spoken narration. Use this sheet to record a voiceover or to present live. Timings are approximate (mm:ss from start).

---

## 01 · SmartRFP — Title  (0:00)
- This is SmartRFP — an automation platform that takes a tender from arrival all the way to a submitted quote.
- It discovers RFPs, parses the Bill of Quantities, matches it to your materials, routes it to bidders, and keeps a full audit trail.
- Here's how it works — and what it's worth to your team.

## 02 · The Problem  (0:15)
- Today, a single RFP is spread across five disconnected tools.
- The BOQ is re-keyed by hand from a PDF. Excel versions multiply. Each material code is looked up in SAP one at a time.
- Hand-offs happen over email, deadlines slip, and there is no record of who quoted what, when.
- That costs about two and a half hours of data entry per RFP.
- Roughly five tenders a month are missed purely on coordination — with no auditable history to learn from.
- The real work is pricing. Everything else is plumbing — and that's exactly what SmartRFP removes.

## 03 · Flow Overview  (0:49)
- Here is the whole pipeline. Six stages, and not a single manual re-entry between them.
- It starts by discovering RFPs — a scheduled scrape of your supplier portals: Ariba, SEC, Aramco, HADEED.
- It downloads and parses the BOQ, pulling out SAP material codes and description keywords.
- It auto-matches each line against your material master, then routes the RFP to the right bidders.
- Bidders return prices and lead times, and the package is submitted back to the customer.
- Underneath, every action is written to Microsoft Dataverse — attributed, timestamped, and governed by role-based access.
- Receipt to bidder in minutes, not hours. Let's walk each stage on the real product.

## 04 · Discover & Ingest  (1:39)
- Stage one: discovery. An operator can trigger a sync, or leave it to the schedule.
- SmartRFP logs into each supplier portal, finds the new events, and downloads every BOQ.
- Files land in SharePoint, records are written to Dataverse — seven new RFPs, ready to work, in under a minute.
- No analyst had to remember to poll. The cron runs Sunday to Thursday, every morning.

## 05 · Auto-Match  (2:19)
- Stage two: matching. Every BOQ line is checked against your SAP material master in two tiers.
- First, an exact match on the nine-digit SAP code. If that misses, keywords from the description take over.
- Each result carries a confidence score — green is a clean match, amber is a keyword hit, red needs a look.
- On a typical RFP, about three quarters of lines match with no human lookup at all.
- And the rest are never silently wrong — they are flagged for a single-click review.

## 06 · Login & Dashboard  (3:01)
- Your team signs in to one portal — secured, role-based, browser-only.
- The dashboard opens on the numbers that matter: new RFPs, work in progress, submissions, and cycle time.
- Every tile is live from Dataverse, and the recent-RFP table shows match rates and deadlines at a glance.
- Throughput is up over two times versus the manual baseline — the whole team works from one source of truth.
- Let's open a single RFP and price it.

## 07 · RFP Insights  (3:47)
- This is the RFP detail — customer, scope, deadline, and the fully matched Bill of Quantities.
- The bidder simply prices the matched lines. No re-keying, no hunting through SAP.
- A lead time, a note, and Submit — the status flips to Submitted and the whole action is logged.
- Receipt to a priced, submitted response — in minutes.

## 08 · Adaptive-Card Email  (4:37)
- Bidders who live in Outlook never have to leave it.
- Each assignment arrives as an actionable adaptive card with the RFP summary built in.
- They type a price, pick a lead time, and submit — right inside the email, on desktop or mobile.
- The response is written straight to Dataverse and the dashboard updates instantly.

## 09 · Open RFP & Reminders  (5:11)
- Deadlines are guarded automatically.
- A reminder fires three days before the due date, and again one day before.
- Sent-flags guarantee each bidder is nudged exactly once per window — no spam, no missed tenders.
- Since go-live, zero RFPs have been missed on coordination.

## 10 · Analytics & Material Insights  (5:37)
- For managers, analytics turn the pipeline into evidence.
- Win rate, cycle time, volume by customer, and outcomes — exportable to a board pack in one click.
- Material insights show what customers ask for most — and exactly where matching can improve.
- Low-scoring families tell admins which keyword alias to add next, so the system keeps getting smarter.

## 11 · Admin & Governance  (6:17)
- Behind it all is real governance. Admins provision users, each with a single role.
- Roles and permissions are fully granular — created and granted with no developer involvement.
- Master data — materials and keyword aliases — is editable in-app, improving every future match.
- Every change lands in an append-only audit log: who did what, when, kept for seven years.
- Even the SAP service password is rotated under permission and logged — settings change without a redeploy.

## 12 · Business Value  (7:03)
- So what's it worth? The same work, measured before and after.
- Receipt to bidder drops from hours to minutes. Submission from days to under a day. Missed tenders to zero.
- That is roughly eight hundred engineering hours back every year — about ten FTE-months.
- Payback in six to nine months, plus the deals you simply stop losing to slipped deadlines.
- Your engineers stop being data-entry clerks and start winning more bids.

## 13 · Close  (7:39)
- SmartRFP — from RFP to quote, automated end to end.
- One governed pipeline, built on the Microsoft 365 tenant you already own.
- Thank you for watching.

---

### Controls
- **Space** — play / pause · **← / →** — seek 0.1s (hold Shift for 1s) · **0** — back to start
- Drag the scrubber to jump to any moment. Playhead position is remembered on refresh.
