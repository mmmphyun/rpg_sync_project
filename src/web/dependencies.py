import os
import jwt

from fastapi import Cookie, HTTPException, status, Depends
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from src.config import JWT_SECRET, JWT_ALGORITHM

def get_required_user(forum_session: str = Cookie(None)):
    if not forum_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 세션입니다.")

def get_admin_user(user: dict = Depends(get_required_user)):
    if user.get("server_role") not in ["STAFF", "주인장"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 없습니다.")
    return user