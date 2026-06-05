# RFP Automation - Server / PC Migration Tasks

**Total Tasks: 16**
- 12 Tasks x 3:00 Hours = 36 Hours
- 4 Tasks x 2:30 Hours = 10 Hours
- **Grand Total: 46 Hours**

---

## TASK OVERVIEW

| Task # | Task Name | Duration | Status |
|--------|-----------|----------|--------|
| Task 1 | New Server OS Setup & System Configuration | 3:00 Hr | [ ] |
| Task 2 | Install Python, Node.js & Development Tools | 3:00 Hr | [ ] |
| Task 3 | Project Source Code Transfer & Git Setup | 3:00 Hr | [ ] |
| Task 4 | Python Virtual Environment & Backend Dependencies | 3:00 Hr | [ ] |
| Task 5 | Playwright Browser Engine Setup & Validation | 3:00 Hr | [ ] |
| Task 6 | Frontend (React) Build & Deployment Setup | 3:00 Hr | [ ] |
| Task 7 | Azure AD, SharePoint & Graph API Configuration | 3:00 Hr | [ ] |
| Task 8 | Dataverse Connection & Table Mapping Verification | 3:00 Hr | [ ] |
| Task 9 | Power Automate, Email & Notification Setup | 3:00 Hr | [ ] |
| Task 10 | Dashboard Server Setup & Authentication Testing | 3:00 Hr | [ ] |
| Task 11 | RFP Download Automation End-to-End Testing | 3:00 Hr | [ ] |
| Task 12 | RFP Submit, Decline & Reminder Automation Testing | 3:00 Hr | [ ] |
| Task 13 | User Management, SAP & Admin Panel Verification | 2:30 Hr | [ ] |
| Task 14 | Logging, Error Handling & SharePoint Log Upload | 2:30 Hr | [ ] |
| Task 15 | Windows Task Scheduler, Firewall & Network Setup | 2:30 Hr | [ ] |
| Task 16 | Go-Live, Smoke Testing & Old Server Decommission | 2:30 Hr | [ ] |

---
---

# TASK 1: New Server OS Setup & System Configuration
**Duration: 3:00 Hours**

## Objective
Prepare the new Windows server/PC with all OS-level configurations, updates, and prerequisites before installing any application software.

## Steps

### 1.1 - Windows OS Initial Setup (45 min)
- [ ] Boot the new server and complete Windows 11/Server initial setup
- [ ] Set computer name (e.g., `BAHRA-RFP-SERVER`)
- [ ] Set timezone to correct region (e.g., Asia/Riyadh - UTC+3)
- [ ] Connect to network (LAN/Wi-Fi)
- [ ] Assign static IP address if required for server
  ```
  Control Panel > Network > Adapter Settings > IPv4 Properties
  ```
- [ ] Verify internet connectivity: open browser and test

### 1.2 - Windows Updates (60 min)
- [ ] Go to Settings > Windows Update
- [ ] Download and install all pending updates
- [ ] Restart if required
- [ ] Check for updates again until "You're up to date"
- [ ] Enable automatic updates for security patches

### 1.3 - System Configuration (30 min)
- [ ] Disable Windows Sleep/Hibernate (server should run 24/7)
  ```
  Control Panel > Power Options > Change plan settings > Never sleep
  ```
- [ ] Set display to never turn off (optional)
- [ ] Enable Remote Desktop (if remote access needed)
  ```
  Settings > System > Remote Desktop > Enable
  ```
- [ ] Note down the server IP address:
  ```bash
  ipconfig
  ```
- [ ] Create a dedicated Windows user account for running the application (optional)

### 1.4 - Create Folder Structure (15 min)
- [ ] Create project directory:
  ```bash
  mkdir C:\python
  mkdir C:\python\RFP-automation
  ```
- [ ] Verify the Downloads folder exists: `%USERPROFILE%\Downloads`
- [ ] Set folder permissions: ensure current user has Full Control on `C:\python\`

### 1.5 - Document Server Details (30 min)
- [ ] Record the following in a document:
  - Server Name / Hostname
  - IP Address (static)
  - Windows Version
  - Admin username
  - Domain joined? (Yes/No)
  - Available RAM and Disk space
- [ ] Share this document with the team

## Deliverables
- [ ] Windows fully updated and configured
- [ ] Static IP assigned (if needed)
- [ ] Remote Desktop enabled
- [ ] `C:\python\` folder created with proper permissions
- [ ] Server details documented

---
---

# TASK 2: Install Python, Node.js & Development Tools
**Duration: 3:00 Hours**

## Objective
Install all required development tools and runtime environments on the new server.

## Steps

### 2.1 - Install Python 3.10 (30 min)
- [ ] Download Python 3.10.x from https://www.python.org/downloads/release/python-31011/
- [ ] Run installer:
  - **CHECK** "Add Python 3.10 to PATH"
  - Select "Customize installation"
  - Check all Optional Features
  - Check "Install for all users"
  - Install location: `C:\Python310\` (or default)
- [ ] Verify installation:
  ```bash
  python --version
  # Expected: Python 3.10.x

  pip --version
  # Expected: pip xx.x.x
  ```
- [ ] Upgrade pip:
  ```bash
  python -m pip install --upgrade pip
  ```

### 2.2 - Install Node.js v24 (30 min)
- [ ] Download Node.js v24.x LTS from https://nodejs.org/
- [ ] Run installer with default settings
- [ ] Verify installation:
  ```bash
  node --version
  # Expected: v24.x.x

  npm --version
  ```
- [ ] Set npm global config (optional):
  ```bash
  npm config set registry https://registry.npmjs.org/
  ```

### 2.3 - Install Git (30 min)
- [ ] Download Git from https://git-scm.com/download/win
- [ ] Run installer:
  - Use default settings
  - Select "Use Git from the Windows Command Prompt"
  - Line ending: "Checkout as-is, commit Unix-style"
- [ ] Verify:
  ```bash
  git --version
  ```
- [ ] Configure Git user (for commit history):
  ```bash
  git config --global user.name "Bahra RFP Server"
  git config --global user.email "rfp-server@bahra-cables.com"
  ```

### 2.4 - Install Google Chrome (20 min)
- [ ] Download Google Chrome from https://www.google.com/chrome/
- [ ] Install with default settings
- [ ] Open Chrome once to complete initial setup
- [ ] Note Chrome version: `chrome://version`
- [ ] Chrome is needed because Playwright uses Chromium engine

### 2.5 - Install Visual Studio Code (Optional) (20 min)
- [ ] Download VS Code from https://code.visualstudio.com/
- [ ] Install with default settings
- [ ] Install Python extension
- [ ] This helps for debugging and config editing on the server

### 2.6 - Install Additional Tools (20 min)
- [ ] Install Microsoft Visual C++ Build Tools (may be needed for some Python packages):
  - Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/
  - Install "Desktop development with C++" workload
- [ ] Install 7-Zip or WinRAR (for extracting archives if needed)

### 2.7 - Verify All Installations (30 min)
- [ ] Open a NEW Command Prompt (to pick up PATH changes)
- [ ] Run verification commands:
  ```bash
  python --version
  pip --version
  node --version
  npm --version
  git --version
  ```
- [ ] Take a screenshot of all version outputs
- [ ] If any command fails, check PATH environment variable:
  ```
  System Properties > Environment Variables > Path
  ```

## Deliverables
- [ ] Python 3.10.x installed and in PATH
- [ ] Node.js v24.x installed and in PATH
- [ ] Git installed and configured
- [ ] Google Chrome installed
- [ ] All versions verified via command line

---
---

# TASK 3: Project Source Code Transfer & Git Setup
**Duration: 3:00 Hours**

## Objective
Transfer the complete RFP Automation project source code from the old server to the new server using Git or manual copy.

## Steps

### 3.1 - Backup Old Server (45 min)
- [ ] On the OLD server, create a full backup:
  ```bash
  # Compress project (exclude unnecessary folders)
  # Use 7-Zip or WinRAR to create archive
  ```
