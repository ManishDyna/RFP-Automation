# Adaptive Card RFP Response Flow

## Overview

This document describes the interactive Adaptive Card email system for collecting RFP team responses. Instead of 5 people replying separately to an RFP notification email, each person fills an interactive form directly inside their Outlook email.

## Architecture

```
Python (email_helper.py)
    → Power Automate (sends email)
        → Outlook (renders Adaptive Card)
            → User fills form, clicks Submit
                → FastAPI callback endpoint (/api/actionable-card/response)
                    → Saves to Dataverse (cr673_bahra_rfp_responses)
                    → If all 5 responded → sends consolidated email
```

## Complete End-to-End Flow

### Phase 1: Download & Send

```
run_automation_download()
     ↓
Login to Ariba portal → scrape open RFPs
     ↓
download_rfp_files() → downloads .xls files
     ↓
process_folder() → matches materials against master CSV
     ↓
FOR EACH new RFP:
     ↓
send_per_rfp_email()
     ↓
Detects Adaptive Card config → calls send_actionable_rfp_emails()
     ↓
Sends 5 PERSONALIZED emails (1 per team member):
     ├─ Lotfy Idrees    → Card: "Cables"            + RFP file + matched CSV
     ├─ Ahmed Ebeed     → Card: "Cable Accessories"  + RFP file + matched CSV
     ├─ Karim Nour      → Card: "Non-Cables"        + RFP file + matched CSV
     ├─ Intikhab Ali    → Card: "TBS and BED"       + RFP file + matched CSV
     └─ Mohammad Ariff  → Card: "TBS and BED"       + RFP file + matched CSV
```

### Phase 2: Team Members Respond (in Outlook)

Each team member opens their email and sees an interactive form:

```
┌─────────────────────────────────────────┐
│  RFP Response: SEC RFP C001743167       │
│  Product: Cables                        │
│  Assigned To: Lotfy Idrees              │
│  Due Date: 02/26/2026 02:15 AM          │
│                                         │
│  Results: [________________]            │
│  Remarks: [________________]            │
│                                         │
│  [ Submit Response ]                    │
└─────────────────────────────────────────┘
```

When they click Submit:

```
Outlook POSTs to → /api/actionable-card/response
     ↓
Callback endpoint:
  1. Verifies Microsoft JWT token (confirms identity)
  2. Saves response to Dataverse: cr673_bahra_rfp_responses
  3. Checks: How many of 5 have responded?
  4. If not all → returns updated card showing "Response Submitted ✓"
  5. If ALL 5 responded → triggers Phase 3
```

### Phase 3: Consolidated Email (automatic)

When the last person (5th) submits:

```
Callback triggers → send_consolidated_response_email()
     ↓
Queries Dataverse for all 5 responses
     ↓
Builds filled HTML table:
┌──────────────────┬─────────────────┬────────────┬───────────┐
│ Products         │ Name            │ Results    │ Remarks   │
├──────────────────┼─────────────────┼────────────┼───────────┤
│ Cables           │ Lotfy Idrees    │ Can Quote  │ 50% match │
│ Cable Accessories│ Ahmed Ebeed     │ Cannot     │ No items  │
│ Non-Cables       │ Karim Nour      │ Can Quote  │ Full match│
│ TBS and BED      │ Intikhab Ali    │ Partial    │ Need info │
│ TBS and BED      │ Mohammad Ariff  │ Can Quote  │ OK        │
└──────────────────┴─────────────────┴────────────┴───────────┘
     ↓
Sends 1 email to ALL team members + management
Subject: "All Responses Received - SEC RFP C001743167"
```

## Files Involved

| File | Purpose |
|------|---------|
| `config/config.py` | Actionable Card config, team table with emails |
| `helpers/email_helper.py` | Card builder, email sender, consolidated email |
| `routes/actionable_cards.py` | FastAPI callback endpoint for card submissions |
| `dashboard_main.py` | Router registration |

## Key Functions

| Function | File | Description |
|----------|------|-------------|
| `_build_adaptive_card_json()` | email_helper.py | Builds Adaptive Card JSON for one team member |
| `send_actionable_rfp_emails()` | email_helper.py | Sends 5 personalized Adaptive Card emails |
| `send_consolidated_response_email()` | email_helper.py | Sends final consolidated email when all respond |
| `receive_card_response()` | actionable_cards.py | Callback endpoint - receives submissions from Outlook |
| `get_rfp_responses()` | actionable_cards.py | Dashboard API - returns response status |

## Configuration

```python
# config/config.py

# Originator ID from Microsoft Actionable Email Developer Dashboard
ACTIONABLE_CARD_ORIGINATOR_ID = "<guid>"

# Public HTTPS callback URL for Outlook to POST to
ACTIONABLE_CARD_CALLBACK_URL = "https://<your-domain>/api/actionable-card/response"

# Dataverse table for storing responses
RFP_RESPONSE_TABLE_LOGICAL = "cr673_bahra_rfp_responses"
RFP_RESPONSE_TABLE_API = "cr673_bahra_rfp_responseses"

# Team table (now with email field)
RFP_TEAM_TABLE = [
    {"product": "Cables",            "name": "Lotfy Idrees",    "email": "...@bahra-cables.com"},
    {"product": "Cable Accessories", "name": "Ahmed Ebeed",     "email": "...@bahra-cables.com"},
    {"product": "Non-Cables",        "name": "Karim Nour",      "email": "...@bahra-cables.com"},
    {"product": "TBS and BED",       "name": "Intikhab Ali",    "email": "...@bahra-cables.com"},
    {"product": "TBS and BED",       "name": "Mohammad Ariff",  "email": "...@bahra-cables.com"},
]
```

## Dataverse Table: cr673_bahra_rfp_responses

| Column | Type | Description |
|--------|------|-------------|
| RFP_ID | Text (100) | RFP identifier |
| Product | Text (200) | Product category |
| Name | Text (200) | Team member name |
| Email | Text (200) | Team member email |
| Results | Text (500) | Free-text results |
| Remarks | Multiline Text (2000) | Free-text remarks |
| Submitted_At | Date/Time | When submitted |
| Company_Name | Text (200) | Company name |

## Prerequisites (One-Time Setup)

1. Register Actionable Message Provider at https://aka.ms/publishactionableemails
   - Sender email: `D365FOadmin@bahra-cables.com`
   - Scope: Organization
   - Get Originator ID

2. Create Dataverse table `cr673_bahra_rfp_responses`

3. Ensure FastAPI server is accessible via public HTTPS URL

## Fallback Behavior

If `ACTIONABLE_CARD_ORIGINATOR_ID` is empty/not configured, the system automatically falls back to the original behavior: 1 shared HTML-table email to all recipients. No code changes needed to switch between modes.

## Email Summary

| Scenario | Emails Sent |
|----------|-------------|
| Current system | 1 notification + 5 manual replies = 6 emails + manual consolidation |
| New system | 5 personalized cards + 1 auto-consolidated = 6 emails, zero manual work |
