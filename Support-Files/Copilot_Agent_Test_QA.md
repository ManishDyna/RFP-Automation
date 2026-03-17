# Copilot Agent - Test Questions & Expected Behavior

## Companies Supported
Saudi Electricity Company, Aramco e-Marketplace, SABIC - Saudi Basic Industries Corp., HADEED - RAJHI STEEL

---

## Core RFP Queries

| # | Category | Question | Expected Behavior |
|---|---|---|---|
| 1 | Status | What is the current status of RFP [RFP_ID]? | Show RFP ID, Company, Deadline, Status, Owner, Material Match |
| 2 | Status | Has RFP [RFP_ID] been submitted? | Check participated field, confirm yes/no with details |
| 3 | Status | Which RFPs are still open? | Table of open RFPs grouped by company, sorted by deadline |
| 4 | Status | Which RFPs have we declined? | Table of declined RFPs grouped by company |
| 5 | Status | Are there any RFPs saved as draft? | Table of drafts + note "not yet submitted to portal" |
| 6 | Deadline | What is the deadline for RFP [RFP_ID]? | Show deadline in DD-MMM-YYYY format |
| 7 | Deadline | Which RFPs are expiring this week? | Open RFPs with deadline within 3 days, marked URGENT |
| 8 | Deadline | Which RFPs passed their deadline without response? | Table of expired RFPs labeled "Expired — Not Participated" |
| 9 | Deadline | What is the nearest upcoming deadline? | Soonest open RFP deadline, URGENT if within 3 days |
| 10 | Submission | Was the submission of RFP [RFP_ID] successful? | Check automation logs for that RFP, plain language answer |
| 11 | Company | How many RFPs from Saudi Electricity Company? | Count + list of RFP IDs |
| 12 | Company | Show me all RFPs from Aramco | Table filtered by Aramco, grouped by status |
| 13 | Company | Which company has the most open RFPs? | Count per company with comparison |
| 14 | Material | Does RFP [RFP_ID] match our products? | Material/Keyword match status + match details |
| 15 | Material | Which open RFPs match our materials? | Matched open RFPs prioritized by deadline |
| 16 | Files | Is the downloaded file available for RFP [RFP_ID]? | Simple Yes/No, no file paths shown |
| 17 | Files | Has the response file been uploaded for RFP [RFP_ID]? | Simple Yes/No, no file paths shown |
| 18 | Summary | How many RFPs total and what's the breakdown? | Counts by status, grouped by company |
| 19 | Urgent | Which RFPs need immediate attention? | Open RFPs with deadline ≤3 days, marked URGENT |
| 20 | Decline | Which RFPs were declined? | Table of declined RFPs with company and date |
| 21 | Monthly | Give me a summary of this month's RFPs | Total + breakdown by status per company |
| 22 | Email | Was the team notified about RFP [RFP_ID]? | Plain language: "Yes, sent" or "No, not sent yet" |
| 23 | Reminder | Which RFPs still need reminders? | Open RFPs within 3 days without reminder sent |
| 24 | Automation | When was the last automation run? | Time + status (success/fail) + brief message |

---

## Natural Language Questions (Business User Style)

| # | Question | Maps To | Expected Behavior |
|---|---|---|---|
| 25 | What's due soon? | Expiring within 3 days | Open RFPs with deadline ≤3 days, marked URGENT |
| 26 | Any new RFPs from Aramco? | Company-filtered open RFPs | Open Aramco RFPs in table format |
| 27 | Did we submit SEC-12345? | Specific RFP status check | Status of that RFP — submitted or not |
| 28 | What's on our plate? | All open RFPs | Full open RFP table grouped by company |
| 29 | Can we supply what they need for RFP [ID]? | Material match check | Material/Keyword match status + details |
| 30 | Is the system running fine? | Last automation status | Time, success/fail, brief message |
| 31 | What did we miss last week? | Expired RFPs | Expired RFPs from last 7 days |
| 32 | How are we doing this month? | Monthly summary | Status breakdown per company |

---

## Out-of-Scope Questions (Should Redirect)

| # | Question | Expected Response |
|---|---|---|
| 33 | Who has access to the system? | "I focus on RFP tracking and submissions. For that request, please contact your system administrator." |
| 34 | Can you change the automation schedule? | Same redirect to system administrator |
| 35 | Update my SAP password | Same redirect to system administrator |

---

## Output Format Checks

| # | Check | Expected |
|---|---|---|
| 36 | Dates format | DD-MMM-YYYY (e.g., 17-Mar-2026) |
| 37 | Grouping | Results grouped by company with header and count |
| 38 | Urgent flag | Deadlines within 3 days show URGENT |
| 39 | Zero results | "No RFPs found matching your criteria. Would you like to check a different status or company?" |
| 40 | No internal names | No table names, field names, or file paths visible in responses |