- [ ] Files to backup:
  - `C:\python\RFP-automation\` (full project)
  - Any Windows Task Scheduler exports
  - Any custom scripts outside the project
- [ ] Files to EXCLUDE from backup (will be recreated):
  - `env\` folder (Python virtual environment - ~500MB)
  - `frontend\node_modules\` folder (~300MB)
  - `__pycache__\` folders
  - `ALLRFPs\` folder (auto-created)
  - `LOGS\` folder (auto-created)
  - `ALLRFPs_old\` folder

### 3.2 - Option A: Git Clone (Recommended) (30 min)
- [ ] On the new server, open Command Prompt:
  ```bash
  cd C:\python
  git clone <your-repository-url> RFP-automation
  cd RFP-automation
  ```
- [ ] Checkout the correct branch:
  ```bash
  git branch -a
  git checkout Bhara-env-rfp-system
  ```
- [ ] Verify all files are present:
  ```bash
  dir
  # Should see: automation_main.py, dashboard_main.py, config\, helpers\, routes\, etc.
  ```

### 3.3 - Option B: Manual File Copy (45 min)
- [ ] Copy the backup archive to new server via:
  - USB drive
  - Network shared folder
  - Cloud storage (OneDrive/SharePoint)
- [ ] Extract to `C:\python\RFP-automation\`
- [ ] Verify folder structure:
  ```
  C:\python\RFP-automation\
  ├── automation_logic.py
  ├── automation_main.py
  ├── dashboard_main.py
  ├── requirements.txt
  ├── requirements_sharepoint_upload.txt
  ├── config\
  │   └── config.py
  ├── core\
  │   ├── common_imports.py
  │   ├── common_process.py
  │   └── local_log.py
  ├── rfp\
  │   ├── download_rfp.py
  │   ├── submit_rfp.py
  │   ├── decline_rfp.py
  │   └── rfp_reminder.py
  ├── helpers\
  │   ├── core_helper.py
  │   ├── sharepoint_helper.py
  │   ├── dataverse_helper.py
  │   ├── email_helper.py
  │   ├── failure_logger.py
  │   └── ...
  ├── routes\
  │   ├── api.py
  │   ├── auth.py
  │   ├── automation.py
  │   ├── dashboard.py
  │   └── user_management.py
  ├── services\
  │   ├── dashboard_service.py
  │   ├── user_service.py
  │   ├── sap_service.py
  │   └── role_service.py
  ├── frontend\
  │   ├── package.json
  │   ├── vite.config.ts
  │   └── src\
  └── static\
  ```

### 3.4 - Verify Critical Files (30 min)
- [ ] Check `config\config.py` exists and has content
- [ ] Check `requirements.txt` exists (127 packages)
- [ ] Check `frontend\package.json` exists
- [ ] Check `automation_logic.py` exists
- [ ] Check `dashboard_main.py` exists
- [ ] Check `automation_main.py` exists
- [ ] Check all route files exist in `routes\`
- [ ] Check all helper files exist in `helpers\`
- [ ] Check all service files exist in `services\`
- [ ] Check all RFP files exist in `rfp\`

### 3.5 - Clean Unnecessary Files (30 min)
- [ ] Delete `__pycache__` folders if copied:
  ```bash
  for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
  ```
- [ ] Delete `env\` folder if copied (will recreate fresh)
- [ ] Delete `node_modules\` if copied (will reinstall fresh)
- [ ] Delete `.pyc` files:
  ```bash
  del /s /q *.pyc
  ```

### 3.6 - Initialize Git (if manual copy) (15 min)
- [ ] If you used manual copy and need Git:
  ```bash
  cd C:\python\RFP-automation
  git init
  git remote add origin <your-repository-url>
  git fetch
  git checkout Bhara-env-rfp-system
  ```

## Deliverables
- [ ] All source code transferred to `C:\python\RFP-automation\`
- [ ] Folder structure verified
- [ ] All critical files present
- [ ] No unnecessary files (pycache, env, node_modules)
- [ ] Git connected to remote repository

---
---

# TASK 4: Python Virtual Environment & Backend Dependencies
**Duration: 3:00 Hours**

## Objective
Create a fresh Python virtual environment and install all 127 backend Python packages with proper version matching.

## Steps

### 4.1 - Create Virtual Environment (15 min)
- [ ] Open Command Prompt as Administrator
  ```bash
  cd C:\python\RFP-automation
  python -m venv env
  ```
- [ ] Verify env created:
  ```bash
  dir env\Scripts\python.exe
  # Should show the file exists
  ```

### 4.2 - Activate Virtual Environment (5 min)
- [ ] Activate:
  ```bash
  # CMD
  env\Scripts\activate

  # PowerShell
  env\Scripts\Activate.ps1
  ```
- [ ] Verify activation (prompt should show `(env)`):
  ```bash
  python --version
  # Should show Python 3.10.x

  where python
  # Should point to env\Scripts\python.exe
  ```

### 4.3 - Upgrade pip & setuptools (10 min)
- [ ] Upgrade pip:
  ```bash
  python -m pip install --upgrade pip setuptools wheel
  ```

### 4.4 - Install Main Requirements (60 min)
- [ ] Install all packages:
  ```bash
  pip install -r requirements.txt
  ```
- [ ] Watch for errors. Common issues and fixes:
  - **pydivert**: May need admin privileges
  - **cryptography**: May need Visual C++ Build Tools
  - **numpy/pandas**: Should install fine on Python 3.10
  - **playwright**: Installs Python bindings (browser installed in Task 5)
- [ ] If a package fails, install it individually:
  ```bash
  pip install <package-name>==<version>
  ```

### 4.5 - Install SharePoint Upload Requirements (15 min)
- [ ] Install additional packages:
  ```bash
  pip install -r requirements_sharepoint_upload.txt
  ```

### 4.6 - Verify Key Packages (30 min)
- [ ] Test critical imports one by one:
  ```bash
  python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
  python -c "import flask; print(f'Flask: {flask.__version__}')"
  python -c "import msal; print('MSAL: OK')"
  python -c "import playwright; print('Playwright: OK')"
  python -c "import pandas; print(f'Pandas: {pandas.__version__}')"
  python -c "import requests; print(f'Requests: {requests.__version__}')"
  python -c "import selenium; print(f'Selenium: {selenium.__version__}')"
  python -c "import uvicorn; print(f'Uvicorn: {uvicorn.__version__}')"
  python -c "import reportlab; print('ReportLab: OK')"
  python -c "import xlrd; print('xlrd: OK')"
  python -c "import sentry_sdk; print('Sentry: OK')"
  python -c "from pydantic import BaseModel; print('Pydantic: OK')"
  ```

### 4.7 - Verify Package Count (15 min)
- [ ] Check total installed packages:
  ```bash
  pip list | find /c /v ""
  # Should be approximately 127+ packages
  ```
- [ ] Generate installed packages list for comparison:
  ```bash
  pip freeze > installed_packages.txt
  ```
- [ ] Compare with original requirements:
  ```bash
  # Manual check: open both files and compare
  ```

### 4.8 - Test Backend Module Imports (30 min)
- [ ] Test project-specific imports:
  ```bash
  cd C:\python\RFP-automation
  python -c "from config.config import TENANT_ID; print('Config: OK')"
  python -c "from helpers.dataverse_helper import DataverseClient; print('Dataverse Helper: OK')"
  python -c "from helpers.sharepoint_helper import GraphClient; print('SharePoint Helper: OK')"
  python -c "from helpers.core_helper import clean_rfp_title; print('Core Helper: OK')"
  ```
- [ ] If any import fails, check the error and install missing packages

## Deliverables
- [ ] Virtual environment created at `env\`
- [ ] All 127+ packages from `requirements.txt` installed
- [ ] SharePoint upload packages installed
- [ ] All key package imports verified
- [ ] Project module imports working

---
---

# TASK 5: Playwright Browser Engine Setup & Validation
**Duration: 3:00 Hours**

## Objective
Install Playwright Chromium browser engine, configure browser automation settings, and validate that the browser can launch and navigate correctly on the new server.

## Steps

### 5.1 - Install Playwright Chromium Browser (30 min)
- [ ] Activate virtual environment:
  ```bash
  cd C:\python\RFP-automation
  env\Scripts\activate
  ```
- [ ] Install Chromium browser:
  ```bash
  playwright install chromium
  ```
- [ ] This downloads ~150MB Chromium browser to:
  ```
  %USERPROFILE%\AppData\Local\ms-playwright\
  ```
- [ ] Verify download:
  ```bash
  playwright install --dry-run
  ```

### 5.2 - Install Playwright System Dependencies (20 min)
- [ ] Install system dependencies (if prompted):
  ```bash
  playwright install-deps chromium
  ```
- [ ] On Windows, most dependencies are already included

### 5.3 - Test Basic Browser Launch (30 min)
- [ ] Create a test script `test_playwright.py`:
  ```python
  import asyncio
  from playwright.async_api import async_playwright

  async def test():
      async with async_playwright() as p:
          browser = await p.chromium.launch(headless=False)
          page = await browser.new_page()
          await page.goto("https://www.google.com")
          print(f"Title: {await page.title()}")
          await browser.close()
          print("Browser test PASSED!")

  asyncio.run(test())
  ```
- [ ] Run the test:
  ```bash
  python test_playwright.py
  ```
- [ ] Chrome window should open, navigate to Google, and close
- [ ] Delete test script after success

### 5.4 - Test Headless Mode (30 min)
- [ ] Test headless mode (how automation runs in production):
  ```python
  # Modify test: headless=True
  browser = await p.chromium.launch(headless=True)
  ```
- [ ] Verify it runs without opening a visible window

### 5.5 - Test Persistent Context (30 min)
- [ ] The RFP automation uses `launch_persistent_context`. Test this:
  ```python
  import asyncio
  from playwright.async_api import async_playwright

  async def test_persistent():
      async with async_playwright() as p:
          context = await p.chromium.launch_persistent_context(
              user_data_dir="./test_browser_data",
              headless=False,
              accept_downloads=True
          )
          page = await context.new_page()
          await page.goto("https://www.google.com")
          print(f"Title: {await page.title()}")
          await context.close()
          print("Persistent context test PASSED!")

  asyncio.run(test_persistent())
  ```
- [ ] Clean up test data:
  ```bash
  rmdir /s /q test_browser_data
  ```

### 5.6 - Test Download Functionality (30 min)
- [ ] Test that browser can download files:
  ```python
  import asyncio, os
  from playwright.async_api import async_playwright

  async def test_download():
      download_dir = os.path.expanduser("~/Downloads")
      async with async_playwright() as p:
          context = await p.chromium.launch_persistent_context(
              user_data_dir="./test_browser_data",
              headless=False,
              accept_downloads=True
          )
          page = await context.new_page()
          # Navigate to a test page
          await page.goto("https://www.google.com")
          print(f"Downloads folder exists: {os.path.exists(download_dir)}")
          print(f"Downloads folder writable: {os.access(download_dir, os.W_OK)}")
          await context.close()
          print("Download path test PASSED!")

  asyncio.run(test_download())
  ```
- [ ] Verify Downloads folder has write permission

### 5.7 - Test Ariba Portal Connectivity (20 min)
- [ ] Test that the server can reach the Ariba portal:
  ```python
  import asyncio
  from playwright.async_api import async_playwright

  async def test_ariba():
      async with async_playwright() as p:
          browser = await p.chromium.launch(headless=False)
          page = await browser.new_page()
          try:
              await page.goto("https://service.ariba.com", timeout=30000)
              print(f"Ariba reachable! Title: {await page.title()}")
          except Exception as e:
              print(f"Cannot reach Ariba: {e}")
          await browser.close()

  asyncio.run(test_ariba())
  ```
- [ ] If Ariba is not reachable, check firewall/proxy settings

### 5.8 - Windows ProactorEventLoop Verification (10 min)
- [ ] The project uses `WindowsProactorEventLoopPolicy` for Playwright. Verify:
  ```python
  import sys, asyncio
  if sys.platform == "win32":
      asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
      print("ProactorEventLoop: OK")
  ```

## Deliverables
- [ ] Playwright Chromium browser installed
- [ ] Browser launches in headed mode
- [ ] Browser launches in headless mode
- [ ] Persistent context works
- [ ] Download functionality works
- [ ] Ariba portal is reachable
- [ ] ProactorEventLoop configured correctly

---
---

# TASK 6: Frontend (React) Build & Deployment Setup
**Duration: 3:00 Hours**

## Objective
Install all frontend npm dependencies, build the React (Vite + TypeScript) dashboard, and configure it to work with the backend API.

## Steps

### 6.1 - Install Frontend Dependencies (30 min)
- [ ] Navigate to frontend folder:
  ```bash
  cd C:\python\RFP-automation\frontend
  ```
- [ ] Install all npm packages:
  ```bash
  npm install
  ```
- [ ] This installs ~43 direct dependencies including:
  - React 18, React Router, React Hook Form
  - Radix UI components
  - TanStack React Query & Table
  - Tailwind CSS, Vite, TypeScript
  - Zustand (state management)
  - Sonner (toast notifications)
  - Lucide React (icons)
  - Zod (validation)

### 6.2 - Verify node_modules (15 min)
- [ ] Check node_modules created:
  ```bash
  dir node_modules
  ```
- [ ] Check for any peer dependency warnings in npm output
- [ ] If warnings about peer dependencies, they are usually non-blocking

### 6.3 - TypeScript Compilation Check (20 min)
- [ ] Run TypeScript check:
  ```bash
  npx tsc --noEmit
  ```
- [ ] Fix any TypeScript errors if they appear
- [ ] Common fix: ensure `@types/node`, `@types/react`, `@types/react-dom` are installed

### 6.4 - Build Frontend for Production (30 min)
- [ ] Run production build:
  ```bash
  npm run build
  ```
- [ ] This executes: `tsc -b && vite build`
- [ ] Verify `dist\` folder is created:
  ```bash
  dir dist
  # Should contain: index.html, assets\ folder
  ```
- [ ] Check build output size:
  ```bash
  dir /s dist
  ```

### 6.5 - Verify Frontend Pages (30 min)
- [ ] Check all page components exist in `src\pages\`:
  - [ ] `login.tsx` - Login page
  - [ ] `dashboard.tsx` - Main dashboard
  - [ ] `logs.tsx` - Automation logs
  - [ ] `rfp-insights.tsx` - RFP insights
  - [ ] `profile.tsx` - User profile
  - [ ] `admin\users.tsx` - User management (admin)
  - [ ] `admin\sap-logs.tsx` - SAP logs (admin)

### 6.6 - Configure Vite Proxy (20 min)
- [ ] Review `vite.config.ts`:
  ```typescript
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // Backend API
        changeOrigin: true,
      },
    },
  },
  ```
- [ ] If backend will run on a different port, update the target
- [ ] If backend will run on a different IP (not localhost), update accordingly

### 6.7 - Test Frontend Dev Server (20 min)
- [ ] Start dev server:
  ```bash
  npm run dev
  ```
- [ ] Open browser: `http://localhost:3000`
- [ ] Should show the login page (backend not running yet, API calls will fail - that's OK)
- [ ] Stop dev server: `Ctrl+C`

### 6.8 - Verify Static Files Serving (15 min)
- [ ] The backend serves static files from `static\` folder
- [ ] The built frontend `dist\` is served by the backend in production
- [ ] Verify `static\` folder exists at project root
- [ ] Check if `dashboard_main.py` has StaticFiles mount configured

## Deliverables
- [ ] All npm packages installed (node_modules created)
- [ ] TypeScript compilation passes
- [ ] Production build successful (dist folder created)
- [ ] All 7 page components verified
- [ ] Vite proxy configured correctly
- [ ] Dev server starts without errors

---
---

# TASK 7: Azure AD, SharePoint & Graph API Configuration
**Duration: 3:00 Hours**

## Objective
Configure and test the Microsoft Azure AD authentication, SharePoint Graph API connection, and verify file upload/download capabilities on the new server.

## Steps

### 7.1 - Verify Azure AD Credentials (30 min)
- [ ] Open `config\config.py` and verify:
  ```python
  TENANT_ID = "46aa82d0-1a4b-4b08-b520-514ccbe1e7ca"
  CLIENT_ID = "97312492-991a-46be-91de-62430026f72d"
  CLIENT_SECRET = "pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"
  ```
- [ ] Check if CLIENT_SECRET has expired in Azure Portal:
  - Go to Azure Portal > App Registrations > Find app by CLIENT_ID
  - Check Certificates & Secrets > Client secrets
  - If expired, create a new secret and update config.py
- [ ] Note the expiry date of the current secret

### 7.2 - Test Azure AD Token Acquisition (30 min)
- [ ] Activate virtual env and run:
  ```python
  from msal import ConfidentialClientApplication

  app = ConfidentialClientApplication(
      "97312492-991a-46be-91de-62430026f72d",
      authority="https://login.microsoftonline.com/46aa82d0-1a4b-4b08-b520-514ccbe1e7ca",
      client_credential="pDN8Q~kLKXRoOmEB5PvLRDo-zVH2o91IjRtaJagr"
  )
  result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
  if "access_token" in result:
      print("Token acquired successfully!")
      print(f"Token length: {len(result['access_token'])}")
  else:
      print(f"FAILED: {result.get('error_description')}")
  ```
- [ ] If token fails, check:
  - Internet connectivity
  - DNS resolution for `login.microsoftonline.com`
  - Firewall rules blocking HTTPS (port 443)

### 7.3 - Verify SharePoint Configuration (30 min)
- [ ] Verify SharePoint settings in config.py:
  ```python
  SHAREPOINT_HOSTNAME = "bahracables.sharepoint.com"
  SITE_PATH = "/sites/LiveSite/RFPAutomation"
  DRIVE_NAME = "Documents"
  SP_BASE_FOLDER = "RFP-logs"
  ```
- [ ] Test SharePoint site resolution:
  ```python
  import requests

  # Use the token from 7.2
  headers = {"Authorization": f"Bearer {token}"}
  url = "https://graph.microsoft.com/v1.0/sites/bahracables.sharepoint.com:/sites/LiveSite/RFPAutomation"
  resp = requests.get(url, headers=headers)
  print(f"Status: {resp.status_code}")
  print(f"Site ID: {resp.json().get('id')}")
  ```

### 7.4 - Test GraphClient Connection (30 min)
- [ ] Test the full GraphClient from the project:
  ```python
  from helpers.sharepoint_helper import GraphClient
  from config.config import *

  client = GraphClient(CLIENT_ID, CLIENT_SECRET, TENANT_ID, SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME)
  client.auth()
  client.resolve_site_and_drive()
  print(f"Site ID: {client.site_id}")
  print(f"Drive ID: {client.drive_id}")
  print("GraphClient: CONNECTED!")
  ```

### 7.5 - Test SharePoint File Upload (30 min)
- [ ] Test uploading a small test file:
  ```python
  # Create a test file
  test_content = b"Test file from new server"
  client.upload_file(
      folder_path="RFP-logs/test-migration",
      file_name="migration_test.txt",
      content=test_content
  )
  print("File uploaded successfully!")
  ```
- [ ] Verify the file appears in SharePoint:
  - Open SharePoint > Documents > RFP-logs > test-migration
- [ ] Delete the test file from SharePoint

### 7.6 - Test SharePoint Folder Listing (20 min)
- [ ] List files in the base folder:
  ```python
  # Test listing folders/files
  items = client.list_folder("RFP-logs")
  for item in items[:5]:
      print(f"  {item['name']}")
  ```

### 7.7 - Verify SharePoint Paths (20 min)
- [ ] Verify all SharePoint paths in config:
  - [ ] `SP_BASE_FOLDER` = "RFP-logs"
  - [ ] `SP_BASE_FOLDER_RFP_UPLOAD_FILES` = "RFP-logs/RFP-upload-files"
  - [ ] `SP_FAILURE_LOGS_FOLDER` = "RFP-logs/automation-error-logs"
  - [ ] `TDS_FILE_PATH` - TDS files SharePoint URL

### 7.8 - Document Connection Status (10 min)
- [ ] Record test results:
  - Azure AD Token: PASS/FAIL
  - SharePoint Site Resolution: PASS/FAIL
  - Drive Resolution: PASS/FAIL
  - File Upload: PASS/FAIL
  - Folder Listing: PASS/FAIL

## Deliverables
- [ ] Azure AD token acquisition working
- [ ] SharePoint site and drive resolved
- [ ] File upload tested and verified
- [ ] Folder listing working
- [ ] All SharePoint paths verified
- [ ] Connection status documented

---
---

# TASK 8: Dataverse Connection & Table Mapping Verification
**Duration: 3:00 Hours**

## Objective
Configure and test the Microsoft Dataverse (Power Platform) connection, verify all table mappings, column names, and CRUD operations work correctly on the new server.

## Steps

### 8.1 - Verify Dataverse Configuration (20 min)
- [ ] Open `config\config.py` and verify:
  ```python
  RESOURCE_URL = "https://operations-bahrauat-1.crm11.dynamics.com"
  ```
- [ ] Verify all table names:
  | Table | Logical Name | API Name |
  |-------|-------------|----------|
  | Automation Log | `cr673_bahra_automation_log1` | `cr673_bahra_automation_log1s` |
  | RFP Activity | `cr673_requestforproposal` | `cr673_requestforproposals` |
  | Users | `cr673_bahra_users` | `cr673_bahra_userses` |
  | SAP Password | `cr673_bahra_sap_infomation` | `cr673_bahra_sap_infomations` |
  | Schedules | `cr673_bahra_automation_schedules` | `cr673_bahra_automation_scheduleses` |
  | RFP Status | `cr673_bhara_rfp_status` | `cr673_bhara_rfp_statuses` |

### 8.2 - Test Dataverse Token (30 min)
- [ ] Activate virtual env and test:
  ```python
  from helpers.dataverse_helper import DataverseClient
  from config.config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL

  dv = DataverseClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET, RESOURCE_URL)
  print(f"Token acquired: {dv.token[:20]}...")
  print("Dataverse connection: OK!")
  ```

### 8.3 - Test Automation Log Table (30 min)
- [ ] Read records from Automation Log table:
  ```python
  from config.config import AUTOMATION_LOG_TABLE_API

  records = dv.get_rows(AUTOMATION_LOG_TABLE_API, top=5)
  print(f"Automation Log records found: {len(records)}")
  for r in records[:3]:
      print(f"  - {r}")
  ```
- [ ] Verify column mappings match expected display names

### 8.4 - Test RFP Activity Table (30 min)
- [ ] Read records from RFP Activity table:
  ```python
  from config.config import RFP_ACTIVITY_LOG_TABLE_API

  records = dv.get_rows(RFP_ACTIVITY_LOG_TABLE_API, top=5)
  print(f"RFP Activity records found: {len(records)}")
  ```

### 8.5 - Test Users Table (20 min)
- [ ] Read records from Users table:
  ```python
  from config.config import USERS_TABLE_API

  records = dv.get_rows(USERS_TABLE_API, top=5)
  print(f"Users found: {len(records)}")
  ```
- [ ] Verify user records match expected data

### 8.6 - Test SAP Password Table (20 min)
- [ ] Read records from SAP table:
  ```python
  from config.config import SAP_PASSWORD_TABLE_API

  records = dv.get_rows(SAP_PASSWORD_TABLE_API, top=5)
  print(f"SAP records found: {len(records)}")
  ```

### 8.7 - Test Schedules Table (20 min)
- [ ] Read records from Schedules table:
  ```python
  from config.config import AUTOMATION_SCHEDULE_TABLE_API

  records = dv.get_rows(AUTOMATION_SCHEDULE_TABLE_API, top=5)
  print(f"Schedule records found: {len(records)}")
  ```

### 8.8 - Test RFP Status Table (20 min)
- [ ] Read records from RFP Status table:
  ```python
  from config.config import RFP_STATUS_TABLE_API

  records = dv.get_rows(RFP_STATUS_TABLE_API, top=5)
  print(f"RFP Status records found: {len(records)}")
  ```

### 8.9 - Test Column Mapping Cache (10 min)
- [ ] Verify column mapping works:
  ```python
  from config.config import AUTOMATION_LOG_TABLE_LOGICAL

  mapping = dv.get_column_mapping(AUTOMATION_LOG_TABLE_LOGICAL)
  print(f"Columns: {list(mapping.keys())[:10]}")
  ```

### 8.10 - Document Dataverse Status (10 min)
- [ ] Record test results for all 6 tables:
  | Table | Read | Status |
  |-------|------|--------|
  | Automation Log | PASS/FAIL | |
  | RFP Activity | PASS/FAIL | |
  | Users | PASS/FAIL | |
  | SAP Password | PASS/FAIL | |
  | Schedules | PASS/FAIL | |
  | RFP Status | PASS/FAIL | |

## Deliverables
- [ ] Dataverse token acquisition working
- [ ] All 6 tables accessible (read operations)
- [ ] Column mappings verified
- [ ] No table name mismatches
- [ ] Dataverse status documented

---
---

# TASK 9: Power Automate, Email & Notification Setup
**Duration: 3:00 Hours**

## Objective
Configure and test Power Automate flow triggers, email notification system, and verify all notification endpoints work from the new server.

## Steps

### 9.1 - Verify Power Automate Flow URLs (20 min)
- [ ] Open `config\config.py` and verify:
  ```python
  FLOW_URL = "https://8250a9bfeb76ef4cba38b14a0bb011.0c.environment..."
  FORGOT_PASSWORD_FLOW_URL = "https://8250a9bfeb76ef4cba38b14a0bb011.0c.environment..."
  ```
- [ ] These URLs contain API keys - they are server-independent (same URL works from any server)

### 9.2 - Test Power Automate Main Flow (40 min)
- [ ] Test the main flow connectivity:
  ```python
  import requests

  # Test with a minimal payload
  test_payload = {
      "test": True,
      "message": "Migration test from new server"
  }

  resp = requests.post(FLOW_URL, json=test_payload, timeout=30)
  print(f"Status: {resp.status_code}")
  print(f"Response: {resp.text[:200]}")
  ```
- [ ] Check if the flow was triggered in Power Automate portal
- [ ] If timeout, check firewall rules for outbound HTTPS

### 9.3 - Test Forgot Password Flow (30 min)
- [ ] Test forgot password flow:
  ```python
  test_payload = {"email": "test@example.com", "test": True}
  resp = requests.post(FORGOT_PASSWORD_FLOW_URL, json=test_payload, timeout=30)
  print(f"Status: {resp.status_code}")
  ```

### 9.4 - Verify Email Recipients Configuration (20 min)
- [ ] Review all email recipients in `config\config.py`:
  ```python
  EMAIL_TO_RFP_SUBMITTED = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_RFP_DECLINED = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_RFP_ERROR_IN_SUBMISSION = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_RFP_ERROR_IN_DECLINE = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_AUTOMATION_FAILURE = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_RFP_SAVED_DRAFT = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_NO_MATCHED_DATA = "Manish.Soni@dynatechconsultancy.com"
  EMAIL_TO_RFP_REMINDER = "Manish.Soni@dynatechconsultancy.com;shubham.kumbhar@dynatechconsultancy.com"
  ```
- [ ] Update email addresses if they should change for the new server
- [ ] Confirm with team which emails should receive notifications

### 9.5 - Test Email Helper Functions (30 min)
- [ ] Test email helper module imports:
  ```python
  from helpers.email_helper import create_file_names_and_source_files

  # Test with sample data
  result = create_file_names_and_source_files(
      ["SEC RFP-c001983", "SEC RFP-c89722"],
      "Saudi Electricity Company"
  )
  print(f"FileNames: {result['FileNames']}")
  print(f"SourceFiles: {result['SourceFiles']}")
  ```

### 9.6 - Test Email Sending via Power Automate (30 min)
- [ ] Send a test email through the flow:
  ```python
  import requests

  email_data = {
      "Subject": "RFP Automation - Migration Test",
      "Body": "This is a test email from the new RFP automation server.",
      "To": "Manish.Soni@dynatechconsultancy.com",
      "FileNames": [],
      "SourceFiles": []
  }

  resp = requests.post(FLOW_URL, json=email_data, timeout=60)
  print(f"Email sent: {resp.status_code}")
  ```
- [ ] Verify the test email was received in the inbox
- [ ] Check email formatting is correct

### 9.7 - Test Network Connectivity to All Endpoints (20 min)
- [ ] Test all external endpoints are reachable:
  ```bash
  # Test from CMD
  ping login.microsoftonline.com
  ping graph.microsoft.com
  ping bahracables.sharepoint.com
  ping operations-bahrauat-1.crm11.dynamics.com
  ping service.ariba.com
  ```
- [ ] If any endpoint is unreachable, configure proxy or firewall

### 9.8 - Verify Company Configuration (10 min)
- [ ] Verify company options:
  ```python
  from config.config import COMPANY_OPTIONS, COMPANY_NAME

  print(f"Default company: {COMPANY_NAME}")
  print(f"All companies: {COMPANY_OPTIONS}")
  ```
- [ ] Verify all 4 companies are listed correctly

## Deliverables
- [ ] Power Automate main flow reachable and triggers
- [ ] Forgot Password flow reachable
- [ ] Email recipients verified and updated if needed
- [ ] Test email sent and received successfully
- [ ] All external endpoints reachable from new server
- [ ] Company configuration verified

---
---

# TASK 10: Dashboard Server Setup & Authentication Testing
**Duration: 3:00 Hours**

## Objective
Start the dashboard backend server (FastAPI + Uvicorn), test all API routes, verify user authentication, session management, and confirm the React frontend connects properly.

## Steps

### 10.1 - Start Dashboard Backend Server (20 min)
- [ ] Open Command Prompt:
  ```bash
  cd C:\python\RFP-automation
  env\Scripts\activate
  python dashboard_main.py
  ```
- [ ] Server should start with output:
  ```
  INFO:     Uvicorn running on http://0.0.0.0:8000
  INFO:     Started reloader process
  ```
- [ ] Verify the two servers:
  - Dashboard: `http://localhost:8000` (port 8000)
  - Automation API: `http://localhost:8100` (port 8100 - separate process)

