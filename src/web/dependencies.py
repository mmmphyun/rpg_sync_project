import os
import jwt
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor

from fastapi import Cookie, HTTPException, status, Depends
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from src.config import JWT_SECRET, JWT_ALGORITHM
from src.database.connection import get_connection, release_connection

def get_required_user(forum_session: str = Cookie(None)):
    if not forum_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    try:
        payload = jwt.decode(forum_session, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 세션입니다.")

def get_user_role_from_db(discord_id: str) -> str:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT server_role FROM users WHERE discord_id = %s", (discord_id,))
        row = cursor.fetchone()
        return row['server_role'] if row else "유저"
    except psycopg2.Error as e:
        print(f"[DB Error] Role check failed: {e}")
        return "유저"
    finally:
        cursor.close()
        release_connection(conn)


async def get_admin_user(user: dict = Depends(get_required_user)):
    discord_id = user.get("sub") or user.get("discord_id")
    if not discord_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 정보가 유효하지 않습니다.")

    current_role = await asyncio.to_thread(get_user_role_from_db, str(discord_id))

    if current_role not in ["STAFF", "주인장"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 없습니다.")

    user["server_role"] = current_role
    return user