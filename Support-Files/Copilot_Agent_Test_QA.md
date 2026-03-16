# Copilot Agent - Test Questions & Answers

## Dataverse Tables Used
| Table | API Name | Purpose |
|---|---|---|
| cr673_requestforproposal | cr673_requestforproposals | Main RFP records |
| cr673_bahra_automation_log1 | cr673_bahra_automation_log1s | Automation run logs |
| cr673_bhara_rfp_status | cr673_bhara_rfp_statuses | RFP status change history |
| cr6db_cr673_bahra_rfp_response | cr6db_cr673_bahra_rfp_responses | Team member responses to RFP reviews |
| cr673_bahra_rfp_team | cr673_bahra_rfp_teams | RFP team assignments by product |
| cr673_bahra_material_master | cr673_bahra_material_masters | Material code catalog |
| cr673_bahra_keywords | cr673_bahra_keywordses | Matching keywords |
| cr673_bahra_audit_logs | cr673_bahra_audit_logses | User action audit trail |

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

---

## Team Response Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 31 | Team Response | Has everyone on the team responded to RFP [RFP_ID]? | Show responded count vs total team size. List who responded and who is pending. |
| 32 | Team Response | Who hasn't responded yet for RFP [RFP_ID]? | List pending team members by name and product from team table minus responses table. |
| 33 | Team Response | What did the Cables team say about RFP [RFP_ID]? | Show response record for product = "Cables": name, results, remarks, responded_at. |
| 34 | Team Response | Which team member takes the longest to respond on average? | Calculate avg(responded_at - publish_time) per team member. Rank slowest first. |
| 35 | Team Response | Show me all RFPs where the team has not fully responded yet. | List RFPs where response count < active team member count. Show RFP_ID, Company, Responded/Total. |

## Team Assignment Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 36 | Team | Who is on the RFP team and what product does each person handle? | Table of all active team members: product, name, email. |
| 37 | Team | How many RFPs has each team member responded to this month? | Count responses per name for current month. Show: name, product, count. |
| 38 | Team | What is the workload distribution across the team? | Response count per team member for recent period. Flag imbalances. |

## Material Catalog Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 39 | Materials | How many active materials do we have in our catalog? | Count from material_masters where is_active = "true". |
| 40 | Materials | Which materials from our catalog have been requested in RFPs? | Cross-reference material_masters with RFP Material_Code/Matched_Data. List matched material codes with RFP count. |
| 41 | Materials | What percentage of our material catalog gets RFP demand? | (Materials with RFP matches / Total active materials) * 100. |
| 42 | Materials | Are there any materials in our catalog that have never appeared in an RFP? | List material codes from catalog NOT found in any RFP Matched_Data or Material_Code. |

## Keyword Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 43 | Keywords | Which keywords trigger the most RFP matches? | Cross-reference keywords table with Matched_Keywords in RFPs. Rank by match count descending. |
| 44 | Keywords | Are there any keywords that have never matched an RFP? | List keywords from catalog NOT found in any RFP's Matched_Keywords field. |

## Cross-Table Deep Dive Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 45 | Deep Dive | Give me the full picture of RFP [RFP_ID]: deadline, team responses, materials, status history. | Combined view: RFP details + all team responses + pending members + status timeline + matched materials. |
| 46 | Deep Dive | For all open RFPs from Saudi Electricity Company, show team response status for each. | Table: RFP_ID, RFP_End_Date, Responded/Total, list of pending member names. Grouped under SEC header. |

## Executive Summary Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 47 | Executive | Give me a summary of this month: total RFPs, submitted, declined, material match rate. | Counts by status + Material_Matched=Yes percentage. Grouped by company. |
| 48 | Executive | What is our participation rate (submitted vs declined)? | submitted / (submitted + declined) * 100 as percentage. |
| 49 | Executive | Which company has the highest material match rate? | Per-company: (Material_Matched=Yes count / total RFPs) * 100. Rank by match rate. |

## Audit Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 50 | Audit | Who logged into the system today? | Query audit_logs where category = "AUTH" and created_date = today. Show: actor_name, created_date. |

## RFP Type & Classification Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 51 | RFP Type | What is the breakdown of RFP types (RFQ vs RFP vs Tender)? | Group by rfp_type, show count per type. |
| 52 | RFP Type | Show me all RFQs from this month. | Filter rfp_type = "RFQ" with date range. Show standard RFP table. |

## File Complexity & Match Quality Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 53 | File Stats | Which RFPs have the most line items? | Sort by total_line_items desc. Show: RFP_ID, Company_Name, total_line_items, file_size_bytes. |
| 54 | Match Quality | What is our average material match rate across all RFPs? | Average of match_rate_pct. Also show per company. |
| 55 | Match Quality | What is the breakdown of exact matches vs keyword matches? | Aggregate exact_match_count vs keyword_match_count. Show ratio/percentage. |

## Response Speed Questions

| # | Category | Question | Expected Answer |
|---|---|---|---|
| 56 | Response Speed | What is the average time from RFP notification to first team response? | Avg of (first_response_at - Email_Sent_At). Show in hours/days. |
| 57 | Response Speed | Which RFPs have full team responses and which are still pending? | Filter by response_count vs total team size. Show: RFP_ID, response_count, first_response_at, all_responses_at. |