### 10.2 - Test Dashboard API Endpoint (20 min)
- [ ] Open browser and test:
  ```
  http://localhost:8000/docs
  ```
- [ ] FastAPI Swagger UI should load showing all routes:
  - Auth routes: `/login`, `/logout`, `/session/refresh`
  - Dashboard routes
  - Automation routes
  - User management routes

### 10.3 - Test Login Authentication (30 min)
- [ ] Open browser: `http://localhost:8000`
- [ ] Try logging in with valid credentials
- [ ] Verify:
  - Login form appears
  - Credentials are validated against Dataverse Users table
  - Session is created on successful login
  - Dashboard page loads after login
  - User info displayed correctly

### 10.4 - Test Session Management (30 min)
- [ ] Verify session settings in `config\config.py`:
  ```python
  SESSION_TIMEOUT_SECONDS = 7200      # 2 hours
  IDLE_TIMEOUT_SECONDS = 1800         # 30 minutes
  SESSION_WARNING_SECONDS = 300       # 5 minutes warning
  SESSION_REFRESH_INTERVAL = 300      # 5 minutes refresh
  ```
- [ ] Test session refresh endpoint:
  ```
  POST http://localhost:8000/session/refresh
  ```
- [ ] Test logout:
  ```
  POST http://localhost:8000/logout
  ```
