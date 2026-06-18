import os
import time
import logging
import asyncio
import traceback
import aiohttp
import jwt  # 누락된 JWT 디코더 임포트

from fastapi import FastAPI, Request, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.datastructures import MutableHeaders, URL

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.web.limiter import limiter

from src.database.jobs import get_all_jobs_for_web
from src.database.connection import initialize_pool
from src.database.cache import init_redis_pool, close_redis_pool, get_cache, set_cache
from src.database.auth import is_guide_completed  # 누락된 DB 함수 임포트
from src.config import JWT_SECRET, JWT_ALGORITHM, DISCORD_INVITE_URL
from src.web.routers import auth, jobs, boards, server, tips, dashboard

# ---------------------------------------------------------------------
# Pure ASGI Middleware Implementation (Fixed & Hardened)
# ---------------------------------------------------------------------
class SecurityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        # 화이트리스트 도메인 정리 (공백 제거)
        self.allowed_origins = [
            origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "https://fossile-wiki.cloud").split(",")
        ]

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1. request.state 안전성 확보: scope["state"]를 확실히 초기화하여 주입
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["discord_invite_url"] = DISCORD_INVITE_URL

        request = Request(scope, receive)
        start_time = time.time()
        url = URL(scope=scope)

        # 2. CSRF Protection (Hardened: Boundary check)
        if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            
            def is_trusted(value: str):
                if not value: return False
                # 단순 startswith가 아닌, 도메인 끝이 /이거나 정확히 일치하는지 체크하여 .attacker.com 우회 차단
                for allowed in self.allowed_origins:
                    if value == allowed or value.startswith(f"{allowed}/"):
                        return True
                return False

            if not (is_trusted(origin) or is_trusted(referer)):
                print(f"[Security Block] CSRF 시도 차단: Method={request.method}, Origin={origin}, Referer={referer}")
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "비정상적인 접근입니다. (CSRF 차단)"}
                )
                await response(scope, receive, send)
                return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                
                # 3. Security Headers
                process_time = time.time() - start_time
                headers["X-Process-Time"] = str(process_time)
                headers["X-Frame-Options"] = "DENY"
                headers["Content-Security-Policy"] = "frame-ancestors 'none'"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
                
                # 4. HSTS Lockout 방지: localhost/127.0.0.1일 경우 HSTS 제외
                host = url.hostname or ""
                if host not in ["localhost", "127.0.0.1"]:
                    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                
                if process_time > 0.5:
                    print(f"[Warning] Slow API Call: [{request.method}] {request.url.path} - {process_time:.4f}s")

            await send(message)

        await self.app(scope, receive, send_wrapper)

# ---------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------
web_domain = os.getenv("WEB_DOMAIN", "http://localhost:8000")
is_prod = "fossile-wiki.cloud" in web_domain

app = FastAPI(
    title="Fossile Server Web Dashboard",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json"
)

# Apply custom ASGI middleware first
app.add_middleware(SecurityMiddleware)

# Apply CORS middleware
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fossile-wiki.cloud").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

