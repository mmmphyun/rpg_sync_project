import psycopg2
from psycopg2.extras import RealDictCursor
from src.database.connection import get_connection, release_connection

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
        release_connection(conn)

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
        release_connection(conn)

def update_job_single_column(job_name: str, column_name: str, value: str) -> int:
    allowed_columns = {
        "range": "RANGE_TYPE", "position": "POSITION", "resource": "RESOURCE_TYPE",
        "img": "IMG", "photo1": "PHOTO_1", "photo2": "PHOTO_2",
        "photo3": "PHOTO_3", "photo4": "PHOTO_4"
    }

    target_col = allowed_columns.get(column_name.lower())
    if not target_col:
        raise ValueError(f"Invalid column name: {column_name}")

    clean_job_name = job_name.replace(" ", "")

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
        release_connection(conn)


def get_all_jobs_for_web() -> list[dict]:
    sql = """
            SELECT 
                j.JOB_ID, j.NAME, j.DISPLAY_NAME, j.GATE, j.JOB_GROUP, j.DESCRIPTION, 
                j.RANGE_TYPE, j.POSITION, j.RESOURCE_TYPE, j.TYPE, j.IS_LIMIT, j.REQ_CONDITION, 
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
        print(f"[DB Error] 쿼리 실행 오류: {e}", flush=True)
        return []
    except Exception as e:
        print(f"[System Error] 기타 오류 발생: {e}", flush=True)
        return []
    finally:
        cursor.close()
        release_connection(conn)