- [ ] Verify session is cleared after logout

### 10.5 - Test Dashboard Data Endpoints (30 min)
- [ ] After login, test these endpoints (logged in session):
  - [ ] `/api/dashboard` - Dashboard data loads
  - [ ] `/api/logs` - Automation logs load
  - [ ] `/api/rfp-status` - RFP status data loads
  - [ ] `/api/companies` - Company list returns
- [ ] Verify data is fetched from Dataverse correctly
- [ ] Check response times (should be < 5 seconds)

### 10.6 - Test CORS Configuration (20 min)
- [ ] Verify CORS allows frontend origins:
  ```python
  # From dashboard_main.py
  allow_origins=[
      "http://localhost:8000",
      "http://localhost:3000",
      "http://localhost:5173",
  ]
  ```
- [ ] If the frontend will run on a different URL, add it to the allowed origins
- [ ] Test from frontend dev server (port 3000) that API calls work

### 10.7 - Test Frontend + Backend Together (30 min)
- [ ] Keep backend running on port 8000
- [ ] In a new terminal, start frontend:
  ```bash
  cd C:\python\RFP-automation\frontend
  npm run dev
  ```
- [ ] Open `http://localhost:3000`
- [ ] Test full flow:
  - [ ] Login page renders
  - [ ] Login works (API call to backend)
  - [ ] Dashboard shows data
  - [ ] Logs page loads and shows records
  - [ ] Navigation between pages works
  - [ ] Logout works

