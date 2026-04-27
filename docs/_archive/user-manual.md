# Bahra Electric - RFP Portal User Manual

**Version:** 1.0
**Last Updated:** February 2026
**Audience:** End Users (RFP Bidders)

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Dashboard](#3-dashboard)
4. [Key Workflows](#4-key-workflows)
   - [Submit an RFP](#4a-submit-an-rfp)
   - [Decline an RFP](#4b-decline-an-rfp)
   - [Download RFPs](#4c-download-rfps)
   - [Download RFP Excel File](#4d-download-rfp-excel-file)
   - [Respond to RFP Email (Adaptive Card)](#4e-respond-to-rfp-email-adaptive-card)
5. [RFP Insights](#5-rfp-insights)
6. [Material Insights](#6-material-insights)
7. [Activity Logs](#7-activity-logs)
8. [Analytics](#8-analytics)
9. [Profile Settings](#9-profile-settings)
10. [Automation Status Indicator](#10-automation-status-indicator)
11. [Quick Reference](#11-quick-reference)
12. [Troubleshooting &amp; FAQ](#12-troubleshooting--faq)

---

## 1. Introduction

The **Bahra Electric RFP Portal** is a web-based system that automates the management of Requests for Proposal (RFPs) across multiple supplier portals. It handles downloading RFPs from company portals, matching materials and keywords, submitting or declining RFPs, and sending email notifications — all from a single dashboard.

**What you can do with this portal:**

- View all downloaded RFPs organized by company and status
- Submit or decline RFPs with automated portal interaction
- Track material and keyword matches for each RFP
- Monitor automation runs and review activity logs
- View analytics and participation reports
- Download RFP Excel files for offline review
- Receive email notifications with interactive Adaptive Cards

**Supported Companies:**

- Saudi Electricity Company
- Aramco e-Marketplace
- SABIC - Saudi Basic Industries Corp.
- HADEED - RAJHI STEEL

**Browser Requirements:** Google Chrome (latest version recommended), Microsoft Edge, or Firefox.

---

## 2. Getting Started

### 2.1 Logging In

1. Open the RFP Portal URL in your browser.
2. You will see the **Login** page with the Bahra Electric logo and "RFP Automation System" heading.
3. Enter your **Email** address in the email field.
4. Enter your **Password** in the password field.
5. Optionally, check **Remember me** to stay signed in.
6. Click **Sign In**.

> **[SCREENSHOT: Login Page — showing the login form with email field, password field, Remember me checkbox, and Sign In button]**

**After logging in**, you will be redirected to the **Dashboard** page.

### 2.2 Forgot Password

If you forget your password:

1. On the Login page, click **"Forgot password?"** (located to the right of the Remember me checkbox).
2. A dialog will appear asking for your email address.
3. Enter the email associated with your account.
4. Click **Send Reset Link**.
5. Check your email inbox for a password reset link.
6. Click the link in the email and follow the instructions to set a new password.

> **[SCREENSHOT: Forgot Password Dialog — showing email input and Send Reset Link button]**

### 2.3 Navigation Overview

After logging in, you will see two main areas:

**Left Sidebar** — Your main navigation panel. It contains:

| Section                 | Items             | Description                                   |
| ----------------------- | ----------------- | --------------------------------------------- |
| **Menu**          | Dashboard         | Main overview with RFP metrics and management |
|                         | RFP Insights      | Detailed RFP data with advanced filters       |
|                         | Material Insights | Material and keyword matching analysis        |
|                         | Activity Logs     | Automation run history and details            |
| **Quick Actions** | Download RFPs     | Trigger RFP download from company portals     |
|                         | Submit RFP        | Submit an RFP with file uploads               |
|                         | Decline RFP       | Decline participation in an RFP               |
| **Status Footer** | Automation Status | Shows whether automation is Ready or Running  |

The sidebar can be **collapsed** by clicking the arrow icon at the top-right corner of the sidebar, and expanded again by clicking the expand arrow. When collapsed, hovering over icons shows tooltip labels.

**Top Header** — Displays the page title, description, and page-specific action buttons (e.g., "View All RFPs").

> **[SCREENSHOT: Full Portal Layout — showing the sidebar (expanded) with all menu items, quick actions, and the main content area with the Dashboard]**

> **[SCREENSHOT: Sidebar Collapsed — showing the compact sidebar with just icons]**

---

## 3. Dashboard

The Dashboard is your home page and provides a quick overview of all RFP activity.

### 3.1 Metric Cards

At the top of the page, you will see four summary cards:

| Card                            | Description                                      |
| ------------------------------- | ------------------------------------------------ |
| **Total Downloaded RFPs** | Total number of RFPs downloaded from all portals |
| **Submitted**             | Number of RFPs that have been submitted          |
| **Declined**              | Number of RFPs that have been declined           |
| **Last Automation**       | Timestamp of the last automation run             |

**Tip:** Clicking on the Total, Submitted, or Declined cards navigates to the **RFP Insights** page with the corresponding filter pre-applied.

> **[SCREENSHOT: Dashboard Metric Cards — showing the four cards with sample numbers]**

### 3.2 RFP Management Section

Below the metrics, you'll find the main **RFP Management** area. This is organized in two levels of tabs:

**Company Tabs** (top row): Each tab represents a company (e.g., "Saudi Electricity Company", "Aramco e-Marketplace"). A badge next to each company name shows the total number of active RFPs for that company.

**Status Sub-Tabs** (second row): Within each company tab, RFPs are split by status:

| Status Tab          | Badge Color | Meaning                                              |
| ------------------- | ----------- | ---------------------------------------------------- |
| **Open**      | Amber       | RFPs awaiting action — can be submitted or declined |
| **Submitted** | Green       | RFPs already submitted to the portal                 |
| **Draft**     | Gray        | RFPs saved as draft on the portal                    |
| **Declined**  | Red         | RFPs where participation was declined                |

> **[SCREENSHOT: RFP Management Section — showing company tabs at top, status sub-tabs below, and the RFP table with sample data]**

### 3.3 RFP Table

Each status tab shows a table with the following columns:

| Column              | Description                                                                           |
| ------------------- | ------------------------------------------------------------------------------------- |
| **RFP ID**    | Unique identifier. Click to open the RFP on the external portal (opens in a new tab). |
| **Owner**     | The RFP owner name from the portal.                                                   |
| **Published** | Date the RFP was published.                                                           |
| **Deadline**  | RFP submission deadline date.                                                         |
| **Match %**   | Material match percentage — how well this RFP matches your company's materials.      |
| **Status**    | Current status badge (Open, Submitted, Draft, Declined).                              |
| **Actions**   | Action buttons available for this RFP.                                                |

**Match % Column Details:**

The Match % shows a color-coded badge and a mini progress bar:

| Color | Range         | Meaning               |
| ----- | ------------- | --------------------- |
| Green | 80% and above | Strong material match |
| Amber | 50% – 79%    | Moderate match        |
| Red   | Below 50%     | Weak match            |

Hover over a row and click the **eye icon** next to the Match % to view a detailed **Material Breakdown** dialog showing exactly which materials matched.

**Available Actions by Status:**

| Status    | Actions                                                          |
| --------- | ---------------------------------------------------------------- |
| Open      | **Submit** button, **Excel** download button         |
| Submitted | **Excel** download button                                  |
| Draft     | **Mark Submitted** button, **Excel** download button |
| Declined  | **Excel** download button                                  |

> **[SCREENSHOT: RFP Table Row — showing an Open RFP with Match % badge, eye icon, and Submit/Excel buttons]**

### 3.4 Sync Portal

Click the **Sync Portal** button (top-right of the RFP Management section) to refresh data from the company portals. This fetches the latest RFP statuses and updates the dashboard.

---

## 4. Key Workflows

### 4a. Submit an RFP

You can submit an RFP in two ways:

**Method 1: From the Dashboard table**

1. Navigate to **Dashboard**.
2. Select the company tab, then the **Open** status tab.
3. Find the RFP you want to submit.
4. Click the **Submit** button in the Actions column.
5. The Submit RFP dialog opens with the RFP ID pre-filled.

**Method 2: From the Sidebar Quick Action**

1. Click **Submit RFP** (green button) in the sidebar's Quick Actions section.
2. The Submit RFP dialog opens with a blank RFP ID field.

**Submit RFP Dialog Steps:**

1. **RFP ID** — Enter or confirm the RFP ID. The system validates it automatically:
   - A green checkmark appears if the RFP is found in the database.
   - A red error appears if the RFP is not found (it must be downloaded first).
2. **Company** — Auto-populated based on the RFP record. This field is locked when the RFP is validated.
3. **Upload Excel File** (required) — Click the dashed upload area to select your filled RFP Excel file (.xls or .xlsx).
4. **Technical PDF Files** (optional) — Click to upload one or more PDF files (Technical Data Sheets). You can remove uploaded PDFs by clicking the X button next to each file.
5. Click **Submit RFP** to start the automation.

The system will:

- Upload files to SharePoint
- Navigate to the company portal
- Fill in the submission form
- Upload the Excel and technical files
- Save the RFP as a draft on the portal

A success notification will appear when the process starts. You can track progress via the **Automation Status** indicator in the sidebar footer.

> **[SCREENSHOT: Submit RFP Dialog — showing RFP ID with green checkmark, auto-filled company, Excel upload area with a file selected, and PDF upload area]**

### 4b. Decline an RFP

1. Click **Decline RFP** (red button) in the sidebar's Quick Actions section.
2. The Decline RFP dialog opens.
3. **RFP Title** — Enter the exact RFP title. The system validates it:
   - Green checkmark = RFP found.
   - Red error = RFP not found in the database.
4. **Company** — Auto-populated and locked after validation.
5. Click **Decline RFP** (red button) to confirm.

The system will navigate to the portal and decline the RFP. A success notification appears when the process starts.

> **[SCREENSHOT: Decline RFP Dialog — showing RFP Title field with validation, company dropdown, and Decline RFP button]**

### 4c. Download RFPs

1. Click **Download RFPs** (blue button) in the sidebar's Quick Actions section.
2. The Download dialog opens with two options:
   - **All Companies** — Download from all configured company portals.
   - **Specific Company** — Select a single company from the dropdown.
3. Review the information about what the automation will do.
4. Click **Yes, Start Download** to begin.

The automation will:

- Navigate to the selected company portal(s)
- Scrape RFP listings and download RFP files
- Save information to the database
- Send email notifications for new RFPs found

> **[SCREENSHOT: Download RFPs Dialog — showing company dropdown set to "All Companies" and the confirmation details]**

### 4d. Download RFP Excel File

To download the Excel file for any individual RFP:

1. Find the RFP in the Dashboard table (any status tab).
2. Click the green **Excel** button in the Actions column.
3. The file will download to your browser's default download location.
4. A success notification confirms the download.

### 4e. Respond to RFP Email (Adaptive Card)

When a new RFP is found, team members receive an email notification in **Microsoft Outlook** with an interactive **Adaptive Card**.

**How to respond:**

1. Open the email notification in Outlook. You will see:
   - RFP details (ID, company, deadline)
   - A table listing all assigned team members (your name is highlighted)
   - Input fields for **Results** and **Remarks**
2. Fill in your **Results** (your assessment or bid information).
3. Fill in your **Remarks** (any additional notes or comments).
4. Click the **Submit** button within the email card.
5. The card updates in-place to show your submission was recorded.

**What happens next:** Once all team members have submitted their responses, a consolidated summary email is automatically sent to the configured stakeholders.

> **[SCREENSHOT: Outlook Adaptive Card Email — showing the RFP details, team member table with highlighted row, Results/Remarks input fields, and Submit button]**

> **[SCREENSHOT: Adaptive Card After Submission — showing the updated card with confirmation message]**

---

## 5. RFP Insights

Navigate to **RFP Insights** from the sidebar menu. This page provides a detailed, filterable view of all RFPs across all companies.

### 5.1 Stats Overview

Five stat cards at the top show:

| Stat            | Description                             |
| --------------- | --------------------------------------- |
| Total RFPs      | All RFPs in the system                  |
| Submitted       | RFPs that have been submitted           |
| Declined        | RFPs that were declined                 |
| Not Participant | RFPs with no participation action taken |
| Open            | Currently open RFPs                     |

### 5.2 Advanced Filters

The filter panel lets you narrow down RFPs using multiple criteria:

| Filter                          | Options                                         |
| ------------------------------- | ----------------------------------------------- |
| **Status**                | All, Open, Submitted, Declined, Not Participant |
| **Company**               | Dropdown populated from your data               |
| **Start Date / End Date** | Date range pickers                              |
| **Material Match**        | All, Matched, Not Matched                       |
| **Keyword Match**         | All, Matched, Not Matched                       |
| **Participation**         | All, Participated, Not Participated, Declined   |
| **Search**                | Free-text search by RFP ID, company, or owner   |

Click **Apply** to filter the results. Click **Reset** to clear all filters.

### 5.3 Column Visibility

Click the **Column Visibility** dropdown (gear icon) to toggle which columns appear in the table. Your selection is saved automatically and persists across sessions.

### 5.4 Results Table

The table displays filtered results with infinite scroll — as you scroll down, more rows load automatically. Each row shows:

- Status badge with icon
- Participation status
- Portal link button (opens RFP on the external portal)
- Download Excel button

> **[SCREENSHOT: RFP Insights Page — showing the stats overview, filter panel with some filters applied, and the results table]**

---

## 6. Material Insights

Navigate to **Material Insights** from the sidebar menu. This page analyzes how your company's materials and keywords match against RFPs.

### 6.1 Stats Overview

Four stat cards show:

- **Unique Materials** — Number of distinct material codes in the system
- **Unique Keywords** — Number of distinct keywords tracked
- **RFPs with Matches** — How many RFPs had at least one material or keyword match
- **Submitted RFPs** — How many matched RFPs were submitted

### 6.2 Tabs: Materials vs Keywords

Toggle between two views using the tabs:

- **Materials** — Analysis by material code
- **Keywords** — Analysis by keyword

### 6.3 Charts

Depending on the selected tab:

- **Bar Chart** — Top 10 Materials (or Keywords) ranked by RFP count
- **Pie Chart** — Keyword frequency distribution (visible on Keywords tab)

### 6.4 Filters

| Filter                  | Options                            |
| ----------------------- | ---------------------------------- |
| **Company**       | Filter by specific company         |
| **Participation** | All, Submitted, Declined, Open     |
| **Search**        | Search by material code or keyword |

### 6.5 Expandable Table

The main table shows materials or keywords as parent rows. Each row shows:

- Code/Keyword, Description, RFP Count, Companies, Submitted Count

Click the **expand arrow** on any row to reveal the individual RFPs that matched:

- RFP ID, Company, Deadline, Match Method (Exact or Keyword), Participation status

The table supports infinite scroll for large datasets.

> **[SCREENSHOT: Material Insights Page — showing the stats cards, tab selection, bar chart, and expandable table with one row expanded]**

---

## 7. Activity Logs

Navigate to **Activity Logs** from the sidebar menu. This page shows the history of all automation runs.

### 7.1 Statistics Cards

Four clickable cards at the top:

- **Total Runs** — All automation runs
- **Completed** — Successfully completed runs (click to filter)
- **Failed** — Runs that encountered errors (click to filter)
- **Running** — Currently active runs (click to filter)

### 7.2 Controls

- **Search box** — Search by RFP ID, action, or run ID
- **Page size selector** — Choose how many logs to show (50, 100, 200, or 500)

### 7.3 Run Cards

Each automation run is displayed as a card with:

- **Left color bar**: Green = Completed, Red = Failed, Blue = Running
- **Status icon**: Checkmark, X, or spinner
- **RFP ID and status badge**
- **Action name** (e.g., Download, Submit, Decline)
- **Start/End time**
- **Step progress** (e.g., 5 success / 0 failed / 5 total)
- **View Details** button

### 7.4 Run Detail Modal

Click **View Details** to open a modal with three tabs:

**Timeline Tab:**
A vertical timeline showing each step of the automation:

- Timestamp, action type, status, and details for each step
- Color-coded dots: Green = success, Red = failure, Gray = skipped

**Error Report Tab:**
If the run encountered errors, this tab shows:

- Error type and summary
- Context information
- Full traceback
- Suggested actions to resolve

**Screenshots Tab:**
If the automation captured browser screenshots during failure, they are displayed here for visual debugging.

> **[SCREENSHOT: Activity Logs Page — showing the stats cards, a mix of completed and failed run cards]**

> **[SCREENSHOT: Run Detail Modal — showing the Timeline tab with a vertical timeline of steps]**

---

## 8. Analytics

Navigate to **Analytics** from the sidebar menu (under Administration, if you have permission). This page provides visual charts and interactive drill-downs.

### 8.1 Key Metrics

Four cards at the top:

- **Total RFPs** — All RFPs in the system
- **Submitted** — Submitted count with participation rate percentage
- **Material Matched** — Count and percentage of RFPs with material matches
- **Keyword Matched** — Count and percentage of RFPs with keyword matches

**Tip:** Click any metric card to navigate to RFP Insights with the relevant filter applied.

### 8.2 Interactive Charts

The page displays four charts in a 2-column layout:

| Chart                             | Type                 | What It Shows                                                |
| --------------------------------- | -------------------- | ------------------------------------------------------------ |
| **RFP Status Distribution** | Donut chart          | Breakdown by Submitted (green), Open (amber), Declined (red) |
| **Top 5 Companies**         | Horizontal bar chart | Companies ranked by RFP count                                |
| **Material Matching**       | Donut chart          | Material Matched vs Not Matched                              |
| **Keyword Matching**        | Donut chart          | Keyword Matched vs Not Matched                               |

**Drill-Down:** Click on any chart segment or bar to navigate to the RFP Insights page with the corresponding filter pre-applied.

### 8.3 Participation by Company

Below the charts, a horizontal stacked bar chart shows participation breakdown per company:

- **Participated** (green), **Not Participated** (gray), **Declined** (red)

Click any segment to drill down to the corresponding filtered view.

> **[SCREENSHOT: Analytics Dashboard — showing the metric cards and four interactive charts]**

---

## 9. Profile Settings

Navigate to **Profile** by clicking your profile icon in the header or navigating to the profile page.

### 9.1 Update Profile Information

The Profile Information card shows:

- **Display Name** — Editable. Change your name and click **Save Changes**.
- **Email** — Read-only. Contact an administrator to change your email.
- **Mobile Number** — Optional. Add or update your phone number.
- **Role** — Read-only. Shows your assigned role (e.g., RFP Bidder).

### 9.2 Change Password

The Change Password card has three fields:

1. **Current Password** — Enter your existing password.
2. **New Password** — Enter a new password that meets these requirements:
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one number
3. **Confirm New Password** — Re-enter the new password.

Click **Change Password** to update. A success notification confirms the change.

> **[SCREENSHOT: Profile Settings Page — showing the Profile Information card and Change Password card]**

---

## 10. Automation Status Indicator

The bottom of the sidebar shows the **Automation Status**.

**When idle (Ready):**

- A green dot with the text "Ready" appears
- This means no automation is currently running

**When running:**

- The indicator changes to yellow/amber with "Running" text and an animated pulse
- A progress bar appears showing the percentage complete
- Detailed progress shows which operation is running:
  - **Download:** Shows current/total count and the current item being processed
  - **Submit:** Shows processing status message
  - **Decline:** Shows processing status message

**Important:** While automation is running, the corresponding Quick Action button in the sidebar is disabled (grayed out) to prevent duplicate runs. You can continue using other parts of the portal normally.

When the sidebar is collapsed, the automation status is shown as a small colored dot (green = Ready, amber = Running). Hover over it to see details.

---

## 11. Quick Reference

### Status Colors

| Status              | Color        | Badge Style                   |
| ------------------- | ------------ | ----------------------------- |
| Open                | Amber/Orange | Amber background, amber text  |
| Submitted           | Green        | Green background, green text  |
| Draft / Saved Draft | Gray         | Gray background, gray text    |
| Declined            | Red          | Red/Rose background, red text |

### Match % Thresholds

| Range         | Color     | Meaning                              |
| ------------- | --------- | ------------------------------------ |
| 80% and above | Green     | Strong match — high relevance       |
| 50% – 79%    | Amber     | Moderate match — review recommended |
| Below 50%     | Red       | Weak match — low relevance          |
| No data       | Gray dash | No material match data available     |

### Quick Action Buttons

| Button        | Color          | Action                                            |
| ------------- | -------------- | ------------------------------------------------- |
| Download RFPs | Blue gradient  | Opens download dialog to scrape RFPs from portals |
| Submit RFP    | Green gradient | Opens submit dialog to upload files and submit    |
| Decline RFP   | Red outline    | Opens decline dialog to decline participation     |

### Automation Run Statuses (Activity Logs)

| Status    | Indicator             | Meaning                       |
| --------- | --------------------- | ----------------------------- |
| Completed | Green bar + checkmark | Run finished successfully     |
| Failed    | Red bar + X icon      | Run encountered a fatal error |
| Running   | Blue bar + spinner    | Run is currently in progress  |

### Supported Companies

| Company                              | Portal                    |
| ------------------------------------ | ------------------------- |
| Saudi Electricity Company            | SEC procurement portal    |
| Aramco e-Marketplace                 | Aramco procurement portal |
| SABIC - Saudi Basic Industries Corp. | SABIC procurement portal  |
| HADEED - RAJHI STEEL                 | HADEED procurement portal |

---

## 12. Troubleshooting & FAQ

### "I can't log in"

- **Check your credentials**: Make sure you're using the correct email and password.
- **Account locked**: After 5 failed login attempts within 5 minutes, your account is locked for 30 minutes. Wait and try again, or contact your administrator to unlock it.
- **Password expired**: Passwords must be changed every 90 days. Use the Forgot Password link to reset.

### "The dashboard shows no data"

- **First time?** Click the **Download RFPs** button in the sidebar to download RFPs from the portals.
- **Data stale?** Click the **Sync Portal** button in the RFP Management section header to refresh.
- **Check Activity Logs** to see if a download automation has run recently.

### "RFP submission failed"

- Go to **Activity Logs** and find the failed run.
- Click **View Details** and check the **Error Report** tab for the error message.
- Common causes: portal was unavailable, file format was incorrect, or session timed out.
- If the issue persists, contact your administrator.

### "I don't see certain menu items"

- Menu items are based on your **role and permissions**. RFP Bidder users may not see admin sections like Users, Roles, or Audit Logs.
- If you need access, contact your administrator to update your role permissions.

### "My session expired"

- Sessions time out after **2 hours** of activity or **30 minutes** of inactivity.
- You will be redirected to the login page. Simply log in again to continue.
- Your unsaved form data (e.g., in a Submit dialog) will be lost — complete submissions promptly.

### "The Submit/Decline button is grayed out"

- This means the corresponding automation is already running. Check the **Automation Status** indicator at the bottom of the sidebar.
- Wait for the current operation to complete before starting a new one.

### "I entered an RFP ID but got an error in the Submit/Decline dialog"

- The message "RFP not found in database" means the RFP must be **downloaded first** before it can be submitted or declined.
- Use the **Download RFPs** action to download it, then try again.

### "Excel download is not working"

- Ensure your browser allows file downloads and pop-ups from the portal URL.
- Check if the RFP has an associated Excel file — some newly downloaded RFPs may not have files yet.

### "How do I know if my Adaptive Card response was saved?"

- After clicking Submit in the Outlook Adaptive Card, the card should update to show a confirmation message.
- If the card doesn't update, check your internet connection and try again.
- Your responses are saved in the system — check with your administrator if unsure.

---

*For additional support, contact your system administrator.*
