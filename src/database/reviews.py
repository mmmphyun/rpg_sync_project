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


def get_job_reviews_data(job_id: int) -> dict:
    """특정 직업에 대한 전체 리뷰 목록 및 평균 평점 조회 (단일 커넥션으로 자원 최적화)"""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # 1. 리뷰 목록 조회
        cursor.execute("""
            SELECT 
                r.rating, 
                r.comment, 
                r.created_at, 
                u.nickname, 
                COALESCE(j.display_name, '직업 없음') AS job_name
            FROM job_reviews r
            JOIN users u ON r.discord_id = u.discord_id
            LEFT JOIN jobs j ON r.job_id = j.job_id
            WHERE r.job_id = %s
            ORDER BY r.created_at DESC
        """, (job_id,))
        reviews = cursor.fetchall()

        # 2. 평균 평점 조회
        cursor.execute(
            "SELECT COALESCE(ROUND(AVG(rating), 1), 0) as avg_rating FROM job_reviews WHERE job_id = %s",
            (job_id,)
        )
        avg_rating = cursor.fetchone()['avg_rating']

        return {"avg_rating": avg_rating, "reviews": reviews}
    except psycopg2.Error as e:
        print(f"DB Error (get_job_reviews_data): {e}")
        raise e
    finally:
        cursor.close()
        release_connection(conn)


def upsert_job_review_db(job_id: int, discord_id: str, rating: int, comment: str) -> dict:
    """유저의 직업 리뷰 등록 혹은 수정 (트랜잭션 커밋/롤백 보장)"""
    conn = get_connection()
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
        """, (job_id, discord_id, rating, comment))
        conn.commit()
        return {"message": "success"}
    except psycopg2.Error as e:
        conn.rollback()
        print(f"DB Error (upsert_job_review_db): {e}")
        raise e
    finally:
        cursor.close()
        release_connection(conn)