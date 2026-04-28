import psycopg2
import json
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection, release_connection


def get_tips_for_web(category: str = 'BUILD', limit: int = 10, offset: int = 0):
    """지정된 카테고리의 팁 게시글을 최신순으로 조회 (웹 UI용)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT t.tip_id, t.category, t.title, t.content, t.image_urls, t.youtube_urls, t.author_id, t.created_at,
                   COALESCE(u.nickname, '알 수 없는 유저') as author_nickname
            FROM tips t
            LEFT JOIN users u ON t.author_id = u.discord_id
            WHERE t.category = %s AND t.is_deleted = FALSE 
            ORDER BY t.created_at DESC 
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, (category, limit, offset))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"[DB Error] get_tips_for_web: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)


def upsert_tip(tip_data: dict) -> int:
    """디스코드 쓰레드 ID를 기준으로 팁 데이터를 삽입하거나 업데이트"""
    sql = """
        INSERT INTO tips (category, title, content, image_urls, youtube_urls, discord_thread_id, author_id)
        VALUES (%(category)s, %(title)s, %(content)s, %(image_urls)s, %(youtube_urls)s, %(discord_thread_id)s, %(author_id)s)
        ON CONFLICT (discord_thread_id) 
        DO UPDATE SET 
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            image_urls = EXCLUDED.image_urls,
            youtube_urls = EXCLUDED.youtube_urls,
            updated_at = CURRENT_TIMESTAMP
        WHERE tips.is_deleted = FALSE;
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, tip_data)
        affected = cursor.rowcount
        conn.commit()
        return affected
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] upsert_tip: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)


def get_tip_images_by_thread_id(thread_id: str) -> list:
    """기존 이미지 정리를 위해 특정 쓰레드의 이미지 URL 목록 조회"""
    sql = "SELECT image_urls FROM tips WHERE discord_thread_id = %s;"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (thread_id,))
        result = cursor.fetchone()
        if result and result[0]:
            return result[0] if isinstance(result[0], list) else json.loads(result[0])
        return []
    except Exception as e:
        print(f"[DB Error] get_tip_images: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)


def delete_tip_by_thread_id(thread_id: str) -> list:
    """쓰레드 삭제 시 Soft Delete 처리 및 연동된 이미지 URL 반환"""
    select_sql = "SELECT image_urls FROM tips WHERE discord_thread_id = %s;"
    update_sql = "UPDATE tips SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP WHERE discord_thread_id = %s;"

    conn = get_connection()
    cursor = conn.cursor()
    image_urls = []
    try:
        cursor.execute(select_sql, (thread_id,))
        result = cursor.fetchone()
        if result and result[0]:
            image_urls = result[0] if isinstance(result[0], list) else json.loads(result[0])

        cursor.execute(update_sql, (thread_id,))
        conn.commit()
        return image_urls
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] delete_tip_by_thread_id: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)

def get_tip_comments(tip_id: int) -> list:
    """팁 게시글의 댓글 목록 평면 조회"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT c.comment_id, c.parent_comment_id, c.author_id, c.content, c.created_at, c.is_deleted,
                   COALESCE(u.nickname, '알 수 없는 유저') as author_nickname
            FROM tip_comments c
            LEFT JOIN users u ON c.author_id = u.discord_id
            WHERE c.tip_id = %s AND c.is_deleted = FALSE
            ORDER BY c.created_at ASC
        """
        cursor.execute(query, (tip_id,))
        return cursor.fetchall()
    except Exception as e:
        print(f"[DB Error] get_tip_comments: {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)

def get_tip_by_id(tip_id: int):
    """단일 팁 게시글 조회 (권한 검증용)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM tips WHERE tip_id = %s AND is_deleted = FALSE", (tip_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        release_connection(conn)

def get_comment_by_id(comment_id: int):
    """단일 댓글 조회 (권한 검증용)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM tip_comments WHERE comment_id = %s AND is_deleted = FALSE", (comment_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        release_connection(conn)

def create_tip_comment(tip_id: int, author_id: str, content: str, parent_id: int = None) -> int:
    """팁 게시글에 새 댓글 작성"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO tip_comments (tip_id, parent_comment_id, author_id, content)
            VALUES (%s, %s, %s, %s)
            RETURNING comment_id;
        """
        cursor.execute(query, (tip_id, parent_id, author_id, content))
        comment_id = cursor.fetchone()[0]
        conn.commit()
        return comment_id
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] create_tip_comment: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)

def update_tip_by_id(tip_id: int, title: str, content: str) -> int:
    """웹에서 작성된 팁 게시글 수정"""
    sql = "UPDATE tips SET title = %s, content = %s, updated_at = CURRENT_TIMESTAMP WHERE tip_id = %s AND is_deleted = FALSE;"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (title, content, tip_id))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] update_tip_by_id: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)

def delete_tip_by_id(tip_id: int) -> int:
    """팁 게시글 Soft Delete"""
    sql = "UPDATE tips SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP WHERE tip_id = %s;"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (tip_id,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] delete_tip_by_id: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)

def update_comment_by_id(comment_id: int, content: str) -> int:
    """댓글 수정"""
    sql = "UPDATE tip_comments SET content = %s, updated_at = CURRENT_TIMESTAMP WHERE comment_id = %s AND is_deleted = FALSE;"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (content, comment_id))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] update_comment_by_id: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)

def delete_comment_by_id(comment_id: int) -> int:
    """댓글 Soft Delete"""
    sql = "UPDATE tip_comments SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP WHERE comment_id = %s;"
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (comment_id,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        conn.rollback()
        print(f"[DB Error] delete_comment_by_id: {e}")
        return 0
    finally:
        cursor.close()
        release_connection(conn)