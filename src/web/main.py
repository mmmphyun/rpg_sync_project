from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
from fastapi.templating import Jinja2Templates

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.database.queries import get_all_jobs_for_web

import os
import json

# API 인증 키 및 헤더 설정
API_KEY = os.getenv("WEB_API_KEY", "dev_secret_key_123")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Depends(api_key_header)):
    """API 요청 헤더의 X-API-Key 값을 검증"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

# IP 기반 Rate Limiter 초기화
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="RPG Server API", version="1.0.0")

# Rate Limiter를 FastAPI 앱 상태에 등록 및 예외 핸들러 연결
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app = FastAPI(title="RPG Server API", version="1.0.0")

# CORS 설정 (실무에서는 특정 도메인만 허용하도록 변경)
# 개발 환경 주소 기본값 세팅, 운영 서버 배포 시 환경변수로 도메인 주입
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

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

@app.get("/", response_class=HTMLResponse)
def serve_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/jobs", response_class=HTMLResponse)
@limiter.limit("30/minute")
def serve_jobs(request: Request):
    """
    직업 목록 페이지 SSR 렌더링
    """
    jobs_data = get_all_jobs_for_web()

    formatted_jobs = []
    for row in jobs_data:
        photos = [p for p in [row.get('photo_1'), row.get('photo_2'), row.get('photo_3'), row.get('photo_4')] if p]

        formatted_jobs.append({
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
        "jobs.html",
        {"request": request, "jobs_json": jobs_json}
    )