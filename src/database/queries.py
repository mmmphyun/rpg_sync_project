import psycopg2
import secrets
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection
from datetime import datetime, timedelta


def update_job_illustrations(job_name: str, image_urls: list[str]) -> int:
    """
    추출된 이미지 URL 리스트(최대 4개)를 해당 직업의 PHOTO_N 컬럼에 일괄 업데이트.
    부족한 배열 크기는 None으로 채워 null 처리함.
    """
    clean_job_name = job_name.replace(" ", "")

    # 4칸 배열 고정 할당 (index out of range 방지)
    urls = (image_urls + [None] * 4)[:4]

    sql = """
        UPDATE JOBS 
        SET PHOTO_1 = %s, PHOTO_2 = %s, PHOTO_3 = %s, PHOTO_4 = %s
        WHERE JOB_ID = (
            SELECT JOB_ID 
            FROM JOBS 
            WHERE NULLIF(%s, '') IS NOT NULL 
              AND REPLACE(NAME, ' ', '') LIKE CONCAT('%%', %s, '%%')
            ORDER BY 
                CASE WHEN REPLACE(NAME, ' ', '') = %s THEN 1 ELSE 2 END ASC,
                LENGTH(NAME) ASC
            LIMIT 1
        )
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Tuple binding for PostgreSQL
        cursor.execute(sql, (urls[0], urls[1], urls[2], urls[3], clean_job_name, clean_job_name, clean_job_name))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def batch_update_profile_images(image_data: dict) -> int:
    """
    Process batch update for profile images based on filename mapping.
    """
    sql = """
        UPDATE JOBS 
        SET IMG = %s
        WHERE JOB_ID = (
            SELECT JOB_ID 
            FROM JOBS 
            WHERE NULLIF(%s, '') IS NOT NULL 
              AND REPLACE(NAME, ' ', '') LIKE CONCAT('%%', %s, '%%')
            ORDER BY 
                CASE WHEN REPLACE(NAME, ' ', '') = %s THEN 1 ELSE 2 END ASC,
                LENGTH(NAME) ASC
            LIMIT 1
        )
    """

    conn = get_connection()
    cursor = conn.cursor()
    success_count = 0

    try:
        for job_name, img_path in image_data.items():
            clean_name = job_name.replace(" ", "")
            cursor.execute(sql, (img_path, clean_name, clean_name, clean_name))
            if cursor.rowcount > 0:
                success_count += 1
        conn.commit()
        return success_count
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def update_job_single_column(job_name: str, column_name: str, value: str) -> int:
    # ... (allowed_columns 및 target_col 검증 로직은 기존과 동일) ...
    allowed_columns = {
        "range": "RANGE_TYPE", "position": "POSITION", "resource": "RESOURCE_TYPE",
        "img": "IMG", "photo1": "PHOTO_1", "photo2": "PHOTO_2",
        "photo3": "PHOTO_3", "photo4": "PHOTO_4"
    }

    target_col = allowed_columns.get(column_name.lower())
    if not target_col:
        raise ValueError(f"Invalid column name: {column_name}")

    clean_job_name = job_name.replace(" ", "")

    # PostgreSQL 파라미터 바인딩은 %s 사용
    sql = f"UPDATE JOBS SET {target_col} = %s WHERE NAME = %s"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (value, clean_job_name))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def get_all_jobs_for_web() -> list[dict]:
    sql = """
            SELECT 
                j.JOB_ID, j.NAME, j.DISPLAY_NAME, j.GATE, j.JOB_GROUP, j.DESCRIPTION, 
                j.RANGE_TYPE, j.POSITION, j.RESOURCE_TYPE, j.IS_LIMIT, j.REQ_CONDITION, 
                j.IMG, j.PHOTO_1, j.PHOTO_2, j.PHOTO_3, j.PHOTO_4,
                COALESCE(
                    (SELECT json_agg(json_build_object('date', jp.PATCH_DATE, 'notes', jp.NOTES)) 
                     FROM JOB_PATCHES jp WHERE jp.JOB_ID = j.JOB_ID), 
                    '[]'::json
                ) AS patches,
                COALESCE(
                    (SELECT json_agg(u.NICKNAME) 
                     FROM USERS u WHERE u.CURRENT_JOB_ID = j.JOB_ID), 
                    '[]'::json
                ) AS players
            FROM JOBS j
            ORDER BY j.GATE, j.DISPLAY_NAME
        """

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        cursor.execute(sql)
        jobs = cursor.fetchall()
        return [dict(row) for row in jobs]
    except psycopg2.Error as e:
        print(f"조회 중 오류 발생: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

""" 보안 로직 """

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
        conn.close()

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
        conn.close()

def verify_and_consume_magic_token(token: str) -> dict:
    """토큰 유효성 검증 후 즉시 폐기, 유저 정보 반환"""
    select_sql = """
        SELECT m.discord_id, u.nickname, j.display_name AS job_name
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
        conn.close()

def upsert_notice(notice_data: dict) -> int:
    """공지 데이터 적재 및 변경분 갱신 (Soft delete 처리된 건 무시)"""
    sql = """
        INSERT INTO notices (type, tag, content, image_urls, discord_message_id, author_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (discord_message_id) 
        DO UPDATE SET 
            content = EXCLUDED.content,
            image_urls = EXCLUDED.image_urls
        WHERE notices.is_deleted = FALSE;
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (
            notice_data.get('type', 'notice'),
            notice_data.get('tag', '일반 공지'),
            notice_data['content'],
            notice_data.get('image_urls', '[]'),
            notice_data['discord_message_id'],
            notice_data['author_id'],
            notice_data['created_at']
        ))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def update_notice_tag(notice_id: int, new_tag: str) -> int:
    """공지 태그 수정"""
    sql = "UPDATE notices SET tag = %s WHERE notice_id = %s AND is_deleted = FALSE"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (new_tag, notice_id))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def delete_notice_logic(notice_id: int) -> list[str]:
    """Soft Delete 적용 후 리소스 초기화. R2 삭제를 위해 기존 이미지 URL 반환"""
    sql = """
        UPDATE notices 
        SET is_deleted = TRUE, content = '', image_urls = '[]'::jsonb 
        WHERE notice_id = %s AND is_deleted = FALSE
        RETURNING image_urls
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (notice_id,))
        result = cursor.fetchone()
        conn.commit()

        if result and result[0]:
            return result[0]
        return []
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def get_notices_for_web(limit: int = 5, offset: int = 0, tag_filter: str = None) -> list[dict]:
    """조건 기반 공지사항 목록 반환 (PK 포함)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        if tag_filter:
            sql = """
                SELECT notice_id, type, tag, content, image_urls, created_at 
                FROM notices 
                WHERE is_deleted = FALSE AND tag = %s
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, (tag_filter, limit, offset))
        else:
            sql = """
                SELECT notice_id, type, tag, content, image_urls, created_at 
                FROM notices 
                WHERE is_deleted = FALSE 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql, (limit, offset))

        return [dict(row) for row in cursor.fetchall()]
    except psycopg2.Error as e:
        print(f"공지사항 목록 조회 중 오류 발생: {e}")
        return []
    finally:
        cursor.close()
        conn.close()