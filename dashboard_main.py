import sys
import asyncio

# Fix for Windows: force UTF-8 stdout/stderr so emoji in print() don't crash
import os
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8:replace")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        import io
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass

# Fix for Windows: Playwright requires ProactorEventLoop for subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from routes import dashboard, user_management, automation
from routes import api as api_routes
from routes.role_routes import router as role_router
from routes.actionable_cards import router as actionable_cards_router
from routes.master_data_routes import router as master_data_router
from routes.system_settings_routes import router as system_settings_router
from routes.open_rfp import router as open_rfp_router
from config.config import SESSION_TIMEOUT_SECONDS
import os
import uuid
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Bahra Dashboard API")

# Static assets (for serving any static files if needed)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Session middleware for authentication
app.add_middleware(SessionMiddleware, secret_key="change-me-please", max_age=SESSION_TIMEOUT_SECONDS)

# CORS - allow React frontend (dev server on port 3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:5173",
        "http://192.168.178.220:3000",
        "http://192.168.178.220:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main API router for React frontend (prefixed with /api)
app.include_router(api_routes.router)

# Automation API router (prefixed with /api and also at root)
app.include_router(automation.router, prefix="/api")
app.include_router(automation.router)

# Dashboard API router for Excel/Material/RFP endpoints (prefixed with /dashboard)
app.include_router(dashboard.router)

# Password reset HTML page router (root-level, no /api prefix)
app.include_router(api_routes.reset_router)

# User management API router
app.include_router(user_management.router)

# Role management API router (RBAC)
app.include_router(role_router)

# Actionable Cards callback (Adaptive Card responses from Outlook)
app.include_router(actionable_cards_router)

# Master Data API router (Material Master + Keywords)
app.include_router(master_data_router)

# System Settings API router (Dynamic Configuration)
app.include_router(system_settings_router)

# Open RFP API router (reminder tracker for non-responders)
app.include_router(open_rfp_router)


# ==================== GLOBAL ERROR HANDLER ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and return a clean 500 response."""
    # Don't catch HTTP exceptions — let FastAPI handle those
    if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
        raise exc
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"Unhandled error [{error_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_id": error_id},
    )


# ==================== HEALTH CHECK ====================

@app.get("/health", tags=["Infrastructure"])
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        from helpers.core_helper import DATAVERSE
        DATAVERSE.query_rows(
            table_api_name="cr673_bahra_logins",
            top=1,
            table_logical_name="cr673_bahra_login",
            use_display_names=False,
        )
        return {"status": "healthy", "dataverse": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "dataverse": "disconnected", "error": str(e)},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_main:app", host="0.0.0.0", port=8000, reload=True)


