import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.web.routers import auth, jobs, boards

app = FastAPI(title="RevivalRPG Web Dashboard")

# Middleware & Static Files
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Include Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(boards.router, prefix="/api/v1/boards", tags=["Boards"])

@app.get("/")
async def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/notice")
async def serve_notice(request: Request):
    return templates.TemplateResponse("board.html", {"request": request, "board_type": "notice"})

@app.get("/event")
async def serve_event(request: Request):
    return templates.TemplateResponse("board.html", {"request": request, "board_type": "event"})