@app.on_event("startup")
async def startup_event():
    """
    서버 구동 시점에 무거운 SSL 커넥션과 외부 API 핑을 미리 처리하여 캐싱(Pre-warming).
    """
    print("[System] DB 커넥션 풀 예열 시작...", flush=True)
    initialize_pool()
    print("[System] Redis 커넥션 풀 초기화 시작...", flush=True)
    await init_redis_pool()
    print("[System] MC 서버 초기 상태 캐싱 시작...", flush=True)
    try:
        await server.get_server_status()
    except Exception as e:
        print(f"[System] MC 서버 캐싱 실패 (무시됨): {e}", flush=True)
    print("[System] 서버 사전 예열 완료", flush=True)

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 DB 및 Redis 커넥션을 안전하게 해제합니다."""
    print("[System] Redis 커넥션 풀 해제...", flush=True)
    await close_redis_pool()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

os.makedirs("public/images", exist_ok=True)
app.mount("/images", StaticFiles(directory="public/images"), name="images")
app.mount("/static", StaticFiles(directory="public"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Include Routers
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(boards.router, prefix="/api/v1/boards", tags=["Boards"])
app.include_router(server.router, prefix="/api/v1/server", tags=["Server"])
app.include_router(tips.router, prefix="/api/v1/tips", tags=["Tips"])

@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/jobs", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_jobs(request: Request):
    cache_key = "cache:jobs:all"

    cached_jobs = await get_cache(cache_key)
    if cached_jobs and isinstance(cached_jobs, list) and len(cached_jobs) > 0:
        # 캐싱된 데이터의 첫 번째 요소가 포맷팅된 구조인지 엄격히 검증
        first_item = cached_jobs[0]
        if isinstance(first_item, dict) and "desc" in first_item and "searchName" in first_item:
            return templates.TemplateResponse(
                request=request,
                name="jobs.html",
                context={
                    "request": request, 
                    "jobs": cached_jobs,
                    "jobs_data": cached_jobs,
                    "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
                }
            )
        else:
            # 원시 데이터 등으로 오염된 캐시 감지 시 자가 치유(Purge)
            print(f"[Warning] Invalid/Raw jobs cache format detected. Purging key '{cache_key}'.", flush=True)
            try:
                from src.database.cache import delete_cache
                await delete_cache(cache_key)
            except Exception as ce:
                print(f"[Error] Failed to purge invalid cache: {ce}", flush=True)

    jobs_data = await asyncio.to_thread(get_all_jobs_for_web)

    formatted_jobs = []
    for row in jobs_data:
        photos = [p for p in [row.get('photo_1'), row.get('photo_2'), row.get('photo_3'), row.get('photo_4')] if p]

        formatted_jobs.append({
            "job_id": row.get('job_id'),
            "name": row.get('display_name'),
            "searchName": row.get('name'),
            "gate": row.get('gate') or "정보 없음",
            "group": row.get('job_group') or "정보 없음",
            "desc": row.get('description') or "설명이 없습니다.",
            "range": row.get('range_type') or "정보 없음",
            "position": row.get('position') or "정보 없음",
            "resource": row.get('resource_type') or "정보 없음",
            "type": row.get('type') or "정보 없음",
            "img": row.get('img', ''),
            "photos": photos,
            "limit": True if row.get('is_limit') == 'Y' else False,
            "req_condition": row.get('req_condition') or "정보 없음",
            "patches": row.get('patches', []),
            "players": row.get('players', []),
            "weapons": row.get('weapons', [])
        })

    await set_cache(cache_key, formatted_jobs, ex=600)

    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "request": request, 
            "jobs": formatted_jobs,
            "jobs_data": formatted_jobs,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/tips", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_tips(request: Request, forum_session: str = Cookie(None)):
    """팁 게시판 서빙 (게스트 접근 차단)"""
    is_logged_in = False
    if forum_session:
        try:
            # JWT 디코딩을 통한 엄격한 세션 만료 및 무결성 검증
            jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            is_logged_in = True
        except Exception:
            is_logged_in = False

    return templates.TemplateResponse(
        request=request,
        name="tips.html",
        context={
            "request": request,
            "is_logged_in": is_logged_in,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/guide", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def serve_guide(request: Request, forum_session: str = Cookie(None)):
    """유저 상태에 따른 가이드 페이지 서빙"""
    user_status = "guest"  # guest, newbie, member
    
    if forum_session:
        try:
            payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            discord_id = payload.get("sub")
            
            # DB에서 완료 여부 확인
            is_completed = await asyncio.to_thread(is_guide_completed, discord_id)
            if is_completed:
                user_status = "member"
            else:
                user_status = "newbie"
        except Exception:
            user_status = "guest"

    return templates.TemplateResponse(
        request=request,
        name="guide.html",
        context={
            "request": request,
            "user_status": user_status,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/notice", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_notice(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={
            "request": request,
            "board_type": "notice",
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/event", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_event(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={
            "request": request,
            "board_type": "event",
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/board", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_board(request: Request, type: str = "notice"):
    board_type = "event" if type == "event" else "notice"
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={
            "request": request,
            "board_type": board_type,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/login", response_class=HTMLResponse)
def serve_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )
