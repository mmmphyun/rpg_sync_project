import os
import json
import jwt
import psycopg2

from fastapi import FastAPI, Request, Depends, HTTPException, status, Response, Form, Cookie
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

from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from pydantic import BaseModel, Field

from psycopg2.extras import RealDictCursor

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

def get_db_connection():
    """DB Connection 객체 생성 (사용 후 반드시 close 처리)"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    return psycopg2.connect(db_url)

class ReviewPayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., max_length=255)

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

@app.post("/api/v1/auth/verify")
def verify_magic_link(token: str = Form(...)):
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


@app.get("/api/v1/auth/me")
def get_current_user(forum_session: str = Cookie(None)):
    """현재 로그인된 유저의 세션 정보를 반환"""
    if not forum_session:
        return {"is_logged_in": False}

    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "is_logged_in": True,
            "discord_id": payload.get("sub"),
            "nickname": payload.get("nickname"),
            "job_name": payload.get("job_name")
        }
    except ExpiredSignatureError:
        return {"is_logged_in": False, "error": "session_expired"}
    except InvalidTokenError:
        return {"is_logged_in": False, "error": "invalid_session"}

def get_required_user(forum_session: str = Cookie(None)):
    """쓰기 권한 검증: 토큰이 없거나 유효하지 않으면 401 반환"""
    if not forum_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다."
        )

    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 세션입니다."
        )

@app.post("/api/v1/auth/logout")
def logout_user(response: Response):
    """현재 유저의 세션 쿠키를 삭제하여 로그아웃 처리"""
    response.delete_cookie(
        key="forum_session",
        path="/",
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return {"message": "success"}


@app.get("/api/v1/jobs/{job_id}/reviews")
def get_job_reviews(job_id: int):
    """특정 직업의 리뷰 목록 및 평균 별점 조회 (게스트 접근 가능)"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 리뷰 목록 조회
        cursor.execute("""
            SELECT r.rating, r.comment, r.created_at, u.nickname, u.job_name
            FROM job_reviews r
            JOIN users u ON r.discord_id = u.discord_id
            WHERE r.job_id = %s
            ORDER BY r.created_at DESC
        """, (job_id,))
        reviews = cursor.fetchall()

        # 평균 별점 계산
        cursor.execute("SELECT COALESCE(ROUND(AVG(rating), 1), 0) as avg_rating FROM job_reviews WHERE job_id = %s",
                       (job_id,))
        avg_rating = cursor.fetchone()['avg_rating']

        return {"avg_rating": avg_rating, "reviews": reviews}
    finally:
        cursor.close()
        conn.close()


@app.post("/api/v1/jobs/{job_id}/reviews", status_code=status.HTTP_200_OK)
def upsert_job_review(job_id: int, payload: ReviewPayload, user: dict = Depends(get_required_user)):
    """직업 리뷰 작성 및 수정 (UPSERT, 인가된 유저만 접근 가능)"""
    discord_id = user.get("sub")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO job_reviews (job_id, discord_id, rating, comment)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (job_id, discord_id) 
            DO UPDATE SET 
                rating = EXCLUDED.rating, 
                comment = EXCLUDED.comment, 
                updated_at = CURRENT_TIMESTAMP
        """, (job_id, discord_id, payload.rating, payload.comment))
        conn.commit()
        return {"message": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()