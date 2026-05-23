import os
import jwt
import asyncio
from fastapi import APIRouter, Request, Form, Response, Cookie, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
from src.database.auth import verify_and_consume_magic_token, update_guide_completion
from src.database.cache import publish_message
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from src.config import JWT_SECRET, JWT_ALGORITHM
from src.web.limiter import limiter

router = APIRouter()

@router.post("/complete")
async def complete_guide(forum_session: str = Cookie(None)):
    """가이드 완료 처리 및 봇 역할 변경 트리거"""
    if not forum_session:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        discord_id = payload.get("sub")
        
        # 1. DB 업데이트
        success = await asyncio.to_thread(update_guide_completion, discord_id)
        if not success:
            raise HTTPException(status_code=500, detail="상태 업데이트 중 오류가 발생했습니다.")
            
        # 2. Redis Pub/Sub을 통해 봇에게 신호 전달
        pub_result = await publish_message("onboarding:complete", {"discord_id": discord_id})
        print(f"[API] Redis publish result for {discord_id}: {pub_result}", flush=True)
        
        return {"message": "success"}
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다.")
    except Exception as e:
        print(f"가이드 완료 처리 에러: {e}")
        raise HTTPException(status_code=500, detail="시스템 오류가 발생했습니다.")

@router.get("/login", response_class=HTMLResponse)
def auto_login_form(token: str, redirect: str = "main"):
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
            <input type="hidden" name="redirect_to" value="{redirect}">
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.post("/verify")
@limiter.limit("5/minute")
def verify_magic_link(request: Request, token: str = Form(...), redirect_to: str = Form("main")):
    user_data = verify_and_consume_magic_token(token)

    if not user_data:
        return RedirectResponse(url="/?error=invalid_token", status_code=status.HTTP_302_FOUND)

    expiration = datetime.utcnow() + timedelta(days=7)
    payload = {
        "sub": user_data["discord_id"],
        "nickname": user_data["nickname"],
        "job_name": user_data["job_name"] or "직업 없음",
        "server_role": user_data["server_role"],
        "exp": expiration
    }

    jwt_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # 리다이렉트 경로 결정
    target_url = "/guide" if redirect_to == "guide" else "/"
    
    redirect = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key="forum_session",
        value=jwt_token,
        httponly=True,
        secure=True,
        max_age=7 * 24 * 60 * 60,
        samesite="strict"
    )
    return redirect

@router.get("/me")
def get_current_user(forum_session: str = Cookie(None)):
    if not forum_session:
        return {"is_logged_in": False}

    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "is_logged_in": True,
            "discord_id": payload.get("sub"),
            "nickname": payload.get("nickname"),
            "job_name": payload.get("job_name"),
            "server_role": payload.get("server_role")
        }
    except ExpiredSignatureError:
        return {"is_logged_in": False, "error": "session_expired"}
    except InvalidTokenError:
        return {"is_logged_in": False, "error": "invalid_session"}

@router.post("/logout")
def logout_user(response: Response):
    response.delete_cookie(
        key="forum_session",
        path="/",
        httponly=True,
        secure=True,
        samesite="strict"
    )
    return {"message": "success"}