### 10.8 - Test Cache Configuration (20 min)
- [ ] Verify cache settings:
  ```python
  DASHBOARD_TTL_SECONDS = 300         # 5 minutes
  LOGS_TTL_SECONDS = 300
  SAP_LOGS_TTL_SECONDS = 300
  DASHBOARD_HTTP_MAX_AGE = 30
  ```
- [ ] Verify pagination settings:
  ```python
  DEFAULT_PAGE_SIZE = 50
  MIN_PAGE_SIZE = 10
  MAX_PAGE_SIZE = 500
  ```

## Deliverables
- [ ] Dashboard server starts on port 8000
- [ ] Swagger UI accessible at `/docs`
- [ ] User login/logout working
- [ ] Session management working
- [ ] All dashboard data endpoints return data
- [ ] Frontend connects to backend correctly
- [ ] Full login-to-dashboard flow working

---
---

# TASK 11: RFP Download Automation End-to-End Testing
**Duration: 3:00 Hours**

## Objective
Test the complete RFP Download automation flow from start to finish - including Ariba portal login, RFP listing, file download, SharePoint upload, and Dataverse logging.

## Steps

### 11.1 - Review Download Flow Code (30 min)
- [ ] Read and understand `rfp\download_rfp.py`
- [ ] Read `automation_logic.py` - specifically the `run_automation_download` function
- [ ] Understand the flow:
  1. Launch Playwright Chromium browser
  2. Navigate to Ariba portal
  3. Login with SAP credentials
  4. Select company (SEC/Aramco/SABIC/HADEED)
  5. List open RFPs
  6. Download RFP Excel files
  7. Upload to SharePoint
  8. Log to Dataverse
  9. Send email notification

