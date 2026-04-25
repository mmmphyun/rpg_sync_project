import os
import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.web.limiter import limiter

from src.database.jobs import get_all_jobs_for_web
from src.web.routers import auth, jobs, boards, server

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

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # 클릭재킹 방어
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"

    # MIME 스니핑 방어
    response.headers["X-Content-Type-Options"] = "nosniff"

    # 강제 HTTPS 접속 처리
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

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
            "type": row.get('type'),
            "img": row.get('img', ''),
            "photos": photos,
            "limit": True if row.get('is_limit') == 'Y' else False,
            "req_condition": row.get('req_condition'),
            "patches": row.get('patches', []),
            "players": row.get('players', [])
        })

    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={"request": request, "jobs_data": formatted_jobs}
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

# 로깅 (서버 터미널만 상세 에러 기록)
logger = logging.getLogger("uvicorn.error")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}
    )