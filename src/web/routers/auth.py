import os
import jwt
from fastapi import APIRouter, Request, Form, Response, Cookie, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timedelta
from src.database.queries import verify_and_consume_magic_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from src.config import JWT_SECRET, JWT_ALGORITHM
from src.web.main import limiter

router = APIRouter()

@router.get("/login", response_class=HTMLResponse)
def auto_login_form(token: str):
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

@router.post("/verify")
@limiter.limit("5/minute")
def verify_magic_link(request: Request, token: str = Form(...)):
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

    redirect = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
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