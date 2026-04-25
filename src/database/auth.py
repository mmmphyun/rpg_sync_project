import psycopg2
import secrets
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection, release_connection
from datetime import datetime, timedelta

def check_user_exists(discord_id: str) -> bool:
    """DB에 유저가 존재하는지 확인합니다."""
    sql = "SELECT 1 FROM USERS WHERE DISCORD_ID = %s"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (discord_id,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        release_connection(conn)

def create_magic_token(discord_id: str) -> str:
    """5분 후 만료되는 일회용 매직 링크 토큰 생성 및 DB 적재"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(minutes=5)

    sql = """
        INSERT INTO public.magic_tokens (token, discord_id, expires_at)
        VALUES (%s, %s, %s)
    """

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (token, discord_id, expires_at))
        conn.commit()
        return token
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        release_connection(conn)

def verify_and_consume_magic_token(token: str) -> dict:
    """토큰 유효성 검증 후 즉시 폐기, 유저 정보 반환"""
    select_sql = """
        SELECT m.discord_id, u.nickname, u.server_role, j.display_name AS job_name
        FROM public.magic_tokens m
        JOIN public.users u ON m.discord_id = u.discord_id
        LEFT JOIN public.jobs j ON u.current_job_id = j.job_id
        WHERE m.token = %s AND m.expires_at > NOW()
    """
    delete_sql = "DELETE FROM public.magic_tokens WHERE token = %s"

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor) # 딕셔너리 반환을 위해 RealDictCursor 사용

    try:
        cursor.execute(select_sql, (token,))
        result = cursor.fetchone()

        if result:
            # 트랜잭션 내에서 즉시 삭제하여 1회성 보장
            cursor.execute(delete_sql, (token,))
            conn.commit()
            return dict(result)

        return None
    except psycopg2.Error as e:
        conn.rollback()
        print(f"매직 토큰 검증 중 오류 발생: {e}")
        return None
    finally:
        cursor.close()
        release_connection(conn)

def delete_user_from_db(discord_id: str) -> int:
    """서버 퇴장 유저 삭제"""
    sql = "DELETE FROM users WHERE discord_id = %s"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (discord_id,))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Error] delete_user_from_db 오류: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)

def update_user_voice_exit(discord_id: str) -> int:
    """음성 채널 퇴장 시간 갱신 (CURRENT_TIMESTAMP 사용)"""
    sql = "UPDATE users SET last_voice_exit = CURRENT_TIMESTAMP WHERE discord_id = %s"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (discord_id,))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        print(f"[DB Error] update_user_voice_exit 오류: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)