### 11.2 - Start Automation API Server (10 min)
- [ ] Open Command Prompt:
  ```bash
  cd C:\python\RFP-automation
  env\Scripts\activate
  python automation_main.py
  ```
- [ ] Server starts on `http://localhost:8100`

### 11.3 - Test Download via API (30 min)
- [ ] Trigger download automation via API:
  ```
  POST http://localhost:8100/automation/download
  Body: {"company_name": "Saudi Electricity Company"}
  ```
- [ ] Or use curl/Postman:
  ```bash
  curl -X POST http://localhost:8100/automation/download -H "Content-Type: application/json" -d "{\"company_name\": \"Saudi Electricity Company\"}"
  ```

### 11.4 - Monitor Browser Automation (30 min)
- [ ] Watch the Chromium browser window:
  - [ ] Browser opens successfully
  - [ ] Ariba login page loads
  - [ ] Credentials entered correctly
  - [ ] Company selection works
  - [ ] RFP list page loads
  - [ ] Download buttons clicked
  - [ ] Files download to `Downloads\` folder

### 11.5 - Verify Downloaded Files (20 min)
- [ ] Check `%USERPROFILE%\Downloads\` for downloaded RFP files (.xls)
- [ ] Check `ALLRFPs\` folder for processed files:
  ```bash
  dir C:\python\RFP-automation\ALLRFPs\
  ```
- [ ] Verify files are organized by company name
- [ ] Verify file format is correct (.xls)

### 11.6 - Verify SharePoint Upload (20 min)
- [ ] Open SharePoint: `bahracables.sharepoint.com`
- [ ] Navigate to: Sites > LiveSite > RFPAutomation > Documents > RFP-logs
- [ ] Verify downloaded RFP files are uploaded correctly
- [ ] Check folder structure matches expected pattern

### 11.7 - Verify Dataverse Log Entry (20 min)
- [ ] Check Dataverse Automation Log table:
  ```python
  from helpers.core_helper import DATAVERSE
  from config.config import AUTOMATION_LOG_TABLE_API

  logs = DATAVERSE.get_rows(AUTOMATION_LOG_TABLE_API, top=5, order_by="createdon desc")
  for log in logs:
      print(log)
  ```
- [ ] Verify log entry was created for the download operation
- [ ] Check log fields: timestamp, status, company, RFP count

### 11.8 - Test All 4 Companies (30 min)
- [ ] Repeat download test for each company:
  - [ ] Saudi Electricity Company
  - [ ] Aramco e-Marketplace
  - [ ] SABIC - Saudi Basic Industries Corp.
  - [ ] HADEED - RAJHI STEEL
- [ ] Note: Some companies may have no open RFPs - that's OK

### 11.9 - Test Error Handling (10 min)
- [ ] Test with invalid company:
  ```
  POST http://localhost:8100/automation/download
  Body: {"company_name": "Invalid Company"}
  ```
- [ ] Verify proper error response
- [ ] Check error is logged to `LOGS\` folder

## Deliverables
- [ ] Download automation runs end-to-end
- [ ] Browser navigates Ariba portal correctly
- [ ] RFP files download to local machine
- [ ] Files uploaded to SharePoint
- [ ] Dataverse log entry created
- [ ] All 4 companies tested
- [ ] Error handling verified

---
---

# TASK 12: RFP Submit, Decline & Reminder Automation Testing
**Duration: 3:00 Hours**

## Objective
Test the RFP Submit, RFP Decline, RFP Reminder, Sync Portal, and Sync SharePoint-Dataverse automation flows end-to-end on the new server.

## Steps

### 12.1 - Review Submit Flow Code (20 min)
- [ ] Read `rfp\submit_rfp.py`
- [ ] Read `automation_logic.py` - `run_automation_submit` function
- [ ] Understand the flow:
  1. Browser opens Ariba
  2. Navigate to specific RFP
  3. Upload filled Excel file from SharePoint
  4. Submit the RFP response
  5. Log to Dataverse
  6. Send notification email

### 12.2 - Test RFP Submit API (30 min)
- [ ] Ensure automation server is running on port 8100
- [ ] Trigger submit automation:
  ```
  POST http://localhost:8100/automation/submit
  Body: {
      "company_name": "Saudi Electricity Company",
      "rfp_title": "<RFP title>",
      "status": "submitted"
  }
  ```
- [ ] Monitor browser automation
- [ ] Verify submission completes or fails gracefully

### 12.3 - Test RFP Submit via Dashboard UI (30 min)
- [ ] Open dashboard: `http://localhost:8000`
- [ ] Login
- [ ] Navigate to RFP management page
- [ ] Find an RFP that is ready for submission
- [ ] Click Submit button
- [ ] Verify file upload from SharePoint works
- [ ] Verify submission status updates in UI

### 12.4 - Review Decline Flow Code (15 min)
- [ ] Read `rfp\decline_rfp.py`
- [ ] Read `automation_logic.py` - `run_automation_decline` function

### 12.5 - Test RFP Decline API (30 min)
- [ ] Trigger decline automation:
  ```
  POST http://localhost:8100/automation/decline
  Body: {
      "company_name": "Saudi Electricity Company",
      "rfp_title": "<RFP title>",
      "status": "declined"
  }
  ```
- [ ] Monitor browser - RFP should be declined in Ariba portal
- [ ] Verify decline logged in Dataverse
- [ ] Verify decline notification email sent

### 12.6 - Review & Test RFP Reminder (20 min)
- [ ] Read `rfp\rfp_reminder.py`
- [ ] Read `automation_logic.py` - `run_automation_reminder` function
- [ ] Trigger reminder:
  ```
  POST http://localhost:8100/automation/reminder
  ```
- [ ] Verify reminder emails sent to:
  ```
  Manish.Soni@dynatechconsultancy.com;shubham.kumbhar@dynatechconsultancy.com
  ```

### 12.7 - Test Sync Portal Flow (20 min)
- [ ] Read `automation_logic.py` - `run_automation_sync_portal` function
- [ ] Trigger sync:
  ```
  POST http://localhost:8100/automation/sync-portal
  ```
- [ ] Verify it syncs RFP data from Ariba portal to Dataverse

### 12.8 - Test Sync SharePoint-Dataverse (15 min)
- [ ] Trigger SharePoint-Dataverse sync:
  ```
  POST http://localhost:8100/automation/sync-sharepoint-dataverse
  ```
- [ ] Verify data consistency between SharePoint and Dataverse

### 12.9 - Verify All Email Notifications (20 min)
- [ ] Check email inbox for all test notifications:
  - [ ] RFP Submitted email
  - [ ] RFP Declined email
  - [ ] RFP Reminder email
  - [ ] Error notification email (if any errors occurred)
  - [ ] Saved Draft email (if applicable)
- [ ] Verify email subject lines and body content are correct

## Deliverables
- [ ] RFP Submit automation works end-to-end
- [ ] RFP Decline automation works end-to-end
- [ ] RFP Reminder sends emails correctly
- [ ] Sync Portal updates Dataverse from Ariba
- [ ] Sync SharePoint-Dataverse works
- [ ] All email notifications received and formatted correctly

---
---

# TASK 13: User Management, SAP & Admin Panel Verification
**Duration: 2:30 Hours**

## Objective
Verify user management features, SAP password management, role-based access control, and admin panel functionality on the new server.

