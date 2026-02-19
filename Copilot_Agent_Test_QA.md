# Copilot Agent - Test Questions & Answers

## Dataverse Tables Used
| Table | API Name | Purpose |
|---|---|---|
| cr673_requestforproposal | cr673_requestforproposals | Main RFP records |
| cr673_bahra_automation_log1 | cr673_bahra_automation_log1s | Automation run logs |
| cr673_bhara_rfp_status | cr673_bhara_rfp_statuses | RFP status change history |

## Companies Supported
Saudi Electricity Company, Aramco e-Marketplace, SABIC - Saudi Basic Industries Corp., HADEED - RAJHI STEEL

---

## Test Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 1 | RFP Status | What is the current status of RFP [RFP_ID]? | |
| 2 | RFP Status | Has RFP [RFP_ID] been submitted? | |
| 3 | RFP Status | Which RFPs are still open and not responded to? | |
| 4 | RFP Status | Which RFPs have we declined? | |
| 5 | RFP Status | Are there any RFPs saved as draft that need to be submitted? | |
| 6 | Deadline | What is the deadline for RFP [RFP_ID]? | |
| 7 | Deadline | Which RFPs are expiring this week? | |
| 8 | Deadline | Which RFPs passed their deadline without any response? | |
| 9 | Deadline | What is the nearest upcoming RFP deadline we still need to act on? | |
| 10 | Submission | When was RFP [RFP_ID] submitted? | |
| 11 | Submission | Who submitted RFP [RFP_ID]? | |
| 12 | Submission | What is the status change history of RFP [RFP_ID]? | |
| 13 | Submission | Was the submission of RFP [RFP_ID] successful or failed? | |
| 14 | Company | How many RFPs have we received from Saudi Electricity Company? | |
| 15 | Company | Show me all RFPs from Aramco. | |
| 16 | Company | Which company has the most pending (open) RFPs right now? | |
| 17 | Material Match | Does RFP [RFP_ID] match our materials/products? | |
| 18 | Material Match | Which open RFPs match our materials and should be prioritized? | |
| 19 | Material Match | How many RFPs match our keywords/capabilities? | |
| 20 | Files | Is the downloaded RFP file available for RFP [RFP_ID]? | |
| 21 | Files | Has the filled response file been uploaded for RFP [RFP_ID]? | |
| 22 | Files | Are there TDS (Technical Data Sheet) files for RFP [RFP_ID]? | |
| 23 | Summary | How many RFPs do we have in total and what is the breakdown by status? | |
| 24 | Summary | What is our RFP submission rate (percentage)? | |
| 25 | Summary | When was the last automation run and what was its status? | |
| 26 | Urgent Action | Which RFPs need immediate attention (deadline within 3 days and still open)? | |
| 27 | Full History | Give me the complete history of RFP [RFP_ID] from download to submission. | |
| 28 | Decline | Which RFPs were declined and on what date? | |
| 29 | Monthly Report | Give me a summary of all RFPs from this month. | |
| 30 | Portal Link | Is there a direct link to view RFP [RFP_ID] on the Ariba portal? | |
