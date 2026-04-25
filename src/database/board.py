import psycopg2
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection, release_connection

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
        release_connection(conn)

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
        release_connection(conn)

def update_notice_type(notice_id: int, new_type: str) -> int:
    """게시글 타입(notice/event) 변경을 통한 게시판 간 데이터 이관"""
    sql = "UPDATE notices SET type = %s WHERE notice_id = %s AND is_deleted = FALSE"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (new_type, notice_id))
        affected_rows = cursor.rowcount
        conn.commit()
        return affected_rows
    except psycopg2.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        release_connection(conn)

def get_notice_images_by_message_id(discord_message_id: int) -> list[str]:
    """수정 이벤트 발생 시 기존 R2 이미지 삭제를 위한 URL 조회"""
    sql = "SELECT image_urls FROM notices WHERE discord_message_id = %s"

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, (str(discord_message_id),))
        result = cursor.fetchone()

        if result and result[0]:
            return result[0]
        return []
    except psycopg2.Error as e:
        print(f"이미지 URL 조회 오류: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)

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
        release_connection(conn)


def get_notices_for_web(board_type: str, limit: int, offset: int, tag_filter: str = None):
    """지정된 타입(notice/event)과 조건에 맞는 게시글을 조회하여 반환"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # type 필터링 필수 적용
        query = query = "SELECT notice_id, type, tag, REPLACE(content, '@everyone', '') AS content, image_urls, is_deleted, created_at FROM notices WHERE type = %s AND is_deleted = FALSE"
        params = [board_type]

        if tag_filter:
            query += " AND tag = %s"
            params.append(tag_filter)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)

def get_recent_posts_for_web(limit: int = 5):
    """서버 상태 공지를 제외한 최신 게시글 조회"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # tag가 NULL인 이벤트 게시글 등도 포함하기 위해 IS DISTINCT FROM 사용
        query = """
            SELECT notice_id, type, tag, REPLACE(content, '@everyone', '') AS content, created_at
            FROM notices 
            WHERE is_deleted = FALSE 
            AND (tag IS NULL OR tag NOT LIKE %s)
            ORDER BY created_at DESC 
            LIMIT %s
        """
        cursor.execute(query, ('%서버 상태 공지%', limit))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error (get_recent_posts): {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)