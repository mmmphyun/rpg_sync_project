import os
import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.database.queries import get_all_jobs_for_web
from src.web.routers import auth, jobs, boards, server

def get_real_ip(request: Request) -> str:
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=get_real_ip)

app = FastAPI(title="Fossile Server Web Dashboard")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware & Static Files
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fossile-wiki.cloud").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["X-API-Key", "Content-Type"],
)

os.makedirs("public/images", exist_ok=True)
app.mount("/images", StaticFiles(directory="public/images"), name="images")
app.mount("/static", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Include Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(boards.router, prefix="/api/v1/boards", tags=["Boards"])
app.include_router(server.router)

@app.get("/")
async def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

@app.get("/jobs", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_jobs(request: Request):
    jobs_data = get_all_jobs_for_web()

    formatted_jobs = []
    for row in jobs_data:
        photos = [p for p in [row.get('photo_1'), row.get('photo_2'), row.get('photo_3'), row.get('photo_4')] if p]

        formatted_jobs.append({
            "job_id": row.get('job_id'),
            "name": row.get('display_name'),
            "searchName": row.get('name'),
            "gate": row.get('gate'),
            "group": row.get('job_group'),
            "desc": row.get('description'),
            "range": row.get('range_type'),
            "position": row.get('position'),
            "resource": row.get('resource_type'),
            "img": row.get('img', ''),
            "photos": photos,
            "limit": True if row.get('is_limit') == 'Y' else False,
            "req_condition": row.get('req_condition'),
            "patches": row.get('patches', []),
            "players": row.get('players', [])
        })

    jobs_json = json.dumps(formatted_jobs)

    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={"request": request, "jobs_json": jobs_json}
    )

@app.get("/notice")
async def serve_notice(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={"request": request, "board_type": "notice"}
    )

@app.get("/event")
async def serve_event(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={"request": request, "board_type": "event"}
    )

@app.get("/tips", response_class=HTMLResponse)
async def serve_tips(request: Request):
    """팁 게시판 더미 페이지 서빙"""
    return templates.TemplateResponse(
        request=request,
        name="tips.html",
        context={"request": request}
    )