## Steps

### 13.1 - Test User Authentication Service (20 min)
- [ ] Verify user service works:
  ```python
  from services.user_service import authenticate_user, list_users, get_user_by_email

  users = list_users()
  print(f"Total users: {len(users)}")
  for u in users[:5]:
      print(f"  - {u}")
  ```

### 13.2 - Test User Login with Different Roles (30 min)
- [ ] Test login with Admin user
- [ ] Test login with Regular user
- [ ] Verify role-based access:
  - Admin can access: User Management, SAP Logs, all pages
  - Regular user can access: Dashboard, Logs, Profile only
- [ ] Verify incorrect password shows error
- [ ] Verify non-existent user shows error

### 13.3 - Test User Management API (30 min)
- [ ] Login as Admin
- [ ] Navigate to Admin > Users page
- [ ] Test operations:
  - [ ] List all users
  - [ ] View user details
  - [ ] Update user information
  - [ ] Verify changes saved to Dataverse Users table

### 13.4 - Test SAP Password Management (30 min)
- [ ] Navigate to Admin > SAP Logs page
- [ ] Test SAP service:
  ```python
  from services.sap_service import create_sap_password_record

  # Read-only test - list existing records
  from helpers.core_helper import DATAVERSE
  from config.config import SAP_PASSWORD_TABLE_API

  records = DATAVERSE.get_rows(SAP_PASSWORD_TABLE_API, top=5)
  print(f"SAP records: {len(records)}")
  ```
- [ ] Verify SAP logs page loads data correctly
- [ ] Verify pagination works

### 13.5 - Test Role Service (20 min)
- [ ] Verify role service:
  ```python
  from services.role_service import *
  # Test role-related functions
  ```
- [ ] Check that admin-only routes are protected
- [ ] Check that non-admin users get 403 Forbidden for admin routes

### 13.6 - Test Profile Page (15 min)
- [ ] Login as any user
- [ ] Navigate to Profile page
- [ ] Verify user information displays correctly:
  - Name, Email, Role
- [ ] Test profile update if applicable

### 13.7 - Test Forgot Password Flow (15 min)
- [ ] From login page, click "Forgot Password"
- [ ] Enter email address
- [ ] Verify Power Automate flow triggers
- [ ] Verify password reset email received

## Deliverables
- [ ] User authentication working for all users
- [ ] Role-based access control working (Admin vs Regular)
- [ ] User Management page (Admin) working
- [ ] SAP Password logs loading correctly
- [ ] Profile page showing correct user data
- [ ] Forgot Password flow working

---
---

# TASK 14: Logging, Error Handling & SharePoint Log Upload
**Duration: 2:30 Hours**

## Objective
Verify all logging mechanisms, error handling, failure logging to local files, SharePoint error log uploads, and Sentry integration on the new server.

## Steps

### 14.1 - Verify Local Log Directory (15 min)
- [ ] Check `LOGS\` folder exists:
  ```bash
  dir C:\python\RFP-automation\LOGS\
  ```
- [ ] If not exists, it auto-creates via config:
  ```python
  FAILURE_LOGS_DIR = os.path.join(os.getcwd(), "LOGS")
  os.makedirs(FAILURE_LOGS_DIR, exist_ok=True)
  ```
- [ ] Verify write permissions on `LOGS\` folder

### 14.2 - Test Failure Logger (30 min)
- [ ] Test failure logging module:
  ```python
  from helpers.failure_logger import *

  # Test creating a failure log
  try:
      raise ValueError("Test error from new server")
  except Exception as e:
      # Log the error (this creates a local JSON file)
      print("Failure logger imported successfully")
  ```
- [ ] Verify log file created in `LOGS\` folder
- [ ] Check log file format (JSON with timestamp, error details, traceback)

### 14.3 - Test Enhanced Error Logger (20 min)
- [ ] Test enhanced error logger:
  ```python
  from helpers.enhanced_error_logger import *
  print("Enhanced error logger: OK")
  ```
- [ ] Verify it captures detailed exception info (file, line, function)

### 14.4 - Test SharePoint Error Log Upload (30 min)
- [ ] Verify SharePoint error logs folder:
  ```python
  SP_FAILURE_LOGS_FOLDER = "RFP-logs/automation-error-logs"
  ```
- [ ] Trigger a test error and verify it uploads to SharePoint:
  - Check SharePoint > Documents > RFP-logs > automation-error-logs
- [ ] Verify error log file appears in SharePoint

### 14.5 - Test Dataverse Automation Log (20 min)
- [ ] Verify automation logs are written to Dataverse:
  ```python
  from helpers.core_helper import DATAVERSE
  from config.config import AUTOMATION_LOG_TABLE_API

  logs = DATAVERSE.get_rows(AUTOMATION_LOG_TABLE_API, top=5, order_by="createdon desc")
  print(f"Recent logs: {len(logs)}")
  for l in logs:
      print(f"  - {l}")
  ```

### 14.6 - Test Local Log Module (15 min)
- [ ] Verify `core\local_log.py` works:
  ```python
  from core.local_log import *
  print("Local log module: OK")
  ```
- [ ] Verify `core\log_events.py` works:
  ```python
  from core.log_events import *
  print("Log events module: OK")
  ```

### 14.7 - Test Sentry Integration (15 min)
- [ ] Verify Sentry SDK is installed:
  ```python
  import sentry_sdk
  print(f"Sentry SDK: {sentry_sdk.VERSION}")
  ```
- [ ] Check if Sentry DSN is configured in the project
- [ ] If configured, test sending a test event to Sentry

### 14.8 - Test Dashboard Logs Page (15 min)
- [ ] Open dashboard: `http://localhost:8000`
- [ ] Login and navigate to Logs page
- [ ] Verify:
  - [ ] Logs load from Dataverse
  - [ ] Pagination works (50 records per page)
  - [ ] Sorting works
  - [ ] Filter by date/company works
  - [ ] Log details expandable

### 14.9 - Verify Logs Fetch Settings (10 min)
- [ ] Check config settings:
  ```python
  LOGS_FETCH_TOP_MAX = 2000
  LOGS_FETCH_AHEAD_FACTOR = 10
  DEFAULT_PAGE_SIZE = 50
  MIN_PAGE_SIZE = 10
  MAX_PAGE_SIZE = 500
  ```

## Deliverables
- [ ] Local LOGS folder created and writable
- [ ] Failure logger creates JSON log files
- [ ] Error logs upload to SharePoint
- [ ] Automation logs written to Dataverse
- [ ] Dashboard Logs page loads and paginates
- [ ] Sentry integration verified (if configured)

---
---

# TASK 15: Windows Task Scheduler, Firewall & Network Setup
**Duration: 2:30 Hours**

## Objective
Configure Windows Task Scheduler for automated runs, set up firewall rules for dashboard access, configure network settings, and set up the application to auto-start on server boot.

## Steps

### 15.1 - Create Task Scheduler for Dashboard Server (30 min)
- [ ] Open Windows Task Scheduler
- [ ] Create New Task: "RFP Dashboard Server"
  - **General Tab:**
    - Name: `RFP_Dashboard_Server`
    - Run whether user is logged on or not
    - Run with highest privileges
  - **Triggers:**
    - At system startup
    - Delay: 30 seconds (wait for network)
  - **Actions:**
    - Program: `C:\python\RFP-automation\env\Scripts\python.exe`
    - Arguments: `dashboard_main.py`
    - Start in: `C:\python\RFP-automation`
  - **Conditions:**
    - Uncheck "Start only if AC power"
  - **Settings:**
    - Allow task to be run on demand
    - Do not stop if running longer than X
    - If the task is already running: Do not start a new instance

### 15.2 - Create Task Scheduler for Automation (30 min)
- [ ] Create automation task schedules based on existing schedules from old server
- [ ] Task: "RFP Download Automation"
  - Program: `C:\python\RFP-automation\env\Scripts\python.exe`
  - Arguments: `automation_main.py`
  - Start in: `C:\python\RFP-automation`
  - Schedule: As per automation schedule table in Dataverse
- [ ] Export task configurations:
  ```bash
  schtasks /query /tn "RFP_Dashboard_Server" /xml > task_dashboard.xml
  ```

### 15.3 - Create Batch Scripts for Easy Start/Stop (20 min)
- [ ] Create `start_dashboard.bat`:
  ```batch
  @echo off
  cd /d C:\python\RFP-automation
  call env\Scripts\activate
  python dashboard_main.py
  ```
