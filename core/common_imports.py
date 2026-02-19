
from numpy import empty
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from playwright.async_api import async_playwright
from rfp.decline_rfp import decline_rfps
from fastapi import Body

from fastapi.responses import JSONResponse

import asyncio
import re
import os
import shutil
from datetime import datetime
import pandas as pd
import csv
import json
import requests
import msal
from pathlib import Path
from io import BytesIO
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from helpers.core_helper import *
from config.config import (
URL,
COMPANY_NAME ,
AUTHORITY ,
SCOPES ,
FLOW_URL ,
CLIENT_ID, CLIENT_SECRET, TENANT_ID,
    SHAREPOINT_HOSTNAME, SITE_PATH, DRIVE_NAME,
    DOWNLOAD_DIR,
    OUTPUT_DIR,
    SP_BASE_FOLDER,
    EMAIL_TO_NO_MATCHED_DATA,
    EMAIL_TO_NEW_RFP_NO_MATCH,
    EMAIL_TO_NEW_RFP_WITH_MATCH,
    EMAIL_TO_NEW_RFP,
    EMAIL_TO_NO_NEW_RFP,
    EMAIL_TO_RFP_REMINDER,
    RFP_TEAM_TABLE,
    EMAIL_TO_RFP_SUBMITTED,
    EMAIL_TO_RFP_ERROR_IN_SUBMISSION,
    EMAIL_TO_RFP_DECLINED,
    EMAIL_TO_RFP_ERROR_IN_DECLINE,
    EMAIL_TO_AUTOMATION_FAILURE,
    EMAIL_TO_RFP_SAVED_DRAFT,
)
from config.runtime_config import USERNAME, PASSWORD
from helpers.sharepoint_helper import (
    GraphClient
)
from core.log_events import log_event,log_rfp_activity
