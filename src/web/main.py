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

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.web.limiter import limiter

from src.database.jobs import get_all_jobs_for_web
from src.database.connection import initialize_pool
from src.database.cache import init_redis_pool, close_redis_pool, get_cache, set_cache
from src.database.auth import is_guide_completed  # 누락된 DB 함수 임포트
from src.config import JWT_SECRET, JWT_ALGORITHM, DISCORD_INVITE_URL
from src.web.routers import auth, jobs, boards, server, tips, dashboard

app = FastAPI(title="Fossile Server Web Dashboard")

# 전역 템플릿 변수 설정
@app.middleware("http")
async def add_global_template_vars(request: Request, call_next):
    # 디스코드 초대 링크를 환경변수/중앙설정에서 가져와 request.state에 저장
    request.state.discord_invite_url = DISCORD_INVITE_URL
    return await call_next(request)

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

# Middleware & Static Files
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fossile-wiki.cloud").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

@app.middleware("http")
async def csrf_protection_middleware(request: Request, call_next):
    if request.method not in ["POST", "PUT", "PATCH", "DELETE"]:
        return await call_next(request)

    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    is_valid_origin = origin and any(origin == allowed.strip() for allowed in ALLOWED_ORIGINS)
    is_valid_referer = referer and any(referer.startswith(allowed.strip()) for allowed in ALLOWED_ORIGINS)

    if not (is_valid_origin or is_valid_referer):
        print(f"[Security Block] CSRF 시도 차단: Method={request.method}, Origin={origin}, Referer={referer}")
        return JSONResponse(
            status_code=403,
            content={"detail": "비정상적인 접근입니다. (CSRF 차단)"}
        )

    return await call_next(request)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    [Security & Monitoring] 보안 헤더 삽입 및 API 처리 시간 로깅 미들웨어
    """
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    if process_time > 0.5:
        print(f"[Warning] Slow API Call: [{request.method}] {request.url.path} - {process_time:.4f}s")

    response.headers["X-Process-Time"] = str(process_time)

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
            "discord_invite_url": request.state.discord_invite_url
        }
    )


@app.get("/jobs", response_class=HTMLResponse)
@limiter.limit("30/minute")
async def serve_jobs(request: Request):
    cache_key = "cache:jobs:all"

    cached_jobs = await get_cache(cache_key)
    if cached_jobs:
        return templates.TemplateResponse(
            request=request,
            name="jobs.html",
            context={
                "request": request, 
                "jobs_data": cached_jobs,
                "discord_invite_url": request.state.discord_invite_url
            }
        )

    jobs_data = await asyncio.to_thread(get_all_jobs_for_web)

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
            "players": row.get('players', []),
            "weapons": row.get('weapons', [])
        })

    await set_cache(cache_key, formatted_jobs, ex=86400)

    return templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "request": request, 
            "jobs_data": formatted_jobs,
            "discord_invite_url": request.state.discord_invite_url
        }
    )

@app.get("/notice")
async def serve_notice(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={
            "request": request, 
            "board_type": "notice",
            "discord_invite_url": request.state.discord_invite_url
        }
    )

@app.get("/event")
async def serve_event(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="board.html",
        context={
            "request": request, 
            "board_type": "event",
            "discord_invite_url": request.state.discord_invite_url
        }
    )

@app.get("/tips", response_class=HTMLResponse)
async def serve_tips(request: Request):
    """팁 게시판 서빙 (게스트 접근 차단)"""
    token = request.cookies.get("forum_session")

    is_logged_in = bool(token)

    return templates.TemplateResponse(
        request=request,
        name="tips.html",
        context={
            "request": request,
            "is_logged_in": is_logged_in,
            "discord_invite_url": request.state.discord_invite_url
        }
    )

@app.get("/guide", response_class=HTMLResponse)
async def get_guide_page(request: Request):
    """유저 상태에 따른 가이드 페이지 서빙"""
    token = request.cookies.get("forum_session")
    user_status = "guest"  # guest, newbie, member
    
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
            "discord_invite_url": request.state.discord_invite_url
        }
    )

logger = logging.getLogger("uvicorn.error")


async def send_discord_webhook(error_msg: str):
    """비동기 논블로킹 웹훅 전송. Discord API 장애가 본 서버에 영향을 주지 않도록 격리."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    if len(error_msg) > 1900:
        error_msg = error_msg[:1900] + "\n... [Truncated]"

    payload = {"content": f"```py\n{error_msg}\n```"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload, timeout=5.0) as resp:
                if resp.status >= 400:
                    logger.error(f"[Webhook Error] 상태 코드: {resp.status}")
    except Exception as e:
        logger.error(f"[Webhook Error] 발송 실패: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: {str(exc)}", exc_info=True)

    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    error_log_content = f"API Error: [{request.method}] {request.url.path}\n{tb_str}"

    asyncio.create_task(send_discord_webhook(error_log_content))

    return JSONResponse(
        status_code=500,
        content={"detail": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."}
    )