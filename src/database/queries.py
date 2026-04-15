import psycopg2
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection


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
        SELECT NAME, DISPLAY_NAME, GATE, JOB_GROUP, DESCRIPTION, 
               RANGE_TYPE, POSITION, RESOURCE_TYPE, IS_LIMIT, 
               REQ_CONDITION, IMG, PHOTO_1, PHOTO_2, PHOTO_3, PHOTO_4
        FROM JOBS
        ORDER BY GATE, DISPLAY_NAME
    """

    conn = get_connection()
    # 결과를 Dictionary 형태로 반환받기 위해 RealDictCursor 사용
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