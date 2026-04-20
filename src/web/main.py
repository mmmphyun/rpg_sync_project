from fastapi import FastAPI, Request, Depends, HTTPException, status, Response, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader
from fastapi.templating import Jinja2Templates

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from datetime import datetime, timedelta

from src.database.queries import get_all_jobs_for_web, verify_and_consume_magic_token

import os
import json
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "production_jwt_secret_key")
JWT_ALGORITHM = "HS256"
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

def get_real_ip(request: Request) -> str:
    """Extract real client IP behind Cloudflare Proxy"""
    if "cf-connecting-ip" in request.headers:
        return request.headers["cf-connecting-ip"]
    elif "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return get_remote_address(request)

# IP 기반 Rate Limiter 초기화
limiter = Limiter(key_func=get_real_ip)

app = FastAPI(title="RPG Server API", version="1.0.0")

# Rate Limiter를 FastAPI 앱 상태에 등록 및 예외 핸들러 연결
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

@app.get("/api/v1/auth/login", response_class=HTMLResponse)
def auto_login_form(token: str):
    """디스코드 링크 클릭 시 POST 요청을 강제하기 위한 징검다리 페이지"""
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>인증 처리 중</title>
    </head>
    <body onload="document.getElementById('login-form').submit();" style="background: #0a0a1a; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: sans-serif;">
        <p>보안 인증 처리 중입니다...</p>
        <form id="login-form" action="/api/v1/auth/verify" method="POST" style="display: none;">
            <input type="hidden" name="token" value="{token}">
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/v1/auth/verify")
def verify_magic_link(token: str, response: Response):
    """디스코드에서 발급받은 일회용 토큰을 검증하고 JWT 쿠키를 발급"""
    user_data = verify_and_consume_magic_token(token)

    if not user_data:
        # 유효하지 않거나 만료된 토큰
        return RedirectResponse(url="/?error=invalid_token", status_code=status.HTTP_302_FOUND)

    # JWT 페이로드 생성 (7일 유지)
    expiration = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": user_data["discord_id"],
        "nickname": user_data["nickname"],
        "job_name": user_data["job_name"] or "직업 없음",
        "exp": expiration
    }

    jwt_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    redirect = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    # HttpOnly, Secure 속성으로 XSS 우회 방지 및 HTTPS 강제
    redirect.set_cookie(
        key="forum_session",
        value=jwt_token,
        httponly=True,
        secure=True,
        max_age=7 * 24 * 60 * 60,  # 7일
        samesite="lax"
    )
    return redirect

@app.get("/", response_class=HTMLResponse)
def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )

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
        request=request,
        name="jobs.html",
        context={"request": request, "jobs_json": jobs_json}
    )