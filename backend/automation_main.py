from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import automation

app = FastAPI(title="Bahra Automation API")

# Allow dashboard origin to call automation APIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only automation routes here
app.include_router(automation.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("automation_main:app", host="0.0.0.0", port=8100, reload=True)


