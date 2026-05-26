import os
import time
import logging
import asyncio
import traceback
import aiohttp
import jwt  # 누락된 JWT 디코더 임포트

from fastapi import FastAPI, Request
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
app = FastAPI(title="Fossile Server Web Dashboard")

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
    if cached_jobs:
        jobs_list = cached_jobs
    else:
        jobs_list = await asyncio.to_thread(get_all_jobs_for_web)
        await set_cache(cache_key, jobs_list, ex=600)

    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "request": request,
            "jobs": jobs_list,
            "jobs_data": jobs_list,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/tips", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_tips(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="tips.html",
        context={
            "request": request,
            "discord_invite_url": getattr(request.state, "discord_invite_url", DISCORD_INVITE_URL)
        }
    )

@app.get("/guide", response_class=HTMLResponse)
@limiter.limit("20/minute")
async def serve_guide(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="guide.html",
        context={
            "request": request,
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
