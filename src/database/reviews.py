import psycopg2
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection, release_connection

def get_recent_reviews_for_web(limit: int = 3):
    """최근 작성된 직업 평가 조회"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        query = """
            SELECT jr.rating, jr.comment, u.nickname, j.display_name AS job_name, jr.created_at
            FROM job_reviews jr
            JOIN jobs j ON jr.job_id = j.job_id
            JOIN users u ON jr.discord_id = u.discord_id
            ORDER BY jr.created_at DESC
            LIMIT %s
        """
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    except psycopg2.Error as e:
        print(f"DB Error (get_recent_reviews): {e}")
        return []
    finally:
        cursor.close()
        release_connection(conn)