- [ ] Create `start_automation.bat`:
  ```batch
  @echo off
  cd /d C:\python\RFP-automation
  call env\Scripts\activate
  python automation_main.py
  ```
- [ ] Create `stop_all.bat`:
  ```batch
  @echo off
  taskkill /f /im python.exe
  echo All Python processes stopped.
  ```

### 15.4 - Configure Windows Firewall (20 min)
- [ ] Open port 8000 for Dashboard (inbound):
  ```bash
  netsh advfirewall firewall add rule name="RFP Dashboard Port 8000" dir=in action=allow protocol=TCP localport=8000
  ```
- [ ] Open port 8100 for Automation API (inbound):
  ```bash
  netsh advfirewall firewall add rule name="RFP Automation API Port 8100" dir=in action=allow protocol=TCP localport=8100
  ```
- [ ] Verify rules created:
  ```bash
  netsh advfirewall firewall show rule name="RFP Dashboard Port 8000"
  netsh advfirewall firewall show rule name="RFP Automation API Port 8100"
  ```

### 15.5 - Test Access from Other Machines (20 min)
- [ ] From another PC on the same network:
  ```
  http://<server-ip>:8000
  ```
- [ ] Verify dashboard loads from remote machine
- [ ] Test login from remote machine
- [ ] If not accessible:
  - Check firewall rules
  - Check if server is on same subnet
  - Check if `0.0.0.0` is used as host (not `127.0.0.1`)

### 15.6 - Configure Auto-Restart on Failure (15 min)
- [ ] In Task Scheduler, configure restart:
  - Settings > If the task fails, restart every: 1 minute
  - Attempt to restart up to: 3 times
- [ ] This ensures dashboard auto-recovers from crashes

### 15.7 - Test Server Reboot (15 min)
- [ ] Restart the server
- [ ] After reboot, verify:
  - [ ] Dashboard server starts automatically
  - [ ] Dashboard is accessible: `http://localhost:8000`
  - [ ] Login works
  - [ ] API endpoints respond

## Deliverables
- [ ] Dashboard Task Scheduler configured
- [ ] Automation Task Scheduler configured
- [ ] Batch scripts created (start/stop)
- [ ] Firewall ports 8000 and 8100 opened
- [ ] Dashboard accessible from remote machines
- [ ] Auto-restart on failure configured
- [ ] Server reboot tested - services auto-start

---
---

# TASK 16: Go-Live, Smoke Testing & Old Server Decommission
**Duration: 2:30 Hours**

## Objective
Perform final go-live smoke testing of all features, switch production traffic to the new server, and plan old server decommission.

## Steps

### 16.1 - Pre Go-Live Checklist (20 min)
- [ ] Verify all previous 15 tasks are completed
- [ ] Review all "FAIL" items from previous tasks and resolve them
- [ ] Confirm with team that migration window is approved
- [ ] Notify all users about the server change

### 16.2 - Full Smoke Test - Dashboard (20 min)
- [ ] Open dashboard from a remote machine
- [ ] Test each page:
  - [ ] Login page - Login successfully
  - [ ] Dashboard - Data loads correctly
  - [ ] Logs - Automation logs display
  - [ ] RFP Insights - RFP data shows
  - [ ] Profile - User info correct
  - [ ] Admin > Users - User list loads (admin only)
  - [ ] Admin > SAP Logs - SAP records load (admin only)
- [ ] Test logout and re-login

### 16.3 - Full Smoke Test - RFP Download (20 min)
- [ ] Trigger RFP Download for one company
- [ ] Verify:
  - [ ] Browser launches
  - [ ] Ariba portal navigated
  - [ ] RFPs downloaded
  - [ ] Files uploaded to SharePoint
  - [ ] Log entry in Dataverse
  - [ ] Email notification received

### 16.4 - Full Smoke Test - RFP Submit/Decline (20 min)
- [ ] Trigger one RFP Submit (if available)
- [ ] Trigger one RFP Decline (if available)
- [ ] Verify:
  - [ ] Actions completed in Ariba portal
  - [ ] Status updated in Dataverse
  - [ ] Notifications sent

### 16.5 - Full Smoke Test - RFP Reminder (10 min)
- [ ] Trigger RFP Reminder
- [ ] Verify reminder email received

### 16.6 - Performance Comparison (15 min)
- [ ] Compare new server vs old server:
  | Metric | Old Server | New Server |
  |--------|-----------|-----------|
  | Dashboard load time | | |
  | API response time | | |
  | Browser launch time | | |
  | RFP download time | | |
  | SharePoint upload time | | |
- [ ] Document any performance differences

### 16.7 - Stop Old Server Services (10 min)
- [ ] On the OLD server:
  - [ ] Stop Dashboard Task Scheduler
  - [ ] Stop Automation Task Scheduler
  - [ ] Disable (don't delete) the scheduled tasks
- [ ] Verify old server is no longer serving requests

### 16.8 - DNS / URL Update (if applicable) (10 min)
- [ ] If using a hostname/DNS for the dashboard:
  - [ ] Update DNS record to point to new server IP
  - [ ] Update any bookmarks or shortcuts shared with team
- [ ] If using direct IP:
  - [ ] Notify team of new IP address
  - [ ] Update any documentation with new IP

### 16.9 - Monitor New Server (15 min)
- [ ] Keep monitoring the new server for 15 minutes:
  - [ ] Check dashboard is responsive
  - [ ] Check no error emails being sent
  - [ ] Check Task Scheduler shows tasks running
  - [ ] Check Windows Event Viewer for errors
  - [ ] Check LOGS folder for new error files

### 16.10 - Old Server Decommission Plan (10 min)
- [ ] Keep old server available for 7 days as backup
- [ ] Schedule decommission date: ________________
- [ ] Before decommission:
  - [ ] Backup any remaining data from old server
  - [ ] Export Task Scheduler configurations
  - [ ] Take final screenshot of old server state
  - [ ] Delete scheduled tasks on old server
  - [ ] Archive old server project folder

### 16.11 - Document Migration Completion (10 min)
- [ ] Create migration completion report:
  - Migration Date: ________________
  - New Server: ________________
  - Old Server: ________________
  - Migrated By: ________________
  - All Tests Passed: Yes / No
  - Issues Found: ________________
  - Resolution: ________________
- [ ] Share report with team

## Deliverables
- [ ] All smoke tests passed
- [ ] Old server services stopped
- [ ] DNS/URL updated (if applicable)
- [ ] New server monitored and stable
- [ ] Decommission plan scheduled
- [ ] Migration completion report created
- [ ] Team notified of successful migration

---
---

# SUMMARY TABLE

| Task # | Task Name | Duration | Completed |
|--------|-----------|----------|-----------|
| 1 | New Server OS Setup & System Configuration | 3:00 Hr | [ ] |
| 2 | Install Python, Node.js & Development Tools | 3:00 Hr | [ ] |
| 3 | Project Source Code Transfer & Git Setup | 3:00 Hr | [ ] |
| 4 | Python Virtual Environment & Backend Dependencies | 3:00 Hr | [ ] |
| 5 | Playwright Browser Engine Setup & Validation | 3:00 Hr | [ ] |
| 6 | Frontend (React) Build & Deployment Setup | 3:00 Hr | [ ] |
| 7 | Azure AD, SharePoint & Graph API Configuration | 3:00 Hr | [ ] |
| 8 | Dataverse Connection & Table Mapping Verification | 3:00 Hr | [ ] |
| 9 | Power Automate, Email & Notification Setup | 3:00 Hr | [ ] |
| 10 | Dashboard Server Setup & Authentication Testing | 3:00 Hr | [ ] |
| 11 | RFP Download Automation End-to-End Testing | 3:00 Hr | [ ] |
| 12 | RFP Submit, Decline & Reminder Automation Testing | 3:00 Hr | [ ] |
| 13 | User Management, SAP & Admin Panel Verification | 2:30 Hr | [ ] |
| 14 | Logging, Error Handling & SharePoint Log Upload | 2:30 Hr | [ ] |
| 15 | Windows Task Scheduler, Firewall & Network Setup | 2:30 Hr | [ ] |
| 16 | Go-Live, Smoke Testing & Old Server Decommission | 2:30 Hr | [ ] |

**Total: 12 x 3:00 + 4 x 2:30 = 36 + 10 = 46 Hours**
