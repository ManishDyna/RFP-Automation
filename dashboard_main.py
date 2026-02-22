import sys
import asyncio

# Fix for Windows: Playwright requires ProactorEventLoop for subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from routes import dashboard, user_management, auth, automation
from routes import api as api_routes
from routes.role_routes import router as role_router
from config.config import SESSION_TIMEOUT_SECONDS
import os


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

# Auth API router (login, logout, session management)
app.include_router(auth.router)

# User management API router
app.include_router(user_management.router)

# Role management API router (RBAC)
app.include_router(role_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard_main:app", host="0.0.0.0", port=8000, reload=True)


